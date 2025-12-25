"""Shared utilities for creating agent models (Gemini via LiteLLM)."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional, Union, Tuple

logger = logging.getLogger(__name__)


def create_gemini_model(
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    agent_name: str = "Agent",
) -> Tuple[Union[str, Any], Optional[Any]]:
    """
    Create model for agents (Gemini via LiteLLM or default) with usage tracking.
    
    If model_name starts with 'gemini/', uses LiteLLM with Gemini and returns ModelSettings
    for usage tracking. Otherwise, returns the model name string for default OpenAI model.
    
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
    Tuple[Union[str, Any], Optional[ModelSettings]]
        Tuple of (model, model_settings):
        - model: Model name string (for OpenAI) or LitellmModel instance (for Gemini)
        - model_settings: ModelSettings(include_usage=True) for LiteLLM models, None for OpenAI
    """
    if not model_name:
        return ("gpt-4o-mini", None)
    
    # Check if using Gemini via LiteLLM
    if model_name.startswith("gemini/"):
        try:
            from agents.extensions.models.litellm_model import LitellmModel
            from agents import ModelSettings
            
            # Get API key from parameter or environment
            gemini_api_key = api_key or os.getenv("GEMINI_API_KEY")
            if not gemini_api_key:
                logger.warning(
                    "[%s] Gemini model specified but GEMINI_API_KEY not found. "
                    "Falling back to default model.",
                    agent_name
                )
                return ("gpt-4o-mini", None)
            
            logger.info(
                "[%s] Using Gemini model via LiteLLM: %s (with usage tracking)",
                agent_name,
                model_name
            )
            model = LitellmModel(model=model_name, api_key=gemini_api_key)
            model_settings = ModelSettings(include_usage=True)
            return (model, model_settings)
        except ImportError:
            logger.warning(
                "[%s] litellm not installed. Install with: pip install 'openai-agents[litellm]'. "
                "Falling back to default model.",
                agent_name
            )
            return ("gpt-4o-mini", None)
        except Exception as e:
            logger.error(
                "[%s] Error creating LiteLLM model: %s. Falling back to default model.",
                agent_name,
                e
            )
            return ("gpt-4o-mini", None)
    
    # Default: return model name string (for OpenAI) with no model_settings
    return (model_name, None)

