#!/usr/bin/env python3
"""
run_scheduler.py — start the Agent Runtime scheduler.

Define your scheduled jobs in this file, then run it.
The scheduler loops forever, firing agents on cron schedules.

Run it:
  python run_scheduler.py

Keep it alive in production:
  systemd service, pm2, supervisor, screen — your call.

Example jobs defined below:
  - Server health check every 15 minutes (DevOps agent)
  - Daily digest at 8am (Research agent)
  - Disk cleanup check weekly (DevOps agent)

Uncomment and configure what you need.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from runtime import build_runtime
from runtime.config import load_config
from runtime.scheduler import Scheduler
from runtime.logger import get_logger

log = get_logger("scheduler_main")


def make_runtime():
    """Factory — called fresh for each job execution."""
    return build_runtime()


def main():
    config = load_config()
    scheduler = Scheduler(tick_interval=60)   # check every 60 seconds

    # ─────────────────────────────────────────────────────────────────────────
    # Example job 1: Server health check every 15 minutes
    # Requires: SSH tool configured, or shell tool for local checks
    # ─────────────────────────────────────────────────────────────────────────
    # from agents.devops_agent import DevOpsAgent
    # scheduler.add_job(
    #     job_id="server-health",
    #     cron="*/15 * * * *",
    #     agent_factory=lambda: DevOpsAgent(),
    #     task=(
    #         "Check system health: disk usage (alert if >80%), "
    #         "memory usage (alert if >90%), nginx status, and CPU load. "
    #         "If anything is critical, use the notify tool to send a Slack alert."
    #     ),
    #     runtime_factory=make_runtime,
    # )

    # ─────────────────────────────────────────────────────────────────────────
    # Example job 2: Daily morning digest at 8am weekdays
    # ─────────────────────────────────────────────────────────────────────────
    # from agents.research_agent import ResearchAgent
    # scheduler.add_job(
    #     job_id="morning-digest",
    #     cron="0 8 * * 1-5",
    #     agent_factory=lambda: ResearchAgent(output_file="daily_digest.md"),
    #     task=(
    #         "Fetch the latest AI news from https://hnrss.org/frontpage.jsonfeed "
    #         "and summarize the top 5 most relevant stories to an AI infrastructure team. "
    #         "Write a clean digest to daily_digest.md."
    #     ),
    #     runtime_factory=make_runtime,
    # )

    # ─────────────────────────────────────────────────────────────────────────
    # Example job 3: Weekly disk cleanup check Sunday midnight
    # ─────────────────────────────────────────────────────────────────────────
    # from agents.devops_agent import DevOpsAgent
    # scheduler.add_job(
    #     job_id="disk-cleanup",
    #     cron="@weekly",
    #     agent_factory=lambda: DevOpsAgent(),
    #     task=(
    #         "Check /var/log for log files larger than 100MB. "
    #         "List them with sizes and ages. "
    #         "If any are older than 30 days, compress or delete them safely. "
    #         "Write a summary of what was cleaned to workspace/disk_cleanup_report.md."
    #     ),
    #     runtime_factory=make_runtime,
    # )

    # ─────────────────────────────────────────────────────────────────────────
    # Add your own jobs here
    # ─────────────────────────────────────────────────────────────────────────

    if not scheduler.jobs:
        log.warning("no_jobs_configured",
                    hint="Uncomment example jobs in run_scheduler.py to get started")
        print("\n  No jobs configured. Edit run_scheduler.py and uncomment example jobs.\n")
        return

    log.info("scheduler_starting", job_count=len(scheduler.jobs))
    for row in scheduler.status():
        log.info("job", **{k: str(v) for k, v in row.items()})

    scheduler.start(block=True)   # blocks; handles SIGINT/SIGTERM gracefully


if __name__ == "__main__":
    main()
