# Personal STEM Instructor (MVP)

This MVP is a local-first tutoring agent that ingests STEM study materials, embeds them with Gemini, and answers questions with grounded citations. The same Gemini API key powers both the generative model and the embedding model, and results are persisted locally for repeatable use.

## Features

- **Document ingestion & chunking** – parse PDF/Markdown/text notes, produce overlapping chunks, and enrich them with metadata for citations.
- **Gemini embeddings** – call `gemini-embedding-001` via the Google Generative AI API (768-d vectors) using the same key as the chat model.
- **Lightweight retrieval + tutoring** – cosine-search a local NumPy store, assemble a context window, and ask the chat model for a cited answer.
- **OpenAI Agents SDK bridge** – expose ingestion and Q&A as tools so you can orchestrate workflows with the OpenAI Agents runtime.

## Project layout

```
src/ai_tutor/
  agents/        # LLM client, context builder, tutor agent, OpenAI SDK adapter
  config/        # Pydantic settings + YAML loader
  ingestion/     # Parsers, chunker, embedding client, ingestion pipeline
  retrieval/     # Simple cosine vector store + retriever
  storage/       # JSONL persistence for ingested chunks
  utils/         # Logging + filesystem helpers
  system.py      # High-level façade wiring ingestion + Q&A together
config/default.yaml  # Editable runtime configuration
scripts/openstax_ingest.py  # Example ingestion helper
```

## Quick start

Install dependencies (Python 3.10+):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Set environment variables for your model provider (example uses Gemini through `litellm` plus Google Generative AI embeddings):

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

Use the OpenAI Agent wrapper to orchestrate everything:

```bash
ai-tutor agent "Summarize the key equations for projectile motion." --learner-id student123
```

## Configuration

Tweak `config/default.yaml` to change models, chunk sizes, retrieval depth, and storage paths. Override values at runtime through the `AI_TUTOR_CONFIG_OVERRIDES` env var (JSON) or by pointing `--config` at another YAML file.

Key settings:

- `model` – chat model name/provider (Litellm-compatible; defaults to Gemini `gemini-1.5-pro`).
- `embeddings` – embedding model, provider (`google-genai`), batch size, and optional dimensionality override.
- `chunking` – character window and overlap for RAG chunks.
- `retrieval` – number of nearest neighbours (`top_k`) returned from the vector store.
- `paths` – where raw data, processed chunks, and vector store files live.

## Logging & storage

- Raw files stay under `data/raw`; derived chunks (`data/processed/chunks.jsonl`) and embeddings (`data/vector_store/`) persist locally.
- Logging is configured via `structlog`; adjust verbosity in `config/default.yaml`.

## Next steps

- Add safety or heuristic filters before answering.
- Layer on reranking / hybrid retrieval for tougher corpora.
- Extend the agent toolkit with workflows like summarization or practice generation once the corpus is stable.
