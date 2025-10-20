from __future__ import annotations

import json
from typing import List

from agents import Agent, function_tool

from ai_tutor.search.tool import SearchTool, SearchResult


def build_web_agent(search_tool: SearchTool, state) -> Agent:
    """Create the web-search fallback agent."""

    def format_citation(result: SearchResult) -> str:
        return f"{result.title} — {result.url}" if result.url else result.title

    @function_tool
    async def web_search(query: str, max_results: int = 5) -> str:
        results = await search_tool.search(query, max_results=max_results)
        state.last_hits = []
        state.last_citations = [format_citation(item) for item in results]
        state.last_source = "web" if results else None
        serialized = [
            {
                "index": idx + 1,
                "title": item.title,
                "snippet": item.snippet,
                "url": item.url,
                "published_at": item.published_at,
            }
            for idx, item in enumerate(results)
        ]
        return json.dumps({"results": serialized, "citations": state.last_citations})

    return Agent(
        name="web_agent",
        instructions=(
            "You answer questions when the local corpus lacks evidence. "
            "Call web_search to gather reputable sources, synthesize a concise answer, and cite URLs."
        ),
        tools=[web_search],
    )
