# Personal STEM Instructor (MVP)

This MVP is a local-first tutoring agent that ingests STEM study materials, embeds them with sentence-transformer models, and answers questions with grounded citations using OpenAI's chat completions API. Results are persisted locally for repeatable use.

## Features

### Core Capabilities
- **Document ingestion & chunking** – parse PDF/Markdown/text notes, produce overlapping chunks, and enrich them with metadata for citations.
- **Sentence-transformer embeddings** – encode chunks locally (default `BAAI/bge-base-en`) so you retain control of the retrieval index.
- **Multi-agent architecture** – orchestrator routes questions to specialist agents (QA, web search, ingestion) for optimal answers with citations.
- **Hybrid retrieval** – searches local course materials first, falls back to web search when needed, always with proper source attribution.

### Learning Features
- **Interactive quiz generation** – generate personalized multiple-choice quizzes on any topic based on learner profiles and course materials.
- **Adaptive learner profiles** – track learner strengths, struggles, concepts mastered, and study time with automatic updates based on quiz performance.
- **Personalized difficulty** – system adapts question difficulty based on performance (foundational guidance → guided practice → independent challenge).

### Technical Features
- **OpenAI Agents SDK** – leverages the official OpenAI Agents runtime for sophisticated multi-agent workflows.
- **Session management** – automatic daily rotation prevents token overflow while maintaining conversation context.
- **Smart routing** – STEM questions automatically get cited answers from course materials or web sources.

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

### System Components

- **TutorSystem** – High-level façade that wires ingestion, retrieval, personalization, and the multi-agent tutor workflow. Provides `ingest_directory`, `answer_question`, `generate_quiz`, and `evaluate_quiz` methods.

- **Multi-Agent Architecture**:
  - **Orchestrator Agent** – Routes questions to the appropriate specialist agent based on content type
  - **QA Agent** – Retrieves and cites local course materials for STEM questions
  - **Web Agent** – Searches the web for current events or when local materials are insufficient
  - **Ingestion Agent** – Handles document upload and indexing requests

- **IngestionPipeline** – Normalizes raw documents: parsers load files, `Chunker` slices text, `EmbeddingClient` encodes slices, and `VectorStore` plus `ChunkJsonlStore` persist embeddings and citation metadata.

- **PersonalizationManager** – Manages learner profiles, tracks progress, and adapts content difficulty based on quiz performance and interaction history.

- **Session Management** – Date-based session rotation automatically prevents token overflow while maintaining same-day conversation context.

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

## Quiz Application

The project includes an interactive quiz interface built with Streamlit that generates personalized quizzes and automatically updates learner profiles based on performance.

### Running the Quiz App

```bash
streamlit run scripts/quiz_app.py
```

The quiz app provides:
- **Topic-based quiz generation** – Enter any topic to generate 3-8 multiple-choice questions
- **Real-time profile tracking** – View learner strengths, struggles, and preferences in the sidebar
- **Automatic profile updates** – Quiz results update domain strengths, concepts mastered, and study time
- **Detailed feedback** – See explanations and references for each answer

### Demo Script

See profile updates in action with the demo script:

```bash
python scripts/demo_profile_update.py
```

This demonstrates how quiz performance affects learner profiles, including strength/struggle scores, difficulty preferences, and concepts mastered.

For more details, see the [Quiz Profile Updates Documentation](docs/quiz_profile_updates.md).

## Session Management

The system automatically manages conversation sessions to prevent token overflow:

- **Automatic daily rotation** – Sessions reset each day, limiting context to same-day conversations
- **Persistent across restarts** – Sessions are stored in SQLite and survive application restarts
- **Manual clearing** – Clear sessions when needed using the management script

```bash
# View current sessions
python scripts/clear_sessions.py

# Clear specific learner's session
python scripts/clear_sessions.py student123

# Clear all sessions
python scripts/clear_sessions.py all
```

Sessions use `gpt-4o-mini` (200K TPM limit) to handle large conversation histories efficiently.

For technical details, see [Token Overflow Fix Documentation](docs/TOKEN_OVERFLOW_FIX.md).

## Multi-Agent Routing

Questions are intelligently routed to specialist agents:

**STEM Questions** → QA Agent → (if needed) Web Agent
- "What is the Bernoulli equation?"
- "Explain Newton's laws"
- "How does photosynthesis work?"
- Results include **citations** from course materials or web sources

**Current Events / Non-STEM** → Web Agent
- "What's the weather tomorrow in San Jose?"
- "Recent developments in AI"
- Results include **URL citations**

**System Questions** → Orchestrator (direct answer)
- "What can you help me with?"
- "What's my learning progress?"

For implementation details, see [Handoff Logic Documentation](docs/HANDOFF_FIX_V2.md).

## Configuration

Tweak `config/default.yaml` to change models, chunk sizes, retrieval depth, and storage paths. Override values at runtime through the `AI_TUTOR_CONFIG_OVERRIDES` env var (JSON) or by pointing `--config` at another YAML file.

Key settings:

- `model` – chat model name/provider (defaults to OpenAI `gpt-4o-mini`).
- `embeddings` – embedding model, provider (`sentence-transformers` by default), batch size, and optional dimensionality override.
- `chunking` – character window and overlap for RAG chunks.
- `retrieval` – number of nearest neighbours (`top_k`) returned from the vector store.
- `paths` – where raw data, processed chunks, and vector store files live.

## Logging & Storage

### Data Persistence
- **Raw files**: `data/raw/` – Original PDFs, Markdown, text files
- **Processed chunks**: `data/processed/chunks.jsonl` – Extracted and chunked content
- **Embeddings**: `data/vector_store/` – Sentence-transformer vectors (NumPy format)
- **Learner profiles**: `data/processed/profiles/` – JSON files tracking progress and preferences
- **Sessions**: `data/processed/sessions.sqlite` – Conversation history (auto-rotates daily)

### Logging
Logging is configured via `structlog`; adjust verbosity in `config/default.yaml`.

Use `DEBUG` level to see:
- Agent handoff events
- Tool calls (retrieve_local_context, web_search)
- Session creation and rotation
- Profile updates

## Troubleshooting

### Token Overflow Errors
If you see "Request too large" errors:
```bash
# Clear the session
python scripts/clear_sessions.py <learner_id>
```
Sessions automatically rotate daily to prevent this.

### Questions Not Getting Citations
Check that:
1. STEM questions are being routed to `qa_agent` (check logs for handoff events)
2. Either local materials exist OR web search is enabled
3. Agents are using `gpt-4o-mini` model (check agent configurations)

See `docs/HANDOFF_FIX_V2.md` for detailed debugging steps.

### Quiz Profile Not Updating
Ensure:
1. You're using the same `learner_id` for quiz generation and evaluation
2. Profile directory exists: `data/processed/profiles/`
3. Check logs for "Profile updated" messages

See `docs/quiz_profile_updates.md` for details.

## Documentation

- **[Architecture Overview](docs/architecture.puml)** – System component diagrams
- **[Handoff Logic Fix](docs/HANDOFF_FIX_V2.md)** – Multi-agent routing implementation
- **[Token Overflow Fix](docs/TOKEN_OVERFLOW_FIX.md)** – Session management and limits
- **[Quiz Profile Updates](docs/quiz_profile_updates.md)** – Adaptive learning system
- **[Retrieval Evaluation](docs/retrieval_evaluation.md)** – Vector store performance

## Development Notes

### Model Selection
All agents use `gpt-4o-mini` for:
- ✅ Higher TPM limits (200K vs 30K)
- ✅ Lower cost (16x cheaper than gpt-4o)
- ✅ Sufficient quality for routing and QA tasks

### Agent Architecture
- **Orchestrator**: Routes questions only, doesn't answer
- **QA Agent**: Must call `retrieve_local_context` before answering
- **Web Agent**: Must call `web_search` before answering
- All specialist agents provide citations

### Session Limits
- Daily rotation prevents unbounded growth
- Date-based session IDs: `ai_tutor_{learner_id}_{YYYYMMDD}`
- Manual clearing available via `clear_sessions.py` script

## Contributing

When extending the system:

1. **Add new agents** via `src/ai_tutor/agents/` following existing patterns
2. **Update orchestrator** routing rules in `tutor.py` to include new agent
3. **Test handoff behavior** to ensure proper delegation
4. **Document changes** in relevant markdown files

## Next Steps

- Add safety or heuristic filters before answering
- Layer on reranking / hybrid retrieval for tougher corpora
- Implement spaced repetition for quiz topics
- Add concept prerequisite tracking
- Support multi-turn problem-solving workflows
