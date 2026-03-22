"""
SSH tool — execute commands on remote servers.

This is the DevOps unlock. Agents can now manage any server
you have SSH access to. Run diagnostics, deploy code, restart
services, manage files — all from an agent loop.

Auth: supports key-based (recommended) and password auth.
Safety: commands run as the SSH user you configure. You control
what that user can do via normal Unix permissions.
"""

from typing import Any, Dict, List, Optional
from runtime.tools.base_tool import BaseTool, ToolResult
from runtime.llm.base import ToolDefinition

try:
    import paramiko
except ImportError:
    raise ImportError("Install paramiko: pip install paramiko")


class SSHTool(BaseTool):
    def __init__(
        self,
        default_host: Optional[str] = None,
        default_user: Optional[str] = None,
        default_key_path: Optional[str] = None,
        default_password: Optional[str] = None,
        default_port: int = 22,
        timeout: int = 30,
        allowed_hosts: Optional[List[str]] = None,
    ):
        super().__init__(
            name="ssh",
            description=(
                "Execute a command on a remote server via SSH. "
                "Use for server management, log inspection, service control, "
                "deployments, and any remote infrastructure task."
            )
        )
        self.default_host = default_host
        self.default_user = default_user
        self.default_key_path = default_key_path
        self.default_password = default_password
        self.default_port = default_port
        self.timeout = timeout
        self.allowed_hosts = allowed_hosts  # None = all allowed

    def _connect(self, host: str, user: str, port: int, key_path: Optional[str], password: Optional[str]) -> paramiko.SSHClient:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs: Dict = {
            "hostname": host,
            "username": user,
            "port": port,
            "timeout": self.timeout,
        }

        if key_path:
            connect_kwargs["key_filename"] = key_path
        elif password:
            connect_kwargs["password"] = password
            connect_kwargs["look_for_keys"] = False

        client.connect(**connect_kwargs)
        return client

    def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        host = input_data.get("host") or self.default_host
        user = input_data.get("user") or self.default_user
        command = input_data.get("command", "").strip()
        port = input_data.get("port") or self.default_port
        key_path = input_data.get("key_path") or self.default_key_path
        password = input_data.get("password") or self.default_password

        if not host:
            return ToolResult(success=False, output=None, error="No host provided and no default_host set")
        if not user:
            return ToolResult(success=False, output=None, error="No user provided and no default_user set")
        if not command:
            return ToolResult(success=False, output=None, error="No command provided")
        if not key_path and not password:
            return ToolResult(success=False, output=None, error="No authentication method: provide key_path or password")

        # Host allowlist check
        if self.allowed_hosts and host not in self.allowed_hosts:
            return ToolResult(
                success=False, output=None,
                error=f"Host '{host}' not in allowed_hosts list"
            )

        client = None
        try:
            client = self._connect(host, user, port, key_path, password)
            stdin, stdout, stderr = client.exec_command(command, timeout=self.timeout)
            exit_code = stdout.channel.recv_exit_status()

            out = stdout.read().decode("utf-8", errors="replace").strip()
            err = stderr.read().decode("utf-8", errors="replace").strip()

            return ToolResult(
                success=exit_code == 0,
                output={
                    "host": host,
                    "user": user,
                    "command": command,
                    "stdout": out,
                    "stderr": err,
                    "exit_code": exit_code,
                },
                error=None if exit_code == 0 else f"Exit code {exit_code}: {err[:200]}"
            )

        except paramiko.AuthenticationException:
            return ToolResult(success=False, output=None, error=f"Authentication failed for {user}@{host}")
        except paramiko.SSHException as e:
            return ToolResult(success=False, output=None, error=f"SSH error: {e}")
        except OSError as e:
            return ToolResult(success=False, output=None, error=f"Connection failed to {host}:{port} — {e}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
        finally:
            if client:
                client.close()

    def get_definition(self) -> ToolDefinition:
        host_desc = f"Hostname or IP of the remote server (default: {self.default_host})" if self.default_host else "Hostname or IP of the remote server"
        user_desc = f"SSH username (default: {self.default_user})" if self.default_user else "SSH username"

        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to run on the remote server (e.g., 'systemctl status nginx', 'df -h', 'tail -n 50 /var/log/syslog')"
                    },
                    "host": {"type": "string", "description": host_desc},
                    "user": {"type": "string", "description": user_desc},
                    "port": {"type": "integer", "description": "SSH port (default: 22)"},
                    "key_path": {"type": "string", "description": "Path to SSH private key file (e.g., '/home/user/.ssh/id_rsa')"},
                    "password": {"type": "string", "description": "SSH password (prefer key_path when possible)"},
                },
                "required": ["command"]
            }
        )
