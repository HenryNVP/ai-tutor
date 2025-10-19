from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ai_tutor.agents.llm_client import LLMClient
from ai_tutor.agents.tutor import TutorAgent, TutorResponse
from ai_tutor.config import Settings, load_settings
from ai_tutor.ingestion import IngestionPipeline
from ai_tutor.ingestion.embeddings import EmbeddingClient
from ai_tutor.retrieval import create_vector_store
from ai_tutor.storage import ChunkJsonlStore
from ai_tutor.utils.files import collect_documents
from ai_tutor.utils.logging import configure_logging

logger = logging.getLogger(__name__)


class TutorSystem:
    """Facade that wires ingestion, retrieval, and generation components for the tutor."""

    def __init__(self, settings: Settings, api_key: Optional[str] = None):
        """Initialize the system with shared infrastructure and lazy clients."""
        self.settings = settings
        configure_logging(settings.logging.level, settings.logging.json)

        self.embedder = EmbeddingClient(settings.embeddings, api_key=api_key)
        self.vector_store = create_vector_store(settings.paths.vector_store_dir)
        self.chunk_store = ChunkJsonlStore(settings.paths.chunks_index)
        self.llm_client = LLMClient(settings.model, api_key=api_key)

        self.ingestion_pipeline = IngestionPipeline(
            settings=settings,
            embedder=self.embedder,
            vector_store=self.vector_store,
            chunk_store=self.chunk_store,
        )
        self.tutor_agent = TutorAgent(
            retrieval_config=settings.retrieval,
            embedder=self.embedder,
            vector_store=self.vector_store,
            llm_client=self.llm_client,
        )

    @classmethod
    def from_config(cls, config_path: str | Path | None = None, api_key: Optional[str] = None) -> "TutorSystem":
        """Load configuration, ensure project directories exist, and build a ready TutorSystem."""
        settings = load_settings(config_path)
        settings.paths.processed_data_dir.mkdir(parents=True, exist_ok=True)
        settings.paths.raw_data_dir.mkdir(parents=True, exist_ok=True)
        settings.paths.logs_dir.mkdir(parents=True, exist_ok=True)
        return cls(settings, api_key=api_key)

    def ingest_directory(self, directory: Path):
        """
        Ingest every supported document under a directory and persist the resulting chunks.

        Uses `collect_documents` to gather PDFs/Markdown/TXT files, then hands the paths to
        `IngestionPipeline.ingest_paths`, which parses, chunks, embeds, and stores them via
        `ChunkJsonlStore` and `SimpleVectorStore`. Logs a summary before returning the pipeline result.
        """
        documents = collect_documents(directory)
        logger.info("Found %s documents to ingest.", len(documents))
        result = self.ingestion_pipeline.ingest_paths(documents)
        return result

    def answer_question(
        self,
        learner_id: str,
        question: str,
        mode: str = "learning",
    ) -> TutorResponse:
        """
        Generate a grounded answer for a learner by delegating to the TutorAgent.

        Delegates retrieval and prompting to `TutorAgent.answer`, which embeds the query, searches
        the configured `VectorStore`, builds a cited prompt with `build_messages`, and calls the LLM.
        Returns the structured `TutorResponse` containing the answer, supporting hits, and citations.
        """
        response = self.tutor_agent.answer(question, mode=mode)
        return response
