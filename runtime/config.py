"""
Configuration loader for Agent Runtime.
Reads config.yaml and applies environment variable overrides.
"""

import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class LLMConfig:
    provider: str = "anthropic"       # anthropic | openai | ollama
    model: str = "claude-haiku-4-5-20251001"
    api_key: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.0
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout: int = 120


@dataclass
class MemoryConfig:
    persist: bool = True
    storage_path: str = "./data/memory"
    session_ttl_hours: int = 24


@dataclass
class ExecutionConfig:
    max_steps: int = 20
    step_timeout_seconds: int = 30
    log_level: str = "INFO"


@dataclass
class ToolConfig:
    enabled: List[str] = field(default_factory=lambda: ["echo", "file", "http", "shell"])
    shell_timeout: int = 15
    http_timeout: int = 20
    allowed_shell_commands: Optional[List[str]] = None

    # File tool
    workspace_path: str = "./workspace"

    # SSH tool
    ssh_default_host: Optional[str] = None
    ssh_default_user: Optional[str] = None
    ssh_key_path: Optional[str] = None
    ssh_timeout: int = 30
    ssh_allowed_hosts: Optional[List[str]] = None

    # Database tool
    db_connection_string: Optional[str] = None
    db_type: str = "sqlite"
    db_allow_writes: bool = False

    # Notify tool
    slack_webhook_url: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
    default_email_to: Optional[str] = None


@dataclass
class Config:
    llm: LLMConfig = field(default_factory=LLMConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    tools: ToolConfig = field(default_factory=ToolConfig)


def load_config(path: str = "config.yaml") -> Config:
    config = Config()

    if Path(path).exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}

        if "llm" in data:
            for k, v in data["llm"].items():
                if hasattr(config.llm, k):
                    setattr(config.llm, k, v)
        if "memory" in data:
            for k, v in data["memory"].items():
                if hasattr(config.memory, k):
                    setattr(config.memory, k, v)
        if "execution" in data:
            for k, v in data["execution"].items():
                if hasattr(config.execution, k):
                    setattr(config.execution, k, v)
        if "tools" in data:
            for k, v in data["tools"].items():
                if hasattr(config.tools, k):
                    setattr(config.tools, k, v)

    # Environment variable overrides (take highest priority)
    if os.getenv("LLM_PROVIDER"):
        config.llm.provider = os.getenv("LLM_PROVIDER")
    if os.getenv("LLM_MODEL"):
        config.llm.model = os.getenv("LLM_MODEL")
    if os.getenv("ANTHROPIC_API_KEY"):
        config.llm.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not os.getenv("LLM_PROVIDER"):
            config.llm.provider = "anthropic"
    if os.getenv("OPENAI_API_KEY") and not config.llm.api_key:
        config.llm.api_key = os.getenv("OPENAI_API_KEY")
        if not os.getenv("LLM_PROVIDER"):
            config.llm.provider = "openai"
    if os.getenv("OLLAMA_BASE_URL"):
        config.llm.ollama_base_url = os.getenv("OLLAMA_BASE_URL")
    if os.getenv("OLLAMA_MODEL"):
        config.llm.model = os.getenv("OLLAMA_MODEL")
        if not os.getenv("LLM_PROVIDER"):
            config.llm.provider = "ollama"
    if os.getenv("MAX_STEPS"):
        config.execution.max_steps = int(os.getenv("MAX_STEPS"))
    if os.getenv("LOG_LEVEL"):
        config.execution.log_level = os.getenv("LOG_LEVEL")

    return config
