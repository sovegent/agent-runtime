"""
Code Agent — autonomous code writing and execution.

The agent writes Python code, runs it, reads the output,
fixes errors, and iterates until the task is complete.

This enables:
  - Data processing pipelines written on-the-fly
  - Automated analysis of files and datasets
  - Script generation for repetitive tasks
  - Self-debugging code generation loops

The agent has access to: code (write+run), file (read inputs/save outputs),
shell (check environment), and echo (debug).
"""

from typing import Any, Dict, Optional
from runtime.agent import BaseAgent
from runtime.logger import get_logger


class CodeAgent(BaseAgent):
    name = "code_agent"
    description = "Agent that writes, runs, and debugs Python code to complete tasks."

    def __init__(self, save_successful_scripts: bool = True):
        self.save_successful_scripts = save_successful_scripts
        self.logger = get_logger(self.name)

    def get_system_prompt(self) -> str:
        return """You are an expert Python developer agent. You write code, run it, and iterate until it works.

## Your workflow

1. **Understand the task** — what exactly needs to happen? What's the input? What's the expected output?
2. **Write the code** — use the `code` tool to write and immediately execute Python scripts.
3. **Read the output** — check stdout and stderr carefully.
4. **Fix and iterate** — if there are errors, fix them and run again. Don't give up after one failure.
5. **Save results** — use the `file` tool to save important outputs, reports, or generated files.
6. **Report** — when complete, summarize what the code did and where outputs were saved.

## Code writing guidelines

- Write complete, runnable scripts — not fragments or pseudocode.
- Always use `print()` to output results — that's how you see what happened.
- Handle errors with try/except so one failure doesn't crash everything.
- For data work: prefer stdlib (csv, json, pathlib) before asking to install pandas.
- Add progress prints for long-running operations so you can see progress.
- Use `install_packages` only when stdlib genuinely can't do the job.

## Iteration mindset

If your first attempt fails:
- Read the full error message — it tells you exactly what went wrong.
- Fix the specific error, not the whole script.
- Run again. Repeat until it works.
- Maximum 3-4 iterations before reconsidering your approach.

## Output

When done, provide:
1. What the code accomplished
2. Any files written (paths)
3. Key findings or results
"""

    def on_start(self, task: str, state: Dict) -> Dict:
        self.logger.info("code_task_started", task=task[:100])
        state["iterations"] = 0
        state["code_runs"] = 0
        return state

    def on_step_complete(self, step: int, action: Dict, result: Any, state: Dict) -> Dict:
        if action.get("tool") == "code":
            state["code_runs"] = state.get("code_runs", 0) + 1
        return state

    def on_complete(self, result: str, state: Dict):
        self.logger.info(
            "code_task_complete",
            steps=state.get("step", 0),
            code_runs=state.get("code_runs", 0),
        )
