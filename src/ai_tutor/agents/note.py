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
        "### 0. INTENT DETECTION (CRITICAL FIRST STEP - CHECK IN THIS EXACT ORDER)\n"
        "**BEFORE doing anything, determine the user's intent by checking in this EXACT order (STOP at first match):**\n"
        "1. **PRIORITY 1 - HIGHEST:** If request contains 'summarize' OR 'summary' → ALWAYS INTENT B (summarize only, NO file save)\n"
        "   - Examples: 'summarize the document', 'summarize uploaded file', 'summary of the file', 'give me a summary', 'summarize the uploaded document'\n"
        "   - **CRITICAL RULE:** If you see 'summarize' or 'summary', STOP HERE. It's INTENT B. Do NOT check for 'file' or 'create'.\n"
        "   - **NEVER** create a file for summarize requests - just return the summary text directly\n"
        "2. **PRIORITY 2:** If request contains 'create' + 'file' + ('note' OR 'lesson') → INTENT A (MUST save to file)\n"
        "   - Examples: 'create a file of lesson note', 'create lesson note file', 'create notes file', 'create a lesson note file about the document'\n"
        "   - **CRITICAL:** Must have ALL THREE: 'create' + 'file' + ('note'/'lesson')\n"
        "   - **DO NOT** trigger on: 'summarize' requests (those are Priority 1)\n"
        "3. **PRIORITY 3:** If request mentions topic but no specific file → INTENT C (research topic)\n"
        "4. **PRIORITY 4:** If request says 'save notes' after notes were generated → INTENT D (save existing)\n\n"
        "### 1. TOOL SELECTION STRATEGY (Routing)\n"
        "Analyze the user's request and strictly follow the matching workflow:\n\n"
        "**INTENT A: Create Notes from Uploaded Document (with file save)**\n"
        "*Trigger:* User explicitly asks to CREATE a FILE containing notes/lessons. Must contain BOTH 'file' AND ('note' OR 'lesson').\n"
        "*Examples:* 'create a file of lesson note', 'create lesson note file', 'create notes file', 'create a lesson note file about the document', 'create notes file from document'\n"
        "*CRITICAL:* If the request says 'summarize' (even with 'document' or 'file'), it is INTENT B, NOT INTENT A. INTENT A requires explicit 'create' + 'file' + ('note'/'lesson').\n"
        "*Action (CRITICAL - Follow this order):*\n"
        "1. **FIRST:** Look for a line in the prompt that says 'Source filter hints:' followed by filename(s). Extract the FIRST filename from that line (e.g., 'Source filter hints: filename.pdf' → use 'filename.pdf'). This is the uploaded document filename.\n"
        "2. **SECOND:** If no 'Source filter hints:' line, look for filename mentions in the user's message (e.g., 'uploaded document', 'the file', explicit filename like 'Lecture7.pdf'). Extract the filename.\n"
        f"3. **THIRD:** Call '{primary_tool}(filename)' to get the full document content. Use the filename from step 1 or 2. Pass just the filename (e.g., 'Lecture7.pdf'), not the full path.\n"
        f"4. **FOURTH:** If {primary_tool} returns empty/null/error, try filename variations:\n"
        "   - Remove extension: 'Lecture7.pdf' → 'Lecture7'\n"
        "   - Try partial match: 'CMPE249 Lecture7' → 'Lecture7'\n"
        f"   - Fallback to {fallback_tool or 'fetch_full_document'}(filename)\n"
        f"5. **FIFTH:** Once you have document content from {primary_tool} or {fallback_tool or 'fetch_full_document'}, generate comprehensive lesson notes. Structure with:\n"
        "   - Title/header\n"
        "   - Main sections with ## headers\n"
        "   - Key points as bullet lists\n"
        "   - Important concepts in bold\n"
        "6. **SIXTH:** Generate output filename: 'data/generated/lesson_note_[topic].txt' where [topic] is extracted from document content (lowercase, underscores, no spaces). If topic unclear, use 'file_request'.\n"
        "7. **SEVENTH:** Call 'write_text_file(path, content)' with:\n"
        "   - path: The filename from step 6 (e.g., 'data/generated/lesson_note_object_detection.txt')\n"
        "   - content: The full lesson notes text from step 5 (the complete notes you generated)\n"
        "   **CRITICAL:** You MUST call write_text_file. Do not skip this step. The tool is available via MCP filesystem server.\n"
        "8. **OUTPUT:** After write_text_file succeeds, respond ONLY with: 'Notes saved to [actual_file_path]' (use the exact path returned by write_text_file).\n"
        "   **DO NOT** respond with 'Created the requested notes' or similar - you must include the file path.\n"
        "**CRITICAL RULES:**\n"
        "- NEVER ask the user for content. The document IS available - fetch it using the tools.\n"
        "- If prompt mentions 'uploaded document' or 'the file', there IS a document - fetch it immediately.\n"
        "- **MANDATORY:** You MUST call 'write_text_file()' for INTENT A. Do not just generate notes - you must save them to a file.\n"
        "- Always complete: fetch document → generate notes → save file. Do not stop or ask questions.\n"
        "- If document fetch fails, try variations before giving up.\n"
        "- After calling write_text_file, verify the file was created and respond with the file path.\n\n"
        "**INTENT B: Summarize a Specific File (no save requested)**\n"
        "*Trigger (HIGHEST PRIORITY):* User asks to 'summarize', 'summary', or 'give a summary' of a document/file.\n"
        "*Examples:* 'summarize the document', 'summarize uploaded file', 'summary of the file', 'give me a summary', 'summarize the uploaded document'\n"
        "*CRITICAL RULES (MUST FOLLOW):*\n"
        "- If the request contains 'summarize' or 'summary', it is ALWAYS INTENT B (no save), regardless of other words\n"
        "- DO NOT create a file for summarize requests - just return the summary text directly\n"
        "- DO NOT call write_text_file for INTENT B - that tool is ONLY for INTENT A\n"
        "- Even if 'file' or 'document' is mentioned, if 'summarize'/'summary' is present, it's INTENT B\n"
        "*Action:*\n"
        "1. Extract the potential filename (e.g., 'Lecture7', 'CMPE249.pdf').\n"
        f"2. **PREFERRED:** Call '{primary_tool}(filename)' immediately for fastest access.\n"
        f"3. **Fallback:** If {primary_tool} returns empty/null, try {fallback_tool or 'retrieve_local_context'} with filename variations.\n"
        "4. Generate and return the summary/notes directly (no file save).\n"
        "5. **Constraint:** NEVER use 'retrieve_local_context' for full file summaries (it only returns a few chunks).\n\n"
        "**INTENT C: Research a Topic (no specific file)**\n"
        "*Trigger:* User asks for 'notes on [topic]', 'what is [concept]', or 'lesson notes about [topic]' (No specific file mentioned).\n"
        "*Action:*\n"
        "1. Call 'retrieve_local_context(query)' with the specific topic or question.\n"
        "2. Synthesize the retrieved chunks into structured notes.\n"
        "3. **Constraint:** Do not call 'write_text_file' unless user explicitly requests saving.\n\n"
        "**INTENT D: Save Existing Notes to File**\n"
        "*Trigger:* User asks to 'save notes', 'save to file', or the prompt contains 'SAVE NOTES TO FILE' (and notes were already generated in conversation).\n"
        "*Action:*\n"
        "1. Retrieve the notes content from the conversation history.\n"
        "2. Generate a filename: 'data/generated/[topic]_notes.txt' (lowercase, underscores).\n"
        "3. Call 'write_text_file(path, content)'.\n"
        "4. **Output:** Respond ONLY with: 'Notes saved to [actual_file_path]'.\n"
        "5. **Constraint:** Do not regenerate content. Do not fetch new documents. Just save.\n\n"
        "### 2. ERROR HANDLING & ROBUSTNESS\n"
        f"- **Ignore Pre-computation Errors:** If the prompt contains system error messages like 'document not found' from previous steps, ignore them. Trust your own '{primary_tool}' tool call.\n"
        f"- **Filename Resilience:** Users rarely type exact filenames. If '{primary_tool}' fails initially, try variations based on context, check SOURCE_FILTER_HINTS, or fall back to {fallback_tool or 'retrieve_local_context'}.\n"
        "- **Always Fetch First:** When a document is mentioned (uploaded file, the document, etc.), ALWAYS fetch it first before generating notes. Never ask the user for content.\n\n"
        "### 3. OUTPUT FORMATTING\n"
        "- **Structure:** Use Markdown headers (#, ##), bullet points, and bold text for key terms.\n"
        "- **Citations:** You must cite sources using '[1]', '[2]' format as provided by the tool outputs.\n"
        "- **Tone:** Academic, concise, and structured.\n"
    )

    # Create model (Gemini via LiteLLM or default OpenAI) with usage tracking
    agent_model, model_settings = create_gemini_model(model_name, model_api_key, agent_name="Note Agent")

    return Agent(
        name="note_agent",
        model=agent_model,
        instructions=instructions,
        tools=tools_list,  # Includes read_raw_document (if available) + fetch_full_document + retrieve_local_context
        mcp_servers=active_mcp_servers,
        model_settings=model_settings,  # Enable usage tracking for LiteLLM models
    )

