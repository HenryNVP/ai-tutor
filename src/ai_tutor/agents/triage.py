from __future__ import annotations

from agents import Agent


def build_triage_agent(ingestion_agent: Agent, qa_agent: Agent, guardrail) -> Agent:
    """Create the triage agent that routes between ingestion and tutoring."""

    return Agent(
        name="triage_agent",
        instructions=(
            "Decide which specialist should handle the request. "
            "If the user asks you to ingest or index files, hand off to ingestion_agent. "
            "Otherwise hand off to qa_agent."
        ),
        handoffs=[ingestion_agent, qa_agent],
        input_guardrails=[guardrail],
    )
