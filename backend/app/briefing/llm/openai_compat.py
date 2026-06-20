"""OpenAI-compatible backend (works with GLM / DeepSeek / OpenAI / Ollama)."""
from __future__ import annotations

import logging

from openai import OpenAI

from .base import LLMError

log = logging.getLogger(__name__)


class OpenAICompatBackend:
    """Thin wrapper around the openai SDK pointing at any compatible endpoint."""

    def __init__(self, api_key: str, base_url: str, model: str, temperature: float = 0.6):
        self.model = model
        self.temperature = temperature
        self._api_key = api_key
        self._base_url = base_url
        self._client = OpenAI(api_key=api_key or "EMPTY", base_url=base_url) if base_url else None

    @property
    def is_configured(self) -> bool:
        return bool(self._client and self._api_key and self.model)

    def chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        if not self.is_configured:
            raise LLMError(
                "LLM not configured. Set LLM_API_KEY, LLM_BASE_URL, LLM_MODEL in .env."
            )
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=self.temperature,
                max_tokens=max_tokens,
            )
            content = resp.choices[0].message.content
            return (content or "").strip()
        except Exception as exc:  # noqa: BLE001 - surface any provider error uniformly
            raise LLMError(f"LLM call failed: {exc}") from exc
