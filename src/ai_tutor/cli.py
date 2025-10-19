from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from ai_tutor.agents.openai_sdk import TutorOpenAIAgent
from ai_tutor.system import TutorSystem

app = typer.Typer(help="Minimal STEM tutor CLI backed by local corpus + LLM.")
console = Console()


def _load_system(config: Optional[Path], api_key: Optional[str]) -> TutorSystem:
    return TutorSystem.from_config(config, api_key=api_key)


@app.command()
def ingest(
    directory: Path = typer.Argument(..., exists=True, file_okay=False, readable=True),
    config: Optional[Path] = typer.Option(None, help="Path to configuration YAML."),
    api_key: Optional[str] = typer.Option(None, help="Model API key."),
):
    """Ingest documents from a directory into the tutor's vector store."""
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
    """Ask a grounded question against the ingested corpus."""
    system = _load_system(config, api_key)
    response = system.answer_question(learner_id=learner_id, question=question, mode=mode)
    console.print("[bold]Answer[/bold]")
    console.print(response.answer)
    if response.citations:
        console.print("\n[bold]Citations[/bold]")
        for citation in response.citations:
            console.print(f"- {citation}")


@app.command()
def agent(
    task: str = typer.Argument(..., help="High-level instruction for the tutor agent."),
    learner_id: str = typer.Option("demo_learner", help="Learner identifier."),
    config: Optional[Path] = typer.Option(None, help="Path to configuration YAML."),
    api_key: Optional[str] = typer.Option(None, help="API key for both LLM and embeddings."),
    model: Optional[str] = typer.Option(None, help="Override the model used by the agent runner."),
):
    """Run the OpenAI Agents SDK wrapper to orchestrate ingestion + Q&A."""
    system = _load_system(config, api_key)
    agent_runner = TutorOpenAIAgent(tutor_system=system, model_name=model, api_key=api_key)
    result = agent_runner.run(task, learner_id=learner_id)
    console.print("[bold]Agent Output[/bold]")
    console.print(result.final_output)


if __name__ == "__main__":
    app()
