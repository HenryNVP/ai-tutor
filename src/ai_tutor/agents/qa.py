from __future__ import annotations

import logging
from typing import Any, List, Optional

from agents import Agent

from .retrieval_tools import build_retrieve_local_context_tool

logger = logging.getLogger(__name__)


def build_qa_agent(
    retriever,
    state,
    min_confidence: float,
    mcp_servers: Optional[List[Any]] = None,
    mcp_server_names: Optional[List[str]] = None,
) -> Agent:
    """Create the local QA agent that consults the vector store."""

    retrieve_local_context = build_retrieve_local_context_tool(
        retriever,
        state,
        min_confidence,
        log_prefix="QA",
    )

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
    
    instructions = (
        "You answer STEM questions using local course materials.\n\n"
        "Process:\n"
        "1. ALWAYS call retrieve_local_context ONCE using the learner's question (or the router-provided paraphrase).\n"
        "2. If you receive source filter hints, pass them via the `source_filter` argument to focus on the correct documents.\n"
        "3. Compose a focused answer (3-6 sentences) citing evidence with [1], [2] markers.\n"
        "4. If retrieve_local_context returns no passages, respond EXACTLY with 'HANDOFF TO web_agent'.\n\n"
        "Rules:\n"
        "- Do not summarize documents into files; that work belongs to note_agent.\n"
        "- Never call write_text_file.\n"
        "- Keep reasoning grounded strictly in provided context.\n"
        "- If question is outside local materials and you have no evidence, hand off to the web agent as described."
    )

    return Agent(
        name="qa_agent",
        model="gpt-4o-mini",
        instructions=instructions,
        tools=[retrieve_local_context],
        mcp_servers=active_mcp_servers,  # Add MCP servers if provided (shared connection, tools cached)
    )
