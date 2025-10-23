from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Callable, Dict, List, Optional

from openai.types.responses import ResponseContentPartDoneEvent, ResponseTextDeltaEvent

from agents import Agent, RawResponsesStreamEvent, Runner, function_tool
from agents import SQLiteSession

from .ingestion import build_ingestion_agent
from .qa import build_qa_agent
from .web import build_web_agent

from ai_tutor.config.schema import RetrievalConfig
from ai_tutor.data_models import RetrievalHit
from ai_tutor.ingestion.embeddings import EmbeddingClient
from ai_tutor.learning.models import LearnerProfile
from ai_tutor.learning.quiz import Quiz, QuizService
from ai_tutor.learning.quiz import Quiz, QuizEvaluation, QuizService
from ai_tutor.retrieval.retriever import Retriever
from ai_tutor.retrieval.vector_store import VectorStore
from ai_tutor.search.tool import SearchTool

logger = logging.getLogger(__name__)


@dataclass
class TutorResponse:
    """Structured answer bundle returned to callers, including hits and formatted citations."""

    answer: str
    hits: List[RetrievalHit]
    citations: List[str]
    style: str
    next_topic: Optional[str] = None
    difficulty: Optional[str] = None
    source: Optional[str] = None
    quiz: Optional[Quiz] = None


@dataclass
class AgentState:
    last_hits: List[RetrievalHit] = field(default_factory=list)
    last_citations: List[str] = field(default_factory=list)
    last_source: Optional[str] = None
    last_quiz: Optional[Quiz] = None

    def reset(self) -> None:
        self.last_hits.clear()
        self.last_citations.clear()
        self.last_source = None
        self.last_quiz = None


class TutorAgent:
    """Multi-agent tutoring orchestrator using the OpenAI Agents runtime."""

    MIN_CONFIDENCE = 0.2

    def __init__(
        self,
        retrieval_config: RetrievalConfig,
        embedder: EmbeddingClient,
        vector_store: VectorStore,
        search_tool: SearchTool,
        ingest_directory: Callable[[Path], object],
        session_db_path: Path,
        quiz_service: QuizService,
    ):
        self.retriever = Retriever(retrieval_config, embedder=embedder, vector_store=vector_store)
        self.search_tool = search_tool
        self.ingest_fn = ingest_directory
        self.sessions: Dict[str, SQLiteSession] = {}
        self.state = AgentState()
        self.session_db_path = session_db_path
        self.quiz_service = quiz_service
        self._active_profile: Optional[LearnerProfile] = None
        self._active_extra_context: Optional[str] = None

        self.ingestion_agent: Agent | None = None
        self.qa_agent: Agent | None = None
        self.web_agent: Agent | None = None
        self.orchestrator_agent: Agent | None = None

        self._build_agents()

    def _build_agents(self) -> None:
        """Instantiate guardrail, QA, and web agents."""

        self.ingestion_agent = build_ingestion_agent(self.ingest_fn)
        self.web_agent = build_web_agent(self.search_tool, self.state)
        self.qa_agent = build_qa_agent(self.retriever, self.state, self.MIN_CONFIDENCE, handoffs=[self.web_agent])

        @function_tool
        def generate_quiz(topic: str, count: int = 4, difficulty: str | None = None) -> str:
            try:
                question_count = int(count)
            except (TypeError, ValueError):
                question_count = 4
            question_count = max(3, min(question_count, 8))
            profile = self._active_profile
            quiz = self.quiz_service.generate_quiz(
                topic=topic,
                profile=profile,
                num_questions=question_count,
                difficulty=difficulty,
                extra_context=self._active_extra_context,
            )
            self.state.last_quiz = quiz
            self.state.last_source = "quiz"
            return (
                f"Prepared a {len(quiz.questions)}-question quiz on {quiz.topic}. "
                "Let the learner know the quiz is ready for them to take."
            )

        handoffs = [agent for agent in (self.ingestion_agent, self.qa_agent, self.web_agent) if agent is not None]
        self.orchestrator_agent = Agent(
            name="tutor_orchestrator",
            instructions=(
                "You are the orchestrator agent in a multi-agent tutoring system. Your job is to decide whether to answer a query yourself or delegate it to a specialist agent.\n\n"

                "You are given a learner profile summary and the current learner question. Use the profile to tailor your decision and, when answering directly, personalize the response.\n\n"

                "You have access to these resources:\n"
                "- Tool `generate_quiz(topic: str, count: int = 4, difficulty: str | None)` which prepares an interactive quiz for the learner.\n"
                "- Specialist agents: ingestion_agent, qa_agent, web_agent.\n\n"

                "Follow these rules:\n"
                "- If the question is about the tutoring system itself, the student profile, learning progress, progress history, or general/common knowledge, you should answer directly.\n"
                "- If the question involves STEM content (math, science, coding, etc.) and may benefit from local course materials or citations, hand it off to the `qa_agent`.\n"
                "- If the question is non-STEM (e.g., literature, history, current events), or clearly requires external information, hand it off to the `web_agent` for a web-based answer.\n"
                "- If the user explicitly asks to upload, ingest, or index files, hand it off to the `ingestion_agent`.\n"
                "- If a learner explicitly asks for a quiz, practice exam, or a set of questions, you must call the `generate_quiz` tool. Extract the subject/topic and desired number of questions from the request when possible (default to 4 questions if unspecified). Never fabricate quiz questions yourself. After the tool succeeds, reply with a concise summary letting the learner know the quiz is ready in the companion interface.\n"
                "- Always prioritize delegating to the most relevant specialist agent.\n\n"

                "When unsure, favor delegation over direct response unless the query clearly falls within your scope."
            ),
            tools=[generate_quiz],
            handoffs=handoffs,
        )

    def create_quiz(
        self,
        *,
        topic: str,
        profile: Optional[LearnerProfile],
        num_questions: int = 4,
        difficulty: Optional[str] = None,
        extra_context: Optional[str] = None,
    ) -> Quiz:
        """Generate a multiple-choice quiz tailored to the learner."""
        return self.quiz_service.generate_quiz(
            topic=topic,
            profile=profile,
            num_questions=num_questions,
            difficulty=difficulty,
            extra_context=extra_context,
        )

    def evaluate_quiz(
        self,
        *,
        quiz: Quiz,
        answers: List[int],
        profile: Optional[LearnerProfile],
    ) -> QuizEvaluation:
        """Score a learner's quiz submission and return detailed feedback."""
        return self.quiz_service.evaluate_quiz(
            quiz=quiz,
            answers=answers,
            profile=profile,
        )

    def answer(
        self,
        learner_id: str,
        question: str,
        mode: str,
        style_hint: str,
        profile: Optional[LearnerProfile] = None,
        extra_context: Optional[str] = None,
        on_delta: Optional[Callable[[str], None]] = None,
    ) -> TutorResponse:
        """Synchronously orchestrate the multi-agent run and produce a TutorResponse."""
        return asyncio.run(
            self._answer_async(
                learner_id=learner_id,
                question=question,
                mode=mode,
                style_hint=style_hint,
                profile=profile,
                extra_context=extra_context,
                on_delta=on_delta,
            )
        )

    async def _answer_async(
        self,
        learner_id: str,
        question: str,
        mode: str,
        style_hint: str,
        profile: Optional[LearnerProfile],
        extra_context: Optional[str],
        on_delta: Optional[Callable[[str], None]],
    ) -> TutorResponse:
        session = self._get_session(learner_id)
        self.state.reset()

        system_preamble = (
            f"Learner mode: {mode}. Preferred explanation style: {style_hint}. "
            "Cite supporting evidence using bracketed indices or URLs when available."
        )
        prompt_sections: List[str] = [system_preamble, ""]

        if profile:
            prompt_sections.append("Learner profile summary:")
            prompt_sections.append(self._render_profile_summary(profile))
            prompt_sections.append("")

        if extra_context:
            prompt_sections.append("Session documents:")
            prompt_sections.append(extra_context)
            prompt_sections.append("")

        prompt_sections.append("Question:")
        prompt_sections.append(question)
        prompt = "\n".join(prompt_sections)

        self._active_profile = profile
        self._active_extra_context = extra_context
        self.state.last_quiz = None
        try:
            raw_answer = await self._run_specialist(
                prompt,
                session,
                on_delta,
            )
        finally:
            self._active_profile = None
            self._active_extra_context = None
        quiz_payload: Optional[Quiz] = None
        answer_text = raw_answer
        if raw_answer.strip().startswith("{"):
            processed, computed_quiz = self._process_quiz_directive(
                raw_answer,
                profile=profile,
                extra_context=extra_context,
            )
            if computed_quiz is not None:
                quiz_payload = computed_quiz
                answer_text = processed
        if quiz_payload is None and self.state.last_quiz is not None:
            quiz_payload = self.state.last_quiz
        if quiz_payload is None and self._should_force_quiz(question):
            quiz_payload = self.quiz_service.generate_quiz(
                topic=self._infer_topic_from_request(question),
                profile=profile,
                num_questions=self._infer_count_from_request(question),
                difficulty=None,
                extra_context=extra_context,
            )
            self.state.last_quiz = quiz_payload
            answer_text = (
                f"I've prepared a {len(quiz_payload.questions)}-question quiz on {quiz_payload.topic}. "
                "Scroll down to take it when you're ready."
            )
        if not quiz_payload and not self.state.last_citations:
            answer_text = self._strip_citation_markers(answer_text)
        if quiz_payload is None:
            processed, computed_quiz = self._process_quiz_directive(
                answer_text,
                profile=profile,
                extra_context=extra_context,
            )
            if computed_quiz is not None:
                quiz_payload = computed_quiz
                answer_text = processed
        hits = self.state.last_hits if not quiz_payload else []
        citations = self.state.last_citations if not quiz_payload else []
        source = "quiz" if quiz_payload else self.state.last_source

        return TutorResponse(
            answer=answer_text,
            hits=hits,
            citations=citations,
            style=style_hint,
            source=source,
            quiz=quiz_payload,
        )

    def _get_session(self, learner_id: str) -> SQLiteSession:
        session = self.sessions.get(learner_id)
        if session is None:
            session = SQLiteSession(
                f"ai_tutor_{learner_id}",
                db_path=str(self.session_db_path),
            )
            self.sessions[learner_id] = session
        return session

    @staticmethod
    def _strip_citation_markers(answer: str) -> str:
        cleaned = re.sub(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]", "", answer)
        return re.sub(r"\s{2,}", " ", cleaned).strip()

    @staticmethod
    def _render_profile_summary(profile: LearnerProfile) -> str:
        lines = [
            f"Name: {profile.name or profile.learner_id}",
            f"Total study time (minutes): {profile.total_time_minutes:.1f}",
        ]
        if profile.domain_strengths:
            strengths = sorted(profile.domain_strengths.items(), key=lambda item: item[1], reverse=True)[:3]
            strength_lines = ", ".join(f"{domain}: {score:.2f}" for domain, score in strengths)
            lines.append(f"Domain strengths: {strength_lines}")
        if profile.difficulty_preferences:
            prefs = ", ".join(f"{domain}: {pref}" for domain, pref in list(profile.difficulty_preferences.items())[:3])
            lines.append(f"Difficulty preferences: {prefs}")
        if profile.next_topics:
            next_topics = ", ".join(f"{domain}: {topic}" for domain, topic in list(profile.next_topics.items())[:3])
            lines.append(f"Upcoming topics: {next_topics}")
        return "\n".join(lines)

    def _process_quiz_directive(
        self,
        answer_text: str,
        profile: Optional[LearnerProfile],
        extra_context: Optional[str],
    ) -> tuple[str, Optional[Quiz]]:
        text = answer_text.strip()
        if not text.startswith("{"):
            return answer_text, None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return answer_text, None
        if not isinstance(payload, dict):
            return answer_text, None
        if payload.get("action") != "generate_quiz":
            return answer_text, None

        topic_raw = payload.get("topic") or payload.get("subject") or "general review"
        topic = str(topic_raw).strip() or "general review"
        count_raw = payload.get("count") or payload.get("num_questions") or 4
        try:
            count = int(count_raw)
        except (TypeError, ValueError):
            count = 4
        count = max(3, min(count, 8))
        message = str(payload.get("message") or "").strip()

        quiz = self.quiz_service.generate_quiz(
            topic=topic,
            profile=profile,
            num_questions=count,
            difficulty=None,
            extra_context=extra_context,
        )
        if not message:
            message = f"I've prepared a {count}-question quiz on {quiz.topic}. Scroll down to take it."
        return message, quiz

    @staticmethod
    def _should_force_quiz(question: str) -> bool:
        lowered = question.lower()
        keywords = [
            "quiz",
            "quizzes",
            "practice questions",
            "practice quiz",
            "give me questions",
            "mcq",
            "multiple choice",
            "test me",
        ]
        return any(keyword in lowered for keyword in keywords)

    @staticmethod
    def _infer_topic_from_request(question: str) -> str:
        match = re.search(r"(?:about|on|regarding)\s+(.+)", question, flags=re.IGNORECASE)
        topic = match.group(1).strip() if match else question.strip()
        topic = re.sub(r"[\.\?!]+$", "", topic)
        return topic or "general review"

    @staticmethod
    def _infer_count_from_request(question: str) -> int:
        match = re.search(r"(\d+)\s*(?:question|questions|quiz|quizzes|mcq)", question, flags=re.IGNORECASE)
        if not match:
            match = re.search(r"(\d+)", question)
        if match:
            try:
                value = int(match.group(1))
                return max(3, min(value, 8))
            except ValueError:
                pass
        return 4

    async def _run_specialist(
        self,
        prompt: str,
        session: SQLiteSession,
        on_delta: Optional[Callable[[str], None]],
    ) -> str:
        final_tokens: List[str] = []

        agent_to_run = self.orchestrator_agent or self.qa_agent
        stream = Runner.run_streamed(agent_to_run, input=prompt, session=session)
        async for event in stream.stream_events():
            if not isinstance(event, RawResponsesStreamEvent):
                continue
            data = event.data
            if isinstance(data, ResponseTextDeltaEvent):
                final_tokens.append(data.delta)
                if on_delta:
                    on_delta(data.delta)
            elif isinstance(data, ResponseContentPartDoneEvent) and on_delta:
                on_delta("\n")

        if self.orchestrator_agent is None and not self.state.last_source and self.web_agent is not None:
            if on_delta:
                on_delta("[info] No local evidence, searching the web...\n")
            self.state.reset()
            final_tokens.clear()
            stream = Runner.run_streamed(self.web_agent, input=prompt, session=session)
            async for event in stream.stream_events():
                if not isinstance(event, RawResponsesStreamEvent):
                    continue
                data = event.data
                if isinstance(data, ResponseTextDeltaEvent):
                    final_tokens.append(data.delta)
                    if on_delta:
                        on_delta(data.delta)
                elif isinstance(data, ResponseContentPartDoneEvent) and on_delta:
                    on_delta("\n")

        return "".join(final_tokens).strip()
