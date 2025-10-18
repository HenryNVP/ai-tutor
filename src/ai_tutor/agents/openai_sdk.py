from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from agents import Agent, Runner, function_tool, set_tracing_disabled
from agents.extensions.models.litellm_model import LitellmModel

from ai_tutor.learning.models import CoursePlan, LessonPlan
from ai_tutor.system import TutorSystem


def _serialize_lesson(lesson: LessonPlan) -> Dict[str, Any]:
    return {
        "title": lesson.title,
        "objectives": [objective.description for objective in lesson.objectives],
        "resources": lesson.resources,
        "practice": lesson.practice,
        "worked_examples": lesson.worked_examples,
    }


def _serialize_course_plan(course_plan: CoursePlan) -> Dict[str, Any]:
    return {
        "course_title": course_plan.course_title,
        "duration_weeks": course_plan.duration_weeks,
        "units": [
            {
                "title": unit.title,
                "focus_topics": unit.focus_topics,
                "lessons": [_serialize_lesson(lesson) for lesson in unit.lessons],
            }
            for unit in course_plan.units
        ],
    }


class TutorOpenAIAgent:
    """Adapter wrapping TutorSystem with the OpenAI Agents SDK."""

    def __init__(
        self,
        tutor_system: TutorSystem,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.tutor_system = tutor_system
        self.model_name = model_name or tutor_system.settings.model.name
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("An API key must be provided via argument or environment variable.")

        set_tracing_disabled(disabled=True)
        self.tools = self._build_tools()
        self.agent = Agent(
            name="PersonalSTEMInstructor",
            instructions=(
                "You are a personal STEM instructor for high-school-to-precollege learners. "
                "Use the provided tools to ingest learner materials, retrieve grounded context, "
                "plan courses, generate assessments, and deliver feedback. "
                "Always cite evidence when answering questions and avoid fabricating information."
            ),
            model=LitellmModel(model=self.model_name, api_key=self.api_key),
            tools=self.tools,
        )

    def _build_tools(self):
        tutor = self.tutor_system

        @function_tool
        def ingest_corpus(directory: str) -> str:
            path = Path(directory)
            if not path.exists() or not path.is_dir():
                return f"The provided directory {directory} does not exist."
            result = tutor.ingest_directory(path)
            payload = {
                "documents_ingested": len(result.documents),
                "chunks_created": len(result.chunks),
                "skipped_files": [str(item) for item in result.skipped],
            }
            return json.dumps(payload)

        @function_tool
        def answer_question(learner_id: str, question: str, mode: str = "learning") -> str:
            response = tutor.answer_question(learner_id=learner_id, question=question, mode=mode)
            payload = {
                "answer": response.answer,
                "citations": response.citations,
                "guardrail_reason": response.guardrail_reason,
                "used_search": response.used_search,
                "search_results": [
                    {
                        "title": result.title,
                        "snippet": result.snippet,
                        "url": result.url,
                        "published_at": result.published_at,
                    }
                    for result in response.search_results or []
                ],
            }
            return json.dumps(payload)

        @function_tool
        def plan_course(
            learner_id: str,
            domain: str,
            weeks: Optional[int] = None,
            lessons_per_week: Optional[int] = None,
        ) -> str:
            course_plan = tutor.plan_course(
                learner_id=learner_id,
                domain=domain,
                weeks=weeks,
                lessons_per_week=lessons_per_week,
            )
            return json.dumps(_serialize_course_plan(course_plan))

        @function_tool
        def build_week_schedule(
            learner_id: str,
            domain: str,
            week: int = 1,
        ) -> str:
            course_plan = tutor.plan_course(learner_id=learner_id, domain=domain)
            schedule = tutor.build_week_schedule(course_plan)
            lessons = schedule.get(week, [])
            payload = {
                "week": week,
                "lessons": [_serialize_lesson(lesson) for lesson in lessons],
            }
            return json.dumps(payload)

        @function_tool
        def generate_assessment(
            learner_id: str,
            domain: str,
            unit_index: int = 0,
        ) -> str:
            course_plan = tutor.plan_course(learner_id=learner_id, domain=domain)
            assessment = tutor.generate_assessment(course_plan, unit_index)
            payload = {
                "title": assessment.title,
                "items": [
                    {
                        "question": item.question,
                        "answer": item.answer,
                        "choices": item.choices,
                        "rationale": item.rationale,
                    }
                    for item in assessment.items
                ],
            }
            return json.dumps(payload)

        @function_tool
        def save_assessment_result(
            learner_id: str,
            domain: str,
            unit_index: int,
            score: float,
            responses: Optional[Dict[str, str]] = None,
            concepts: Optional[Dict[str, float]] = None,
        ) -> str:
            course_plan = tutor.plan_course(learner_id=learner_id, domain=domain)
            assessment = tutor.generate_assessment(course_plan, unit_index)
            profile = tutor.record_assessment_attempt(
                learner_id=learner_id,
                assessment=assessment,
                score=score,
                responses=responses or {},
                concepts=concepts,
            )
            payload = {
                "recent_attempts": [
                    {
                        "assessment_title": attempt.assessment_title,
                        "timestamp": attempt.timestamp.isoformat(),
                        "score": attempt.score,
                    }
                    for attempt in profile.attempts[-3:]
                ]
            }
            return json.dumps(payload)

        @function_tool
        def learner_feedback(learner_id: str) -> str:
            feedback = tutor.get_feedback(learner_id)
            return json.dumps(feedback)

        return [
            ingest_corpus,
            answer_question,
            plan_course,
            build_week_schedule,
            generate_assessment,
            save_assessment_result,
            learner_feedback,
        ]

    async def arun(self, task: str, learner_id: Optional[str] = None) -> Any:
        prompt = task
        if learner_id:
            prompt = f"Learner ID: {learner_id}\nTask: {task}"
        return await Runner.run(self.agent, prompt)

    def run(self, task: str, learner_id: Optional[str] = None) -> Any:
        return asyncio.run(self.arun(task, learner_id=learner_id))
