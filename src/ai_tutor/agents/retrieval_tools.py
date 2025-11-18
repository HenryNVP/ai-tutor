from __future__ import annotations

import json
import logging
from typing import List, Optional

from agents import function_tool

from ai_tutor.data_models import Query, RetrievalHit

logger = logging.getLogger(__name__)


def build_retrieve_local_context_tool(
    retriever,
    state,
    min_confidence: float,
    *,
    log_prefix: str = "QA",
) -> function_tool:
    """
    Create a cached retrieve_local_context tool that can be shared across agents.

    Parameters
    ----------
    retriever :
        Retriever instance used to perform vector searches.
    state :
        Shared AgentState used to store hits/citations for downstream formatting.
    min_confidence : float
        Minimum score threshold for accepting retrieval hits.
    log_prefix : str, optional
        Identifier used in log statements so multiple agents can be differentiated.
    """

    _retrieval_cache: dict[str, str] = {}

    def _format_citation(hit: RetrievalHit, index: int) -> str:
        metadata = hit.chunk.metadata
        return f"[{index}] {metadata.title} (Doc: {metadata.doc_id})"

    @function_tool
    def retrieve_local_context(
        question: str,
        top_k: int = 5,
        source_filter: Optional[List[str]] = None,
    ) -> str:
        """
        Retrieve relevant context from local course materials.

        Parameters
        ----------
        question : str
            The query or instruction that needs supporting context.
        top_k : int, default=5
            Maximum number of chunks to return.
        source_filter : Optional[List[str]]
            List of filenames or document identifiers to constrain the search to.
        """

        cache_key = f"{question}:{top_k}:{','.join(source_filter or [])}"
        if cache_key in _retrieval_cache:
            logger.info("[%s Agent] Returning cached retrieval result for: %s", log_prefix, question)
            return _retrieval_cache[cache_key]

        logger.info("[%s Agent] Retrieving context (top_k=%s, filter=%s)", log_prefix, top_k, source_filter)

        query = Query(text=question, source_filter=source_filter)
        hits = retriever.retrieve(query)

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
        state.last_citations = [_format_citation(hit, idx + 1) for idx, hit in enumerate(filtered)]
        state.last_source = "local" if filtered else None

        MAX_CHUNK_LENGTH = 300
        context_items = [
            {
                "index": idx + 1,
                "citation": state.last_citations[idx],
                "text": hit.chunk.text[:MAX_CHUNK_LENGTH]
                + ("..." if len(hit.chunk.text) > MAX_CHUNK_LENGTH else ""),
                "score": hit.score,
            }
            for idx, hit in enumerate(filtered)
        ]

        result_json = json.dumps(
            {
                "context": context_items,
                "citations": state.last_citations,
                "source_filter": source_filter,
            }
        )
        _retrieval_cache[cache_key] = result_json

        if not filtered:
            logger.warning(
                "[%s Agent] No context found (question='%s', min_confidence=%.2f, source_filter=%s)",
                log_prefix,
                question,
                min_confidence,
                source_filter,
            )
        else:
            logger.info(
                "[%s Agent] Returning %s context items (filter=%s)",
                log_prefix,
                len(context_items),
                source_filter,
            )

        return result_json

    return retrieve_local_context

