"""
Multi-agent orchestration — one task, many specialists.

The orchestrator decomposes a task into sub-tasks and dispatches
each to a specialized agent running in parallel. Results are
collected and synthesized into a final output.

This is the architectural leap from "one agent does everything"
to "a team of agents, each doing one thing well."

Pattern:
  Orchestrator
    ├── SubAgent A  (e.g., check nginx)
    ├── SubAgent B  (e.g., check disk)
    └── SubAgent C  (e.g., check memory)
    → synthesize results → final report

Usage:
  orchestrator = Orchestrator(runtime_factory=build_runtime)
  result = orchestrator.run(
      task="Audit the production server",
      subtasks=[
          SubTask("Check nginx status and errors", DevOpsAgent()),
          SubTask("Check disk usage and identify large files", DevOpsAgent()),
          SubTask("Check memory and top processes", DevOpsAgent()),
      ]
  )
  print(result.synthesis)
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from runtime.agent_loop import LoopResult
from runtime.logger import get_logger


@dataclass
class SubTask:
    """A single unit of work dispatched to a sub-agent."""
    task: str
    agent: Any  # BaseAgent instance
    label: Optional[str] = None  # Human-readable name for logging

    def __post_init__(self):
        if not self.label:
            self.label = self.task[:40]


@dataclass
class OrchestratorResult:
    """Aggregated result from all sub-agents."""
    overall_success: bool
    subtask_results: List[Dict]         # Each sub-agent's result
    synthesis: str                       # Final synthesized output
    total_steps: int
    elapsed_seconds: float
    failed_count: int

    def to_dict(self) -> Dict:
        return {
            "overall_success": self.overall_success,
            "synthesis": self.synthesis,
            "total_steps": self.total_steps,
            "elapsed_seconds": self.elapsed_seconds,
            "failed_count": self.failed_count,
            "subtask_results": self.subtask_results,
        }


class Orchestrator:
    """
    Runs multiple sub-agents in parallel and synthesizes their results.

    The runtime_factory is called fresh for each sub-agent — each
    gets its own session, memory, and LLM connection.

    max_workers controls parallelism. Default 4 means up to 4
    agents run simultaneously.
    """

    def __init__(
        self,
        runtime_factory: Callable,
        max_workers: int = 4,
        synthesize: bool = True,
        synthesis_agent_factory: Optional[Callable] = None,
    ):
        """
        Args:
            runtime_factory: Callable that returns a fresh AgentLoop
            max_workers: Max parallel sub-agents
            synthesize: If True, run a final synthesis pass over all results
            synthesis_agent_factory: Agent to use for synthesis (default: TaskAgent)
        """
        self.runtime_factory = runtime_factory
        self.max_workers = max_workers
        self.synthesize = synthesize
        self.synthesis_agent_factory = synthesis_agent_factory
        self.logger = get_logger("orchestrator")

    def _run_subtask(self, subtask: SubTask, index: int) -> Dict:
        """Execute a single sub-task. Returns a result dict."""
        self.logger.info("subtask_start", index=index, label=subtask.label)
        start = time.time()

        try:
            loop = self.runtime_factory()
            result: LoopResult = loop.run(subtask.agent, task=subtask.task)
            elapsed = round(time.time() - start, 1)
            self.logger.info(
                "subtask_done",
                index=index,
                label=subtask.label,
                success=result.success,
                steps=result.steps_taken,
                elapsed=f"{elapsed}s",
            )
            return {
                "index": index,
                "label": subtask.label,
                "task": subtask.task,
                "success": result.success,
                "output": result.output,
                "steps": result.steps_taken,
                "stop_reason": result.stop_reason,
                "session_id": result.session_id,
                "elapsed_seconds": elapsed,
                "error": result.error,
            }
        except Exception as e:
            self.logger.error("subtask_error", index=index, label=subtask.label, error=str(e))
            return {
                "index": index,
                "label": subtask.label,
                "task": subtask.task,
                "success": False,
                "output": "",
                "error": str(e),
            }

    def _build_synthesis_prompt(self, main_task: str, results: List[Dict]) -> str:
        """Build the synthesis task from sub-agent results."""
        lines = [
            f"You coordinated multiple agents to complete this task: {main_task}",
            "",
            "Here are the results from each sub-agent:",
            "",
        ]
        for r in results:
            status = "✓" if r["success"] else "✗"
            lines.append(f"## [{status}] {r['label']}")
            lines.append(f"Task: {r['task']}")
            if r["success"] and r.get("output"):
                lines.append(f"Result:\n{r['output']}")
            elif r.get("error"):
                lines.append(f"Error: {r['error']}")
            lines.append("")

        lines.extend([
            "---",
            "Synthesize these results into a single, clear final report.",
            "Highlight what succeeded, what failed, and any key findings.",
            "Do not use any tools — just write the synthesis directly.",
        ])
        return "\n".join(lines)

    def run(
        self,
        task: str,
        subtasks: List[SubTask],
        timeout: Optional[float] = None,
    ) -> OrchestratorResult:
        """
        Run all sub-tasks in parallel, then synthesize results.

        Args:
            task: The top-level task description (used for synthesis framing)
            subtasks: List of SubTask objects to run in parallel
            timeout: Optional per-subtask timeout in seconds

        Returns:
            OrchestratorResult with synthesis and all sub-results
        """
        if not subtasks:
            return OrchestratorResult(
                overall_success=False,
                subtask_results=[],
                synthesis="No subtasks provided.",
                total_steps=0,
                elapsed_seconds=0,
                failed_count=0,
            )

        self.logger.banner(f"Orchestrator — {len(subtasks)} sub-agents")
        self.logger.info("task", description=task[:100])

        wall_start = time.time()
        results: List[Dict] = [None] * len(subtasks)

        # Run all sub-tasks in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            future_to_idx = {
                pool.submit(self._run_subtask, st, i): i
                for i, st in enumerate(subtasks)
            }
            for future in as_completed(future_to_idx, timeout=timeout):
                idx = future_to_idx[future]
                results[idx] = future.result()

        total_steps = sum(r.get("steps", 0) for r in results if r)
        failed_count = sum(1 for r in results if r and not r["success"])
        elapsed = round(time.time() - wall_start, 1)

        self.logger.info(
            "all_subtasks_done",
            total=len(subtasks),
            failed=failed_count,
            elapsed=f"{elapsed}s",
        )

        # Synthesis pass
        synthesis = ""
        if self.synthesize:
            self.logger.info("synthesis_start")
            try:
                synthesis_task = self._build_synthesis_prompt(task, results)

                if self.synthesis_agent_factory:
                    synth_agent = self.synthesis_agent_factory()
                else:
                    from agents.task_agent import TaskAgent
                    synth_agent = TaskAgent()

                synth_loop = self.runtime_factory()
                synth_result = synth_loop.run(synth_agent, task=synthesis_task)
                synthesis = synth_result.output
                total_steps += synth_result.steps_taken
                self.logger.info("synthesis_done", length=len(synthesis))
            except Exception as e:
                self.logger.error("synthesis_error", error=str(e))
                synthesis = f"Synthesis failed: {e}\n\nRaw results:\n" + "\n\n".join(
                    f"[{r['label']}]: {r.get('output', r.get('error', ''))}"
                    for r in results if r
                )
        else:
            synthesis = "\n\n".join(
                f"[{r['label']}]:\n{r.get('output', r.get('error', ''))}"
                for r in results if r
            )

        return OrchestratorResult(
            overall_success=failed_count == 0,
            subtask_results=results,
            synthesis=synthesis,
            total_steps=total_steps,
            elapsed_seconds=elapsed,
            failed_count=failed_count,
        )
