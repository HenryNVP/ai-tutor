from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import List, Optional

from agents import Agent, Runner, WebSearchTool
from agents.models.openai_responses import OpenAIResponsesModel
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Structured result returned by the OpenAI web search tool."""

    title: str
    snippet: str
    url: str
    published_at: str | None = None


class SearchTool:
    """Wrapper around the Agents WebSearchTool that returns structured snippets."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        user_location: Optional[str] = None,
    ) -> None:
        instructions = (
            "Use the web_search tool to gather up-to-date information. "
            "Respond strictly as JSON in the shape {\"results\": [{\"title\": str, \"snippet\": str, \"url\": str, \"published_at\": str|None}]} "
            "with concise snippets (<= 320 characters)."
        )
        tool = WebSearchTool(user_location=user_location)
        self._client = AsyncOpenAI()
        self.agent = Agent(
            name="WebSearchAgent",
            instructions=instructions,
            model=OpenAIResponsesModel(model=model, openai_client=self._client),
            tools=[tool],
        )

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        prompt = (
            f"Collect up to {max_results} high-quality sources about: {query}. "
            "Ensure results focus on reputable references."
        )
        try:
            result = await Runner.run(self.agent, prompt)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Web search agent failed: %s", exc)
            return []

        raw_output = (result.final_output or "").strip()
        if not raw_output:
            return []

        try:
            payload = json.loads(raw_output)
        except json.JSONDecodeError:
            logger.debug("Unable to parse web search output as JSON: %s", raw_output)
            return []

        results_data = payload.get("results", [])
        structured: List[SearchResult] = []
        for item in results_data[:max_results]:
            structured.append(
                SearchResult(
                    title=str(item.get("title", "")),
                    snippet=str(item.get("snippet", "")),
                    url=str(item.get("url", "")),
                    published_at=item.get("published_at"),
                )
            )
        return structured
