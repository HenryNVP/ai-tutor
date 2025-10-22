# Personal STEM Instructor (MVP)

This MVP is a local-first tutoring agent that ingests STEM study materials, embeds them with sentence-transformer models, and answers questions with grounded citations using OpenAI's chat completions API. Results are persisted locally for repeatable use.

## Features

- **Document ingestion & chunking** – parse PDF/Markdown/text notes, produce overlapping chunks, and enrich them with metadata for citations.
- **Sentence-transformer embeddings** – encode chunks locally (default `BAAI/bge-base-en`) so you retain control of the retrieval index.
- **Lightweight retrieval + tutoring** – cosine-search a local NumPy store, assemble a context window, and ask the chat model for a cited answer.
- **OpenAI Agents SDK bridge** – create ingestion and tutoring agents directly with the OpenAI Agents runtime (no custom wrapper required).

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

## Architecture overview

- **TutorSystem** wires ingestion, retrieval, personalization, and the multi-agent tutor workflow. Its `ingest_directory` and `answer_question` methods are shared by the CLI, demo REPL, and Agents examples.
- **IngestionPipeline** normalizes raw documents: parsers load files, `Chunker` slices text, `EmbeddingClient` encodes slices, and `VectorStore` plus `ChunkJsonlStore` persist embeddings and citation metadata.
- **TutorAgent** orchestrates local QA and web-search fallback agents, streaming responses back to callers while the CLI/demo interfaces handle ingestion commands separately.
- **SearchTool** encapsulates the OpenAI web search tool, ensuring fallback answers cite URL sources when the local corpus lacks evidence.

The diagrams in `docs/architecture.puml` and `docs/components.puml` illustrate component relationships and data flow in more detail.

## Quick start

Install dependencies (Python 3.10+):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Set environment variables for your model provider (example uses OpenAI for chat plus optional Google Generative AI embeddings if you switch providers):

```bash
export OPENAI_API_KEY=...
```

Run ingestion on a directory of PDFs/Markdown/txt files:

```bash
ai-tutor ingest ./data/raw
```

Ask a grounded question:

```bash
ai-tutor ask student123 "Explain the steps to solve projectile motion problems."
```

Use the OpenAI Agents runtime to orchestrate everything:

```bash
ai-tutor agent --agent-role tutor "Summarize the key equations for projectile motion." --learner-id student123

# Ingestion agent example
ai-tutor agent --agent-role ingest "Ingest the files under ./data/raw/openstax" --learner-id student123
```

> **Note:** The optional `ai-tutor agent` command depends on the `openai-agents` runtime. Install it separately (`pip install openai-agents`) if you need that workflow; the core CLI (`ingest` / `ask`) only requires the dependencies listed above.

## Configuration

Tweak `config/default.yaml` to change models, chunk sizes, retrieval depth, and storage paths. Override values at runtime through the `AI_TUTOR_CONFIG_OVERRIDES` env var (JSON) or by pointing `--config` at another YAML file.

Key settings:

- `model` – chat model name/provider (defaults to OpenAI `gpt-4o-mini`).
- `embeddings` – embedding model, provider (`sentence-transformers` by default), batch size, and optional dimensionality override.
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
