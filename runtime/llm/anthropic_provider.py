"""
Anthropic Claude provider for Agent Runtime.
Uses native tool_use API for structured agent actions.
"""

from typing import Dict, List, Optional

try:
    import anthropic
except ImportError:
    raise ImportError("Install anthropic: pip install anthropic")

from runtime.llm.base import BaseLLM, LLMResponse, ToolCall, ToolDefinition


class AnthropicLLM(BaseLLM):
    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def complete(
        self,
        messages: List[Dict],
        system: str,
        tools: Optional[List[ToolDefinition]] = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }

        if tools:
            kwargs["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in tools
            ]

        response = self.client.messages.create(**kwargs)

        text_parts = []
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    tool_name=block.name,
                    tool_input=block.input,
                    tool_use_id=block.id,
                ))

        return LLMResponse(
            content="\n".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=response.stop_reason,
            raw=response,
        )

    @property
    def provider_name(self) -> str:
        return "anthropic"
