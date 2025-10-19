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
        self.tutor_system = tutor_system
        self.model_name = model_name or tutor_system.settings.model.name
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("An API key must be provided via argument or environment variable.")

        set_tracing_disabled(disabled=True)
        self.tools = self._build_tools()
        self.agent = Agent(
            name="STEMTutorMVP",
            instructions=(
                "You are a grounded STEM tutor. Use the tools to ingest learner materials "
                "and answer questions with citations from the local corpus."
            ),
            model=LitellmModel(model=self.model_name, api_key=self.api_key),
            tools=self.tools,
        )

    def _build_tools(self):
        tutor = self.tutor_system

        @function_tool
        def ingest_corpus(directory: str) -> str:
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
            response = tutor.answer_question(learner_id=learner_id, question=question, mode=mode)
            payload = {
                "answer": response.answer,
                "citations": response.citations,
            }
            return json.dumps(payload)

        return [
            ingest_corpus,
            answer_question,
        ]

    async def arun(self, task: str, learner_id: Optional[str] = None) -> Any:
        prompt = task
        if learner_id:
            prompt = f"Learner ID: {learner_id}\nTask: {task}"
        return await Runner.run(self.agent, prompt)

    def run(self, task: str, learner_id: Optional[str] = None) -> Any:
        return asyncio.run(self.arun(task, learner_id=learner_id))
