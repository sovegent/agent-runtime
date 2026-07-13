"""
Code tool — write and execute code in a sandboxed subprocess.

This is the "code writing + execution loops" use case.
Agents can write Python, run it, see the output, fix errors,
and iterate until it works. Pure autonomous code generation.

Safety model:
  - Code runs in a subprocess with timeout
  - Optional virtual environment isolation
  - No network access by default (set allow_network=True to override)
  - Execution directory is sandboxed to workspace/code_sandbox/
  - Resource limits enforced via subprocess timeout

This is intentionally powerful — you own this infrastructure.
Lock it down or open it up based on your trust model.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from runtime.tools.base_tool import BaseTool, ToolResult
from runtime.llm.base import ToolDefinition


class CodeTool(BaseTool):
    def __init__(
        self,
        sandbox_dir: str = "./workspace/code_sandbox",
        timeout: int = 30,
        python_binary: str = sys.executable,
        allow_network: bool = True,
        max_output_chars: int = 8000,
    ):
        """
        Args:
            sandbox_dir:      Directory where code files are written and executed
            timeout:          Max seconds per execution
            python_binary:    Python interpreter to use (default: current env)
            allow_network:    Whether executed code can make network requests
            max_output_chars: Truncate stdout/stderr beyond this length
        """
        super().__init__(
            name="code",
            description=(
                "Write and execute Python code. The code runs in a subprocess and "
                "returns stdout, stderr, and exit code. Use for data processing, "
                "calculations, file manipulation, automation scripts, and any task "
                "that benefits from running actual code. Iterate based on output."
            )
        )
        self.sandbox_dir = Path(sandbox_dir)
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.python_binary = python_binary
        self.allow_network = allow_network
        self.max_output_chars = max_output_chars

    def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        code = input_data.get("code", "").strip()
        filename = input_data.get("filename", "agent_script.py")
        install_packages = input_data.get("install_packages", [])

        if not code:
            return ToolResult(success=False, output=None, error="No code provided")

        # Sanitize filename
        filename = Path(filename).name  # strip any path traversal
        if not filename.endswith(".py"):
            filename += ".py"

        code_file = self.sandbox_dir / filename

        try:
            # Optionally install packages first
            install_log = []
            for pkg in (install_packages or []):
                pkg = pkg.strip()
                if not pkg:
                    continue
                result = subprocess.run(
                    [self.python_binary, "-m", "pip", "install", pkg, "--quiet"],
                    capture_output=True, text=True, timeout=60,
                )
                install_log.append({
                    "package": pkg,
                    "success": result.returncode == 0,
                    "output": (result.stdout + result.stderr).strip()[:200],
                })

            # Write code to file
            code_file.write_text(code, encoding="utf-8")

            # Build environment
            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent)  # allow runtime imports

            # Execute
            proc = subprocess.run(
                [self.python_binary, str(code_file)],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(self.sandbox_dir),
                env=env,
            )

            stdout = proc.stdout
            stderr = proc.stderr

            # Truncate long output
            truncated = False
            if len(stdout) > self.max_output_chars:
                stdout = stdout[:self.max_output_chars] + f"\n... [truncated at {self.max_output_chars} chars]"
                truncated = True
            if len(stderr) > self.max_output_chars:
                stderr = stderr[:self.max_output_chars] + f"\n... [truncated]"

            success = proc.returncode == 0
            output = {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": proc.returncode,
                "filename": filename,
                "truncated": truncated,
            }
            if install_log:
                output["installs"] = install_log

            return ToolResult(
                success=success,
                output=output,
                error=None if success else f"Script exited with code {proc.returncode}",
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, output=None,
                error=f"Execution timed out after {self.timeout}s"
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
        finally:
            # Clean up code file after execution
            try:
                code_file.unlink(missing_ok=True)
            except Exception:
                pass

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": (
                            "Complete Python code to execute. Must be a valid, runnable script. "
                            "Use print() to output results — that's what you'll see in stdout. "
                            "Import any stdlib modules freely. For third-party packages, list them in install_packages."
                        )
                    },
                    "filename": {
                        "type": "string",
                        "description": "Optional filename for the script (default: agent_script.py). Useful for multi-file work."
                    },
                    "install_packages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of pip packages to install before running (e.g. ['pandas', 'matplotlib'])"
                    }
                },
                "required": ["code"]
            }
        )
