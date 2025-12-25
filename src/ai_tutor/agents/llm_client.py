from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI

from ai_tutor.config.schema import ModelConfig

logger = logging.getLogger(__name__)


class LLMClient:
    """Minimal helper for issuing chat completions using OpenAI-compatible APIs or Gemini via LiteLLM."""

    def __init__(
        self,
        config: ModelConfig,
        api_key: Optional[str] = None,
        client: Optional[OpenAI] = None,
    ):
        self.config = config
        self.use_gemini = config.name.startswith("gemini/")
        
        if self.use_gemini:
            # For Gemini, always prioritize GEMINI_API_KEY environment variable
            # The api_key parameter might be an OpenAI key, so ignore it for Gemini
            self.gemini_api_key = os.getenv("GEMINI_API_KEY")
            if not self.gemini_api_key:
                logger.warning(
                    "Gemini model specified (%s) but GEMINI_API_KEY not found. "
                    "Falling back to OpenAI.",
                    config.name
                )
                self.use_gemini = False
                key = api_key or os.getenv("OPENAI_API_KEY")
                if not key and client is None:
                    raise RuntimeError("OPENAI_API_KEY must be set or an OpenAI client provided.")
                self.client = client or OpenAI(api_key=key)
            else:
                logger.info("LLMClient using Gemini model via LiteLLM: %s", config.name)
                self.client = None  # Will use LiteLLM instead
        else:
            # For OpenAI models
            key = api_key or os.getenv("OPENAI_API_KEY")
            if not key and client is None:
                raise RuntimeError("OPENAI_API_KEY must be set or an OpenAI client provided.")
            self.client = client or OpenAI(api_key=key)
    def generate(self, messages: List[Dict[str, Any]], **kwargs: Any) -> str:
        if self.use_gemini:
            # Use LiteLLM for Gemini
            try:
                import litellm
                
                # Convert messages format if needed
                litellm_messages = []
                for msg in messages:
                    litellm_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
                
                params = {
                    "model": self.config.name,
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_output_tokens,
                    "api_key": self.gemini_api_key,
                }
                params.update(kwargs)
                
                response = litellm.completion(
                    messages=litellm_messages,
                    **params
                )
                return response.choices[0].message.content or ""
            except ImportError:
                logger.error(
                    "litellm not installed. Install with: pip install litellm. "
                    "Falling back to OpenAI."
                )
                # Fallback to OpenAI if LiteLLM not available
                if not self.client:
                    raise RuntimeError("LiteLLM not available and no OpenAI client configured.")
            except Exception as e:
                logger.error("Error calling Gemini via LiteLLM: %s", e, exc_info=True)
                raise
        
        # Use OpenAI for non-Gemini models
        params = {
            "model": self.config.name,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_output_tokens,
        }
        params.update(kwargs)
        response = self.client.chat.completions.create(messages=messages, **params)
        choice = response.choices[0]
        return choice.message.content or ""
