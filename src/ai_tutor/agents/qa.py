from __future__ import annotations

import logging
from typing import Any, List, Optional

from agents import Agent

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
    """

    retrieve_local_context = build_retrieve_local_context_tool(
        retriever,
        state,
        min_confidence,
        log_prefix="QA",
    )

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
    
    instructions = (
        "You answer STEM questions using local course materials.\n\n"
        "Process:\n"
        "1. For simple greetings or general questions that don't require course materials (e.g., 'hello', 'how are you', 'what can you help with'), respond naturally without calling retrieve_local_context.\n"
        "2. If the prompt already includes inline document content (look for sections labelled 'Inline Context: Session Uploads' or 'Inline Context: Prompt Snippet'), use that text directly. "
        "Call retrieve_local_context when you need additional passages or when the router supplies specific filenames.\n"
        "3. When calling retrieve_local_context, invoke it at most once and pass any `source_filter` hints to stay on the correct documents.\n"
        "4. Merge inline context (if present) with retrieved passages to compose a focused 3–6 sentence answer with bracketed citations. "
        "Use [1], [2], etc. for retrieved passages; when only inline context is available, cite the document title in-line instead.\n"
        "5. Only respond 'HANDOFF TO web_agent' when neither inline context nor retrieve_local_context produced any evidence.\n\n"
        "Rules:\n"
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
        tools=[retrieve_local_context],
        mcp_servers=active_mcp_servers,  # Add MCP servers if provided (shared connection, tools cached)
    )
