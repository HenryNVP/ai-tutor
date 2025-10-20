from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

from ai_tutor.agents.tutor import TutorAgent, TutorResponse
from ai_tutor.config import Settings, load_settings
from ai_tutor.ingestion import IngestionPipeline
from ai_tutor.ingestion.embeddings import EmbeddingClient
from ai_tutor.learning import PersonalizationManager, ProgressTracker
from ai_tutor.retrieval import create_vector_store
from ai_tutor.search.tool import SearchTool
from ai_tutor.storage import ChunkJsonlStore
from ai_tutor.utils.files import collect_documents
from ai_tutor.utils.logging import configure_logging

logger = logging.getLogger(__name__)


class TutorSystem:
    """Facade that wires ingestion, retrieval, and generation components for the tutor."""

    def __init__(self, settings: Settings, api_key: Optional[str] = None):
        """Initialize the system with shared infrastructure and lazy clients."""
        self.settings = settings
        configure_logging(settings.logging.level, settings.logging.use_json)

        self.embedder = EmbeddingClient(settings.embeddings, api_key=api_key)
        self.vector_store = create_vector_store(settings.paths.vector_store_dir)
        self.chunk_store = ChunkJsonlStore(settings.paths.chunks_index)
        self.progress_tracker = ProgressTracker(settings.paths.profiles_dir)
        self.personalizer = PersonalizationManager(self.progress_tracker)
        self.search_tool = SearchTool(model=settings.model.name)

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
            search_tool=self.search_tool,
            ingest_directory=self.ingest_directory,
        )

    @classmethod
    def from_config(cls, config_path: str | Path | None = None, api_key: Optional[str] = None) -> "TutorSystem":
        """Load configuration, ensure project directories exist, and build a ready TutorSystem."""
        settings = load_settings(config_path)
        settings.paths.processed_data_dir.mkdir(parents=True, exist_ok=True)
        settings.paths.raw_data_dir.mkdir(parents=True, exist_ok=True)
        settings.paths.logs_dir.mkdir(parents=True, exist_ok=True)
        settings.paths.profiles_dir.mkdir(parents=True, exist_ok=True)
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
        on_delta: Optional[Callable[[str], None]] = None,
    ) -> TutorResponse:
        """
        Generate a grounded answer for a learner by delegating to the TutorAgent.

        Loads learner memory, selects a prompting style via the personalization manager, streams
        the response if requested, and persists the updated learner profile so future sessions
        continue seamlessly. Returns the structured response including personalization hints.
        """
        profile = self.personalizer.load_profile(learner_id)
        style_hint = self.personalizer.select_style(profile, None)

        response = self.tutor_agent.answer(
            learner_id=learner_id,
            question=question,
            mode=mode,
            style_hint=style_hint,
            on_delta=on_delta,
        )
        domain = self.personalizer.infer_domain(response.hits)
        personalization = self.personalizer.record_interaction(
            profile=profile,
            question=question,
            answer=response.answer,
            domain=domain,
            citations=response.citations,
        )
        self.personalizer.save_profile(profile)
        response.next_topic = personalization.get("next_topic")
        response.difficulty = personalization.get("difficulty")
        return response
