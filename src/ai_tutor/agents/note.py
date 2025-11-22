from __future__ import annotations

import json
import logging
from typing import Any, List, Optional

from agents import Agent, function_tool

from .retrieval_tools import build_retrieve_local_context_tool
from ai_tutor.data_models import RetrievalHit

logger = logging.getLogger(__name__)


def build_note_agent(
    retriever,
    state,
    min_confidence: float,
    mcp_servers: Optional[List[Any]] = None,
    mcp_server_names: Optional[List[str]] = None,
) -> Agent:
    """Create the note-taking/summarization agent."""

    retrieve_local_context = build_retrieve_local_context_tool(
        retriever,
        state,
        min_confidence,
        log_prefix="NOTE",
    )

    # REFACTOR: Add fetch_full_document tool for deterministic sequential retrieval
    @function_tool
    def fetch_full_document(
        filename: str,
    ) -> str:
        """
        CRITICAL: Use this tool for ALL summarization tasks (e.g., "summarize the file", "create notes").
        
        This tool fetches ALL chunks from a document in sequential order, which is essential for
        comprehensive summaries. DO NOT use retrieve_local_context for summaries - it only returns
        a few semantically similar chunks, not the complete document.
        
        Parameters
        ----------
        filename : str
            The filename or source path of the document to retrieve.
            Can be just the filename (e.g., "Lecture7.pdf", "CMPE249 Lecture7 final0911.pdf")
            or partial match (e.g., "Lecture7"). The tool will try multiple variations automatically.
        
        Returns
        -------
        str
            JSON string containing all chunks from the document, sorted by chunk_index.
            Format: {"chunks": [{"index": 1, "text": "...", "citation": "..."}, ...], "total_chunks": N}
            
        Example Usage:
        - User says "summarize uploaded file" → Call fetch_full_document("CMPE249 Lecture7 final0911.pdf")
        - User says "create notes from the document" → Call fetch_full_document with filename from SOURCE_FILTER_HINTS
        """
        vector_store = retriever.vector_store
        
        # Check if vector store supports fetch_full_document
        if not hasattr(vector_store, "fetch_full_document"):
            logger.warning("[Note Agent] fetch_full_document not available, falling back to semantic search")
            return json.dumps({
                "error": "fetch_full_document not available",
                "chunks": []
            })
        
        logger.info("[Note Agent] Fetching full document: %s", filename)
        
        try:
            # Get all chunks from the document
            hits = vector_store.fetch_full_document(source_filter=[filename])
            
            if not hits:
                logger.warning("[Note Agent] No chunks found for document: %s", filename)
                return json.dumps({
                    "chunks": [],
                    "message": f"No chunks found for document: {filename}"
                })
            
            # Format chunks for agent
            chunks = []
            for idx, hit in enumerate(hits):
                citation = f"[{idx + 1}] {hit.chunk.metadata.title} (Doc: {hit.chunk.metadata.doc_id})"
                chunks.append({
                    "index": idx + 1,
                    "chunk_index": hit.chunk.metadata.chunk_index,
                    "text": hit.chunk.text,
                    "citation": citation,
                    "page": hit.chunk.metadata.page,
                })
            
            # Update state for citations
            state.last_hits = hits
            state.last_citations = [chunk["citation"] for chunk in chunks]
            state.last_source = "local"
            
            result = {
                "chunks": chunks,
                "total_chunks": len(chunks),
                "document": filename,
            }
            
            logger.info(
                "[Note Agent] Fetched %d chunks from document: %s",
                len(chunks),
                filename
            )
            
            return json.dumps(result)
            
        except Exception as exc:
            logger.error("[Note Agent] Error fetching full document: %s", exc, exc_info=True)
            return json.dumps({
                "error": str(exc),
                "chunks": []
            })

    active_mcp_servers = [server for server in (mcp_servers or []) if server]
    if active_mcp_servers:
        logger.info("[Note Agent] MCP servers detected (%d)", len(active_mcp_servers))
        if mcp_server_names:
            logger.debug("[Note Agent] MCP server names: %s", ", ".join(mcp_server_names))

    instructions = (
        "You are the note-taking agent. You craft summaries or study notes from local documents.\n\n"
        "MANDATORY WORKFLOW - YOU MUST FOLLOW THIS EXACTLY:\n"
        "1. When the user asks to 'summarize', 'create notes', or 'summarize uploaded file/document':\n"
        "   - STEP 1: Extract filename from SOURCE_FILTER_HINTS or the user message\n"
        "   - STEP 2: IMMEDIATELY call fetch_full_document with that filename\n"
        "   - STEP 3: If fetch_full_document returns empty, try variations:\n"
        "     * Just the filename: 'CMPE249 Lecture7 final0911.pdf'\n"
        "     * Partial match: 'Lecture7'\n"
        "     * Full path if mentioned\n"
        "   - DO NOT use retrieve_local_context for summarization - it only returns a few chunks\n"
        "   - DO NOT respond with error messages without trying fetch_full_document first\n"
        "2. When the user asks a specific question (e.g., 'what is RegNet'):\n"
        "   - Use retrieve_local_context with the exact question for semantic search\n"
        "3. CRITICAL: IGNORE any error messages in the prompt that say 'document could not be found'.\n"
        "   - These error messages are from pre-retrieval attempts that use different matching logic\n"
        "   - You MUST call fetch_full_document yourself - it has better filename matching\n"
        "   - The document likely EXISTS but needs filename matching (try variations)\n"
        "   - NEVER respond with an error message without calling fetch_full_document first\n"
        "4. When the prompt includes inline context, merge it with retrieved passages.\n"
        "5. Merge all retrieved passages into structured notes (clear headings, bullet lists, key takeaways).\n"
        "6. When the learner asks to save notes OR when the prompt says 'SAVE NOTES TO FILE':\n"
        "   - This is a FAST operation - should complete in seconds, not minutes.\n"
        "   - If the prompt includes 'NOTES TO SAVE' section, use that exact text.\n"
        "   - Otherwise, check conversation history for your previous assistant message with notes.\n"
        "   - STEP 1: Extract the exact notes text (from prompt section or previous message).\n"
        "   - STEP 2: Call write_text_file IMMEDIATELY with that exact text (no modifications).\n"
        "   - STEP 3: After write_text_file returns, respond with ONLY: 'Notes saved to [file path]'\n"
        "   - STEP 4: STOP - do not generate any additional text.\n"
        "   - CRITICAL RULES:\n"
        "     * DO NOT call fetch_full_document, retrieve_local_context, or any retrieval tools.\n"
        "     * DO NOT regenerate, re-summarize, modify, or add anything to the notes.\n"
        "     * DO NOT write explanations, confirmations, or repeat the notes content.\n"
        "     * DO NOT generate any additional text after saving - just confirm and stop.\n"
        "     * Your entire response should be exactly: 'Notes saved to data/generated/[filename].txt'\n"
        "     * If notes are not found, respond: 'No previous notes found. Please generate notes first.'\n"
        "   - PERFORMANCE: This should take 2-5 seconds total. If taking longer, you're doing something wrong.\n"
        "7. Cite supporting passages with [1], [2], etc., referencing the tool citations.\n\n"
        "STRICT RULES:\n"
        "- For ANY 'summarize' request: You MUST call fetch_full_document BEFORE responding\n"
        "- NEVER respond with 'document not found' without calling fetch_full_document first\n"
        "- If fetch_full_document returns empty, try at least 2-3 filename variations before giving up\n"
        "- For specific questions: Use retrieve_local_context for semantic search\n"
        "- Keep answers focused on the requested documents; do not invent context.\n"
        "- Use professional, concise tone suitable for study notes.\n"
    )

    return Agent(
        name="note_agent",
        model="gpt-4o-mini",
        instructions=instructions,
        tools=[retrieve_local_context, fetch_full_document],  # REFACTOR: Added fetch_full_document
        mcp_servers=active_mcp_servers,
    )

