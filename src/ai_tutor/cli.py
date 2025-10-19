from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

from ai_tutor.agents.openai_sdk import TutorOpenAIAgent
from ai_tutor.system import TutorSystem

app = typer.Typer(help="Minimal STEM tutor CLI backed by local corpus + LLM.")
console = Console()

if load_dotenv:
    candidate_paths = [Path.cwd() / ".env"]
    module_root = Path(__file__).resolve().parents[2]
    module_env = module_root / ".env"
    if module_env not in candidate_paths:
        candidate_paths.append(module_env)
    for env_path in candidate_paths:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)
            break
    else:  # fallback to default discovery but ignore missing-file assertion
        try:
            load_dotenv(override=False)
        except AssertionError:
            pass


def _load_system(config: Optional[Path], api_key: Optional[str]) -> TutorSystem:
    """Instantiate `TutorSystem` with optional config overrides and API key."""
    return TutorSystem.from_config(config, api_key=api_key)


@app.command()
def ingest(
    directory: Path = typer.Argument(..., exists=True, file_okay=False, readable=True),
    config: Optional[Path] = typer.Option(None, help="Path to configuration YAML."),
    api_key: Optional[str] = typer.Option(None, help="Model API key."),
):
    """
    Parse, chunk, and embed all supported documents in a directory.

    Loads a `TutorSystem` via `_load_system`, calls `TutorSystem.ingest_directory`
    (which delegates to `IngestionPipeline.ingest_paths` and the vector store), then reports
    document and chunk counts along with any skipped files back to the user via Rich.
    """
    system = _load_system(config, api_key)
    result = system.ingest_directory(directory)
    console.print(f"Ingested {len(result.documents)} documents into {len(result.chunks)} chunks.")
    if result.skipped:
        console.print("Skipped files:")
        for path in result.skipped:
            console.print(f"- {path}")


@app.command()
def ask(
    learner_id: str = typer.Argument(...),
    question: str = typer.Argument(...),
    mode: str = typer.Option("learning", help="Label to pass through to the prompt."),
    config: Optional[Path] = typer.Option(None),
    api_key: Optional[str] = typer.Option(None),
):
    """
    Ask the tutor for a grounded answer with citations.

    Instantiates `TutorSystem`, invokes `TutorSystem.answer_question` which orchestrates the
    `TutorAgent`, `Retriever`, and `LLMClient`, and renders the final answer plus citations
    to the terminal using Rich formatting.
    """
    system = _load_system(config, api_key)
    response = system.answer_question(learner_id=learner_id, question=question, mode=mode)
    console.print("[bold]Answer[/bold]")
    console.print(response.answer)
    if response.citations:
        console.print("\n[bold]Citations[/bold]")
        for citation in response.citations:
            console.print(f"- {citation}")
    console.print("\n[bold]Personalization[/bold]")
    console.print(f"Style: {response.style}")
    if response.difficulty:
        console.print(f"Difficulty focus: {response.difficulty}")
    if response.next_topic:
        console.print(f"Suggested next topic: {response.next_topic}")


@app.command()
def agent(
    task: str = typer.Argument(..., help="High-level instruction for the tutor agent."),
    learner_id: str = typer.Option("demo_learner", help="Learner identifier."),
    config: Optional[Path] = typer.Option(None, help="Path to configuration YAML."),
    api_key: Optional[str] = typer.Option(None, help="API key for both LLM and embeddings."),
    model: Optional[str] = typer.Option(None, help="Override the model used by the agent runner."),
):
    """
    Run the OpenAI Agents SDK wrapper so an agent can call tutor tools.

    Boots a `TutorSystem`, wraps it in `TutorOpenAIAgent` to expose the ingest and answer tools,
    forwards the task to `TutorOpenAIAgent.run`, and prints the agent's final output block.
    """
    system = _load_system(config, api_key)
    agent_runner = TutorOpenAIAgent(tutor_system=system, model_name=model, api_key=api_key)
    result = agent_runner.run(task, learner_id=learner_id)
    console.print("[bold]Agent Output[/bold]")
    console.print(result.final_output)


if __name__ == "__main__":
    app()
