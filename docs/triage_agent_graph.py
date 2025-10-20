from __future__ import annotations

import asyncio
import os
from pathlib import Path

from agents import Agent
from agents.extensions.visualization import draw_graph

from ai_tutor.agents.guardrails import build_request_guardrail
from ai_tutor.agents.ingestion import build_ingestion_agent
from ai_tutor.agents.qa import build_qa_agent
from ai_tutor.agents.triage import build_triage_agent
from ai_tutor.agents.web import build_web_agent
from ai_tutor.retrieval.retriever import Retriever
from ai_tutor.search.tool import SearchTool


class DummyState:
    def __init__(self):
        self.last_hits = []
        self.last_citations = []
        self.last_source = None


def build_sample_graph() -> Agent:
    # Minimal dummy implementations to visualize handoffs and tools.
    class DummyRetriever:
        def retrieve(self, query):  # noqa: D401
            return []

    retriever = DummyRetriever()
    state = DummyState()
    search_tool = SearchTool()

    guardrail_agent, request_guardrail = build_request_guardrail()
    ingestion_agent = build_ingestion_agent(lambda _: Path("."))
    web_agent = build_web_agent(search_tool, state)
    qa_agent = build_qa_agent(retriever, state, min_confidence=0.2, handoffs=[web_agent])
    triage_agent = build_triage_agent(ingestion_agent, qa_agent, request_guardrail)
    return triage_agent


if __name__ == "__main__":
    agent = build_sample_graph()
    draw_graph(agent).view()
