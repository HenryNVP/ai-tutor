"""Legacy entry point for Streamlit UI."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # pragma: no cover - environment glue
    sys.path.insert(0, str(ROOT))

import apps.ui

if __name__ == "__main__":  # pragma: no cover - CLI entry
    apps.ui.render()
