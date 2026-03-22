"""
Structured logger for Agent Runtime.
All steps are traceable — this is your observability layer.
"""

import logging
import sys
from typing import Any, Dict


class StructuredLogger:
    def __init__(self, name: str, level: str = "INFO"):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))

        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%H:%M:%S"
            ))
            self.logger.addHandler(handler)
            self.logger.propagate = False

    def _fmt(self, msg: str, **kwargs) -> str:
        if kwargs:
            kv = "  ".join(f"{k}={str(v)[:300]}" for k, v in kwargs.items())
            return f"{msg}  {kv}"
        return msg

    def info(self, msg: str, **kwargs):
        self.logger.info(self._fmt(msg, **kwargs))

    def debug(self, msg: str, **kwargs):
        self.logger.debug(self._fmt(msg, **kwargs))

    def warning(self, msg: str, **kwargs):
        self.logger.warning(self._fmt(msg, **kwargs))

    def error(self, msg: str, **kwargs):
        self.logger.error(self._fmt(msg, **kwargs))

    def step(self, step: int, phase: str, data: Dict[str, Any] = None):
        """Log a named agent execution step with structured data."""
        data = data or {}
        self.logger.info(self._fmt(f"[STEP {step:02d}] {phase}", **data))

    def banner(self, msg: str):
        """Print a visual separator for readability."""
        self.logger.info(f"{'─' * 50}")
        self.logger.info(f"  {msg}")
        self.logger.info(f"{'─' * 50}")


def get_logger(name: str, level: str = "INFO") -> StructuredLogger:
    return StructuredLogger(name, level)
