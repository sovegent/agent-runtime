"""
Provider-agnostic LLM interface.
Swap between Anthropic and OpenAI without changing agent code.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolCall:
    """A single tool invocation requested by the LLM."""
    tool_name: str
    tool_input: Dict[str, Any]
    tool_use_id: str = ""


@dataclass
class LLMResponse:
    """Normalized response from any LLM provider."""
    content: str                              # Text content (may be empty if tool_calls present)
    tool_calls: List[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"
    raw: Any = None                           # Raw provider response, available if needed

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


@dataclass
class ToolDefinition:
    """Schema definition for a tool, passed to the LLM."""
    name: str
    description: str
    input_schema: Dict[str, Any]


class BaseLLM(ABC):
    """Abstract LLM provider. Implement for Anthropic, OpenAI, Ollama, etc."""

    @abstractmethod
    def complete(
        self,
        messages: List[Dict],
        system: str,
        tools: Optional[List[ToolDefinition]] = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """
        Send messages to the LLM and return a normalized response.

        Args:
            messages: Conversation history in [{role, content}] format
            system: System prompt defining agent behavior
            tools: Optional list of tool definitions for tool use
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with content and/or tool_calls
        """
        pass

    @property
    def provider_name(self) -> str:
        return type(self).__name__
