"""
Retry wrapper for LLM providers.

Production LLM calls fail. Rate limits, transient errors, timeouts.
This wrapper adds exponential backoff with jitter so agents
keep running instead of crashing on the first hiccup.

Usage:
  from runtime.llm.retry import RetryLLM
  from runtime.llm.anthropic_provider import AnthropicLLM

  base_llm = AnthropicLLM(api_key=key)
  llm = RetryLLM(base_llm, max_retries=3)
  # drop-in replacement — same interface
"""

import time
import random
from typing import Dict, List, Optional

from runtime.llm.base import BaseLLM, LLMResponse, ToolDefinition
from runtime.logger import get_logger


class RetryLLM(BaseLLM):
    """
    Wraps any BaseLLM with exponential backoff retry logic.

    Retries on:
      - Rate limit errors (429)
      - Server errors (500, 502, 503)
      - Transient connection errors
      - Timeout errors

    Does NOT retry on:
      - Authentication errors (401) — fix your key
      - Invalid request errors (400) — fix your prompt
    """

    # Error strings that indicate a retryable condition
    RETRYABLE_SIGNALS = [
        "rate_limit", "rate limit", "429", "overloaded",
        "529", "503", "502", "500", "timeout", "connection",
        "temporarily", "retry", "too many requests",
    ]

    # Error strings that indicate a non-retryable failure
    FATAL_SIGNALS = [
        "401", "403", "authentication", "invalid_api_key",
        "permission", "invalid_request_error",
    ]

    def __init__(
        self,
        llm: BaseLLM,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter: bool = True,
    ):
        self.llm = llm
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.logger = get_logger("retry_llm")

    def _is_retryable(self, error: Exception) -> bool:
        msg = str(error).lower()
        if any(s in msg for s in self.FATAL_SIGNALS):
            return False
        return any(s in msg for s in self.RETRYABLE_SIGNALS)

    def _delay(self, attempt: int) -> float:
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        if self.jitter:
            delay *= (0.5 + random.random() * 0.5)
        return delay

    def complete(
        self,
        messages: List[Dict],
        system: str,
        tools: Optional[List[ToolDefinition]] = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                return self.llm.complete(
                    messages=messages,
                    system=system,
                    tools=tools,
                    max_tokens=max_tokens,
                )
            except Exception as e:
                last_error = e

                if attempt == self.max_retries:
                    break

                if not self._is_retryable(e):
                    self.logger.error("non_retryable_error", error=str(e)[:200])
                    raise

                delay = self._delay(attempt)
                self.logger.warning(
                    "retrying",
                    attempt=attempt + 1,
                    max=self.max_retries,
                    delay=f"{delay:.1f}s",
                    error=str(e)[:100],
                )
                time.sleep(delay)

        self.logger.error("all_retries_exhausted", attempts=self.max_retries + 1)
        raise last_error

    @property
    def provider_name(self) -> str:
        return f"retry({self.llm.provider_name})"
