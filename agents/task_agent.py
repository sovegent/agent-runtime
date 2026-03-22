"""
Task Agent — general-purpose agent for the sovereign stack.

Use this for most tasks: research, file ops, system commands,
API calls, multi-step workflows.

Customize the system prompt to shape behavior for your use case.
"""

from typing import Any, Dict, Optional
from runtime.agent import BaseAgent
from runtime.logger import get_logger


class TaskAgent(BaseAgent):
    """
    General-purpose task agent.

    Capable of using all registered tools to complete tasks.
    Stops naturally when it decides the task is done.

    Customize by:
      - Subclassing and overriding get_system_prompt()
      - Passing a custom_prompt to __init__
      - Adding on_complete() logic for notifications / persistence
    """

    name = "task_agent"
    description = "A general-purpose agent that uses available tools to complete tasks."

    def __init__(self, custom_prompt: Optional[str] = None):
        self.custom_prompt = custom_prompt
        self.logger = get_logger(self.name)

    def get_system_prompt(self) -> str:
        if self.custom_prompt:
            return self.custom_prompt

        return """You are a capable, methodical AI agent running on sovereign infrastructure.

You have access to tools that let you interact with the real world:
- shell: execute system commands
- http: make API calls and web requests
- file: read and write files in your workspace
- echo: test and debug

## How to work

1. **Think before acting.** Understand the task before using tools.
2. **Be systematic.** Break complex tasks into clear steps.
3. **Use the right tool.** Shell for system ops, HTTP for APIs, file for persistence.
4. **Verify results.** Check that each step succeeded before proceeding.
5. **Report clearly.** When done, give a concise summary of what was accomplished.

## When you're done

When the task is complete, provide a final response WITHOUT using any tool.
Your final response should clearly answer the original task.

## Important

- You run on infrastructure the user controls — operate with appropriate care.
- If a command or action feels destructive, confirm the intent in your response.
- Prefer reading before writing. Prefer dry-runs before execution.
"""

    def on_start(self, task: str, state: Dict) -> Dict:
        self.logger.info("starting", task=task[:100])
        return state

    def on_complete(self, result: str, state: Dict):
        steps = state.get("step", 0)
        self.logger.info("complete", steps=steps, output_length=len(result))
