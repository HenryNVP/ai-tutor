from __future__ import annotations

import json
import logging
from typing import List, Optional, Sequence

from pydantic import BaseModel, Field, ValidationError, validator

from ai_tutor.agents.llm_client import LLMClient
from ai_tutor.data_models import Query, RetrievalHit
from ai_tutor.learning.models import LearnerProfile
from ai_tutor.learning.progress import ProgressTracker
from ai_tutor.retrieval.retriever import Retriever

logger = logging.getLogger(__name__)


class QuizQuestion(BaseModel):
    """Single multiple-choice item."""

    question: str
    choices: List[str]
    correct_index: int = Field(ge=0, le=3)
    explanation: Optional[str] = None
    references: List[str] = Field(default_factory=list)

    @validator("choices")
    def validate_choices(cls, value: List[str]) -> List[str]:
        if len(value) != 4:
            raise ValueError("choices must contain exactly four options")
        return value


class Quiz(BaseModel):
    """Model describing a generated quiz."""

    topic: str
    difficulty: str = "balanced"
    questions: List[QuizQuestion]
    references: List[str] = Field(default_factory=list)

    @validator("questions")
    def validate_questions(cls, value: List[QuizQuestion]) -> List[QuizQuestion]:
        if not value:
            raise ValueError("quiz must include at least one question")
        return value


class QuizAnswerResult(BaseModel):
    """Feedback for a single submitted answer."""

    index: int
    is_correct: bool
    correct_index: int
    selected_index: Optional[int] = None
    explanation: Optional[str] = None
    references: List[str] = Field(default_factory=list)


class QuizEvaluation(BaseModel):
    """Aggregate evaluation of a learner's submission."""

    topic: str
    total_questions: int
    correct_count: int
    score: float
    answers: List[QuizAnswerResult]
    review_topics: List[str] = Field(default_factory=list)


def _format_references(hits: Sequence[RetrievalHit], limit: int = 5) -> List[str]:
    formatted: List[str] = []
    for idx, hit in enumerate(hits[:limit], start=1):
        metadata = hit.chunk.metadata
        page = metadata.page or "N/A"
        formatted.append(
            f"[{idx}] {metadata.title} (Doc: {metadata.doc_id}, Page: {page})"
        )
    return formatted


def _render_hit_context(hits: Sequence[RetrievalHit]) -> str:
    blocks: List[str] = []
    for idx, hit in enumerate(hits, start=1):
        metadata = hit.chunk.metadata
        page = metadata.page or "N/A"
        blocks.append(
            f"[{idx}] Title: {metadata.title} (Doc: {metadata.doc_id}, Page: {page}, Score: {hit.score:.2f})\n"
            f"{hit.chunk.text}"
        )
    return "\n\n".join(blocks)


def _profile_summary(profile: LearnerProfile | None, topic: str) -> str:
    if profile is None:
        return "No prior learner data available."
    strengths = sorted(
        profile.domain_strengths.items(), key=lambda item: item[1], reverse=True
    )[:3]
    struggles = sorted(
        profile.domain_struggles.items(), key=lambda item: item[1], reverse=True
    )[:3]
    segments: List[str] = [f"Learner: {profile.name or profile.learner_id}"]
    if strengths:
        segments.append(
            "Top strengths: "
            + ", ".join(f"{domain} ({score:.2f})" for domain, score in strengths)
        )
    if struggles:
        segments.append(
            "Needs support: "
            + ", ".join(f"{domain} ({score:.2f})" for domain, score in struggles)
        )
    if topic:
        segments.append(f"Requested topic: {topic}")
    return " | ".join(segments)


def _clean_json_payload(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        fence_end = text.find("```", 3)
        if fence_end != -1:
            text = text[3:fence_end].strip()
        if text.startswith("json"):
            text = text[4:].strip()
    return text


class QuizService:
    """Generate and evaluate quizzes grounded in retrieved course materials."""

    def __init__(
        self,
        retriever: Retriever,
        llm_client: LLMClient,
        progress_tracker: ProgressTracker,
    ):
        self.retriever = retriever
        self.llm = llm_client
        self.progress_tracker = progress_tracker

    def generate_quiz(
        self,
        *,
        topic: str,
        profile: LearnerProfile | None,
        num_questions: int = 4,
        difficulty: Optional[str] = None,
        extra_context: Optional[str] = None,
    ) -> Quiz:
        hits = list(self.retriever.retrieve(Query(text=topic)))
        references = _format_references(hits)
        context_sections: List[str] = []
        if hits:
            context_sections.append("Retrieved passages:\n" + _render_hit_context(hits))
        if extra_context:
            context_sections.append("Session context:\n" + extra_context.strip())
        if not context_sections:
            context_sections.append(
                "No local passages found. Base questions on trustworthy STEM knowledge."
            )
        context_block = "\n\n".join(context_sections)

        learner_summary = _profile_summary(profile, topic)
        requested_difficulty = difficulty or "balanced"
        system_message = (
            "You are a STEM tutoring assistant that creates multiple-choice quizzes. "
            "Always respond with strict JSON matching this schema:\n"
            "{\n"
            '  "topic": str,\n'
            '  "difficulty": str,\n'
            '  "questions": [\n'
            "    {\n"
            '      "question": str,\n'
            '      "choices": [str, str, str, str],\n'
            '      "correct_index": int,\n'
            '      "explanation": str,\n'
            '      "references": [str, ...]\n'
            "    }\n"
            "  ],\n"
            '  "references": [str, ...]\n'
            "}\n"
            "Do not wrap the JSON in markdown fences."
        )
        user_message = (
            f"Create a quiz on: {topic}\n"
            f"Number of questions: {num_questions}\n"
            f"Target difficulty: {requested_difficulty}\n"
            f"Learner summary: {learner_summary}\n\n"
            "Guidance:\n"
            "- Cover varied facets of the topic.\n"
            "- Each question must have exactly four answer choices.\n"
            "- Provide the zero-based index of the correct option.\n"
            "- Include a short explanation and cite relevant references when possible.\n"
            "- Prefer the supplied context for grounding.\n\n"
            f"Context:\n{context_block}"
        )
        response = self.llm.generate(
            [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ]
        )
        cleaned = _clean_json_payload(response)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse quiz generation response: %s", cleaned)
            raise ValueError("Quiz generation failed due to invalid JSON output.") from exc

        try:
            quiz = Quiz.model_validate(payload)
        except ValidationError as exc:
            logger.error("Quiz payload validation failed: %s", exc)
            raise ValueError("Quiz generation failed due to invalid quiz structure.") from exc

        if len(quiz.questions) > num_questions:
            quiz.questions = quiz.questions[:num_questions]
        if references and not quiz.references:
            quiz.references = references
        return quiz

    def evaluate_quiz(
        self,
        *,
        quiz: Quiz,
        answers: Sequence[int],
        profile: LearnerProfile | None,
        topic: Optional[str] = None,
    ) -> QuizEvaluation:
        submitted = list(answers)
        if len(submitted) != len(quiz.questions):
            raise ValueError("Answer count must match number of quiz questions.")

        review_topics: List[str] = []
        answer_results: List[QuizAnswerResult] = []
        correct = 0

        for idx, (question, selected) in enumerate(zip(quiz.questions, submitted, strict=False)):
            selected_index = selected if 0 <= selected < len(question.choices) else None
            is_correct = selected_index == question.correct_index
            if is_correct:
                correct += 1
            else:
                review_topics.append(question.question)
            answer_results.append(
                QuizAnswerResult(
                    index=idx,
                    is_correct=is_correct,
                    correct_index=question.correct_index,
                    selected_index=selected_index,
                    explanation=question.explanation,
                    references=question.references or quiz.references,
                )
            )

        total = len(quiz.questions)
        score = correct / total if total else 0.0

        evaluation = QuizEvaluation(
            topic=topic or quiz.topic,
            total_questions=total,
            correct_count=correct,
            score=score,
            answers=answer_results,
            review_topics=review_topics,
        )

        # Update learner profile based on quiz results
        if profile is not None:
            self._update_profile_from_quiz(profile, quiz, evaluation)

        return evaluation

    def _update_profile_from_quiz(
        self,
        profile: LearnerProfile,
        quiz: Quiz,
        evaluation: QuizEvaluation,
    ) -> None:
        """Update learner profile based on quiz evaluation results."""
        # Infer domain from quiz topic (use topic as domain for now)
        domain = quiz.topic.lower()
        
        # Update domain strengths based on score
        # Score range: 0-1, we'll scale the strength delta accordingly
        if evaluation.score >= 0.8:
            # Excellent performance
            strength_delta = 0.15
            struggle_delta = -0.10
        elif evaluation.score >= 0.6:
            # Good performance
            strength_delta = 0.10
            struggle_delta = -0.05
        elif evaluation.score >= 0.4:
            # Moderate performance
            strength_delta = 0.05
            struggle_delta = 0.05
        else:
            # Poor performance - needs more support
            strength_delta = 0.02
            struggle_delta = 0.12
        
        # Apply updates to domain strengths and struggles
        self.progress_tracker.mark_strength(profile, domain, strength_delta)
        self.progress_tracker.mark_struggle(profile, domain, struggle_delta)
        
        # Update concepts mastered based on correct answers
        for answer_result in evaluation.answers:
            if answer_result.is_correct:
                # Extract concept from question (use first few words as concept identifier)
                question_text = quiz.questions[answer_result.index].question
                concept_key = question_text[:50].lower().strip()
                current_mastery = profile.concepts_mastered.get(concept_key, 0.0)
                profile.concepts_mastered[concept_key] = min(1.0, current_mastery + 0.15)
        
        # Update difficulty preference based on performance
        if evaluation.score >= 0.8:
            profile.difficulty_preferences[domain] = "independent challenge"
        elif evaluation.score >= 0.5:
            profile.difficulty_preferences[domain] = "guided practice"
        else:
            profile.difficulty_preferences[domain] = "foundational guidance"
        
        # Estimate time spent (roughly 1-2 minutes per question)
        estimated_minutes = len(quiz.questions) * 1.5
        self.progress_tracker.update_time_on_task(profile, estimated_minutes)
        
        # Set next topic based on review topics if available
        if evaluation.review_topics:
            profile.next_topics[domain] = evaluation.review_topics[0][:50]
        
        logger.info(
            "Updated profile for %s: score=%.2f, domain=%s, strength_delta=%.2f, struggle_delta=%.2f",
            profile.learner_id,
            evaluation.score,
            domain,
            strength_delta,
            struggle_delta,
        )
