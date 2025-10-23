from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, List, Optional

from ai_tutor.agents.llm_client import LLMClient
from ai_tutor.agents.tutor import TutorAgent, TutorResponse
from ai_tutor.config import Settings, load_settings
from ai_tutor.ingestion import IngestionPipeline
from ai_tutor.ingestion.embeddings import EmbeddingClient
from ai_tutor.learning import PersonalizationManager, ProgressTracker, QuizService
from ai_tutor.learning.quiz import Quiz, QuizEvaluation
from ai_tutor.retrieval import create_vector_store
from ai_tutor.retrieval.retriever import Retriever
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
        self.llm_client = LLMClient(settings.model, api_key=api_key)
        self.search_tool = SearchTool(model=settings.model.name, api_key=api_key)
        quiz_retriever = Retriever(settings.retrieval, embedder=self.embedder, vector_store=self.vector_store)
        self.quiz_service = QuizService(
            retriever=quiz_retriever,
            llm_client=self.llm_client,
            progress_tracker=self.progress_tracker,
        )

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
            session_db_path=settings.paths.processed_data_dir / "sessions.sqlite",
            quiz_service=self.quiz_service,
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
        extra_context: Optional[str] = None,
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
            profile=profile,
            extra_context=extra_context,
            on_delta=on_delta,
        )
        if response.source != "local":
            return response
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

    def generate_quiz(
        self,
        learner_id: str,
        topic: str,
        num_questions: int = 4,
        extra_context: Optional[str] = None,
    ) -> Quiz:
        """Produce a multiple-choice quiz tailored to the learner and topic."""
        profile = self.personalizer.load_profile(learner_id)
        style = self.personalizer.select_style(profile, None)
        difficulty = self._style_to_difficulty(style)
        quiz = self.tutor_agent.create_quiz(
            topic=topic,
            profile=profile,
            num_questions=num_questions,
            difficulty=difficulty,
            extra_context=extra_context,
        )
        self.personalizer.save_profile(profile)
        return quiz

    def evaluate_quiz(
        self,
        learner_id: str,
        quiz_payload: Quiz | dict,
        answers: List[int],
    ) -> QuizEvaluation:
        """Evaluate a learner's quiz submission, returning detailed feedback."""
        profile = self.personalizer.load_profile(learner_id)
        quiz = quiz_payload if isinstance(quiz_payload, Quiz) else Quiz.model_validate(quiz_payload)
        evaluation = self.tutor_agent.evaluate_quiz(
            quiz=quiz,
            answers=answers,
            profile=profile,
        )
        self.personalizer.save_profile(profile)
        return evaluation

    def clear_conversation_history(self, learner_id: str) -> None:
        """Clear the conversation session history for a learner to prevent token overflow."""
        self.tutor_agent.clear_session(learner_id)
        logger.info(f"Cleared conversation history for learner: {learner_id}")

    @staticmethod
    def _style_to_difficulty(style: str) -> str:
        mapping = {
            "scaffolded": "foundational",
            "stepwise": "guided",
            "concise": "advanced",
        }
        return mapping.get(style, "balanced")
