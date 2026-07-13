"""
Base tool interface for Agent Runtime.

All tools follow the same contract:
  - Receive structured input (Dict)
  - Execute a defined function
  - Return structured output (ToolResult)

Tools are the capability layer. This is how agents interact
with the real world.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from runtime.llm.base import ToolDefinition


@dataclass
class ToolResult:
    """Normalized result from any tool execution."""
    success: bool
    output: Any                        # The actual output data
    error: Optional[str] = None        # Error message if success=False

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
        }


class BaseTool(ABC):
    """
    Abstract base for all tools.

    To add a new tool:
      1. Subclass BaseTool
      2. Implement execute() and get_definition()
      3. Register it in tools/__init__.py
    """

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description

    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Execute the tool with the given input. Must return a ToolResult."""
        pass

    @abstractmethod
    def get_definition(self) -> ToolDefinition:
        """Return the tool's schema definition for the LLM."""
        pass
