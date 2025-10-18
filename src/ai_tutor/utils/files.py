from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt"}


def iter_documents(directory: Path) -> Iterable[Path]:
    for ext in SUPPORTED_EXTENSIONS:
        yield from directory.rglob(f"*{ext}")


def collect_documents(directory: Path) -> List[Path]:
    return list(iter_documents(directory))
