"""LLM backend interface."""
from __future__ import annotations

from typing import Protocol


class LLMError(RuntimeError):
    """Raised when the LLM call fails."""


class LLMBackend(Protocol):
    """Minimal chat-completion interface used by the briefing service."""

    model: str

    def chat(self, system: str, user: str, max_tokens: int = 2000) -> str:  # pragma: no cover
        ...

    @property
    def is_configured(self) -> bool:  # pragma: no cover
        ...
