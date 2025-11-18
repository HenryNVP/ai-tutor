from __future__ import annotations

import logging
from typing import Any, List, Optional

from agents import Agent

from .retrieval_tools import build_retrieve_local_context_tool

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

    active_mcp_servers = [server for server in (mcp_servers or []) if server]
    if active_mcp_servers:
        logger.info("[Note Agent] MCP servers detected (%d)", len(active_mcp_servers))
        if mcp_server_names:
            logger.debug("[Note Agent] MCP server names: %s", ", ".join(mcp_server_names))

    instructions = (
        "You are the note-taking agent. You craft summaries or study notes from local documents.\n\n"
        "Workflow:\n"
        "1. ALWAYS call retrieve_local_context before writing any notes. Pass `source_filter` if the user or router provided specific document names.\n"
        "2. Use the retrieved context to produce structured notes (headings + bullets) or narrative summaries as requested.\n"
        "3. When the learner asks to save notes or create a file, call the write_text_file tool via the filesystem MCP server. "
        "Name files under data/generated/ with a descriptive slug.\n"
        "4. Cite supporting passages using [1], [2] style markers that align with the provided citations.\n\n"
        "Rules:\n"
        "- Keep answers focused on the requested documents; do not invent context.\n"
        "- If retrieve_local_context returns no entries, explain that no local evidence was found and STOP (do not fabricate notes).\n"
        "- Use professional, concise tone suitable for study notes.\n"
        "- If write_text_file is unavailable when requested, reply with an explicit error message.\n"
    )

    return Agent(
        name="note_agent",
        model="gpt-4o-mini",
        instructions=instructions,
        tools=[retrieve_local_context],
        mcp_servers=active_mcp_servers,
    )

