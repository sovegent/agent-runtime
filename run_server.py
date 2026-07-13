#!/usr/bin/env python3
"""
run_server.py — start the Agent Runtime event server.

HTTP server that triggers agents from external events.
Anything that can POST to an endpoint can trigger an agent.

Run it:
  python run_server.py

Behind nginx in production:
  proxy_pass http://127.0.0.1:8080;

Trigger an agent:
  curl -X POST http://localhost:8080/run \\
    -H "Content-Type: application/json" \\
    -d '{"task": "Check disk usage and summarize"}'

Fire a named webhook handler:
  curl -X POST http://localhost:8080/webhook/github-push \\
    -H "Content-Type: application/json" \\
    -d '{"ref": "refs/heads/main", "repository": {"name": "myapp"}}'

Health check:
  curl http://localhost:8080/status
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from runtime import build_runtime
from runtime.server import EventServer
from runtime.logger import get_logger

log = get_logger("server_main")


def make_runtime():
    return build_runtime()


def main():
    port = int(os.getenv("SERVER_PORT", 8080))
    secret = os.getenv("AGENT_SECRET_TOKEN")   # optional auth

    from agents.task_agent import TaskAgent
    from agents.devops_agent import DevOpsAgent

    server = EventServer(
        port=port,
        host="0.0.0.0",
        default_runtime_factory=make_runtime,
        default_agent_factory=lambda: TaskAgent(),
        secret_token=secret,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Named webhook handlers — register these to handle specific event types
    # ─────────────────────────────────────────────────────────────────────────

    # GitHub push events
    # server.register_handler(
    #     "github-push",
    #     agent_factory=lambda: DevOpsAgent(),
    #     task_template=(
    #         "A GitHub push was received: {payload}. "
    #         "Check if the deployment succeeded by verifying the service is running. "
    #         "Notify the team on Slack with the result."
    #     ),
    #     runtime_factory=make_runtime,
    # )

    # Monitoring alert (e.g. from Grafana, Datadog, UptimeRobot)
    # server.register_handler(
    #     "monitor-alert",
    #     agent_factory=lambda: DevOpsAgent(),
    #     task_template=(
    #         "A monitoring alert was received: {payload}. "
    #         "Investigate the cause. Check relevant logs, service status, and system health. "
    #         "Attempt to resolve if possible, then notify with a full report."
    #     ),
    #     runtime_factory=make_runtime,
    # )

    # Form submission / lead intake
    # from agents.task_agent import TaskAgent
    # server.register_handler(
    #     "lead-intake",
    #     agent_factory=lambda: TaskAgent(custom_prompt="You process lead intake forms..."),
    #     task_template="New lead received: {payload}. Qualify and route appropriately.",
    #     runtime_factory=make_runtime,
    # )

    if secret:
        log.info("auth_enabled", hint="Requests must include X-Agent-Token header")
    else:
        log.warning("no_auth", hint="Set AGENT_SECRET_TOKEN env var for production")

    log.info("handlers_registered", count=len(server.handlers), handlers=list(server.handlers.keys()))

    server.start(block=True)


if __name__ == "__main__":
    main()
