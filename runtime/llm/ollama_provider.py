"""
Ollama provider for Agent Runtime.

Run any open-source model locally. No API key. No external calls.
No data leaving your network. This is what sovereign actually means.

Supported models (with tool use):
  llama3.2, llama3.1, mistral, mistral-nemo,
  qwen2.5, qwen2.5-coder, deepseek-r1, phi4, gemma2

Models without tool use still work — agents fall back to
ReAct-style text parsing instead of native tool calls.

Prerequisites:
  1. Install Ollama: https://ollama.com
  2. Pull a model: ollama pull llama3.2
  3. Start Ollama: ollama serve  (or it runs as a service)

Config:
  llm:
    provider: ollama
    model: llama3.2
    ollama_base_url: http://localhost:11434  # default

No API key needed.
"""

import json
import uuid
from typing import Any, Dict, List, Optional

import requests

from runtime.llm.base import BaseLLM, LLMResponse, ToolCall, ToolDefinition


# Models known to support tool/function calling
TOOL_CAPABLE_MODELS = {
    "llama3.1", "llama3.1:8b", "llama3.1:70b", "llama3.1:405b",
    "llama3.2", "llama3.2:1b", "llama3.2:3b",
    "llama3.3", "llama3.3:70b",
    "mistral", "mistral:7b", "mistral-nemo", "mistral-small",
    "qwen2.5", "qwen2.5:7b", "qwen2.5:14b", "qwen2.5:32b", "qwen2.5:72b",
    "qwen2.5-coder", "qwen2.5-coder:7b", "qwen2.5-coder:14b", "qwen2.5-coder:32b",
    "deepseek-r1", "deepseek-r1:8b", "deepseek-r1:14b", "deepseek-r1:32b",
    "phi4", "phi4:14b",
    "firefunction-v2",
    "command-r",
}


class OllamaLLM(BaseLLM):
    """
    Ollama provider using the OpenAI-compatible /v1/chat/completions endpoint.

    Falls back gracefully for models that don't support tool calling —
    the agent loop continues to work, just without native tool dispatch.
    """

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        timeout: int = 120,
        force_tool_support: Optional[bool] = None,
    ):
        """
        Args:
            model:              Ollama model name (e.g. 'llama3.2', 'mistral', 'qwen2.5-coder:7b')
            base_url:           Ollama server URL (default: http://localhost:11434)
            timeout:            Request timeout in seconds — local models can be slow on first run
            force_tool_support: Override auto-detection. True = always use tools, False = never
        """
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._tool_support = force_tool_support  # None = auto-detect from model name

    @property
    def supports_tools(self) -> bool:
        if self._tool_support is not None:
            return self._tool_support
        base = self.model.split(":")[0].lower()
        return base in TOOL_CAPABLE_MODELS or self.model.lower() in TOOL_CAPABLE_MODELS

    def _check_health(self):
        """Verify Ollama is running and the model is available."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code != 200:
                raise ConnectionError(f"Ollama returned {resp.status_code}")
            models = [m["name"] for m in resp.json().get("models", [])]
            base = self.model.split(":")[0]
            available = any(
                m == self.model or m.startswith(base + ":") or m == base
                for m in models
            )
            if not available:
                raise ValueError(
                    f"Model '{self.model}' not found in Ollama. "
                    f"Run: ollama pull {self.model}\n"
                    f"Available models: {', '.join(models) or 'none'}"
                )
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                f"Is Ollama running? Start it with: ollama serve"
            )

    def _convert_messages(self, messages: List[Dict], system: str) -> List[Dict]:
        """
        Convert from our internal message format to OpenAI/Ollama format.

        Our format uses Anthropic-style content blocks for tool calls/results.
        Ollama's OpenAI-compatible endpoint uses a different structure.
        """
        converted = [{"role": "system", "content": system}]

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            # Simple string content — pass through
            if isinstance(content, str):
                converted.append({"role": role, "content": content})
                continue

            # List content — could be tool_use (assistant) or tool_result (user)
            if isinstance(content, list):
                # Assistant message with tool calls
                if role == "assistant":
                    text_parts = []
                    tool_calls = []
                    for block in content:
                        if block.get("type") == "text":
                            text_parts.append(block["text"])
                        elif block.get("type") == "tool_use":
                            tool_calls.append({
                                "id": block.get("id", str(uuid.uuid4())[:8]),
                                "type": "function",
                                "function": {
                                    "name": block["name"],
                                    "arguments": json.dumps(block.get("input", {})),
                                }
                            })
                    out: Dict[str, Any] = {"role": "assistant"}
                    if text_parts:
                        out["content"] = "\n".join(text_parts)
                    if tool_calls:
                        out["tool_calls"] = tool_calls
                    converted.append(out)

                # User message with tool results
                elif role == "user":
                    for block in content:
                        if block.get("type") == "tool_result":
                            converted.append({
                                "role": "tool",
                                "tool_call_id": block.get("tool_use_id", ""),
                                "content": str(block.get("content", "")),
                            })

        return converted

    def _tools_to_openai(self, tools: List[ToolDefinition]) -> List[Dict]:
        """Convert ToolDefinition list to OpenAI/Ollama function format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                }
            }
            for t in tools
        ]

    def complete(
        self,
        messages: List[Dict],
        system: str,
        tools: Optional[List[ToolDefinition]] = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:

        converted_messages = self._convert_messages(messages, system)

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": converted_messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
            }
        }

        # Only pass tools if the model supports them
        use_tools = tools and self.supports_tools
        if use_tools:
            payload["tools"] = self._tools_to_openai(tools)

        try:
            resp = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=self.timeout,
            )
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                f"Is it running? Start with: ollama serve"
            )

        if resp.status_code == 404:
            # Model not found — give a helpful error
            raise ValueError(
                f"Model '{self.model}' not found. Run: ollama pull {self.model}"
            )

        if not resp.ok:
            raise RuntimeError(
                f"Ollama API error {resp.status_code}: {resp.text[:300]}"
            )

        data = resp.json()
        choice = data["choices"][0]
        message = choice["message"]

        text = message.get("content") or ""
        tool_calls = []

        # Parse native tool calls (OpenAI format)
        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                fn = tc.get("function", {})
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(
                    tool_name=fn.get("name", ""),
                    tool_input=args,
                    tool_use_id=tc.get("id", str(uuid.uuid4())[:8]),
                ))

        # If model doesn't support tools natively, try parsing tool calls
        # from the text response (ReAct-style fallback)
        if not tool_calls and not self.supports_tools and tools and text:
            tool_calls = self._parse_text_tool_calls(text, tools)
            if tool_calls:
                text = ""  # Consumed by parsing

        return LLMResponse(
            content=text,
            tool_calls=tool_calls,
            stop_reason=choice.get("finish_reason", "stop"),
            raw=data,
        )

    def _parse_text_tool_calls(
        self,
        text: str,
        tools: List[ToolDefinition],
    ) -> List[ToolCall]:
        """
        Fallback for models without native tool support.

        Looks for JSON blocks in the model's text output that match
        a tool call pattern. Works when the system prompt instructs
        the model to output tool calls as JSON.
        """
        import re
        tool_names = {t.name for t in tools}
        calls = []

        # Look for JSON blocks that look like tool calls
        json_pattern = re.compile(r'\{[^{}]*"tool"\s*:\s*"([^"]+)"[^{}]*\}', re.DOTALL)
        for match in json_pattern.finditer(text):
            try:
                obj = json.loads(match.group(0))
                tool_name = obj.get("tool") or obj.get("name") or obj.get("function")
                if tool_name in tool_names:
                    tool_input = obj.get("input") or obj.get("arguments") or obj.get("parameters") or {}
                    calls.append(ToolCall(
                        tool_name=tool_name,
                        tool_input=tool_input,
                        tool_use_id=str(uuid.uuid4())[:8],
                    ))
            except json.JSONDecodeError:
                continue

        return calls

    def list_local_models(self) -> List[str]:
        """Return a list of models currently available in Ollama."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            return []

    @property
    def provider_name(self) -> str:
        return f"ollama/{self.model}"
