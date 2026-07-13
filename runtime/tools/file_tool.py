"""
File tool — read and write files in the agent's workspace.

Agents can persist findings, write reports, read configs,
and build up a body of work across sessions.

Security: All paths are restricted to the workspace directory.
No path traversal allowed.
"""

from pathlib import Path
from typing import Any, Dict
from runtime.tools.base_tool import BaseTool, ToolResult
from runtime.llm.base import ToolDefinition


class FileTool(BaseTool):
    def __init__(self, workspace_path: str = "./workspace"):
        super().__init__(
            name="file",
            description=(
                "Read from and write to files in the agent workspace. "
                "Operations: read, write, append, list, delete. "
                "All paths are relative to the workspace directory."
            )
        )
        self.workspace = Path(workspace_path)
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, filename: str) -> Path:
        """Resolve path and ensure it stays within workspace."""
        resolved = (self.workspace / filename).resolve()
        workspace_resolved = self.workspace.resolve()
        if not str(resolved).startswith(str(workspace_resolved)):
            raise ValueError(f"Path traversal not allowed: {filename}")
        return resolved

    def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        operation = input_data.get("operation", "read")
        filename = input_data.get("filename", "")
        content = input_data.get("content")

        if not filename and operation != "list":
            return ToolResult(success=False, output=None, error="No filename provided")

        try:
            if operation == "list":
                files = sorted([
                    str(p.relative_to(self.workspace))
                    for p in self.workspace.rglob("*")
                    if p.is_file()
                ])
                return ToolResult(success=True, output={
                    "workspace": str(self.workspace),
                    "files": files,
                    "count": len(files),
                })

            path = self._safe_path(filename)

            if operation == "read":
                if not path.exists():
                    return ToolResult(success=False, output=None, error=f"File not found: {filename}")
                text = path.read_text(encoding="utf-8")
                return ToolResult(success=True, output={
                    "filename": filename,
                    "content": text,
                    "size_bytes": path.stat().st_size,
                })

            elif operation == "write":
                if content is None:
                    return ToolResult(success=False, output=None, error="No content provided for write")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(str(content), encoding="utf-8")
                return ToolResult(success=True, output={
                    "filename": filename,
                    "bytes_written": len(str(content)),
                })

            elif operation == "append":
                if content is None:
                    return ToolResult(success=False, output=None, error="No content provided for append")
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "a", encoding="utf-8") as f:
                    f.write(str(content))
                return ToolResult(success=True, output={
                    "filename": filename,
                    "appended_bytes": len(str(content)),
                })

            elif operation == "delete":
                if not path.exists():
                    return ToolResult(success=False, output=None, error=f"File not found: {filename}")
                path.unlink()
                return ToolResult(success=True, output={"deleted": filename})

            else:
                return ToolResult(success=False, output=None, error=f"Unknown operation: {operation}. Use: read, write, append, list, delete")

        except ValueError as e:
            return ToolResult(success=False, output=None, error=str(e))
        except PermissionError:
            return ToolResult(success=False, output=None, error=f"Permission denied: {filename}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["read", "write", "append", "list", "delete"],
                        "description": "File operation: read=get contents, write=overwrite, append=add to end, list=show all files, delete=remove"
                    },
                    "filename": {
                        "type": "string",
                        "description": "Relative filename within workspace (e.g., 'notes.txt', 'reports/summary.md'). Not needed for 'list'."
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write or append (required for write/append operations)"
                    }
                },
                "required": ["operation"]
            }
        )
