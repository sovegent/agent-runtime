"""
Runtime factory — wires everything together from config.

One call to build_runtime() gives you a fully wired AgentLoop
ready to accept agents and tasks.

This is the entry point for programmatic use.
"""

import uuid
from typing import Optional

from runtime.config import Config, load_config
from runtime.agent_loop import AgentLoop
from runtime.executor import Executor
from runtime.memory.memory_store import MemoryStore
from runtime.memory.session import SessionManager
from runtime.tools import build_tool_registry
from runtime.logger import get_logger


def build_runtime(
    config: Optional[Config] = None,
    session_id: Optional[str] = None,
) -> AgentLoop:
    """
    Build a fully-wired AgentLoop from config.

    Args:
        config:     Config object (or None to auto-load from config.yaml + env)
        session_id: Resume an existing session, or None to start a new one

    Returns:
        AgentLoop ready to run agents

    Example:
        loop = build_runtime()
        result = loop.run(MyAgent(), task="Do the thing")
        print(result.output)
    """
    if config is None:
        config = load_config()

    logger = get_logger("runtime", config.execution.log_level)

    # ── LLM provider ──────────────────────────────────────────────────────────
    if not config.llm.api_key and config.llm.provider != "ollama":
        raise ValueError(
            "No API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY environment variable, "
            "or set llm.api_key in config.yaml.\n"
            "Using a local model? Set LLM_PROVIDER=ollama instead."
        )

    if config.llm.provider == "ollama":
        from runtime.llm.ollama_provider import OllamaLLM
        llm = OllamaLLM(
            model=config.llm.model if config.llm.model != "claude-haiku-4-5-20251001" else "llama3.2",
            base_url=config.llm.ollama_base_url,
            timeout=config.llm.ollama_timeout,
        )
        logger.info("ollama_ready", model=llm.model, base_url=llm.base_url, tool_support=llm.supports_tools)
    elif config.llm.provider == "anthropic":
        from runtime.llm.anthropic_provider import AnthropicLLM
        llm = AnthropicLLM(api_key=config.llm.api_key, model=config.llm.model)
    elif config.llm.provider == "openai":
        from runtime.llm.openai_provider import OpenAILLM
        llm = OpenAILLM(api_key=config.llm.api_key, model=config.llm.model)
    else:
        raise ValueError(f"Unknown LLM provider: {config.llm.provider}. Use 'anthropic', 'openai', or 'ollama'.")

    logger.info("llm_ready", provider=config.llm.provider, model=config.llm.model)

    # ── Tools ─────────────────────────────────────────────────────────────────
    tool_registry = build_tool_registry(config.tools.enabled, config)
    executor = Executor(tool_registry)
    logger.info("tools_loaded", tools=str(list(tool_registry.keys())))

    # ── Memory & session ──────────────────────────────────────────────────────
    sessions = SessionManager(storage_path="./data/sessions")

    if session_id and sessions.exists(session_id):
        logger.info("resuming_session", session_id=session_id)
    else:
        session_id = sessions.create_session()
        logger.info("new_session", session_id=session_id)

    memory = MemoryStore(
        session_id=session_id,
        storage_path=config.memory.storage_path,
        persist=config.memory.persist,
    )

    # ── Assemble loop ─────────────────────────────────────────────────────────
    loop = AgentLoop(
        llm=llm,
        executor=executor,
        memory=memory,
        max_steps=config.execution.max_steps,
        log_level=config.execution.log_level,
    )

    logger.info("runtime_ready", session=session_id)
    return loop


def get_session_memory(session_id: str, config: Optional[Config] = None) -> MemoryStore:
    """Load memory for an existing session — for inspection or replay."""
    if config is None:
        config = load_config()
    return MemoryStore(
        session_id=session_id,
        storage_path=config.memory.storage_path,
        persist=config.memory.persist,
    )
