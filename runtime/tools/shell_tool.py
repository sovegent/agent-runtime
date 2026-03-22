"""
Shell tool — execute system commands.

This is the power tool. Agents can run scripts, check system state,
manage files, interact with any CLI tool.

Safety: Set allowed_commands in config to restrict what can run.
Default: all commands allowed (you own this infrastructure).
"""

import subprocess
from typing import Any, Dict, List, Optional
from runtime.tools.base_tool import BaseTool, ToolResult
from runtime.llm.base import ToolDefinition


class ShellTool(BaseTool):
    def __init__(
        self,
        timeout: int = 10,
        allowed_commands: Optional[List[str]] = None,
        working_dir: Optional[str] = None,
    ):
        super().__init__(
            name="shell",
            description=(
                "Execute a shell command and return stdout/stderr. "
                "Use for system operations, running scripts, checking state, "
                "file management, and interacting with any CLI tool."
            )
        )
        self.timeout = timeout
        self.allowed_commands = allowed_commands  # None = allow all
        self.working_dir = working_dir

    def _is_allowed(self, command: str) -> bool:
        if self.allowed_commands is None:
            return True
        first_word = command.strip().split()[0] if command.strip() else ""
        return first_word in self.allowed_commands

    def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        command = input_data.get("command", "").strip()

        if not command:
            return ToolResult(success=False, output=None, error="No command provided")

        if not self._is_allowed(command):
            first = command.split()[0]
            return ToolResult(
                success=False,
                output=None,
                error=f"Command '{first}' is not in the allowed list"
            )

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.working_dir,
            )
            return ToolResult(
                success=result.returncode == 0,
                output={
                    "stdout": result.stdout.strip(),
                    "stderr": result.stderr.strip(),
                    "return_code": result.returncode,
                }
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, output=None,
                error=f"Command timed out after {self.timeout}s"
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute (e.g., 'ls -la', 'python3 script.py', 'systemctl status nginx')"
                    }
                },
                "required": ["command"]
            }
        )
