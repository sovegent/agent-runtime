# Agent Runtime

Runtime layer for executing AI agents and automation workflows in sovereign environments.

Part of the [LiberLayer](https://liberlayer.com) / Sovereign AI Stack.

---

## What This Is

Agent Runtime is the execution engine for AI agents that run on infrastructure you own.

Not a chatbot wrapper. Not a SaaS platform. **Infrastructure.**

The core loop:

```
Input → Reason → Act → Observe → Repeat → Complete
```

Every step is logged, persisted to memory, and traceable. You can inspect exactly what the agent did and why.

---

## Architecture

```
agent-runtime/
├── main.py                      # CLI entry point
├── run_ollama.py                # Local model runner (no API key needed)
├── run_scheduler.py             # Cron-driven autonomous execution
├── run_server.py                # HTTP webhook event server
├── config.yaml                  # Configuration
├── requirements.txt
│
├── runtime/
│   ├── __init__.py              # build_runtime() factory
│   ├── agent.py                 # BaseAgent interface
│   ├── agent_loop.py            # Core ReAct execution loop
│   ├── executor.py              # Tool dispatch layer
│   ├── scheduler.py             # Cron job scheduler
│   ├── server.py                # HTTP event server
│   ├── orchestrator.py          # Multi-agent parallel execution
│   ├── config.py                # Config loader (YAML + env vars)
│   ├── logger.py                # Structured observability
│   │
│   ├── llm/
│   │   ├── base.py              # Provider-agnostic interface
│   │   ├── anthropic_provider.py
│   │   ├── openai_provider.py
│   │   ├── ollama_provider.py   # Local models — no API key needed
│   │   └── retry.py             # Exponential backoff wrapper
│   │
│   ├── memory/
│   │   ├── memory_store.py      # Persistent JSON-backed memory
│   │   ├── semantic_memory.py   # SQLite FTS5 full-text search
│   │   └── session.py           # Session tracking
│   │
│   └── tools/
│       ├── base_tool.py         # BaseTool + ToolResult contract
│       ├── echo_tool.py         # Testing/debug
│       ├── shell_tool.py        # Execute system commands
│       ├── http_tool.py         # Make HTTP/API requests
│       ├── file_tool.py         # Read/write workspace files
│       ├── code_tool.py         # Write and execute Python code
│       ├── ssh_tool.py          # Remote server management
│       ├── db_tool.py           # SQLite + PostgreSQL queries
│       └── notify_tool.py       # Slack, email, webhook alerts
│
├── agents/
│   ├── task_agent.py            # General-purpose agent
│   ├── devops_agent.py          # Infrastructure management
│   ├── research_agent.py        # Web research + report writing
│   └── code_agent.py            # Code writing + execution loops
│
├── dashboard/
│   └── app.py                   # Web observability UI
│
└── examples/
    ├── parallel_server_audit.py  # Multi-agent orchestration
    ├── code_generation.py        # Autonomous code writing
    ├── webhook_deploy_verifier.py
    └── semantic_memory_demo.py
```

---

## Quick Start

### Option A — Cloud models (Anthropic or OpenAI)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python main.py "Check disk usage and summarize which directories are largest"
```

### Option B — Local models via Ollama (no API key, no external calls)

```bash
# 1. Install Ollama: https://ollama.com
# 2. Pull a model
ollama pull llama3.2

# 3. Run an agent — fully local, zero external dependency
pip install -r requirements.txt
python run_ollama.py "Check disk usage and summarize which directories are largest"
```

That's it. No API key. No data leaving your machine.

---

## Running Locally with Ollama

`run_ollama.py` is a zero-config entry point for local model execution.

```bash
# General task
python run_ollama.py "Summarize the largest log files on this system"

# Specific agent
python run_ollama.py "Check nginx and memory usage" --agent devops

# Different model
python run_ollama.py "Write a Python script to parse this CSV" --agent code --model qwen2.5-coder:7b

# See what models you have installed
python run_ollama.py --list-models
```

**Recommended models:**

| Model | Size | Best for |
|---|---|---|
| `llama3.2` | 2GB | General tasks, fast |
| `mistral` | 4GB | Instruction following |
| `qwen2.5-coder:7b` | 5GB | Code generation |
| `deepseek-r1:8b` | 5GB | Reasoning tasks |
| `phi4` | 9GB | Strong all-around |

All of the above support native tool calling. The agent loop works identically to cloud providers — same tools, same memory, same observability.

Or switch via environment variable without touching config:

```bash
LLM_PROVIDER=ollama OLLAMA_MODEL=mistral python main.py "your task"
```

---

## CLI Reference

```
python main.py "task" [--agent task|devops|research|code] [--session ID]

Options:
  --agent           Which agent to use (default: task)
  --session         Resume an existing session
  --config          Config file path (default: config.yaml)
  --list-sessions   Show recent sessions
  --show-session ID Inspect session memory
```

```
python run_ollama.py "task" [--model MODEL] [--agent AGENT]

Options:
  --model           Ollama model name (default: llama3.2)
  --agent           Which agent to use (default: task)
  --base-url        Ollama server URL (default: http://localhost:11434)
  --list-models     List locally available models
```

---

## Configuration

Edit `config.yaml` or override with environment variables:

| Env Var | Effect |
|---|---|
| `ANTHROPIC_API_KEY` | Use Claude |
| `OPENAI_API_KEY` | Use OpenAI |
| `LLM_PROVIDER=ollama` | Use local Ollama model |
| `OLLAMA_MODEL` | Which Ollama model to use |
| `OLLAMA_BASE_URL` | Ollama server URL (default: localhost:11434) |
| `LLM_MODEL` | Override model string |
| `MAX_STEPS` | Override max execution steps |
| `LOG_LEVEL` | DEBUG / INFO / WARNING |

---

## Tools

Nine built-in tools, enabled via `config.yaml`:

| Tool | What it does |
|---|---|
| `shell` | Execute system commands |
| `http` | Make HTTP/API requests |
| `file` | Read/write workspace files |
| `code` | Write and execute Python scripts |
| `ssh` | Run commands on remote servers |
| `database` | Query SQLite or PostgreSQL |
| `notify` | Send Slack, email, or webhook alerts |
| `echo` | Testing and debug |

---

## Agents

| Agent | Best for |
|---|---|
| `task` | General-purpose tasks |
| `devops` | Server management, logs, diagnostics |
| `research` | Web research, API fetching, report writing |
| `code` | Writing, running, and debugging Python code |

---

## Beyond Single Agents

**Scheduler** — run agents on a cron schedule:

```bash
python run_scheduler.py
# Edit run_scheduler.py to define your jobs
```

**Event server** — trigger agents from webhooks:

```bash
python run_server.py
curl -X POST http://localhost:8080/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Check disk usage and summarize"}'
```

**Multi-agent orchestration** — parallel specialists:

```python
from runtime.orchestrator import Orchestrator, SubTask
from agents.devops_agent import DevOpsAgent

orchestrator = Orchestrator(runtime_factory=make_runtime)
result = orchestrator.run(
    task="Full server audit",
    subtasks=[
        SubTask("Check nginx and web layer", DevOpsAgent()),
        SubTask("Check disk and memory", DevOpsAgent()),
        SubTask("Check security and open ports", DevOpsAgent()),
    ]
)
print(result.synthesis)
```

**Dashboard** — live session viewer:

```bash
python -m dashboard.app
# Open http://localhost:5001
```

**Docker** — deploy the full stack:

```bash
docker-compose up -d
```

---

## Extending: Add a Tool

```python
# runtime/tools/my_tool.py
from runtime.tools.base_tool import BaseTool, ToolResult
from runtime.llm.base import ToolDefinition

class MyTool(BaseTool):
    def __init__(self):
        super().__init__("my_tool", "Does something useful")

    def execute(self, input_data) -> ToolResult:
        return ToolResult(success=True, output={"result": "..."})

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "param": {"type": "string", "description": "..."}
                },
                "required": ["param"]
            }
        )
```

Register in `runtime/tools/__init__.py`, enable in `config.yaml`. Done.

---

## Extending: Add an Agent

```python
# agents/my_agent.py
from runtime.agent import BaseAgent

class MyAgent(BaseAgent):
    name = "my_agent"
    description = "Does a specific thing well."

    def get_system_prompt(self) -> str:
        return """You are a specialized agent for [domain].
        [Instructions for behavior, priorities, output format]
        """
```

```python
from runtime import build_runtime
from agents.my_agent import MyAgent

loop = build_runtime()
result = loop.run(MyAgent(), task="Do the specific thing")
print(result.output)
```

---

## Memory and Sessions

Every session persists to `./data/memory/<session_id>.json`.

```bash
# List sessions
python main.py --list-sessions

# Inspect a session
python main.py --show-session abc12345

# Resume a session
python main.py "Continue the previous task" --session abc12345
```

---

## Design Principles

- **Local-first.** Runs on hardware you control. Ollama support means zero external dependency.
- **Provider-agnostic.** Swap Anthropic, OpenAI, or Ollama without changing agent code.
- **Observable.** Every step logged. Every action stored in memory.
- **Modular.** Tools, agents, and LLM providers are independently swappable.
- **Minimal dependencies.** `anthropic`, `pyyaml`, `requests`. That's the core.

---

## Part of Sovereign AI Stack

Agent Runtime is the execution layer within [Sovereign AI Stack](https://github.com/liberlayer/sovereign-ai-stack).

```
Sovereign AI Stack (LiberLayer)
└── Agent Runtime          ← this repo
    ├── LLM Providers      (Anthropic, OpenAI, Ollama)
    ├── Tool System        (9 built-in tools)
    ├── Memory Layer       (persistent, searchable)
    └── Execution Loop     (ReAct, observable)
```

---

## LiberLayer

LiberLayer builds AI systems and infrastructure you own and control.

https://liberlayer.com