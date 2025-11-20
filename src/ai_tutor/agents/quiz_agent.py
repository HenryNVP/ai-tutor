from __future__ import annotations
import logging
from typing import Callable, List, Optional

from agents import Agent, function_tool

from ai_tutor.learning.models import LearnerProfile
from ai_tutor.learning.quiz import QuizService

logger = logging.getLogger(__name__)


def build_quiz_agent(
    quiz_service: QuizService,
    state,
    get_profile: Callable[[], Optional[LearnerProfile]],
    get_extra_context: Callable[[], Optional[str]],
    get_source_filter: Callable[[], Optional[List[str]]],
    get_documents_only: Callable[[], bool],
) -> Agent:
    """Create an agent that owns quiz generation responsibilities."""

    _quiz_cache: dict[str, str] = {}

    @function_tool
    def generate_quiz(topic: str, count: int = 4, difficulty: str | None = None) -> str:
        cache_key = f"{topic.lower().strip()}:{count}:{difficulty or 'auto'}"
        if cache_key in _quiz_cache:
            logger.info("[Quiz Agent] Returning cached quiz message for '%s'", topic)
            return _quiz_cache[cache_key]

        try:
            question_count = int(count)
        except (TypeError, ValueError):
            question_count = 4
        question_count = max(3, min(question_count, 40))

        profile = get_profile()
        extra_context = get_extra_context()
        source_filter = get_source_filter()
        documents_only = get_documents_only()

        logger.info(
            "[Quiz Agent] Generating quiz: topic='%s', count=%s, difficulty=%s",
            topic,
            question_count,
            difficulty,
        )
        quiz = quiz_service.generate_quiz(
            topic=topic,
            profile=profile,
            num_questions=question_count,
            difficulty=difficulty,
            extra_context=extra_context,
            source_filter=source_filter,
            documents_only=documents_only,
        )
        state.last_quiz = quiz
        state.last_source = "quiz"

        message = (
            f"Prepared a {len(quiz.questions)}-question quiz on {quiz.topic}. "
            "Invite the learner to take it."
        )
        _quiz_cache[cache_key] = message
        return message

    instructions = (
        "You specialize in quiz generation.\n"
        "- Read the routing metadata to determine the topic and number of questions.\n"
        "- Call generate_quiz EXACTLY ONCE per request.\n"
        "- After the tool call succeeds, briefly summarize what was generated.\n"
        "- Do not answer academic questions — only prepare quizzes.\n"
    )

    return Agent(
        name="quiz_agent",
        model="gpt-4o-mini",
        instructions=instructions,
        tools=[generate_quiz],
    )

