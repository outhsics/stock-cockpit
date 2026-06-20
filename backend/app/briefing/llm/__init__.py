"""LLM abstraction layer.

A single factory returns a backend that speaks the OpenAI Chat Completions
protocol. Default points at Z.ai / GLM (open.bigmodel.cn). Swap by setting
LLM_PROVIDER / LLM_BASE_URL / LLM_MODEL in .env.

Supported providers via the same OpenAI-compatible client:
  glm       -> https://open.bigmodel.cn/api/paas/v4   (default)
  deepseek  -> https://api.deepseek.com
  openai    -> https://api.openai.com/v1
  ollama    -> http://localhost:11434/v1               (local, no key)
  custom    -> whatever LLM_BASE_URL you set
"""
from __future__ import annotations

import logging

from ...config import settings
from .base import LLMBackend, LLMError
from .openai_compat import OpenAICompatBackend

log = logging.getLogger(__name__)


# Sensible defaults per provider; user can override any via env.
_PROVIDER_PRESETS = {
    "glm": {"base_url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4-flash"},
    "deepseek": {"base_url": "https://api.deepseek.com", "model": "deepseek-chat"},
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    "ollama": {"base_url": "http://localhost:11434/v1", "model": "qwen2.5:7b"},
}


def get_llm() -> LLMBackend:
    """Return a configured LLM backend instance."""
    provider = settings.llm_provider.lower()
    preset = _PROVIDER_PRESETS.get(provider, {})
    base_url = settings.llm_base_url or preset.get("base_url", "")
    model = settings.llm_model or preset.get("model", "")

    # GLM requires the key in the Authorization header as a bearer token;
    # the openai client sends `Authorization: Bearer <key>`, so we pass it as api_key.
    api_key = settings.llm_api_key or ("ollama" if provider == "ollama" else "")

    if not api_key and provider != "ollama":
        log.warning(
            "LLM_API_KEY not set — AI briefing will return a stub. "
            "Set LLM_API_KEY in .env (e.g. a Z.ai key from open.bigmodel.cn)."
        )

    return OpenAICompatBackend(
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=settings.llm_temperature,
    )


__all__ = ["get_llm", "LLMBackend", "LLMError"]
