"""
Scheduler — cron-driven autonomous agent execution.

Agents that run without humans triggering them.
This is what separates a tool from infrastructure.

Schedule syntax (cron-style):
  "*/5 * * * *"   — every 5 minutes
  "0 9 * * 1-5"   — 9am weekdays
  "0 0 * * *"     — midnight daily
  "@hourly"       — every hour
  "@daily"        — midnight daily
  "@weekly"       — Sunday midnight

Usage:
  scheduler = Scheduler()
  scheduler.add_job(
      job_id="health_check",
      cron="*/15 * * * *",
      agent_factory=lambda: DevOpsAgent(),
      task="Check nginx, disk usage, and memory. Notify if anything is above 80%.",
      runtime_factory=lambda: build_runtime(),
  )
  scheduler.start()  # blocks, or run in a thread
"""

import time
import threading
import signal
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from croniter import croniter

from runtime.logger import get_logger


@dataclass
class ScheduledJob:
    job_id: str
    cron: str
    agent_factory: Callable
    task: str
    runtime_factory: Callable
    enabled: bool = True
    last_run: Optional[datetime] = None
    last_status: Optional[str] = None
    run_count: int = 0
    error_count: int = 0

    def next_run_time(self) -> datetime:
        base = self.last_run or datetime.now(timezone.utc)
        it = croniter(self.cron, base)
        return it.get_next(datetime)

    def is_due(self) -> bool:
        if not self.enabled:
            return False
        next_run = self.next_run_time()
        return datetime.now(timezone.utc) >= next_run


# Convenience aliases for non-cron users
CRON_ALIASES = {
    "@hourly":  "0 * * * *",
    "@daily":   "0 0 * * *",
    "@weekly":  "0 0 * * 0",
    "@monthly": "0 0 1 * *",
}


class Scheduler:
    """
    Runs scheduled agent jobs. Each job defines:
      - When to run (cron expression)
      - Which agent to use (factory function)
      - What task to give it (string)
      - Which runtime to use (factory function)

    Jobs run in separate threads so they don't block each other.
    The scheduler loop ticks every 30 seconds by default.
    """

    def __init__(self, tick_interval: int = 30):
        self.jobs: Dict[str, ScheduledJob] = {}
        self.tick_interval = tick_interval
        self.logger = get_logger("scheduler")
        self._running = False
        self._lock = threading.Lock()

    def add_job(
        self,
        job_id: str,
        cron: str,
        agent_factory: Callable,
        task: str,
        runtime_factory: Callable,
        enabled: bool = True,
    ) -> "Scheduler":
        """Register a scheduled job. Returns self for chaining."""
        cron = CRON_ALIASES.get(cron, cron)
        # Validate cron expression
        try:
            croniter(cron)
        except Exception:
            raise ValueError(f"Invalid cron expression: '{cron}'")

        job = ScheduledJob(
            job_id=job_id,
            cron=cron,
            agent_factory=agent_factory,
            task=task,
            runtime_factory=runtime_factory,
            enabled=enabled,
        )
        with self._lock:
            self.jobs[job_id] = job

        next_run = job.next_run_time()
        self.logger.info("job_registered", job_id=job_id, cron=cron, next_run=str(next_run)[:19])
        return self

    def remove_job(self, job_id: str):
        with self._lock:
            self.jobs.pop(job_id, None)
        self.logger.info("job_removed", job_id=job_id)

    def enable_job(self, job_id: str):
        if job_id in self.jobs:
            self.jobs[job_id].enabled = True

    def disable_job(self, job_id: str):
        if job_id in self.jobs:
            self.jobs[job_id].enabled = False

    def _run_job(self, job: ScheduledJob):
        """Execute a single job in its own thread."""
        self.logger.info("job_start", job_id=job.job_id, task=job.task[:80])
        start = time.time()

        try:
            loop = job.runtime_factory()
            agent = job.agent_factory()
            result = loop.run(agent, task=job.task)

            elapsed = round(time.time() - start, 1)
            job.last_run = datetime.now(timezone.utc)
            job.run_count += 1
            job.last_status = "success" if result.success else "failed"

            self.logger.info(
                "job_complete",
                job_id=job.job_id,
                status=job.last_status,
                steps=result.steps_taken,
                elapsed=f"{elapsed}s",
            )

        except Exception as e:
            job.error_count += 1
            job.last_status = "error"
            job.last_run = datetime.now(timezone.utc)
            self.logger.error("job_error", job_id=job.job_id, error=str(e))

    def tick(self):
        """Check all jobs and fire any that are due. Called every tick_interval seconds."""
        due = [j for j in self.jobs.values() if j.is_due()]
        for job in due:
            # Mark last_run immediately to prevent double-firing on slow runs
            job.last_run = datetime.now(timezone.utc)
            t = threading.Thread(target=self._run_job, args=(job,), daemon=True)
            t.start()

    def status(self) -> List[Dict]:
        """Return current status of all jobs."""
        result = []
        for job in self.jobs.values():
            result.append({
                "job_id": job.job_id,
                "cron": job.cron,
                "enabled": job.enabled,
                "run_count": job.run_count,
                "error_count": job.error_count,
                "last_run": str(job.last_run)[:19] if job.last_run else None,
                "last_status": job.last_status,
                "next_run": str(job.next_run_time())[:19],
            })
        return result

    def start(self, block: bool = True):
        """
        Start the scheduler loop.
        block=True: runs in foreground, handles SIGINT gracefully.
        block=False: runs in a background daemon thread.
        """
        self._running = True
        self.logger.banner(f"Scheduler started — {len(self.jobs)} job(s) registered")

        def loop():
            while self._running:
                self.tick()
                time.sleep(self.tick_interval)

        if block:
            def _shutdown(sig, frame):
                self.logger.info("scheduler_stopping")
                self._running = False
                sys.exit(0)

            signal.signal(signal.SIGINT, _shutdown)
            signal.signal(signal.SIGTERM, _shutdown)
            loop()
        else:
            t = threading.Thread(target=loop, daemon=True)
            t.start()

    def stop(self):
        self._running = False
        self.logger.info("scheduler_stopped")
