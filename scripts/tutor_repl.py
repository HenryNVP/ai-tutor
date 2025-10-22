from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from ai_tutor.system import TutorSystem

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


def stream_printer(token: str) -> None:
    """Print streamed deltas as they arrive."""
    end = "" if token.endswith("\n") else ""
    print(token, end=end, flush=True)


def build_system(config: Optional[Path], api_key: Optional[str]) -> TutorSystem:
    if load_dotenv:
        try:
            load_dotenv(override=False)
        except AssertionError:
            pass
    return TutorSystem.from_config(config, api_key=api_key)


def handle_ingest(system: TutorSystem, directory: str) -> None:
    path = Path(directory).expanduser()
    if not path.exists() or not path.is_dir():
        print(f"[ingest] Directory not found: {path}")
        return
    result = system.ingest_directory(path)
    print(f"[ingest] Documents: {len(result.documents)} | Chunks: {len(result.chunks)}")
    if result.skipped:
        print("[ingest] Skipped files:")
        for item in result.skipped:
            print(f"  - {item}")


def handle_question(system: TutorSystem, learner_id: str, question: str, mode: str) -> None:
    print("[answer] ", end="", flush=True)
    response = system.answer_question(
        learner_id=learner_id,
        question=question,
        mode=mode,
        on_delta=stream_printer,
    )
    print()  # ensure newline after streaming output
    if response.citations:
        print("[citations]")
        for citation in response.citations:
            print(f" - {citation}")
    print(f"[style] {response.style}")
    if response.difficulty:
        print(f"[difficulty] {response.difficulty}")
    if response.next_topic:
        print(f"[next-topic] {response.next_topic}")


def repl(
    system: TutorSystem,
    learner_id: str,
    mode: str,
) -> None:
    print(
        "\nTutor REPL ready.\n"
        "Commands:\n"
        "  /ingest <directory>  - ingest a folder of documents\n"
        "  /mode <name>         - switch tutoring mode (default: learning)\n"
        "  /quit or /exit       - leave the REPL\n"
        "Any other input is treated as a learner question.\n"
    )
    current_mode = mode
    while True:
        try:
            user_input = input(" > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye!")
            break
        if not user_input:
            continue
        lowered = user_input.lower()
        if lowered in {"/quit", "/exit", "quit", "exit"}:
            print("bye!")
            break
        if lowered.startswith("/ingest "):
            directory = user_input.split(" ", 1)[1]
            handle_ingest(system, directory)
            continue
        if lowered.startswith("/mode "):
            current_mode = user_input.split(" ", 1)[1].strip() or current_mode
            print(f"[info] mode set to '{current_mode}'")
            continue
        handle_question(system, learner_id, user_input, current_mode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive tutor REPL for ai-tutor.")
    parser.add_argument("--learner-id", default="demo_learner", help="Learner identifier for personalization.")
    parser.add_argument("--mode", default="learning", help="Initial tutoring mode passed to the prompt.")
    parser.add_argument("--config", type=Path, default=None, help="Optional path to configuration YAML.")
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY"), help="Override API key.")
    args = parser.parse_args()

    try:
        system = build_system(args.config, api_key=args.api_key)
    except Exception as exc:  # pragma: no cover - initialization errors
        print(f"Failed to initialize TutorSystem: {exc}", file=sys.stderr)
        sys.exit(1)

    repl(system, learner_id=args.learner_id, mode=args.mode)


if __name__ == "__main__":
    main()
