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
        "1. ALWAYS ground your notes in uploaded documents. Pass the provided `source_filter` straight into retrieve_local_context so you stay within those files.\n"
        "2. For comprehensive summaries, call retrieve_local_context ONCE with top_k=50 (or higher for very large documents) using a broad question such as \"What does <document name> cover?\" or \"Summarize the entire content of <document name>\". For specific questions (e.g., \"what is RegNet\"), use the exact question as the query with top_k=50 to retrieve all relevant chunks. This ensures you retrieve ALL chunks from the document.\n"
        "3. Merge all retrieved passages into structured notes (clear headings, bullet lists, key takeaways). Include the learner's requested focus areas. Make sure to cover ALL major topics from the retrieved context.\n"
        "4. When the learner asks to save notes or create a file, call the write_text_file tool via the filesystem MCP server. Name files under data/generated/ with a descriptive slug.\n"
        "5. Cite supporting passages with [1], [2], etc., referencing the retrieve_local_context citations. If no citations were returned, mention the document title directly instead.\n\n"
        "Rules:\n"
        "- Keep answers focused on the requested documents; do not invent context.\n"
        "- Use top_k=50 or higher to ensure comprehensive coverage of the entire document.\n"
        "- If retrieve_local_context returns zero entries, explain that no local evidence matched and ask the learner to re-check the document name.\n"
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

