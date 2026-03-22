"""
examples/webhook_deploy_verifier.py

Event-driven deployment verification.

When GitHub pushes to main, this server:
  1. Receives the webhook
  2. Triggers a DevOps agent
  3. Agent verifies the deployment succeeded
  4. Notifies Slack with the result

Run:
  ANTHROPIC_API_KEY=... python examples/webhook_deploy_verifier.py

Test it:
  curl -X POST http://localhost:8080/webhook/deploy \\
    -H "Content-Type: application/json" \\
    -d '{"ref": "refs/heads/main", "repository": {"name": "myapp"}, "pusher": {"name": "dev"}}'

Then watch the agent run and check /sessions for results.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from runtime import build_runtime
from runtime.server import EventServer
from agents.devops_agent import DevOpsAgent
from agents.task_agent import TaskAgent


def make_runtime():
    return build_runtime()


def main():
    server = EventServer(
        port=8080,
        default_runtime_factory=make_runtime,
        default_agent_factory=lambda: TaskAgent(),
    )

    # Deployment verification handler
    server.register_handler(
        "deploy",
        agent_factory=lambda: DevOpsAgent(),
        task_template=(
            "A deployment was just pushed to production. Event data: {payload}\n\n"
            "Your job:\n"
            "1. Check that the application process is running (nginx, gunicorn, pm2, docker — whatever's relevant)\n"
            "2. Verify it's responding on its expected port\n"
            "3. Check the last 20 lines of the application log for errors\n"
            "4. Report: SUCCESS if everything looks healthy, DEGRADED if partial, FAILED if it's down\n"
            "5. Include specific details: what's running, what port, any errors found"
        ),
        runtime_factory=make_runtime,
    )

    # Generic task endpoint — useful for testing
    print("\n  Event server started")
    print("  POST /run                — run any task")
    print("  POST /webhook/deploy     — deployment verification")
    print("  GET  /status             — server health")
    print("  GET  /sessions           — recent runs")
    print()

    server.start(block=True)


if __name__ == "__main__":
    main()
