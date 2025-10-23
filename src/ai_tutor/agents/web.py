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
        model="gpt-4o-mini",
        instructions=(
            "You answer questions using web search.\n\n"
            "PROCESS:\n"
            "1. ALWAYS call web_search tool first\n"
            "2. Review the search results\n"
            "3. Synthesize an answer using the information found\n"
            "4. Cite sources with URLs\n\n"
            "IMPORTANT:\n"
            "- ALWAYS call web_search before answering\n"
            "- Include URL citations in your answer\n"
            "- List all sources at the end"
        ),
        tools=[web_search],
    )
