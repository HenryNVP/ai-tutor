from __future__ import annotations

import json
import logging
from typing import Any, List, Optional

from agents import Agent, function_tool

from .model_utils import create_gemini_model
from .retrieval_tools import build_retrieve_local_context_tool
from .mcp_compat import get_gemini_compatible_mcp_servers
from ai_tutor.data_models import RetrievalHit

logger = logging.getLogger(__name__)


def build_note_agent(
    retriever,
    state,
    min_confidence: float,
    mcp_servers: Optional[List[Any]] = None,
    mcp_server_names: Optional[List[str]] = None,
    model_name: Optional[str] = None,
    model_api_key: Optional[str] = None,
    document_cache: Optional[Any] = None,
) -> Agent:
    """
    Create the note-taking/summarization agent.
    
    Parameters
    ----------
    retriever
        Vector retriever for document search.
    state
        Agent state for storing context and citations.
    min_confidence : float
        Minimum similarity score for retrieval results.
    mcp_servers : Optional[List[Any]]
        List of MCP server connections.
    mcp_server_names : Optional[List[str]]
        List of MCP server names.
    model_name : Optional[str]
        Model identifier for Note Agent. For Gemini via LiteLLM, use 'gemini/gemini-2.0-flash'.
        If None, uses default 'gpt-4o-mini'.
    model_api_key : Optional[str]
        API key for the model. If None, reads from environment variables.
    document_cache : Optional[DocumentCache]
        Document cache for direct text access (bypasses chunking). When provided and using Gemini,
        Note Agent can read full documents directly without retrieving chunks.
    """

    retrieve_local_context = build_retrieve_local_context_tool(
        retriever,
        state,
        min_confidence,
        log_prefix="NOTE",
    )

    # OPTIMIZATION: Add read_raw_document tool for direct text access (bypasses chunking)
    # This is faster and more efficient when using Gemini (large context window)
    @function_tool
    def read_raw_document(
        filename: str,
    ) -> str:
        """
        OPTIMIZED: Read full document text directly from cache (bypasses chunking/embedding).
        
        This tool reads the complete document text directly from the document cache,
        which is much faster than retrieving and concatenating chunks. Use this when:
        - You need the full document for summarization or note-taking
        - You're using Gemini (large context window can handle full documents)
        - The document was recently uploaded/ingested
        
        This is preferred over fetch_full_document when available, as it:
        - Skips chunk retrieval from vector store
        - Provides cleaner text (no chunk boundaries)
        - Is faster (no database queries)
        
        Parameters
        ----------
        filename : str
            The filename or source path of the document to read.
            Can be just the filename (e.g., "Lecture7.pdf", "CMPE249 Lecture7 final0911.pdf")
            or partial match (e.g., "Lecture7"). The tool will try multiple variations automatically.
        
        Returns
        -------
        str
            JSON string containing the full document text and metadata.
            Format: {"text": "...", "title": "...", "doc_id": "...", "source_path": "..."}
            
        Example Usage:
        - User says "summarize uploaded file" → Call read_raw_document("CMPE249 Lecture7 final0911.pdf")
        - User says "create notes from the document" → Call read_raw_document with filename from SOURCE_FILTER_HINTS
        """
        if not document_cache:
            logger.warning("[Note Agent] Document cache not available, falling back to fetch_full_document")
            return json.dumps({
                "error": "Document cache not available",
                "text": "",
                "message": "Document cache not initialized. Use fetch_full_document instead."
            })
        
        logger.info("[Note Agent] Reading raw document from cache: %s", filename)
        
        try:
            # Try to find document by filename
            document = document_cache.get_by_filename(filename)
            
            if not document:
                logger.warning("[Note Agent] Document not found in cache: %s", filename)
                return json.dumps({
                    "error": "Document not found",
                    "text": "",
                    "message": f"Document '{filename}' not found in cache. It may not have been ingested yet, or the filename doesn't match."
                })
            
            # Return full document text
            result = {
                "text": document.text,
                "title": document.metadata.title,
                "doc_id": document.metadata.doc_id,
                "source_path": str(document.metadata.source_path),
                "domain": document.metadata.primary_domain,
                "total_chars": len(document.text),
            }
            
            # Update state for citations (use document title)
            citation = f"[1] {document.metadata.title} (Doc: {document.metadata.doc_id})"
            state.last_citations = [citation]
            state.last_source = "local"
            
            logger.info(
                "[Note Agent] Read raw document: %s (%d chars)",
                filename,
                len(document.text)
            )
            
            return json.dumps(result)
            
        except Exception as exc:
            logger.error("[Note Agent] Error reading raw document: %s", exc, exc_info=True)
            return json.dumps({
                "error": str(exc),
                "text": "",
                "message": f"Error reading document: {exc}"
            })

    # REFACTOR: Add fetch_full_document tool for deterministic sequential retrieval (fallback)
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

    # Filter MCP servers for Gemini compatibility
    active_mcp_servers, active_mcp_names = get_gemini_compatible_mcp_servers(
        mcp_servers,
        mcp_server_names,
        model_name,
    )
    
    if active_mcp_servers:
        logger.info("[Note Agent] MCP servers detected (%d)", len(active_mcp_servers))
        if active_mcp_names:
            logger.debug("[Note Agent] MCP server names: %s", ", ".join(active_mcp_names))

    # Determine if using Gemini (large context window)
    is_gemini = model_name and model_name.startswith("gemini/")
    
    # Build tool list - prefer read_raw_document if cache available and using Gemini
    tools_list = [retrieve_local_context]
    if document_cache and is_gemini:
        # Add read_raw_document for optimized full document access
        tools_list.append(read_raw_document)
        tools_list.append(fetch_full_document)  # Keep as fallback
        primary_tool = "read_raw_document"
        fallback_tool = "fetch_full_document"
    else:
        # Fallback to chunk-based retrieval
        tools_list.append(fetch_full_document)
        primary_tool = "fetch_full_document"
        fallback_tool = None

    instructions = (
        "You are the Note-Taking Agent, responsible for creating accurate study notes and summaries from local documents.\n\n"
        "### 1. TOOL SELECTION STRATEGY (Routing)\n"
        "Analyze the user's request and strictly follow the matching workflow:\n\n"
        "**INTENT A: Summarize a Specific File**\n"
        "*Trigger:* User asks to 'summarize [filename]', 'summary of uploaded file', or references a specific document.\n"
        "*Action:*\n"
        "1. Extract the potential filename (e.g., 'Lecture7', 'CMPE249.pdf').\n"
        f"2. **PREFERRED:** Call '{primary_tool}(filename)' immediately for fastest access.\n"
        f"3. **Fallback:** If {primary_tool} returns empty/null, try {fallback_tool or 'retrieve_local_context'} with filename variations.\n"
        "4. **Constraint:** NEVER use 'retrieve_local_context' for full file summaries (it only returns a few chunks).\n\n"
        "**INTENT B: Research a Topic**\n"
        "*Trigger:* User asks for 'notes on [topic]', 'what is [concept]', or 'lesson notes about [topic]' (No specific file mentioned).\n"
        "*Action:*\n"
        "1. Call 'retrieve_local_context(query)' with the specific topic or question.\n"
        "2. Synthesize the retrieved chunks into structured notes.\n"
        "3. **Constraint:** Do not call 'write_text_file' until you have generated the notes content first.\n\n"
        "**INTENT C: Save Notes to File**\n"
        "*Trigger:* User asks to 'save notes', 'save to file', or the prompt contains 'SAVE NOTES TO FILE'.\n"
        "*Action:*\n"
        "1. Retrieve the notes content from the conversation history (or the current prompt's context).\n"
        "2. Generate a filename: 'data/generated/[topic]_notes.txt' (lowercase, underscores).\n"
        "3. Call 'write_text_file(path, content)'.\n"
        "4. **Output:** Respond ONLY with: 'Notes saved to [actual_file_path]'.\n"
        "5. **Constraint:** Do not regenerate content. Do not fetch new documents. Just save.\n\n"
        "### 2. ERROR HANDLING & ROBUSTNESS\n"
        f"- **Ignore Pre-computation Errors:** If the prompt contains system error messages like 'document not found' from previous steps, ignore them. Trust your own '{primary_tool}' tool call.\n"
        f"- **Filename Resilience:** Users rarely type exact filenames. If '{primary_tool}' fails initially, try variations based on context or fall back to {fallback_tool or 'retrieve_local_context'}.\n\n"
        "### 3. OUTPUT FORMATTING\n"
        "- **Structure:** Use Markdown headers (#, ##), bullet points, and bold text for key terms.\n"
        "- **Citations:** You must cite sources using '[1]', '[2]' format as provided by the tool outputs.\n"
        "- **Tone:** Academic, concise, and structured.\n"
    )

    # Create model (Gemini via LiteLLM or default OpenAI)
    agent_model = create_gemini_model(model_name, model_api_key, agent_name="Note Agent")

    return Agent(
        name="note_agent",
        model=agent_model,
        instructions=instructions,
        tools=tools_list,  # Includes read_raw_document (if available) + fetch_full_document + retrieve_local_context
        mcp_servers=active_mcp_servers,
    )

