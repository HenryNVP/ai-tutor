from __future__ import annotations

import json
import logging
from typing import Any, List, Optional

from agents import Agent, function_tool

from .model_utils import create_gemini_model
from .retrieval_tools import build_retrieve_local_context_tool
from .mcp_compat import get_gemini_compatible_mcp_servers

logger = logging.getLogger(__name__)


def build_qa_agent(
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
    Create the local QA agent that consults the vector store.
    
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
        Model identifier for QA Agent. For Gemini via LiteLLM, use 'gemini/gemini-2.0-flash'.
        If None, uses default 'gpt-4o-mini'.
    model_api_key : Optional[str]
        API key for the model. If None, reads from environment variables.
    document_cache : Optional[DocumentCache]
        Document cache for direct text access (bypasses chunking/embedding). When provided and using Gemini,
        QA Agent can read full documents directly for uploaded document questions.
    """

    retrieve_local_context = build_retrieve_local_context_tool(
        retriever,
        state,
        min_confidence,
        log_prefix="QA",
    )

    # OPTIMIZATION: Add read_raw_document tool for direct text access (bypasses chunking/embedding)
    # This is faster and more efficient when using Gemini (large context window) for uploaded documents
    @function_tool
    def read_raw_document(
        filename: str,
    ) -> str:
        """
        OPTIMIZED: Read full document text directly from cache (bypasses chunking/embedding).
        
        This tool reads the complete document text directly from the document cache,
        which is much faster than semantic search. Use this when:
        - You're answering questions about a specific uploaded document
        - The question mentions a filename or document reference
        - You need the full document context for accurate answers
        
        This is preferred over retrieve_local_context for uploaded document questions, as it:
        - Skips embedding queries (faster)
        - Provides cleaner text (no chunk boundaries)
        - Is more efficient (no database queries)
        
        For general questions (no specific document), use retrieve_local_context instead.
        
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
        - User asks "What is BiFPN in the uploaded document?" → Call read_raw_document("CMPE249 Lecture8 final0916.pdf")
        - User asks "How does R-CNN work?" with source_filter → Call read_raw_document with filename from source_filter
        """
        if not document_cache:
            logger.warning("[QA Agent] Document cache not available, falling back to retrieve_local_context")
            return json.dumps({
                "error": "Document cache not available",
                "text": "",
                "message": "Document cache not initialized. Use retrieve_local_context instead."
            })
        
        logger.info("[QA Agent] Reading raw document from cache: %s", filename)
        
        try:
            # Try to find document by filename
            document = document_cache.get_by_filename(filename)
            
            if not document:
                logger.warning("[QA Agent] Document not found in cache: %s", filename)
                return json.dumps({
                    "error": "Document not found",
                    "text": "",
                    "message": f"Document '{filename}' not found in cache. It may not have been processed yet, or the filename doesn't match. Use retrieve_local_context for general queries."
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
                "[QA Agent] Read raw document: %s (%d chars)",
                filename,
                len(document.text)
            )
            
            return json.dumps(result)
            
        except Exception as exc:
            logger.error("[QA Agent] Error reading raw document: %s", exc, exc_info=True)
            return json.dumps({
                "error": str(exc),
                "text": "",
                "message": f"Error reading document: {exc}"
            })

    # Filter MCP servers for Gemini compatibility
    active_mcp_servers, active_mcp_names = get_gemini_compatible_mcp_servers(
        mcp_servers,
        mcp_server_names,
        model_name,
    )
    
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
    
    # Determine if using Gemini (large context window) and if cache is available
    is_gemini = model_name and model_name.startswith("gemini/")
    has_cache = document_cache is not None
    
    # Build tool list - prefer read_raw_document if cache available and using Gemini
    tools_list = [retrieve_local_context]
    if document_cache and is_gemini:
        tools_list.append(read_raw_document)
        primary_tool = "read_raw_document"
        fallback_tool = "retrieve_local_context"
    else:
        primary_tool = "retrieve_local_context"
        fallback_tool = None

    instructions = (
        "You answer STEM questions using local course materials.\n\n"
        "### TOOL SELECTION STRATEGY\n"
        "Choose the appropriate tool based on the question context:\n\n"
        "**For Questions About Uploaded Documents (with source_filter or filename mentioned):**\n"
        f"1. **PREFERRED:** If a specific document is mentioned (check for source_filter hints or filename references), "
        f"call '{primary_tool}(filename)' to read the full document text directly.\n"
        f"2. **Fallback:** If {primary_tool} returns an error or document not found, use {fallback_tool or 'retrieve_local_context'} instead.\n\n"
        "**For General Questions (no specific document):**\n"
        "1. Use 'retrieve_local_context(question)' for semantic search across all documents.\n"
        "2. This works best for questions that span multiple documents or general knowledge.\n\n"
        "**For Simple Greetings:**\n"
        "1. Respond naturally without calling any tools (e.g., 'hello', 'how are you', 'what can you help with').\n\n"
        "### PROCESS\n"
        "1. If the prompt already includes inline document content (look for sections labelled 'Inline Context: Session Uploads' or 'Inline Context: Prompt Snippet'), use that text directly.\n"
        "2. When calling tools, invoke at most once and pass any `source_filter` hints to stay on the correct documents.\n"
        "3. Compose a focused 3–6 sentence answer with bracketed citations. "
        "Use [1], [2], etc. for retrieved passages; when only inline context is available, cite the document title in-line instead.\n"
        "4. Only respond 'HANDOFF TO web_agent' when neither inline context nor tool calls produced any evidence.\n\n"
        "### RULES\n"
        "- Do not summarize documents into files; that work belongs to note_agent.\n"
        "- Never call write_text_file.\n"
        "- Keep reasoning grounded strictly in provided context (inline text and/or retrieved passages).\n"
        "- Hand off to the web agent only when no local or inline evidence exists.\n"
        "- For greetings and simple conversational prompts, respond directly without retrieval."
    )

    # Create model (Gemini via LiteLLM or default OpenAI)
    agent_model = create_gemini_model(model_name, model_api_key, agent_name="QA Agent")

    return Agent(
        name="qa_agent",
        model=agent_model,
        instructions=instructions,
        tools=tools_list,  # Includes read_raw_document (if available) + retrieve_local_context
        mcp_servers=active_mcp_servers,  # Add MCP servers if provided (shared connection, tools cached)
    )
