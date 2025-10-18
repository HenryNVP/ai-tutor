from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ai_tutor.agents.tutor import TutorAgent, TutorResponse
from ai_tutor.config import Settings, load_settings
from ai_tutor.guardrails import GuardrailManager
from ai_tutor.ingestion import IngestionPipeline
from ai_tutor.ingestion.embeddings import EmbeddingClient
from ai_tutor.learning import (
    Assessment,
    AssessmentGenerator,
    CoursePlan,
    CoursePlanner,
    LearnerProfile,
    ProgressTracker,
    generate_feedback,
)
from ai_tutor.learning.lessons import create_daily_plan, create_weekly_schedule
from ai_tutor.retrieval import create_vector_store
from ai_tutor.search import SearchTool
from ai_tutor.storage import ChunkJsonlStore
from ai_tutor.utils.files import collect_documents
from ai_tutor.utils.logging import configure_logging

from .agents.llm_client import LLMClient

logger = logging.getLogger(__name__)


class TutorSystem:
    def __init__(self, settings: Settings, api_key: Optional[str] = None):
        self.settings = settings
        configure_logging(settings.logging.level, settings.logging.json)

        self.embedder = EmbeddingClient(settings.embeddings)
        self.vector_store = create_vector_store(settings.paths.vector_store_dir)
        self.chunk_store = ChunkJsonlStore(settings.paths.chunks_index)
        self.guardrails = GuardrailManager(
            guardrail_config=settings.guardrails,
            search_config=settings.search_tool,
        )
        self.search_tool = SearchTool()
        self.llm_client = LLMClient(settings.model, api_key=api_key)

        self.ingestion_pipeline = IngestionPipeline(
            settings=settings,
            embedder=self.embedder,
            vector_store=self.vector_store,
            chunk_store=self.chunk_store,
        )
        self.tutor_agent = TutorAgent(
            settings=settings,
            embedder=self.embedder,
            vector_store=self.vector_store,
            guardrails=self.guardrails,
            search_tool=self.search_tool,
            llm_client=self.llm_client,
        )
        self.course_planner = CoursePlanner(defaults=settings.course_defaults)
        learners_dir = settings.paths.processed_data_dir / "learners"
        self.progress_tracker = ProgressTracker(learners_dir)
        self.assessment_generator = AssessmentGenerator()

    @classmethod
    def from_config(cls, config_path: str | Path | None = None, api_key: Optional[str] = None) -> "TutorSystem":
        settings = load_settings(config_path)
        settings.paths.processed_data_dir.mkdir(parents=True, exist_ok=True)
        settings.paths.raw_data_dir.mkdir(parents=True, exist_ok=True)
        settings.paths.logs_dir.mkdir(parents=True, exist_ok=True)
        return cls(settings, api_key=api_key)

    def ingest_directory(self, directory: Path):
        documents = collect_documents(directory)
        logger.info("Found %s documents to ingest.", len(documents))
        result = self.ingestion_pipeline.ingest_paths(documents)
        return result

    def load_profile(self, learner_id: str, name: Optional[str] = None) -> LearnerProfile:
        return self.progress_tracker.load_profile(learner_id, name=name or learner_id)

    def answer_question(
        self,
        learner_id: str,
        question: str,
        mode: str = "learning",
        name: Optional[str] = None,
    ) -> TutorResponse:
        profile = self.load_profile(learner_id, name=name)
        response = self.tutor_agent.answer(question, mode=mode)
        # Record time-on-task heuristic: assume 5 minutes per question
        self.progress_tracker.update_time_on_task(profile, minutes=5)
        self.progress_tracker.save_profile(profile)
        return response

    def plan_course(
        self,
        learner_id: str,
        domain: str,
        weeks: Optional[int] = None,
        lessons_per_week: Optional[int] = None,
        name: Optional[str] = None,
    ) -> CoursePlan:
        profile = self.load_profile(learner_id, name=name)
        plan = self.course_planner.plan_course(
            domain=domain,
            learner=profile,
            weeks=weeks,
            lessons_per_week=lessons_per_week,
        )
        return plan

    def generate_assessment(self, course_plan: CoursePlan, unit_index: int) -> Assessment:
        return self.assessment_generator.generate_unit_assessment(course_plan, unit_index)

    def build_week_schedule(self, course_plan: CoursePlan, lessons_per_week: int | None = None):
        return create_weekly_schedule(course_plan, lessons_per_week=lessons_per_week)

    def build_daily_plan(self, lesson_index: int, course_plan: CoursePlan):
        all_lessons = [lesson for unit in course_plan.units for lesson in unit.lessons]
        if lesson_index < 0 or lesson_index >= len(all_lessons):
            raise IndexError("Lesson index out of range.")
        lesson = all_lessons[lesson_index]
        return create_daily_plan(lesson)

    def record_assessment_attempt(
        self,
        learner_id: str,
        assessment: Assessment,
        score: float,
        responses: dict[str, str],
        concepts: dict[str, float] | None = None,
    ) -> LearnerProfile:
        profile = self.load_profile(learner_id)
        updated = self.progress_tracker.record_attempt(
            profile,
            assessment_title=assessment.title,
            score=score,
            responses=responses,
            concepts=concepts,
        )
        self.progress_tracker.save_profile(updated)
        return updated

    def get_feedback(self, learner_id: str) -> dict[str, list[str]]:
        profile = self.load_profile(learner_id)
        return generate_feedback(profile)
