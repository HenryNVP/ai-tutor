"""
Example script demonstrating how to interact with the Personal STEM Instructor
using OpenAI chat models.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from ai_tutor.system import TutorSystem
from agents import Agent, Runner, WebSearchTool, function_tool, set_trace_processors, set_tracing_disabled
from agents.models.openai_responses import OpenAIResponsesModel
from agents.tracing.processors import default_processor


def main():
    """Demonstrate programmatic use of TutorSystem with OpenAI Agents via CLI args."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--api-key", type=str, default=os.getenv("OPENAI_API_KEY"))
    parser.add_argument("--model", type=str, default=os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini"))
    parser.add_argument("--learner-id", type=str, default="demo_learner")
    parser.add_argument(
        "--question",
        type=str,
        default="Outline the steps to analyze projectile motion launched at an angle.",
    )
    parser.add_argument(
        "--task",
        type=str,
        default=None,
        help="High-level instruction for the agent. If omitted, the question prompt is used.",
    )
    args = parser.parse_args()

    if not args.api_key:
        raise SystemExit("Please provide OPENAI_API_KEY or --api-key.")

    tutor = TutorSystem.from_config(args.config, api_key=args.api_key)

    # Optional: ingest demo documents before asking questions
    demo_docs = Path("data/raw")
    if demo_docs.exists():
        tutor.ingest_directory(demo_docs)

    set_tracing_disabled(disabled=False)
    set_trace_processors([default_processor()])

    @function_tool
    def answer_question(learner_id: str, question: str, mode: str = "learning") -> str:
        response = tutor.answer_question(learner_id=learner_id, question=question, mode=mode)
        payload = {
            "answer": response.answer,
            "citations": response.citations,
            "style": response.style,
            "difficulty": response.difficulty,
            "next_topic": response.next_topic,
        }
        return json.dumps(payload)

    qa_agent = Agent(
        name="TutorExampleAgent",
        instructions=(
            "Answer the learner's question using the available tools. "
            "Prefer local corpus evidence and cite it with bracketed indices. "
            "If insufficient evidence is found locally, call web_search to gather reputable snippets."
        ),
        model=OpenAIResponsesModel(model=args.model, api_key=args.api_key),
        tools=[answer_question, WebSearchTool()],
    )

    task = args.task or (
        "Provide a concise, stepwise explanation to answer the learner's question "
        f'while citing evidence. Learner question: "{args.question}"'
    )
    prompt = f"Learner ID: {args.learner_id}\nTask: {task}"
    result = asyncio.run(Runner.run(qa_agent, prompt))
    print("Agent Output:\n", result.final_output)


if __name__ == "__main__":
    main()
