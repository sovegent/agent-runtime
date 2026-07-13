"""
Executor — dispatches tool calls from the agent loop.

The executor is the bridge between the LLM's decisions and
real-world actions. It validates, routes, and executes tool calls.
"""

from typing import Any, Dict, List
from runtime.tools.base_tool import BaseTool, ToolResult
from runtime.llm.base import ToolDefinition
from runtime.logger import get_logger


class Executor:
    def __init__(self, tool_registry: Dict[str, BaseTool]):
        self.tools = tool_registry
        self.logger = get_logger("executor")

    def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> ToolResult:
        """Execute a named tool with input. Always returns a ToolResult."""
        if tool_name not in self.tools:
            available = list(self.tools.keys())
            error = f"Tool '{tool_name}' not found. Available: {available}"
            self.logger.error("tool_not_found", tool=tool_name, available=str(available))
            return ToolResult(success=False, output=None, error=error)

        tool = self.tools[tool_name]
        self.logger.debug("executing", tool=tool_name, input=str(tool_input)[:200])

        try:
            result = tool.execute(tool_input)
            status = "✓" if result.success else "✗"
            self.logger.debug(
                "result",
                tool=tool_name,
                status=status,
                output=str(result.output)[:200] if result.output else result.error
            )
            return result
        except Exception as e:
            self.logger.error("tool_exception", tool=tool_name, error=str(e))
            return ToolResult(success=False, output=None, error=f"Unhandled exception: {e}")

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Return schema definitions for all registered tools (passed to LLM)."""
        return [tool.get_definition() for tool in self.tools.values()]

    def list_tools(self) -> List[str]:
        return list(self.tools.keys())

    def has_tool(self, name: str) -> bool:
        return name in self.tools
