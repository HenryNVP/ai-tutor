from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

import yaml
from pydantic import ValidationError

from .schema import Settings

DEFAULT_CONFIG_PATH = Path("config/default.yaml")


def read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            result[key] = merge_dicts(base[key], value)
        else:
            result[key] = value
    return result


def load_settings(config_path: str | Path | None = None) -> Settings:
    """Load settings from YAML, with optional overrides from env var JSON blobs."""

    config_file = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    data = read_yaml(config_file)

    overrides_env = os.getenv("AI_TUTOR_CONFIG_OVERRIDES")
    if overrides_env:
        try:
            overrides = json.loads(overrides_env)
        except json.JSONDecodeError as err:
            raise ValueError(
                "Failed to parse AI_TUTOR_CONFIG_OVERRIDES env var as JSON."
            ) from err
        data = merge_dicts(data, overrides)

    try:
        settings = Settings.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"Invalid configuration: {exc}") from exc

    return settings
