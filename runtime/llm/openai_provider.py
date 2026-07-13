"""
OpenAI provider for Agent Runtime.
Uses function calling API for structured agent actions.
"""

import json
from typing import Dict, List, Optional

try:
    from openai import OpenAI
except ImportError:
    raise ImportError("Install openai: pip install openai")

from runtime.llm.base import BaseLLM, LLMResponse, ToolCall, ToolDefinition


class OpenAILLM(BaseLLM):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def complete(
        self,
        messages: List[Dict],
        system: str,
        tools: Optional[List[ToolDefinition]] = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        all_messages = [{"role": "system", "content": system}] + messages

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": all_messages,
        }

        if tools:
            kwargs["tools"] = [
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
            kwargs["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        message = choice.message

        text = message.content or ""
        tool_calls = []

        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(ToolCall(
                    tool_name=tc.function.name,
                    tool_input=json.loads(tc.function.arguments),
                    tool_use_id=tc.id,
                ))

        return LLMResponse(
            content=text,
            tool_calls=tool_calls,
            stop_reason=choice.finish_reason,
            raw=response,
        )

    @property
    def provider_name(self) -> str:
        return "openai"
