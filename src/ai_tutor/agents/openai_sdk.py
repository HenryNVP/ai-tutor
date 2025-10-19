from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Optional

from agents import Agent, Runner, function_tool, set_tracing_disabled
from agents.extensions.models.litellm_model import LitellmModel

from ai_tutor.system import TutorSystem


class TutorOpenAIAgent:
    """Adapter wrapping TutorSystem with the OpenAI Agents SDK."""

    def __init__(
        self,
        tutor_system: TutorSystem,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Bridge the core TutorSystem into an OpenAI Agents workflow runner.

        Stores the shared system, resolves a default model name and API key, disables tracing
        for local runs, and registers callable tools produced by `_build_tools` with a Litellm-
        backed `Agent` instance.
        """
        self.tutor_system = tutor_system
        self.model_name = model_name or tutor_system.settings.model.name
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("An API key must be provided via argument or environment variable.")

        set_tracing_disabled(disabled=True)
        self.tools = self._build_tools()
        self.agent = Agent(
            name="STEMTutorMVP",
            instructions=(
                "You are a grounded STEM tutor. "
                "Use the available tools to ingest learner materials and to answer questions ONLY from the local corpus. "
                "Ground every factual statement in the provided context chunks. "
                "Citation policy: When (and only when) a statement is supported by a specific context chunk, add a bracketed index like [1] that matches the numbered Context section. "
                "Do not invent or guess citations. If you did not use any context chunk, include no bracketed indices. "
                "If the local corpus does not contain enough evidence to answer, say so briefly and suggest next steps (e.g., rephrase the question, ingest more material, or search the web); do not include any citations in that case. "
                "Be clear and concise; match the requested style (scaffolded, stepwise, concise) when provided."
            ),
            model=LitellmModel(model=self.model_name, api_key=self.api_key),
            tools=self.tools,
        )

    def _build_tools(self):
        """Define the ingestion and Q&A function tools that the agent can call."""
        tutor = self.tutor_system

        @function_tool
        def ingest_corpus(directory: str) -> str:
            """Ingest documents from a directory and return a JSON summary for the agent."""
            path = Path(directory)
            if not path.exists() or not path.is_dir():
                return json.dumps({"error": f"The provided directory {directory} does not exist."})
            result = tutor.ingest_directory(path)
            payload = {
                "documents_ingested": len(result.documents),
                "chunks_created": len(result.chunks),
                "skipped_files": [str(item) for item in result.skipped],
            }
            return json.dumps(payload)

        @function_tool
        def answer_question(learner_id: str, question: str, mode: str = "learning") -> str:
            """Answer a learner question by delegating to `TutorSystem.answer_question`."""
            response = tutor.answer_question(learner_id=learner_id, question=question, mode=mode)
            payload = {
                "answer": response.answer,
                "citations": response.citations,
                "style": response.style,
                "difficulty": response.difficulty,
                "next_topic": response.next_topic,
            }
            return json.dumps(payload)

        return [
            ingest_corpus,
            answer_question,
        ]

    async def arun(self, task: str, learner_id: Optional[str] = None) -> Any:
        """Run the agent asynchronously, optionally annotating the task with a learner ID."""
        prompt = task
        if learner_id:
            prompt = f"Learner ID: {learner_id}\nTask: {task}"
        return await Runner.run(self.agent, prompt)

    def run(self, task: str, learner_id: Optional[str] = None) -> Any:
        """
        Execute an agent task synchronously for convenience.

        Wraps the `arun` coroutine in `asyncio.run`, letting scripts and CLI commands invoke
        the OpenAI Agent without managing an event loop directly.
        """
        return asyncio.run(self.arun(task, learner_id=learner_id))
