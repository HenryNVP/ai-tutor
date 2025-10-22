from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

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

    Instantiates `TutorSystem`, streams the response from the multi-agent tutor workflows,
    and renders the final answer plus citations to the terminal using Rich formatting.
    """
    system = _load_system(config, api_key)
    console.print("[bold]Answer[/bold]")

    def stream_printer(text: str) -> None:
        console.print(text, end="", soft_wrap=True, highlight=False)

    response = system.answer_question(
        learner_id=learner_id,
        question=question,
        mode=mode,
        on_delta=stream_printer,
    )
    console.print()  # newline after streaming output
    if response.citations:
        console.print("\n[bold]Citations[/bold]")
        for citation in response.citations:
            console.print(f"- {citation}")
    # console.print("\n[bold]Personalization[/bold]")
    # console.print(f"Style: {response.style}")
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
    agent_role: str = typer.Option(
        "tutor",
        help="Which agent to run. Options: 'tutor' (default) for Q&A, 'ingest' for ingestion.",
    ),
):
    """
    Run OpenAI Agents directly to invoke TutorSystem tools.

    Builds dedicated ingestion and tutoring agents backed by OpenAI's Responses API, each with
    their own tool stack. Select the desired role to orchestrate ingestion or answer questions.
    """
    try:
        from agents import Agent, Runner, WebSearchTool, function_tool, set_trace_processors, set_tracing_disabled
        from agents.models.openai_responses import OpenAIResponsesModel
        from agents.tracing.processors import default_processor
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise typer.BadParameter(
            "The agent command requires the optional 'openai-agents' package. "
            "Install it with `pip install openai-agents`."
        ) from exc

    system = _load_system(config, api_key)

    resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not resolved_api_key:
        raise typer.BadParameter("OPENAI_API_KEY must be provided via environment or --api-key.")

    resolved_model = model or system.settings.model.name

    set_tracing_disabled(disabled=False)
    set_trace_processors([default_processor()])

    @function_tool
    def ingest_corpus(directory: str) -> str:
        path = Path(directory)
        if not path.exists() or not path.is_dir():
            return json.dumps({"error": f"The provided directory {directory} does not exist."})
        result = system.ingest_directory(path)
        payload = {
            "documents_ingested": len(result.documents),
            "chunks_created": len(result.chunks),
            "skipped_files": [str(item) for item in result.skipped],
        }
        return json.dumps(payload)

    @function_tool
    def answer_question(learner_id: str, question: str, mode: str = "learning") -> str:
        response = system.answer_question(learner_id=learner_id, question=question, mode=mode)
        payload = {
            "answer": response.answer,
            "citations": response.citations,
            "style": response.style,
            "difficulty": response.difficulty,
            "next_topic": response.next_topic,
        }
        return json.dumps(payload)

    ingest_agent = Agent(
        name="TutorIngestionAgent",
        instructions=(
            "You ingest new study materials into the learner's local knowledge base. "
            "Use the ingest_corpus tool when asked to add content. Respond concisely after each action."
        ),
        model=OpenAIResponsesModel(model=resolved_model, api_key=resolved_api_key),
        tools=[ingest_corpus],
    )

    tutor_agent = Agent(
        name="TutorAnswerAgent",
        instructions=(
            "You answer learner questions using the available tools. "
            "Prefer the local corpus and cite supporting chunks with bracketed indices like [1]. "
            "If local evidence is insufficient, call the web_search tool to gather reputable sources "
            "and cite the returned URLs. If no evidence is found, state that and suggest next steps."
        ),
        model=OpenAIResponsesModel(model=resolved_model, api_key=resolved_api_key),
        tools=[answer_question, WebSearchTool()],
    )

    agents = {
        "ingest": ingest_agent,
        "tutor": tutor_agent,
    }

    if agent_role not in agents:
        raise typer.BadParameter("agent-role must be one of: " + ", ".join(agents))

    selected_agent = agents[agent_role]
    prompt = task if agent_role == "ingest" else f"Learner ID: {learner_id}\nTask: {task}"

    result = asyncio.run(Runner.run(selected_agent, prompt))
    console.print("[bold]Agent Output[/bold]")
    console.print(result.final_output)


if __name__ == "__main__":
    app()
