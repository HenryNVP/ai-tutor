# AI Tutor Backend - Quick Reference Summary

## Overview

The AI Tutor backend is a multi-layered system providing intelligent STEM tutoring through natural language interaction. It uses an **agent-first architecture** with specialized agents for different tasks, all orchestrated by a central `TutorAgent`.

## Architecture Layers

```
┌─────────────────────────────────────┐
│   Entry Points (Presentation)        │
│   - Streamlit UI                     │
│   - FastAPI REST API                 │
│   - CLI                              │
│   - Python API                       │
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│   Service Layer (TutorService)       │
│   - Session event processing         │
│   - Source-filtered retrieval        │
│   - Error handling                   │
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│   Core System (TutorSystem)         │
│   - Component lifecycle              │
│   - Configuration management        │
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│   Agent Layer (TutorAgent)           │
│   - Multi-agent orchestration        │
│   - Routing (deterministic + LLM)   │
│   - Session management               │
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│   Specialist Agents                  │
│   - QA Agent (RAG)                   │
│   - Web Agent (current events)       │
│   - Quiz Agent (assessments)         │
│   - Note Agent (summaries)          │
│   - Ingestion Agent (documents)      │
│   - Visualization Agent (plots)      │
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│   Infrastructure                     │
│   - VectorStore (ChromaDB)           │
│   - EmbeddingClient                 │
│   - Retriever                        │
│   - LLM Client                       │
│   - Session Storage (SQLite)        │
└──────────────────────────────────────┘
```

## Key Components

### 1. TutorService (Service Layer)

**Location:** `src/ai_tutor/services/tutor_service.py`

**Purpose:** Abstraction layer between UI and core system

**Key Methods:**
- `answer_question()` - Main Q&A entry point
- `process_event()` - Session event processing
- `retrieve_from_uploaded_documents()` - Source-filtered retrieval
- `create_quiz()` - Quiz generation
- `ingest_directory()` - Document ingestion

**Features:**
- Singleton pattern (cached via `@lru_cache`)
- MCP connection caching
- Tool list caching per session
- Error response generation

### 2. TutorSystem (Core Facade)

**Location:** `src/ai_tutor/system.py`

**Purpose:** Main facade coordinating all components

**Key Responsibilities:**
- Component initialization
- Configuration loading
- Lifecycle management
- Profile management

**Key Methods:**
- `answer_question()` - Orchestrates Q&A flow
- `create_quiz()` - Quiz generation
- `ingest_directory()` - Document ingestion
- `clear_conversation_history()` - Session clearing

### 3. TutorAgent (Orchestrator)

**Location:** `src/ai_tutor/agents/tutor.py`

**Purpose:** Multi-agent orchestrator with routing

**Key Features:**
- Two-tier routing (deterministic + LLM)
- Session management (daily rotation + turn pruning)
- AgentState for inter-agent communication
- Specialist agent delegation

**Routing Flow:**
```
User Query
  ↓
apply_deterministic_routing() [keyword-based]
  ↓ (if no match)
_route_with_llm() [LLM-based]
  ↓
_execute_decision() → Specialist Agent
```

### 4. Specialist Agents

**QA Agent** (`src/ai_tutor/agents/qa.py`)
- Retrieval-augmented generation
- Source filtering support
- Citation generation

**Web Agent** (`src/ai_tutor/agents/web.py`)
- Current events and web search
- URL citations

**Quiz Agent** (`src/ai_tutor/agents/quiz_agent.py`)
- Quiz generation via QuizService
- Dynamic token calculation
- Source-filtered retrieval

**Note Agent** (`src/ai_tutor/agents/note.py`)
- Document summarization
- Study note generation

**Ingestion Agent** (`src/ai_tutor/agents/ingestion.py`)
- Document processing
- Corpus management

**Visualization Agent** (`src/ai_tutor/agents/viz_ui_helper.py`)
- CSV analysis
- Plot generation (matplotlib/seaborn)
- Safe code execution

## API Endpoints

### FastAPI Backend (`apps/api.py`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/answer` | Generate cited answer |
| POST | `/quiz` | Create quiz |
| POST | `/quiz/evaluate` | Evaluate quiz submission |
| POST | `/ingest` | Upload and ingest documents |
| POST | `/sessions/{learner_id}/events` | Process session event |
| GET | `/sessions/{learner_id}` | Get session history |
| POST | `/sessions/{learner_id}/reset` | Clear session history |

### Request/Response Examples

**POST /answer**
```json
{
  "learner_id": "student123",
  "question": "Explain the Bernoulli equation",
  "extra_context": null,
  "source_hints": ["lecture9.pdf"]
}
```

**Response:**
```json
{
  "answer": "...",
  "citations": ["[1] ..."],
  "style": "concise",
  "source": "local",
  "next_topic": null,
  "difficulty": null,
  "hits": [...],
  "quiz": null,
  "route": "qa"
}
```

**POST /sessions/{learner_id}/events**
```json
{
  "session_id": "student123",
  "event": {
    "type": "message",
    "content": "Explain neural networks",
    "source_hints": ["lecture9.pdf"],
    "documents_only": false
  }
}
```

## Session Management

### Session Key Format
```
ai_tutor_{learner_id}_{YYYYMMDD}_{turn_batch}
```

Example: `ai_tutor_student123_20251023_0`

### Automatic Rotation
- **Daily rotation**: New session key each day
- **Turn-based pruning**: New session after `max_turns_per_session` turns (default: 3)
- **History pruning**: Only last 3 turns kept in context

### Storage
- **SQLite**: `data/processed/sessions.sqlite`
- **In-memory cache**: `TutorAgent.sessions: Dict[str, SQLiteSession]`

### Manual Clearing
```python
# API
POST /sessions/{learner_id}/reset

# CLI
python scripts/clear_sessions.py student123

# Python
system.clear_conversation_history(learner_id)
```

## Component Communication

### AgentState Pattern

Specialist agents communicate via shared mutable state:

```python
@dataclass
class AgentState:
    last_hits: List[RetrievalHit]
    last_citations: List[str]
    last_source: Optional[str]
    last_quiz: Optional[Quiz]
```

**Flow:**
1. Agent executes and stores results in `AgentState`
2. Orchestrator collects from `AgentState`
3. Formats into `TutorResponse`
4. State reset for next query

**Benefits:**
- Loose coupling between agents
- No direct agent-to-agent calls
- Centralized result collection

## Data Storage

### Directory Structure
```
data/
├── raw/                      # Original documents
├── uploads/                  # CSV files
├── processed/
│   ├── chunks.jsonl         # Chunk storage
│   ├── profiles/            # Learner profiles
│   └── sessions.sqlite      # Session history
└── vector_store/            # ChromaDB data
    ├── chroma.sqlite3
    └── {collection_id}/
```

### Vector Store (ChromaDB)

**Domain Collections:**
- Separate collection per domain: `ai_tutor_{domain}`
- Domains: math, physics, cs, chemistry, biology, general
- Metadata: chunk_id, title, doc_id, page, source_path, domain

**Source Filtering:**
- Pre-filter by filename before similarity search
- 320x speedup for document-specific queries
- Query format: `Query(text="...", source_filter=["file.pdf"])`

## Key Design Patterns

### 1. Service Layer Pattern
- Abstraction between UI and core
- Shared singleton for all requests
- Error handling and logging

### 2. Agent-First Architecture
- Specialized agents for different tasks
- Natural language routing
- Shared state for communication

### 3. Source Filtering
- Document-specific queries
- Pre-filtering before similarity search
- Filename variation handling

### 4. Session Rotation
- Automatic daily rotation
- Turn-based pruning
- Prevents token overflow

## Performance Optimizations

1. **Source Filtering**: 320x speedup for document queries
2. **Domain Collections**: Reduced search space
3. **Embedding Caching**: Embeddings computed once during ingestion
4. **Batch Processing**: Embeddings in batches (256 chunks)
5. **In-Memory Session Cache**: Fast access to active sessions
6. **History Pruning**: Only last 3 turns in context

## Error Handling

**Layered Approach:**
1. Component level: Try/except in methods
2. Service level: Error responses for UI
3. API level: HTTP exceptions with details
4. Logging: Comprehensive logging at all levels

**Error Response:**
```python
TutorResponse(
    answer="I encountered an error: {message}",
    route="error",
    ...
)
```

## Configuration

**Location:** `config/default.yaml`

**Key Settings:**
- Model configuration (gpt-4o-mini)
- Retrieval settings (top_k, thresholds)
- Chunking parameters (size, overlap)
- Paths (data directories)

## Testing

**Test Files:**
- `tests/test_e2e_use_cases.py` - End-to-end workflows
- `tests/test_quiz_api.py` - Quiz generation
- `tests/test_routing.py` - Routing logic
- `tests/test_sessions.py` - Session management

## Documentation

- **Implementation Review**: `docs/IMPLEMENTATION_REVIEW.md`
- **Architecture Diagrams**: `docs/architecture.puml`
- **Component Diagrams**: `docs/components.puml`
- **Session Management**: `docs/session_management.puml`
- **Backend API**: `docs/backend_api.md`
- **Session API**: `docs/session_api.md`

## Quick Start

### Start FastAPI Backend
```bash
uvicorn apps.api:app --reload --port 8080
```

### Start Streamlit UI
```bash
streamlit run apps/ui.py
```

### Environment Variables
```bash
export OPENAI_API_KEY=your_key_here
export API_ALLOW_ORIGINS=*  # Optional, defaults to *
export MCP_USE_SERVER=true  # Optional, for MCP integration
```

## Key Files Reference

| Component | File Path |
|-----------|-----------|
| FastAPI App | `apps/api.py` |
| Service Layer | `src/ai_tutor/services/tutor_service.py` |
| Core System | `src/ai_tutor/system.py` |
| Orchestrator | `src/ai_tutor/agents/tutor.py` |
| Routing | `src/ai_tutor/agents/routing.py` |
| QA Agent | `src/ai_tutor/agents/qa.py` |
| Quiz Service | `src/ai_tutor/learning/quiz.py` |
| Vector Store | `src/ai_tutor/retrieval/chroma_store.py` |
| Ingestion | `src/ai_tutor/ingestion/pipeline.py` |
| Session Models | `src/ai_tutor/data_models/session.py` |

---

For detailed information, see:
- [Implementation Review](IMPLEMENTATION_REVIEW.md) - Comprehensive architecture review
- [Backend API](backend_api.md) - API documentation
- [Session API](session_api.md) - Session management details

