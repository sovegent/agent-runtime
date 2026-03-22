"""
examples/code_generation.py

Code agent that writes and runs a data analysis pipeline.

Give it a task. It writes Python, runs it, fixes errors,
and iterates until it produces the output.

No pre-written scripts — the agent writes everything fresh.

Run:
  ANTHROPIC_API_KEY=... python examples/code_generation.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from runtime import build_runtime
from runtime.config import load_config
from runtime.tools import build_tool_registry
from runtime.tools.code_tool import CodeTool
from runtime.executor import Executor
from runtime.memory.memory_store import MemoryStore
from runtime.memory.session import SessionManager
from runtime.agent_loop import AgentLoop
from runtime.llm.anthropic_provider import AnthropicLLM
from runtime.llm.retry import RetryLLM
from agents.code_agent import CodeAgent


def make_code_runtime():
    """Build a runtime with the code tool enabled."""
    config = load_config()

    from runtime.llm.anthropic_provider import AnthropicLLM
    from runtime.llm.retry import RetryLLM

    base_llm = AnthropicLLM(api_key=config.llm.api_key, model=config.llm.model)
    llm = RetryLLM(base_llm, max_retries=3)

    # Tools for the code agent
    tools = build_tool_registry(["echo", "file", "shell"], config)
    tools["code"] = CodeTool(
        sandbox_dir="./workspace/code_sandbox",
        timeout=30,
    )

    executor = Executor(tools)

    sessions = SessionManager()
    session_id = sessions.create_session(agent="code_agent")

    memory = MemoryStore(
        session_id=session_id,
        storage_path=config.memory.storage_path,
        persist=config.memory.persist,
    )

    return AgentLoop(
        llm=llm,
        executor=executor,
        memory=memory,
        max_steps=config.execution.max_steps,
        log_level=config.execution.log_level,
    )


def main():
    task = """
    Write a Python script that:
    1. Generates a dataset of 100 fake sales records (date, product, quantity, price)
    2. Computes: total revenue, top 3 products by revenue, average order value
    3. Prints a clean summary report to stdout
    4. Saves the dataset as CSV to sales_data.csv and the report as report.txt

    Use only Python stdlib — no pandas needed.
    """

    loop = make_code_runtime()
    agent = CodeAgent()

    result = loop.run(agent, task=task.strip())

    print("\n" + "═" * 60)
    status = "✓ COMPLETE" if result.success else "✗ FAILED"
    print(f"  {status}  |  {result.steps_taken} steps  |  session {result.session_id}")
    print("═" * 60)
    print()
    print(result.output)


if __name__ == "__main__":
    main()
