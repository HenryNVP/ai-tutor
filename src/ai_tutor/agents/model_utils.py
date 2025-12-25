"""Shared utilities for creating agent models (Gemini via LiteLLM)."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


def create_gemini_model(
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    agent_name: str = "Agent",
) -> Union[str, Any]:
    """
    Create model for agents (Gemini via LiteLLM or default).
    
    If model_name starts with 'gemini/', uses LiteLLM with Gemini.
    Otherwise, returns the model name string for default OpenAI model.
    
    Parameters
    ----------
    model_name : Optional[str]
        Model identifier. For Gemini via LiteLLM, use 'gemini/gemini-2.0-flash' (recommended)
        or 'gemini/gemini-1.5-pro'. If None, uses default 'gpt-4o-mini'.
    api_key : Optional[str]
        API key for the model. If None, reads from environment variables.
    agent_name : str
        Name of the agent (for logging purposes).
        
    Returns
    -------
    Union[str, Any]
        Model name string (for OpenAI) or LitellmModel instance (for Gemini).
    """
    if not model_name:
        return "gpt-4o-mini"
    
    # Check if using Gemini via LiteLLM
    if model_name.startswith("gemini/"):
        try:
            from agents.extensions.models.litellm_model import LitellmModel
            
            # Get API key from parameter or environment
            gemini_api_key = api_key or os.getenv("GEMINI_API_KEY")
            if not gemini_api_key:
                logger.warning(
                    "[%s] Gemini model specified but GEMINI_API_KEY not found. "
                    "Falling back to default model.",
                    agent_name
                )
                return "gpt-4o-mini"
            
            logger.info(
                "[%s] Using Gemini model via LiteLLM: %s",
                agent_name,
                model_name
            )
            return LitellmModel(model=model_name, api_key=gemini_api_key)
        except ImportError:
            logger.warning(
                "[%s] litellm not installed. Install with: pip install 'openai-agents[litellm]'. "
                "Falling back to default model.",
                agent_name
            )
            return "gpt-4o-mini"
        except Exception as e:
            logger.error(
                "[%s] Error creating LiteLLM model: %s. Falling back to default model.",
                agent_name,
                e
            )
            return "gpt-4o-mini"
    
    # Default: return model name string (for OpenAI)
    return model_name

