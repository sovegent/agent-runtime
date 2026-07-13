"""
Echo tool — development and testing.
Reflects its input back as output. Useful for verifying the loop works.
"""

from typing import Any, Dict
from runtime.tools.base_tool import BaseTool, ToolResult
from runtime.llm.base import ToolDefinition


class EchoTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="echo",
            description="Echo back whatever message you provide. Use for testing the agent loop."
        )

    def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, output={
            "echoed": input_data.get("message", input_data)
        })

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The message to echo back"
                    }
                },
                "required": ["message"]
            }
        )
