"""
Base agent class for Agent Runtime.

Agents define behavior — goals, system prompts, stop conditions.
The runtime handles execution — loops, tools, memory, observability.

Separation of concerns:
  Agent = what to do and why
  Runtime = how to do it
"""

from abc import ABC
from typing import Any, Dict


class BaseAgent(ABC):
    """
    Abstract base for all agents in the sovereign runtime.

    To create a new agent:
      1. Subclass BaseAgent
      2. Set name and description
      3. Override get_system_prompt() with your agent's behavior
      4. Optionally override on_start, on_step_complete, should_stop, on_complete
    """

    name: str = "agent"
    description: str = "A sovereign AI agent."

    def get_system_prompt(self) -> str:
        """
        System prompt that defines this agent's role, behavior, and constraints.
        This is the primary way to shape what the agent does.
        """
        return (
            f"You are {self.name}. {self.description}\n\n"
            "Use the available tools to complete tasks. "
            "Think step by step. When the task is complete, provide a clear final answer."
        )

    def should_stop(self, step: int, last_result: Any, state: Dict) -> bool:
        """
        Optional: implement custom stop conditions beyond the default max_steps limit.
        Return True to stop the loop early.
        """
        return False

    def on_start(self, task: str, state: Dict) -> Dict:
        """
        Called before the loop begins.
        Use to initialize state, log task receipt, etc.
        Returns (possibly modified) state dict.
        """
        return state

    def on_step_complete(self, step: int, action: Dict, result: Any, state: Dict) -> Dict:
        """
        Called after each tool execution step.
        Use to update state, implement early-stop logic, etc.
        Returns (possibly modified) state dict.
        """
        return state

    def on_complete(self, result: str, state: Dict):
        """
        Called when the loop finishes (success or max_steps).
        Use for cleanup, notifications, result persistence, etc.
        """
        pass
