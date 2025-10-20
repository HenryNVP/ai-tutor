from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from agents import Agent, function_tool


def build_ingestion_agent(ingest_fn: Callable[[Path], object]) -> Agent:
    """Create an agent that exposes the corpus ingestion tool."""

    @function_tool
    def ingest_corpus(directory: str) -> str:
        path = Path(directory)
        if not path.exists() or not path.is_dir():
            return json.dumps({"error": f"The provided directory {directory} does not exist."})
        result = ingest_fn(path)
        payload = {
            "documents_ingested": len(result.documents),
            "chunks_created": len(result.chunks),
            "skipped_files": [str(item) for item in result.skipped],
        }
        return json.dumps(payload)

    return Agent(
        name="ingestion_agent",
        instructions=(
            "You ingest new learner materials. Use the ingest_corpus tool to process directories. "
            "Always summarize the ingestion result briefly after calling the tool."
        ),
        tools=[ingest_corpus],
    )
