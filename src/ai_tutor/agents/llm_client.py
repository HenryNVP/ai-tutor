from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from ai_tutor.config.schema import ModelConfig

logger = logging.getLogger(__name__)


class LLMClient:
    """Lightweight wrapper around the OpenAI Python SDK for chat completion calls."""

    def __init__(self, config: ModelConfig, api_key: Optional[str] = None):
        """Store configuration and defer client construction until the first request."""
        self.config = config
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._client = None

    def _ensure_client(self):
        """Import and cache the OpenAI client so subsequent calls can reuse it."""
        if self._client is not None:
            return
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY must be set to use the OpenAI chat completions API."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "openai package is required for LLM access. Install it with `pip install openai`."
            ) from exc
        self._client = OpenAI(api_key=self.api_key)

    def generate(self, messages: List[Dict[str, Any]], **kwargs: Any) -> str:
        """
        Execute a chat completion request with the configured OpenAI model and return the content.

        Lazily ensures the client is ready, merges default parameters from the project configuration,
        forwards the request to `chat.completions.create`, and returns the assistant message content.
        """
        self._ensure_client()
        params = {
            "model": self.config.name,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_output_tokens,
        }
        params.update(kwargs)
        logger.debug("Calling OpenAI model %s", self.config.name)
        try:
            response = self._client.chat.completions.create(messages=messages, **params)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"OpenAI chat completion failed: {exc}") from exc
        choice = response.choices[0]
        message = getattr(choice, "message", None)
        if isinstance(message, dict):
            content = message.get("content")
        else:
            content = getattr(message, "content", None)
        if content:
            return content
        return str(response)
