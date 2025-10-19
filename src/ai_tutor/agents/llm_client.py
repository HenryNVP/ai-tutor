from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from ai_tutor.config.schema import ModelConfig

logger = logging.getLogger(__name__)


class LLMClient:
    """Lightweight wrapper around litellm for chat completion calls."""

    def __init__(self, config: ModelConfig, api_key: Optional[str] = None):
        """Store configuration and defer client construction until the first request."""
        self.config = config
       self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
       self._client = None

    def _ensure_client(self):
        """Import and cache the litellm module so subsequent calls can reuse it."""
        if self._client is not None:
            return
        try:
            import litellm
        except ImportError as exc:
            raise RuntimeError("litellm package is required for LLM access.") from exc
        self._client = litellm  # module acts as namespace

    def generate(self, messages: List[Dict[str, Any]], **kwargs: Any) -> str:
        """
        Execute a chat completion request with the configured provider and return the content.

        Lazily ensures the litellm client is ready, merges default parameters from the project
        configuration, and delegates the call to `litellm.completion`. Supports optional overrides
        (temperature, max tokens, etc.) through keyword arguments.
        """
        self._ensure_client()
        params = {
            "model": self.config.name,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_output_tokens,
        }
        params.update(kwargs)
        if self.api_key:
            params["api_key"] = self.api_key
        logger.debug("Calling LLM with model %s", self.config.name)
        response = self._client.completion(  # type: ignore[operator]
            messages=messages, **params
        )
        if hasattr(response, "choices"):
            return response.choices[0].message["content"]
        return str(response)
