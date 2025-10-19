"""
Example script demonstrating how to interact with the Personal STEM Instructor
using Litellm-compatible models (e.g., Gemini).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from ai_tutor.agents.openai_sdk import TutorOpenAIAgent
from ai_tutor.system import TutorSystem


def main():
    """Demonstrate programmatic use of TutorSystem and TutorOpenAIAgent via CLI args."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--api-key", type=str, default=os.getenv("GEMINI_API_KEY"))
    parser.add_argument("--model", type=str, default=os.getenv("GEMINI_MODEL_NAME"))
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
        raise SystemExit("Please provide GEMINI_API_KEY (or OPENAI_API_KEY) or --api-key.")

    tutor = TutorSystem.from_config(args.config, api_key=args.api_key)

    # Optional: ingest demo documents before asking questions
    demo_docs = Path("data/raw")
    if demo_docs.exists():
        tutor.ingest_directory(demo_docs)

    agent = TutorOpenAIAgent(
        tutor_system=tutor,
        model_name=args.model,
        api_key=args.api_key,
    )

    task = args.task or (
        "Provide a concise, stepwise explanation to answer the learner's question "
        f'while citing evidence. Learner question: "{args.question}"'
    )
    result = agent.run(task, learner_id=args.learner_id)
    print("Agent Output:\n", result.final_output)


if __name__ == "__main__":
    main()
