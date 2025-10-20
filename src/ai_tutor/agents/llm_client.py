from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from openai import OpenAI

from ai_tutor.config.schema import ModelConfig


class LLMClient:
    """Minimal helper for issuing chat completions."""

    def __init__(self, config: ModelConfig, api_key: Optional[str] = None, client: Optional[OpenAI] = None):
        self.config = config
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key and client is None:
            raise RuntimeError("OPENAI_API_KEY must be set or an OpenAI client provided.")
        self.client = client or OpenAI(api_key=key)

    def generate(self, messages: List[Dict[str, Any]], **kwargs: Any) -> str:
        params = {
            "model": self.config.name,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_output_tokens,
        }
        params.update(kwargs)
        response = self.client.chat.completions.create(messages=messages, **params)
        return response.choices[0].message.content or ""
