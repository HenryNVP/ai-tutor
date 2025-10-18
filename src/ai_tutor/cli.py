from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ai_tutor.agents.openai_sdk import TutorOpenAIAgent
from ai_tutor.learning.models import CoursePlan
from ai_tutor.system import TutorSystem

app = typer.Typer(help="Personal STEM Instructor CLI")
console = Console()


def _load_system(config: Optional[Path], api_key: Optional[str]) -> TutorSystem:
    return TutorSystem.from_config(config, api_key=api_key)


@app.command()
def ingest(
    directory: Path = typer.Argument(..., exists=True, file_okay=False, readable=True),
    config: Optional[Path] = typer.Option(None, help="Path to configuration YAML."),
    api_key: Optional[str] = typer.Option(None, help="LLM API key."),
):
    """Ingest documents from a directory into the tutor's knowledge base."""
    system = _load_system(config, api_key)
    result = system.ingest_directory(directory)
    console.print(f"Ingested {len(result.documents)} documents into {len(result.chunks)} chunks.")
    if result.skipped:
        console.print(f"Skipped {len(result.skipped)} files:")
        for path in result.skipped:
            console.print(f"- {path}")


@app.command()
def ask(
    learner_id: str = typer.Argument(...),
    question: str = typer.Argument(...),
    mode: str = typer.Option("learning", help="learning|practice|exam"),
    config: Optional[Path] = typer.Option(None),
    api_key: Optional[str] = typer.Option(None),
):
    """Ask the tutor a question."""
    system = _load_system(config, api_key)
    response = system.answer_question(learner_id=learner_id, question=question, mode=mode)
    console.print("[bold]Answer[/bold]")
    console.print(response.answer)
    if response.citations:
        console.print("\n[bold]Citations[/bold]")
        for citation in response.citations:
            console.print(f"- {citation}")
    if response.guardrail_reason:
        console.print(f"[yellow]Guardrail note:[/yellow] {response.guardrail_reason}")


def _render_course_plan(course_plan: CoursePlan):
    table = Table(title=course_plan.course_title)
    table.add_column("Unit")
    table.add_column("Focus Topics")
    table.add_column("Lessons")
    for unit in course_plan.units:
        lesson_titles = "\n".join(lesson.title for lesson in unit.lessons)
        table.add_row(unit.title, ", ".join(unit.focus_topics), lesson_titles)
    console.print(table)


@app.command()
def plan(
    learner_id: str = typer.Argument(...),
    domain: str = typer.Option("math"),
    config: Optional[Path] = typer.Option(None),
    api_key: Optional[str] = typer.Option(None),
):
    """Generate a syllabus-style course plan."""
    system = _load_system(config, api_key)
    course_plan = system.plan_course(learner_id=learner_id, domain=domain)
    _render_course_plan(course_plan)


@app.command()
def assessment(
    learner_id: str = typer.Argument(...),
    domain: str = typer.Option("math"),
    config: Optional[Path] = typer.Option(None),
    api_key: Optional[str] = typer.Option(None),
):
    """Generate a formative assessment for the first unit of the course plan."""
    system = _load_system(config, api_key)
    course_plan = system.plan_course(learner_id=learner_id, domain=domain)
    assessment = system.generate_assessment(course_plan, unit_index=0)
    console.print(f"[bold]{assessment.title}[/bold]")
    for idx, item in enumerate(assessment.items, start=1):
        console.print(f"\n[{idx}] {item.question}")
        if item.choices:
            for option in item.choices:
                console.print(f"  - {option}")
        console.print(f"Answer: {item.answer}")
        console.print(f"Rationale: {item.rationale}")


@app.command()
def feedback(
    learner_id: str = typer.Argument(...),
    config: Optional[Path] = typer.Option(None),
    api_key: Optional[str] = typer.Option(None),
):
    """Summarize learner strengths, focus areas, and suggested next steps."""
    system = _load_system(config, api_key)
    report = system.get_feedback(learner_id)
    for section, items in report.items():
        console.print(f"\n[bold]{section.replace('_', ' ').title()}[/bold]")
        for item in items:
            console.print(f"- {item}")


@app.command()
def agent(
    task: str = typer.Argument(..., help="High-level instruction for the tutor agent."),
    learner_id: str = typer.Option("demo_learner", help="Learner identifier to operate on."),
    config: Optional[Path] = typer.Option(None, help="Path to configuration YAML."),
    api_key: Optional[str] = typer.Option(None, help="API key for the underlying model provider."),
    model: Optional[str] = typer.Option(None, help="Override the model used by the OpenAI Agent."),
):
    """Execute a high-level instruction using the OpenAI Agents SDK."""
    system = _load_system(config, api_key)
    agent_runner = TutorOpenAIAgent(tutor_system=system, model_name=model, api_key=api_key)
    result = agent_runner.run(task, learner_id=learner_id)
    console.print("[bold]Agent Output[/bold]")
    console.print(result.final_output)


if __name__ == "__main__":
    app()
