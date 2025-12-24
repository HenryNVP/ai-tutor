# Architecture Overview

## System Design

### Agent-First Architecture
- **Orchestrator** routes requests to specialized agents
- **Specialized Agents**: QA, Quiz, Note, Visualization, Web, Ingestion
- **Keyword-based routing** (simplified, no LLM fallback)

### Core Components

1. **TutorSystem** - Main facade coordinating all components
2. **TutorAgent** - Multi-agent coordinator with routing logic
3. **Vector Store** - ChromaDB for document retrieval
4. **Session Management** - SQLite-based, one session per learner
5. **MCP Servers** - Optional tool access (Filesystem, ChromaDB)

## Data Flow

### Document Ingestion
```
PDF/TXT/MD → Chunking → Embeddings → ChromaDB Storage
```

### Q&A Flow
```
Question → Routing → QA Agent → Retrieval → LLM → Response with Citations
```

### Quiz Generation
```
Request → Quiz Agent → Document Retrieval → LLM → Quiz Questions
```

### Note Generation
```
Request → Note Agent → Full Document Fetch → LLM → Structured Notes
```

## Session Management

- **Simplified**: One session per learner (`ai_tutor_{learner_id}`)
- **Storage**: SQLite database
- **No rotation or pruning** (simplified for demo)

## Demo Mode

When `demo_mode: true`:
- Personalization disabled
- Static "stepwise" style
- No profile loading/saving
- Faster startup

## API Endpoints

- `GET /health` - Health check
- `POST /answer` - Answer questions
- `POST /quiz` - Create quizzes
- `POST /quiz/evaluate` - Evaluate quiz answers
- `POST /ingest` - Ingest documents
- `POST /sessions/{learner_id}/events` - Process session events
- `GET /sessions/{learner_id}` - Get session history
- `POST /sessions/{learner_id}/reset` - Reset session

## See Also

- [GETTING_STARTED.md](GETTING_STARTED.md) - Quick start guide
- [TESTING.md](TESTING.md) - Testing documentation

