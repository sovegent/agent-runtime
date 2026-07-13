#!/usr/bin/env python3
"""
run_ollama.py — run agents locally with Ollama. No API key needed.

Prerequisites:
  1. Install Ollama:    https://ollama.com
  2. Pull a model:      ollama pull llama3.2
  3. Run this script:   python run_ollama.py "your task here"

Good models to start with:
  llama3.2          — fast, good tool use, 2GB
  mistral           — reliable, good instruction following, 4GB
  qwen2.5-coder:7b  — excellent for code tasks, 5GB
  deepseek-r1:8b    — strong reasoning, 5GB
  phi4              — Microsoft's small but capable model, 9GB

Usage:
  python run_ollama.py "Check disk usage and summarize"
  python run_ollama.py "Write a Python script to count words in a file" --agent code
  python run_ollama.py "Check nginx status" --agent devops --model mistral
  python run_ollama.py --list-models
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def main():
    parser = argparse.ArgumentParser(
        description="Run agents locally with Ollama — no API key needed",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("task", nargs="?", help="Task for the agent")
    parser.add_argument("--model", "-m", default="llama3.2", help="Ollama model (default: llama3.2)")
    parser.add_argument("--agent", "-a", choices=["task", "devops", "research", "code"], default="task")
    parser.add_argument("--base-url", default="http://localhost:11434", help="Ollama server URL")
    parser.add_argument("--list-models", action="store_true", help="List available local models")
    parser.add_argument("--session", "-s", default=None)
    args = parser.parse_args()

    from runtime.llm.ollama_provider import OllamaLLM, TOOL_CAPABLE_MODELS
    from runtime.config import load_config
    from runtime.tools import build_tool_registry
    from runtime.executor import Executor
    from runtime.memory.memory_store import MemoryStore
    from runtime.memory.session import SessionManager
    from runtime.agent_loop import AgentLoop
    from runtime.llm.retry import RetryLLM
    from runtime.logger import get_logger

    log = get_logger("ollama_runner")

    # List models mode
    if args.list_models:
        llm = OllamaLLM(base_url=args.base_url)
        models = llm.list_local_models()
        if not models:
            print(f"\n  No models found at {args.base_url}")
            print("  Is Ollama running? Start it with: ollama serve")
            print("  Pull a model with: ollama pull llama3.2\n")
            return
        print(f"\n  Local models at {args.base_url}:\n")
        for m in models:
            base = m.split(":")[0]
            tool_mark = "✓ tools" if base in TOOL_CAPABLE_MODELS or m in TOOL_CAPABLE_MODELS else "  text only"
            print(f"    {tool_mark}   {m}")
        print()
        return

    if not args.task:
        parser.print_help()
        sys.exit(1)

    config = load_config()

    # Build Ollama LLM
    base_llm = OllamaLLM(
        model=args.model,
        base_url=args.base_url,
        timeout=config.llm.ollama_timeout,
    )
    llm = RetryLLM(base_llm, max_retries=2, base_delay=2.0)

    tool_support = "native tool use" if base_llm.supports_tools else "text-only (no native tool use)"
    log.info("ollama_ready", model=args.model, support=tool_support)

    if not base_llm.supports_tools:
        print(f"\n  ⚠  {args.model} doesn't support native tool calling.")
        print(f"     Tool calls will use text parsing fallback.")
        print(f"     For best results try: llama3.2, mistral, or qwen2.5\n")

    # Build runtime
    tools = build_tool_registry(config.tools.enabled, config)
    executor = Executor(tools)

    sessions = SessionManager()
    session_id = args.session if args.session and sessions.exists(args.session) else sessions.create_session(agent=f"ollama/{args.model}")
    memory = MemoryStore(session_id=session_id, storage_path=config.memory.storage_path, persist=config.memory.persist)

    loop = AgentLoop(
        llm=llm,
        executor=executor,
        memory=memory,
        max_steps=config.execution.max_steps,
        log_level=config.execution.log_level,
    )

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
    elif args.agent == "code":
        from agents.code_agent import CodeAgent
        agent = CodeAgent()

    result = loop.run(agent, task=args.task)

    print("\n" + "═" * 60)
    status = "✓ COMPLETE" if result.success else "✗ INCOMPLETE"
    print(f"  {status}  |  {result.steps_taken} steps  |  {args.model}  |  session {result.session_id}")
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
