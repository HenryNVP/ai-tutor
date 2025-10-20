from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from openai.types.responses import ResponseContentPartDoneEvent, ResponseTextDeltaEvent

from agents import Agent, RawResponsesStreamEvent, Runner, WebSearchTool, function_tool
from agents import SQLiteSession
from agents.tracing import trace

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

        self._last_hits: List[RetrievalHit] = []
        self._last_citations: List[str] = []

        self.ingestion_agent: Agent | None = None
        self.qa_agent: Agent | None = None
        self.web_agent: Agent | None = None
        self.triage_agent: Agent | None = None

        self._build_agents()

    def _build_agents(self) -> None:
        """Instantiate ingestion, QA, web, and triage agents with shared tools."""

        @function_tool
        def ingest_corpus(directory: str) -> str:
            path = Path(directory)
            if not path.exists() or not path.is_dir():
                return json.dumps({"error": f"The provided directory {directory} does not exist."})
            result = self.ingest_fn(path)
            payload = {
                "documents_ingested": len(result.documents),
                "chunks_created": len(result.chunks),
                "skipped_files": [str(item) for item in result.skipped],
            }
            return json.dumps(payload)

        @function_tool
        def retrieve_local_context(question: str, top_k: int = 8) -> str:
            hits = self.retriever.retrieve(Query(text=question))
            filtered = self._filter_hits(hits)[:top_k]
            self._last_hits = filtered
            self._last_citations = [self._format_citation(hit) for hit in filtered]
            context_items = []
            for idx, hit in enumerate(filtered, start=1):
                meta = hit.chunk.metadata
                context_items.append(
                    {
                        "index": idx,
                        "citation": f"[{idx}] {meta.title} (Doc: {meta.doc_id}, Page: {meta.page or 'N/A'})",
                        "text": hit.chunk.text,
                        "score": hit.score,
                    }
                )
            return json.dumps({"context": context_items, "citations": self._last_citations})

        @function_tool
        async def web_search(query: str, max_results: int = 5) -> str:
            results = await self.search_tool.search(query, max_results=max_results)
            self._last_hits = []
            self._last_citations = [
                f"{item.title} — {item.url}" if item.url else item.title for item in results
            ]
            serialized = [
                {
                    "index": idx,
                    "title": item.title,
                    "snippet": item.snippet,
                    "url": item.url,
                    "published_at": item.published_at,
                }
                for idx, item in enumerate(results, start=1)
            ]
            return json.dumps({"results": serialized, "citations": self._last_citations})

        ingestion_agent = Agent(
            name="ingestion_agent",
            instructions=(
                "You ingest new learner materials. Use the ingest_corpus tool to process directories. "
                "Always summarize the ingestion result briefly after calling the tool."
            ),
            tools=[ingest_corpus],
        )

        web_agent = Agent(
            name="web_agent",
            instructions=(
                "You answer questions when the local corpus lacks evidence. "
                "Call web_search to gather reputable sources, synthesize a concise answer, and cite URLs."
            ),
            tools=[web_search],
        )

        qa_agent = Agent(
            name="qa_agent",
            instructions=(
                "Answer learner questions using the local corpus. "
                "Call retrieve_local_context to gather relevant chunks and cite them with [index] notation. "
                "If the tool returns no useful context, hand off to web_agent."
            ),
            tools=[retrieve_local_context],
            handoffs=[web_agent],
        )

        triage_agent = Agent(
            name="triage_agent",
            instructions=(
                "Decide which specialist should handle the request. "
                "If the user asks you to ingest or index files, hand off to ingestion_agent. "
                "Otherwise hand off to qa_agent."
            ),
            handoffs=[ingestion_agent, qa_agent],
        )

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
        self._reset_state()

        system_preamble = (
            f"Learner mode: {mode}. Preferred explanation style: {style_hint}. "
            "Cite supporting evidence using bracketed indices or URLs when available."
        )
        prompt = f"{system_preamble}\n\nQuestion:\n{question}"

        stream = Runner.run_streamed(
            self.triage_agent,
            input=prompt,
            session=session,
        )

        final_tokens: List[str] = []

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

        answer_text = "".join(final_tokens).strip()
        answer_text = self._strip_citation_markers(answer_text) if not self._last_citations else answer_text

        return TutorResponse(
            answer=answer_text,
            hits=self._last_hits,
            citations=self._last_citations,
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

    def _filter_hits(self, hits: List[RetrievalHit]) -> List[RetrievalHit]:
        filtered: List[RetrievalHit] = []
        seen_docs: set[str] = set()
        for hit in hits:
            if hit.score < self.MIN_CONFIDENCE:
                continue
            doc_id = hit.chunk.metadata.doc_id.lower()
            if doc_id in seen_docs:
                continue
            seen_docs.add(doc_id)
            filtered.append(hit)
        return filtered

    @staticmethod
    def _format_citation(hit: RetrievalHit) -> str:
        metadata = hit.chunk.metadata
        page = metadata.page or "N/A"
        return f"{metadata.title} ({metadata.doc_id}) p.{page}"

    @staticmethod
    def _strip_citation_markers(answer: str) -> str:
        cleaned = re.sub(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]", "", answer)
        return re.sub(r"\s{2,}", " ", cleaned).strip()
