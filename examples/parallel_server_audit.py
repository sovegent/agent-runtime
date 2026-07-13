"""
examples/parallel_server_audit.py

Multi-agent parallel server audit.

Three specialist agents run simultaneously:
  - Web agent: checks nginx, endpoints, response times
  - System agent: checks disk, memory, CPU load
  - Security agent: checks auth logs, failed logins, open ports

Results synthesized into a single audit report.

This completes in ~1/3 the time of running sequentially.

Run:
  ANTHROPIC_API_KEY=... python examples/parallel_server_audit.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from runtime import build_runtime
from runtime.orchestrator import Orchestrator, SubTask
from agents.devops_agent import DevOpsAgent


def make_runtime():
    return build_runtime()


def main():
    orchestrator = Orchestrator(
        runtime_factory=make_runtime,
        max_workers=3,
        synthesize=True,
    )

    result = orchestrator.run(
        task="Full server health and security audit",
        subtasks=[
            SubTask(
                task=(
                    "Audit the web layer: check nginx status and configuration, "
                    "verify it's listening on port 80 and 443, check the last 20 error log lines, "
                    "and test response time with a simple curl to localhost."
                ),
                agent=DevOpsAgent(),
                label="Web layer audit",
            ),
            SubTask(
                task=(
                    "Audit system resources: check disk usage on all mounts (flag anything >80%), "
                    "check memory and swap usage, check CPU load average, "
                    "and list the top 5 processes by CPU and memory."
                ),
                agent=DevOpsAgent(),
                label="System resources audit",
            ),
            SubTask(
                task=(
                    "Audit security basics: check for failed SSH login attempts in auth logs, "
                    "list all open listening ports, check if any unexpected processes are running as root, "
                    "and verify that ufw or iptables is active."
                ),
                agent=DevOpsAgent(),
                label="Security audit",
            ),
        ]
    )

    print("\n" + "═" * 60)
    print(f"  AUDIT COMPLETE")
    print(f"  Success: {result.overall_success}")
    print(f"  Agents: 3 parallel  |  Steps: {result.total_steps}  |  Time: {result.elapsed_seconds}s")
    print("═" * 60)
    print()
    print(result.synthesis)


if __name__ == "__main__":
    main()
