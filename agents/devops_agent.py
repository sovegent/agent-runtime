"""
DevOps Agent — infrastructure management and server operations.

Specialized for:
  - Server health checks
  - Log analysis
  - Service management (nginx, systemd, docker)
  - Automated diagnostics
  - SSH-driven remote tasks (via shell tool)

This is the "AI agents that manage servers" use case from the spec.
"""

from typing import Any, Dict
from runtime.agent import BaseAgent
from runtime.logger import get_logger


class DevOpsAgent(BaseAgent):
    name = "devops_agent"
    description = "Infrastructure agent for server management, diagnostics, and automation."

    def __init__(self):
        self.logger = get_logger(self.name)

    def get_system_prompt(self) -> str:
        return """You are a DevOps automation agent running on sovereign infrastructure.

Your capabilities:
- Execute shell commands to inspect, manage, and fix systems
- Read and analyze log files
- Check service health (nginx, systemd, docker, PM2)
- Write runbooks and findings to files
- Make HTTP calls to monitoring endpoints or webhooks

## Approach

1. **Diagnose before acting.** Always read/check state before making changes.
2. **Non-destructive first.** Prefer read operations, then dry-run, then execute.
3. **Explain what you're doing.** Narrate each step so the operator understands.
4. **Document findings.** Write important findings to a file so they persist.
5. **Error context.** If something fails, capture stderr and return code.

## Common patterns

Check service: `systemctl status <service>`
Recent logs: `journalctl -u <service> -n 50 --no-pager`
Disk usage: `df -h` and `du -sh /var/log/*`
Process state: `ps aux | grep <process>`
Port check: `ss -tlnp | grep <port>`
Nginx test: `nginx -t`

## When done

Provide a clear status report: what you found, what you did, current system state.
If you wrote a file, mention the path.
"""

    def on_step_complete(self, step: int, action: Dict, result: Any, state: Dict) -> Dict:
        # Track failed commands for the final report
        if not result.success:
            failures = state.get("failures", [])
            failures.append({
                "step": step,
                "tool": action.get("tool"),
                "error": result.error,
            })
            state["failures"] = failures
        return state

    def on_complete(self, result: str, state: Dict):
        failures = state.get("failures", [])
        self.logger.info(
            "devops_complete",
            steps=state.get("step", 0),
            failures=len(failures),
        )
