from __future__ import annotations

from typing import Optional

from agents import Agent, WebSearchTool


def build_web_agent(
    user_location: Optional[str] = None,
    api_key: Optional[str] = None,
    state=None,
) -> Agent:
    """Create the web-search fallback agent using WebSearchTool directly."""
    
    # Use WebSearchTool directly - no wrapper needed
    web_search_tool = WebSearchTool(user_location=user_location)
    
    return Agent(
        name="web_agent",
        model="gpt-4o-mini",
        instructions=(
            "You answer questions using web search.\n\n"
            "PROCESS:\n"
            "1. ALWAYS call the web_search tool first\n"
            "2. Review the search results carefully\n"
            "3. Synthesize a clear, concise answer using the information found\n"
            "4. Cite sources with URLs in your answer\n\n"
            "IMPORTANT:\n"
            "- ALWAYS call web_search before answering\n"
            "- Include URL citations in your answer (e.g., [Source: URL])\n"
            "- List all sources at the end of your answer\n"
            "- Keep answers focused and cite all sources used"
        ),
        tools=[web_search_tool],
    )
