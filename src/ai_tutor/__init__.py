"""
Personal STEM Instructor (MVP).

This package bundles a minimal ingestion + retrieval stack with Gemini-powered
LLM responses and optional OpenAI Agents orchestration.
"""

from importlib import resources

from .config.loader import load_settings

__all__ = ["load_settings", "resources"]
