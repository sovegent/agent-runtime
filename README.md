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
├── main.py                     # CLI entry point
├── config.yaml                 # Configuration
├── requirements.txt
│
├── runtime/
│   ├── __init__.py             # build_runtime() factory
│   ├── agent.py                # BaseAgent interface
│   ├── agent_loop.py           # Core ReAct execution loop
│   ├── executor.py             # Tool dispatch layer
│   ├── config.py               # Config loader (YAML + env vars)
│   ├── logger.py               # Structured observability
│   │
│   ├── llm/
│   │   ├── base.py             # Provider-agnostic interface
│   │   ├── anthropic_provider.py
│   │   └── openai_provider.py
│   │
│   ├── memory/
│   │   ├── memory_store.py     # Persistent JSON-backed memory
│   │   └── session.py          # Session tracking
│   │
│   └── tools/
│       ├── base_tool.py        # BaseTool + ToolResult contract
│       ├── echo_tool.py        # Testing/debug
│       ├── shell_tool.py       # Execute system commands
│       ├── http_tool.py        # Make HTTP/API requests
│       └── file_tool.py        # Read/write workspace files
│
└── agents/
    ├── task_agent.py           # General-purpose agent
    ├── devops_agent.py         # Infrastructure management
    └── research_agent.py       # Web research + report writing
```

---

## Quick Start

**1. Install dependencies**

```bash
pip install -r requirements.txt
```

**2. Set your API key**

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# or
export OPENAI_API_KEY=sk-...
```

**3. Run an agent**

```bash
# General task
python main.py "Check disk usage and summarize which directories are largest"

# DevOps task
python main.py "Check nginx status and show the last 20 error log lines" --agent devops

# Research task
python main.py "Fetch the latest Bitcoin price from the CoinGecko API and write a report" --agent research
```

---

## CLI Reference

```
python main.py "task" [--agent task|devops|research] [--session ID]

Options:
  --agent       Which agent to use (default: task)
  --session     Resume an existing session
  --config      Config file path (default: config.yaml)
  --list-sessions         Show recent sessions
  --show-session ID       Inspect session memory
```

---

## Configuration

Edit `config.yaml` or override with environment variables:

| Env Var              | Effect                          |
|----------------------|---------------------------------|
| `ANTHROPIC_API_KEY`  | Use Claude                      |
| `OPENAI_API_KEY`     | Use OpenAI                      |
| `LLM_MODEL`          | Override model string           |
| `MAX_STEPS`          | Override max execution steps    |
| `LOG_LEVEL`          | DEBUG / INFO / WARNING          |

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
        # Do the thing
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

Register it in `runtime/tools/__init__.py`:

```python
from runtime.tools.my_tool import MyTool

TOOL_REGISTRY = {
    ...
    "my_tool": MyTool,
}
```

Enable it in `config.yaml`:

```yaml
tools:
  enabled:
    - my_tool
```

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

Use it:

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

# Resume a session (agent has full history context)
python main.py "Continue the previous task" --session abc12345
```

---

## Design Principles

- **Local-first.** Runs on hardware you control. No mandatory cloud.
- **Provider-agnostic.** Swap Anthropic / OpenAI without changing agent code.
- **Observable.** Every step logged. Every action stored in memory.
- **Modular.** Tools, agents, and LLM providers are independently swappable.
- **Minimal dependencies.** `anthropic`, `pyyaml`, `requests`. That's the core.

---

## Part of Sovereign AI Stack

Agent Runtime is the execution layer within [Sovereign AI Stack](https://github.com/liberlayer/sovereign-ai-stack).

```
Sovereign AI Stack (LiberLayer)
└── Agent Runtime          ← this repo
    ├── LLM Providers
    ├── Tool System
    ├── Memory Layer
    └── Execution Loop
```

---

## LiberLayer

LiberLayer builds AI systems and infrastructure you own and control.

https://liberlayer.com
