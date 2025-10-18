"""
Personal STEM Instructor package.

This package provides ingestion, retrieval, learning plan generation, assessments,
and guardrailed tutoring flows for high-school-to-precollege STEM subjects.
"""

from importlib import resources

from .config.loader import load_settings

__all__ = ["load_settings", "resources"]
