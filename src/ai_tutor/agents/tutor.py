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
    ):
        self.retriever = Retriever(retrieval_config, embedder=embedder, vector_store=vector_store)
        self.search_tool = search_tool
        self.ingest_fn = ingest_directory
        self.sessions: Dict[str, SQLiteSession] = {}
        self.state = AgentState()

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
                "You orchestrate specialist agents for a tutoring system.\n"
                "- For STEM questions, hand off to qa_agent so it can cite local materials.\n"
                "- For non-STEM questions, hand off to web_agent for a web-sourced answer.\n"
                "- If the user explicitly requests ingestion or indexing of files, hand off to ingestion_agent.\n"
                "Never answer questions yourself—always hand off to the best specialist."
            ),
            handoffs=handoffs,
        )

    def answer(
        self,
        learner_id: str,
        question: str,
        mode: str,
        style_hint: str,
        on_delta: Optional[Callable[[str], None]] = None,
    ) -> TutorResponse:
        """Synchronously orchestrate the multi-agent run and produce a TutorResponse."""
        return asyncio.run(
            self._answer_async(
                learner_id=learner_id,
                question=question,
                mode=mode,
                style_hint=style_hint,
                on_delta=on_delta,
            )
        )

    async def _answer_async(
        self,
        learner_id: str,
        question: str,
        mode: str,
        style_hint: str,
        on_delta: Optional[Callable[[str], None]],
    ) -> TutorResponse:
        session = self._get_session(learner_id)
        self.state.reset()

        system_preamble = (
            f"Learner mode: {mode}. Preferred explanation style: {style_hint}. "
            "Cite supporting evidence using bracketed indices or URLs when available."
        )
        prompt = f"{system_preamble}\n\nQuestion:\n{question}"
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
            session = SQLiteSession(f"ai_tutor_{learner_id}")
            self.sessions[learner_id] = session
        return session

    @staticmethod
    def _strip_citation_markers(answer: str) -> str:
        cleaned = re.sub(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]", "", answer)
        return re.sub(r"\s{2,}", " ", cleaned).strip()

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
