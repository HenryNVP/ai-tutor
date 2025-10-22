from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from openai.types.responses import ResponseContentPartDoneEvent, ResponseTextDeltaEvent

from agents import Agent, RawResponsesStreamEvent, Runner
from agents import SQLiteSession

from .ingestion import build_ingestion_agent
from .qa import build_qa_agent
from .web import build_web_agent

from ai_tutor.config.schema import RetrievalConfig
from ai_tutor.data_models import RetrievalHit
from ai_tutor.ingestion.embeddings import EmbeddingClient
from ai_tutor.learning.models import LearnerProfile
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


@dataclass
class AgentState:
    last_hits: List[RetrievalHit] = field(default_factory=list)
    last_citations: List[str] = field(default_factory=list)
    last_source: Optional[str] = None

    def reset(self) -> None:
        self.last_hits.clear()
        self.last_citations.clear()
        self.last_source = None


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
    ):
        self.retriever = Retriever(retrieval_config, embedder=embedder, vector_store=vector_store)
        self.search_tool = search_tool
        self.ingest_fn = ingest_directory
        self.sessions: Dict[str, SQLiteSession] = {}
        self.state = AgentState()
        self.session_db_path = session_db_path

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
        handoffs = [agent for agent in (self.ingestion_agent, self.qa_agent, self.web_agent) if agent is not None]
        self.orchestrator_agent = Agent(
            name="tutor_orchestrator",
            instructions=(
                "You are the orchestrator agent in a multi-agent tutoring system. Your job is to decide whether to answer a query yourself or delegate it to a specialist agent.\n\n"

                "You are given a learner profile summary and the current learner question. Use the profile to tailor your decision and, when answering directly, personalize the response.\n\n"

                "Follow these rules:\n"
                "- If the question is about the tutoring system itself, the student profile, learning progress, progress history, or general/common knowledge, you should answer directly.\n"
                "- If the question involves STEM content (math, science, coding, etc.) and may benefit from local course materials or citations, hand it off to the `qa_agent`.\n"
                "- If the question is non-STEM (e.g., literature, history, current events), or clearly requires external information, hand it off to the `web_agent` for a web-based answer.\n"
                "- If the user explicitly asks to upload, ingest, or index files, hand it off to the `ingestion_agent`.\n"
                "- Always prioritize delegating to the most relevant specialist agent.\n\n"

                "When unsure, favor delegation over direct response unless the query clearly falls within your scope."
            ),
            handoffs=handoffs,
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

        answer_text = await self._run_specialist(
            prompt,
            session,
            on_delta,
        )
        answer_text = self._strip_citation_markers(answer_text) if not self.state.last_citations else answer_text

        return TutorResponse(
            answer=answer_text,
            hits=self.state.last_hits,
            citations=self.state.last_citations,
            style=style_hint,
            source=self.state.last_source,
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
        if profile.session_history:
            recent = profile.session_history[-3:]
            summaries = []
            for item in recent:
                question = item.get("question", "").strip()
                answer = item.get("answer", "").strip()
                summaries.append(f"Q: {question[:120]} | A: {answer[:120]}")
            lines.append("Recent interactions: " + " ; ".join(summaries))
        return "\n".join(lines)

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
