#!/usr/bin/env python3
"""
main.py — CLI entry point for Agent Runtime.

Usage:
  python main.py "Your task here"
  python main.py "Your task here" --agent task
  python main.py "Your task here" --agent devops
  python main.py "Your task here" --agent research --session abc123
  python main.py --list-sessions

Environment:
  ANTHROPIC_API_KEY=...    Use Claude (default)
  OPENAI_API_KEY=...       Use OpenAI instead
  LLM_MODEL=...            Override the model
  MAX_STEPS=...            Override max steps
  LOG_LEVEL=DEBUG          Verbose output
"""

import argparse
import sys
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Agent Runtime — sovereign AI agent execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "task",
        nargs="?",
        help="The task for the agent to perform"
    )
    parser.add_argument(
        "--agent", "-a",
        choices=["task", "devops", "research"],
        default="task",
        help="Which agent to run (default: task)"
    )
    parser.add_argument(
        "--session", "-s",
        default=None,
        help="Resume a specific session ID"
    )
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Path to config file (default: config.yaml)"
    )
    parser.add_argument(
        "--list-sessions",
        action="store_true",
        help="List recent sessions and exit"
    )
    parser.add_argument(
        "--show-session",
        metavar="SESSION_ID",
        help="Show memory contents of a session and exit"
    )

    args = parser.parse_args()

    # ── Import here so we get clean error messages ────────────────────────────
    try:
        from runtime.config import load_config
        from runtime import build_runtime, get_session_memory
        from runtime.memory.session import SessionManager
    except ImportError as e:
        print(f"\n✗ Import error: {e}")
        print("  Make sure you've run: pip install -r requirements.txt")
        sys.exit(1)

    config = load_config(args.config)

    # ── Utility commands ──────────────────────────────────────────────────────
    if args.list_sessions:
        sessions = SessionManager()
        rows = sessions.list_sessions(n=20)
        if not rows:
            print("No sessions found.")
            return
        print(f"\n{'ID':<12} {'Agent':<16} {'Label':<28} {'Updated'}")
        print("─" * 70)
        for s in rows:
            print(f"{s['id']:<12} {s.get('agent','?'):<16} {s.get('label',''):<28} {s['updated_at'][:19]}")
        return

    if args.show_session:
        memory = get_session_memory(args.show_session, config)
        entries = memory.get_all()
        if not entries:
            print(f"No memory found for session: {args.show_session}")
            return
        print(f"\nSession {args.show_session} — {len(entries)} entries\n")
        for e in entries:
            print(json.dumps(e, indent=2, default=str))
            print()
        return

    # ── Task execution ────────────────────────────────────────────────────────
    if not args.task:
        parser.print_help()
        sys.exit(1)

    # Load agent
    if args.agent == "task":
        from agents.task_agent import TaskAgent
        agent = TaskAgent()
    elif args.agent == "devops":
        from agents.devops_agent import DevOpsAgent
        agent = DevOpsAgent()
    elif args.agent == "research":
        from agents.research_agent import ResearchAgent
        agent = ResearchAgent()
    else:
        print(f"Unknown agent: {args.agent}")
        sys.exit(1)

    # Build runtime and run
    try:
        loop = build_runtime(config=config, session_id=args.session)
    except ValueError as e:
        print(f"\n✗ Configuration error: {e}\n")
        sys.exit(1)

    result = loop.run(agent, task=args.task)

    # ── Print result ──────────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    status = "✓ COMPLETE" if result.success else "✗ INCOMPLETE"
    print(f"  {status}  |  {result.steps_taken} steps  |  session {result.session_id}")
    print("═" * 60)
    print()
    if result.output:
        print(result.output)
    if result.error:
        print(f"\nError: {result.error}")
    print()

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
