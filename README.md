# Personal STEM Instructor

The Personal STEM Instructor is a local-first tutoring agent that ingests your study materials, retrieves grounded context, plans courses, generates lessons and assessments, and tracks learner progress. It targets high-school to pre-college domains across mathematics, physics, and computer science.

## Features

- **Corpus ingestion & RAG** – Parse PDF, Markdown, or plaintext notes, chunk and embed them with MiniLM/BGE models, and store vectors locally for fast retrieval.
- **Guardrailed tutoring** – Retrieve context with similarity thresholds, refuse unsafe topics, and fall back to the search tool only when corpus coverage is insufficient.
- **Course planning** – Produce multi-week syllabi with units, lesson objectives, examples, and practice suggestions tailored per learner profile.
- **Assessments & feedback** – Generate formative quizzes with MCQ and short-answer items, log attempts, update mastery, and surface next steps.
- **Progress tracking** – Maintain per-learner profiles on disk (JSON) covering mastery metrics, struggles, attempts, and time-on-task.
- **OpenAI Agents SDK integration** – Drive complex tutoring workflows through function-call tools powered by the OpenAI Agents SDK.

## Project layout

```
src/ai_tutor/
  config/            # Pydantic schemas and YAML loader
  ingestion/         # Parsers, chunkers, embeddings, and ingestion pipeline
  retrieval/         # Vector store (cosine) and retrieval orchestration
  agents/            # LLM client, context builders, tutor agent
  guardrails/        # Safety & integrity checks on retrieval hits
  learning/          # Course planning, lessons, assessments, progress
  search/            # Search tool interface (stub implementation)
  utils/             # Logging and filesystem helpers
  system.py          # High-level facade that wires everything together
config/default.yaml  # Editable runtime configuration
```

## Quick start

Install dependencies (Python 3.10+):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Set environment variables for your model provider (example uses Gemini via `litellm`; you can also supply `OPENAI_API_KEY`):

```bash
export GEMINI_API_KEY=...
export GEMINI_MODEL_NAME=gemini-1.5-pro
```

Run ingestion on a directory of PDFs/Markdown/txt files:

```bash
ai-tutor ingest ./data/raw
```

Ask a grounded question:

```bash
ai-tutor ask student123 "Explain the steps to solve projectile motion problems."
```

Generate a course plan and assessment:

```bash
ai-tutor plan student123 --domain physics
ai-tutor assessment student123 --domain physics
```

Review personalized feedback:

```bash
ai-tutor feedback student123
```

Kick off the OpenAI Agent to orchestrate tools automatically:

```bash
ai-tutor agent "Design a two-week review plan for energy conservation." --learner-id student123
```

## Configuration

Tweak `config/default.yaml` to change models, chunk sizes, retrieval thresholds, syllabus defaults, and storage paths. Override values at runtime by setting `AI_TUTOR_CONFIG_OVERRIDES` to a JSON object, or by providing an alternate YAML file with `--config path/to/config.yaml`.

Key settings:

- `model` – chat model name/provider (Litellm-compatible).
- `embeddings` – embedding model and batch size (MiniLM for dev, BGE for prod).
- `chunking` – token window and overlap for RAG chunks.
- `retrieval` – `initial_k`, `top_k`, and minimum similarity score.
- `guardrails` – minimum evidence thresholds, integrity mode, blocked topics.
- `course_defaults` – syllabus length, lesson cadence, default domains.

## Logging & storage

- Raw files remain in `data/raw`; derived content (chunks, learner profiles, vector store) lives under `data/processed`.
- Retrieval calls, ingestion, and tutor responses are logged via `structlog`. Adjust verbosity in the config file.

## Next steps

This foundation is ready for:

- Wiring in a production-grade search tool implementation.
- Adding reranking and hybrid dense/sparse retrieval.
- Enforcing academic integrity modes (`practice` and `exam`) with more granular responses.
- Integrating UI layers (web/desktop) on top of the CLI facade.
