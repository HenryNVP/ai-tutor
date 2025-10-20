from __future__ import annotations

import json
from typing import List, Optional

from agents import Agent, function_tool

from ai_tutor.data_models import Query, RetrievalHit


def build_qa_agent(
    retriever,
    state,
    min_confidence: float,
    handoffs: Optional[List[Agent]] = None,
) -> Agent:
    """Create the local QA agent that consults the vector store."""

    def format_citation(hit: RetrievalHit, index: int) -> str:
        metadata = hit.chunk.metadata
        page = metadata.page or "N/A"
        return f"[{index}] {metadata.title} (Doc: {metadata.doc_id}, Page: {page})"

    @function_tool
    def retrieve_local_context(question: str, top_k: int = 8) -> str:
        hits = retriever.retrieve(Query(text=question))
        filtered: List[RetrievalHit] = []
        seen_docs: set[str] = set()
        for hit in hits:
            if hit.score < min_confidence:
                continue
            doc_id = hit.chunk.metadata.doc_id.lower()
            if doc_id in seen_docs:
                continue
            seen_docs.add(doc_id)
            filtered.append(hit)
            if len(filtered) >= top_k:
                break

        state.last_hits = filtered
        state.last_citations = [format_citation(hit, idx + 1) for idx, hit in enumerate(filtered)]
        state.last_source = "local" if filtered else None

        context_items = [
            {
                "index": idx + 1,
                "citation": state.last_citations[idx],
                "text": hit.chunk.text,
                "score": hit.score,
            }
            for idx, hit in enumerate(filtered)
        ]
        return json.dumps({"context": context_items, "citations": state.last_citations})

    return Agent(
        name="qa_agent",
        instructions=(
            "Answer learner questions using the local corpus. "
            "Call retrieve_local_context to gather relevant chunks and cite them with [index] notation. "
            "If the tool returns no useful context, hand off to web_agent."
        ),
        tools=[retrieve_local_context],
        handoffs=handoffs or [],
    )
