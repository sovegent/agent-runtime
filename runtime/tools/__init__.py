"""
Tool registry for Agent Runtime.

Register all tools here. The executor loads from this registry.
To add a new tool: implement BaseTool, add it to TOOL_REGISTRY.
"""

from runtime.tools.echo_tool import EchoTool
from runtime.tools.shell_tool import ShellTool
from runtime.tools.http_tool import HttpTool
from runtime.tools.file_tool import FileTool
from runtime.tools.db_tool import DatabaseTool
from runtime.tools.notify_tool import NotifyTool
from runtime.tools.code_tool import CodeTool

# SSH is optional — requires: pip install paramiko
try:
    from runtime.tools.ssh_tool import SSHTool
    _SSH_AVAILABLE = True
except ImportError:
    _SSH_AVAILABLE = False

# Registry of all available tool classes
TOOL_REGISTRY = {
    "echo":     EchoTool,
    "shell":    ShellTool,
    "http":     HttpTool,
    "file":     FileTool,
    "database": DatabaseTool,
    "notify":   NotifyTool,
    "code":     CodeTool,
}
if _SSH_AVAILABLE:
    TOOL_REGISTRY["ssh"] = SSHTool


def build_tool_registry(enabled: list, config) -> dict:
    """
    Build an instantiated tool registry from config.
    Only tools in the 'enabled' list are loaded.
    """
    registry = {}
    for name in enabled:
        if name not in TOOL_REGISTRY:
            continue

        if name == "shell":
            registry[name] = ShellTool(
                timeout=getattr(config.tools, "shell_timeout", 15),
                allowed_commands=getattr(config.tools, "allowed_shell_commands", None),
            )
        elif name == "http":
            registry[name] = HttpTool(
                timeout=getattr(config.tools, "http_timeout", 20)
            )
        elif name == "file":
            registry[name] = FileTool(
                workspace_path=getattr(config.tools, "workspace_path", "./workspace")
            )
        elif name == "code":
            registry[name] = CodeTool(
                sandbox_dir=getattr(config.tools, "code_sandbox_dir", "./workspace/code_sandbox"),
                timeout=getattr(config.tools, "code_timeout", 30),
            )
        elif name == "database":
            registry[name] = DatabaseTool(
                connection_string=getattr(config.tools, "db_connection_string", None),
                db_type=getattr(config.tools, "db_type", "sqlite"),
                allow_writes=getattr(config.tools, "db_allow_writes", False),
            )
        elif name == "notify":
            registry[name] = NotifyTool(
                slack_webhook_url=getattr(config.tools, "slack_webhook_url", None),
                smtp_host=getattr(config.tools, "smtp_host", None),
                smtp_port=getattr(config.tools, "smtp_port", 587),
                smtp_user=getattr(config.tools, "smtp_user", None),
                smtp_password=getattr(config.tools, "smtp_password", None),
                smtp_from=getattr(config.tools, "smtp_from", None),
                default_email_to=getattr(config.tools, "default_email_to", None),
            )
        elif name == "ssh" and _SSH_AVAILABLE:
            registry[name] = SSHTool(
                default_host=getattr(config.tools, "ssh_default_host", None),
                default_user=getattr(config.tools, "ssh_default_user", None),
                default_key_path=getattr(config.tools, "ssh_key_path", None),
                timeout=getattr(config.tools, "ssh_timeout", 30),
                allowed_hosts=getattr(config.tools, "ssh_allowed_hosts", None),
            )
        else:
            registry[name] = TOOL_REGISTRY[name]()

    return registry


# Legacy compat
AVAILABLE_TOOLS = {"echo": EchoTool()}
