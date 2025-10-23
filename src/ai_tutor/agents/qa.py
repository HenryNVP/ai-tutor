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
        model="gpt-4o-mini",
        instructions=(
            "You answer STEM questions using local course materials.\n\n"
            "PROCESS:\n"
            "1. ALWAYS call retrieve_local_context tool first\n"
            "2. Read the returned context carefully\n"
            "3. If context is useful, answer using it and cite sources with [1], [2], etc.\n"
            "4. If NO useful context or empty results, hand off to web_agent\n\n"
            "IMPORTANT:\n"
            "- ALWAYS call retrieve_local_context before answering\n"
            "- Include citations in your answer using bracketed numbers\n"
            "- List all citations at the end"
        ),
        tools=[retrieve_local_context],
        handoffs=handoffs or [],
    )
