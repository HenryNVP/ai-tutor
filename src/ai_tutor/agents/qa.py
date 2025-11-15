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
    mcp_servers: Optional[List[Any]] = None,
    mcp_server_names: Optional[List[str]] = None,
) -> Agent:
    """Create the local QA agent that consults the vector store."""
    
    # Cache to prevent redundant retrieval calls within the same agent execution
    _retrieval_cache: dict[str, str] = {}

    def format_citation(hit: RetrievalHit, index: int) -> str:
        metadata = hit.chunk.metadata
        return f"[{index}] {metadata.title} (Doc: {metadata.doc_id})"

    @function_tool
    def retrieve_local_context(question: str, top_k: int = 5) -> str:
        """
        Retrieve relevant context from local course materials.
        
        ⚠️ IMPORTANT: This tool is automatically cached - calling it multiple times with the same question returns the cached result.
        Call this tool ONCE per question - do NOT call it multiple times.
        
        Parameters
        ----------
        question : str
            The question to search for in local documents.
        top_k : int, default=5
            Maximum number of relevant chunks to return.
            
        Returns
        -------
        str
            JSON string containing context items and citations.
        """
        # Check cache first to avoid redundant calls
        cache_key = f"{question}:{top_k}"
        if cache_key in _retrieval_cache:
            logger.info(f"[QA Agent] Returning cached retrieval result for: {question}")
            return _retrieval_cache[cache_key]
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
        
        # Cache the result to prevent redundant calls
        _retrieval_cache[cache_key] = result_json
        
        return result_json

    # If MCP servers are available, use them; otherwise use direct retriever
    active_mcp_servers = [server for server in (mcp_servers or []) if server]
    
    if active_mcp_servers:
        logger.info(f"[QA Agent] Building with {len(active_mcp_servers)} MCP server(s) - tools will be automatically available")
        # Check if filesystem MCP server is present (for write_text_file)
        # Use server names if provided (more reliable than string matching)
        has_filesystem = False
        if mcp_server_names:
            # Check server names for filesystem indicator
            has_filesystem = any(
                "filesystem" in name.lower() or "fs" in name.lower() or name.lower() == "filesystem"
                for name in mcp_server_names
            )
        else:
            # Fallback: try to detect from server object (less reliable)
            # Check if server has write_text_file tool or if name contains filesystem
            for server in active_mcp_servers:
                server_str = str(server).lower()
                if "filesystem" in server_str or "fs" in server_str:
                    has_filesystem = True
                    break
                # Try checking server name attribute if available
                if hasattr(server, 'name') and server.name:
                    if "filesystem" in server.name.lower() or "fs" in server.name.lower():
                        has_filesystem = True
                        break
        
        if has_filesystem:
            logger.info("[QA Agent] ✅ Filesystem MCP server detected - write_text_file tool should be available")
        else:
            logger.warning("[QA Agent] ⚠️  No filesystem MCP server detected - write_text_file may not be available")
            if mcp_server_names:
                logger.debug(f"[QA Agent] Available MCP server names: {', '.join(mcp_server_names)}")
    
    return Agent(
        name="qa_agent",
        model="gpt-4o-mini",
        instructions=(
            "You answer STEM questions and create summary files from local course materials.\n\n"

            "WHEN USER ASKS TO SUMMARIZE A DOCUMENT AND SAVE TO FILE:\n"
            "**CRITICAL: You MUST use the write_text_file tool - DO NOT just write text in your response!**\n\n"
            "Step-by-step process:\n"
            "1. Identify the document name/topic from the user's request\n"
            "   - If user says 'summarize the uploaded document' → document = 'uploaded document'\n"
            "   - If user mentions a specific document (e.g., 'CMPE249 Lecture9') → use that name\n"
            "2. Call retrieve_local_context with a simple question about the document:\n"
            "   - For 'uploaded document': question='What is the main content and topics covered?'\n"
            "   - For specific document: question='What is the content of [document name]?'\n"
            "   - Use top_k=10 to get enough context for a summary\n"
            "3. Generate a comprehensive 1-page summary (~500-800 words) from the retrieved context\n"
            "4. **MANDATORY: Call write_text_file tool to save the file**\n"
            "   - You MUST call the write_text_file function/tool - this is NOT optional\n"
            "   - Tool name: write_text_file\n"
            "   - Required parameters:\n"
            "     * path: 'data/generated/{document_name}_summary.txt' (sanitize document_name for filename)\n"
            "     * content: The FULL summary text you generated in step 3\n"
            "   - Do NOT include the summary text in your chat response - ONLY call the tool\n"
            "   - The tool will create the file - you don't need to write it manually\n"
            "5. After successfully calling write_text_file, respond with ONLY: 'I've saved the summary to data/generated/{filename}.txt'\n\n"
            "**REMINDER: If write_text_file is not in your available tools list, respond with: 'Error: write_text_file tool not available. Please check MCP server connection.'**\n\n"

            "WHEN USER ASKS A REGULAR QUESTION:\n"
            "1. Call retrieve_local_context ONCE with the user's exact question\n"
            "2. If context found, give a 2–4 sentence answer with citations [1], [2], etc\n"
            "3. If no context, reply EXACTLY: HANDOFF TO web_agent\n\n"

            "CRITICAL RULES:\n"
            "- For summaries: DO NOT use the full user instruction as the retrieve_local_context question\n"
            "- For summaries: Extract the document name and ask about its content\n"
            "- For summaries: You MUST call write_text_file TOOL - do NOT just provide text in chat\n"
            "- For summaries: If write_text_file is not in your available tools, say 'write_text_file tool not available'\n"
            "- For summaries: DO NOT hand off to web_agent - you handle file creation directly\n"
            "- Call retrieve_local_context ONCE per request (it's cached)\n"
            "- write_text_file is a MCP tool that should be available if filesystem MCP server is connected"
        ),
        tools=[retrieve_local_context],
        handoffs=handoffs or [],
        mcp_servers=active_mcp_servers,  # Add MCP servers if provided (shared connection, tools cached)
    )
