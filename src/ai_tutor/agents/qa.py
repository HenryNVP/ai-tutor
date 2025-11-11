from __future__ import annotations

import json
import logging
from typing import Any, List, Optional

from agents import Agent, function_tool

from ai_tutor.data_models import Query, RetrievalHit

logger = logging.getLogger(__name__)


def build_qa_agent(
    retriever,
    state,
    min_confidence: float,
    handoffs: Optional[List[Agent]] = None,
    mcp_server: Optional[Any] = None,  # Optional MCP server for Chroma
) -> Agent:
    """Create the local QA agent that consults the vector store."""

    def format_citation(hit: RetrievalHit, index: int) -> str:
        metadata = hit.chunk.metadata
        return f"[{index}] {metadata.title} (Doc: {metadata.doc_id})"

    @function_tool
    def retrieve_local_context(question: str, top_k: int = 5) -> str:
        import time
        start_time = time.time()
        logger.info(f"[QA Agent] Retrieving context for question: {question}")
        logger.info(f"[QA Agent] min_confidence threshold: {min_confidence}, top_k: {top_k}")
        
        # Search across all domain collections
        query = Query(text=question, domain=None)
        logger.info("[QA Agent] Searching across all domain collections")
        
        retrieve_start = time.time()
        hits = retriever.retrieve(query)
        retrieve_duration = time.time() - retrieve_start
        logger.info(f"[QA Agent] Retrieved {len(hits)} total hits from vector store in {retrieve_duration:.3f}s")
        
        # Log all hits with scores
        for i, hit in enumerate(hits[:10]):  # Log first 10
            logger.info(
                f"[QA Agent] Hit {i+1}: score={hit.score:.4f}, "
                f"title={hit.chunk.metadata.title}, "
                f"domain={getattr(hit.chunk.metadata, 'primary_domain', hit.chunk.metadata.domain)}, "
                f"text_preview={hit.chunk.text[:100]}..."
            )
        
        filtered: List[RetrievalHit] = []
        seen_docs: set[str] = set()
        skipped_low_score = 0
        skipped_duplicate = 0
        
        for hit in hits:
            if hit.score < min_confidence:
                skipped_low_score += 1
                logger.debug(f"[QA Agent] Skipping hit with score {hit.score:.4f} < {min_confidence}")
                continue
            doc_id = hit.chunk.metadata.doc_id.lower()
            if doc_id in seen_docs:
                skipped_duplicate += 1
                logger.debug(f"[QA Agent] Skipping duplicate doc: {doc_id}")
                continue
            seen_docs.add(doc_id)
            filtered.append(hit)
            logger.info(f"[QA Agent] Added hit: score={hit.score:.4f}, doc={doc_id}")
            if len(filtered) >= top_k:
                break

        logger.info(
            f"[QA Agent] Filtered results: {len(filtered)} hits kept, "
            f"{skipped_low_score} skipped (low score), {skipped_duplicate} skipped (duplicate)"
        )

        state.last_hits = filtered
        state.last_citations = [format_citation(hit, idx + 1) for idx, hit in enumerate(filtered)]
        state.last_source = "local" if filtered else None

        # Truncate context chunks to prevent prompt bloat (max 300 chars per chunk)
        # This reduces LLM processing time while keeping essential information
        MAX_CHUNK_LENGTH = 300
        context_items = [
            {
                "index": idx + 1,
                "citation": state.last_citations[idx],
                "text": hit.chunk.text[:MAX_CHUNK_LENGTH] + ("..." if len(hit.chunk.text) > MAX_CHUNK_LENGTH else ""),
                "score": hit.score,
            }
            for idx, hit in enumerate(filtered)
        ]
        
        result_json = json.dumps({"context": context_items, "citations": state.last_citations})
        total_duration = time.time() - start_time
        logger.info(f"[QA Agent] Returning {len(context_items)} context items (total time: {total_duration:.3f}s, retrieval: {retrieve_duration:.3f}s)")
        
        if not filtered:
            logger.warning(
                f"[QA Agent] No context found for question: '{question}'. "
                f"Total hits: {len(hits)}, Filtered: {len(filtered)}, "
                f"Min confidence: {min_confidence} (took {total_duration:.3f}s)"
            )
        
        return result_json

    # If MCP server is available, use it; otherwise use direct retriever
    mcp_servers = [mcp_server] if mcp_server else []
    
    return Agent(
        name="qa_agent",
        model="gpt-4o-mini",
        instructions=(
            "You answer STEM questions using local course materials. Keep answers CONCISE and focused.\n\n"
            "PROCESS:\n"
            "1. ALWAYS call retrieve_local_context tool first (or use Chroma MCP tools if available)\n"
            "2. Read the returned context carefully\n"
            "3. If context is useful, provide a CONCISE answer (2-4 sentences max) using it and cite sources with [1], [2], etc.\n"
            "4. If NO useful context or the retrieved passages are not helpful:\n"
            "   - DO NOT answer from your own knowledge or generate unsupported content\n"
            "   - Immediately hand off to the web_agent using the provided handoff (reply EXACTLY with: HANDOFF TO web_agent)\n"
            "   - After handing off, wait for the web_agent to respond (your work is done)\n\n"
            "IMPORTANT:\n"
            "- ALWAYS call retrieve_local_context before answering\n"
            "- The retriever searches across all domain collections automatically\n"
            "- ⚠️ KEEP ANSWERS BRIEF: 2-4 sentences for most questions, up to 6 sentences for complex topics\n"
            "- ⚠️ Focus on the key points - avoid lengthy explanations unless absolutely necessary\n"
            "- Include citations in your answer using bracketed numbers when context is available\n"
            "- List all citations at the end (one line per citation)\n"
            "- ⚠️ CRITICAL: After you provide an answer (with or without context), your job is DONE\n"
            "- ⚠️ Only hand off to web_agent when context is missing or insufficient\n"
            "- ⚠️ If you provide an answer, the orchestrator should NOT route to you again"
        ),
        tools=[retrieve_local_context],
        handoffs=handoffs or [],
        mcp_servers=mcp_servers,  # Add MCP server if provided (shared connection, tools cached)
    )
