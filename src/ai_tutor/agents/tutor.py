from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from openai.types.responses import ResponseContentPartDoneEvent, ResponseTextDeltaEvent

from agents import Agent, InputGuardrailTripwireTriggered, RawResponsesStreamEvent, Runner
from agents import SQLiteSession
from agents.tracing import trace

from .guardrails import build_request_guardrail
from .ingestion import build_ingestion_agent
from .qa import build_qa_agent
from .triage import build_triage_agent
from .web import build_web_agent

from ai_tutor.config.schema import RetrievalConfig
from ai_tutor.data_models import Query, RetrievalHit
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
        self.triage_agent: Agent | None = None
        self.guardrail_agent: Agent | None = None

        self._build_agents()

    def _build_agents(self) -> None:
        """Instantiate ingestion, QA, web, and triage agents with shared tools."""

        guardrail_agent, request_guardrail = build_request_guardrail()
        self.guardrail_agent = guardrail_agent

        ingestion_agent = build_ingestion_agent(self.ingest_fn)
        web_agent = build_web_agent(self.search_tool, self.state)
        qa_agent = build_qa_agent(self.retriever, self.state, self.MIN_CONFIDENCE, handoffs=[web_agent])
        triage_agent = build_triage_agent(ingestion_agent, qa_agent, request_guardrail)

        self.ingestion_agent = ingestion_agent
        self.qa_agent = qa_agent
        self.web_agent = web_agent
        self.triage_agent = triage_agent

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
        if self.triage_agent is None:
            raise RuntimeError("Agents are not initialized.")

        session = self._get_session(learner_id)
        self.state.reset()

        system_preamble = (
            f"Learner mode: {mode}. Preferred explanation style: {style_hint}. "
            "Cite supporting evidence using bracketed indices or URLs when available."
        )
        prompt = f"{system_preamble}\n\nQuestion:\n{question}"

        final_tokens: List[str] = []

        try:
            stream = Runner.run_streamed(
                self.triage_agent,
                input=prompt,
                session=session,
            )

            with trace("Tutor session", metadata={"learner_id": learner_id, "mode": mode}):
                async for event in stream.stream_events():
                    if not isinstance(event, RawResponsesStreamEvent):
                        continue
                    data = event.data
                    if isinstance(data, ResponseTextDeltaEvent):
                        final_tokens.append(data.delta)
                        if on_delta:
                            on_delta(data.delta)
                    elif isinstance(data, ResponseContentPartDoneEvent):
                        if on_delta:
                            on_delta("\n")
        except InputGuardrailTripwireTriggered:
            refusal = "Sorry, I can’t help with that request."
            if on_delta:
                on_delta(refusal + "\n")
            return TutorResponse(answer=refusal, hits=[], citations=[], style=style_hint)

        answer_text = "".join(final_tokens).strip()
        answer_text = self._strip_citation_markers(answer_text) if not self.state.last_citations else answer_text

        return TutorResponse(
            answer=answer_text,
            hits=self.state.last_hits,
            citations=self.state.last_citations,
            style=style_hint,
        )

    def _get_session(self, learner_id: str) -> SQLiteSession:
        session = self.sessions.get(learner_id)
        if session is None:
            session = SQLiteSession(f"ai_tutor_{learner_id}")
            self.sessions[learner_id] = session
        return session

    def _reset_state(self) -> None:
        self._last_hits = []
        self._last_citations = []

    @staticmethod
    def _strip_citation_markers(answer: str) -> str:
        cleaned = re.sub(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]", "", answer)
        return re.sub(r"\s{2,}", " ", cleaned).strip()
