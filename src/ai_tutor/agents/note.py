from __future__ import annotations

import json
import logging
import os
from typing import Any, List, Optional, Union

from agents import Agent, function_tool

from .retrieval_tools import build_retrieve_local_context_tool
from ai_tutor.data_models import RetrievalHit

logger = logging.getLogger(__name__)


def _create_note_agent_model(
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Union[str, Any]:
    """
    Create model for Note Agent.
    
    If model_name starts with 'gemini/', uses LiteLLM with Gemini.
    Otherwise, returns the model name string for default OpenAI model.
    
    Parameters
    ----------
    model_name : Optional[str]
        Model identifier. For Gemini via LiteLLM, use 'gemini/gemini-1.5-pro' or 'gemini/gemini-1.5-flash'.
        If None, uses default 'gpt-4o-mini'.
    api_key : Optional[str]
        API key for the model. If None, reads from environment variables.
        
    Returns
    -------
    Union[str, Any]
        Model name string (for OpenAI) or LitellmModel instance (for Gemini).
    """
    if not model_name:
        return "gpt-4o-mini"
    
    # Check if using Gemini via LiteLLM
    if model_name.startswith("gemini/"):
        try:
            from agents.extensions.models.litellm_model import LitellmModel
            
            # Get API key from parameter or environment
            gemini_api_key = api_key or os.getenv("GEMINI_API_KEY")
            if not gemini_api_key:
                logger.warning(
                    "[Note Agent] Gemini model specified but GEMINI_API_KEY not found. "
                    "Falling back to default model."
                )
                return "gpt-4o-mini"
            
            logger.info(
                "[Note Agent] Using Gemini model via LiteLLM: %s",
                model_name
            )
            return LitellmModel(model=model_name, api_key=gemini_api_key)
        except ImportError:
            logger.warning(
                "[Note Agent] litellm not installed. Install with: pip install 'openai-agents[litellm]'. "
                "Falling back to default model."
            )
            return "gpt-4o-mini"
        except Exception as e:
            logger.error(
                "[Note Agent] Error creating LiteLLM model: %s. Falling back to default model.",
                e
            )
            return "gpt-4o-mini"
    
    # Default: return model name string (for OpenAI)
    return model_name


def build_note_agent(
    retriever,
    state,
    min_confidence: float,
    mcp_servers: Optional[List[Any]] = None,
    mcp_server_names: Optional[List[str]] = None,
    model_name: Optional[str] = None,
    model_api_key: Optional[str] = None,
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
        Model identifier for Note Agent. For Gemini via LiteLLM, use 'gemini/gemini-1.5-pro'.
        If None, uses default 'gpt-4o-mini'.
    model_api_key : Optional[str]
        API key for the model. If None, reads from environment variables.
    """

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
        "You are the Note-Taking Agent, responsible for creating accurate study notes and summaries from local documents.\n\n"
        "### 1. TOOL SELECTION STRATEGY (Routing)\n"
        "Analyze the user's request and strictly follow the matching workflow:\n\n"
        "**INTENT A: Summarize a Specific File**\n"
        "*Trigger:* User asks to 'summarize [filename]', 'summary of uploaded file', or references a specific document.\n"
        "*Action:*\n"
        "1. Extract the potential filename (e.g., 'Lecture7', 'CMPE249.pdf').\n"
        "2. **MANDATORY:** Call 'fetch_full_document(filename)' immediately.\n"
        "3. **Fallback:** If the tool returns empty/null, retry immediately with filename variations (e.g., remove extension, use partial match).\n"
        "4. **Constraint:** NEVER use 'retrieve_local_context' for full file summaries.\n\n"
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
        "- **Ignore Pre-computation Errors:** If the prompt contains system error messages like 'document not found' from previous steps, ignore them. Trust your own 'fetch_full_document' tool call.\n"
        "- **Filename Resilience:** Users rarely type exact filenames. If 'fetch_full_document' fails initially, try variations based on context.\n\n"
        "### 3. OUTPUT FORMATTING\n"
        "- **Structure:** Use Markdown headers (#, ##), bullet points, and bold text for key terms.\n"
        "- **Citations:** You must cite sources using '[1]', '[2]' format as provided by the tool outputs.\n"
        "- **Tone:** Academic, concise, and structured.\n"
    )

    # Create model (Gemini via LiteLLM or default OpenAI)
    agent_model = _create_note_agent_model(model_name, model_api_key)
    
    return Agent(
        name="note_agent",
        model=agent_model,
        instructions=instructions,
        tools=[retrieve_local_context, fetch_full_document],  # REFACTOR: Added fetch_full_document
        mcp_servers=active_mcp_servers,
    )

