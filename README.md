# AI Tutor

A local-first AI tutoring system that ingests STEM course materials, answers questions with cited references, and adapts to learner progress through interactive quizzes.

## Features

- **📚 Document Ingestion** – Parse PDFs, Markdown, and text files into searchable chunks
- **🔍 Smart Retrieval** – Semantic search using local sentence-transformer embeddings
- **🤖 Multi-Agent Q&A** – Orchestrator routes questions to specialized agents (QA, web search, ingestion)
- **📝 Interactive Quizzes** – Generate personalized multiple-choice quizzes that adapt to learner performance
- **📊 Learner Profiles** – Track strengths, struggles, and progress with automatic updates from quiz results
- **💬 Conversation Memory** – Maintains context within sessions with automatic daily rotation

## Quick Start

# Set API key
export OPENAI_API_KEY=your_key_here
```

### Basic Usage

```bash
# Start the web UI (includes Q&A, quiz, and file upload)
python scripts/tutor_web.py

# Or use CLI
ai-tutor ingest ./data/raw
ai-tutor ask student123 "What is the Bernoulli equation?"
```

## Architecture

### Multi-Agent System

Questions are routed to specialized agents based on content:

```
User Question
    ↓
Orchestrator Agent (answering general questions and routing)
    ↓
    ├─→ QA Agent → retrieve_local_context → Answer with citations
    ├─→ Web Agent → web_search → Answer with URLs
    └─→ Ingestion Agent → ingest_corpus → Process documents
```

**STEM Questions** (physics, math, chemistry, etc.)
- Route to QA Agent
- Searches local course materials
- Falls back to web if needed
- Always includes citations

**Current Events / Web Search**
- Route to Web Agent
- Searches the web
- Returns URLs as sources

**System Questions** (help, progress, etc.)
- Answered directly by orchestrator


## Web UI Features

The web interface (`python scripts/tutor_web.py`) includes:

### Q&A with Citations
- Ask STEM questions and get cited answers
- Upload documents for temporary context
- Conversation history with session management

### Interactive Quizzes
- Generate quizzes on any topic
- Multiple choice questions with explanations
- Automatic profile updates based on score:
  - ≥70%: Independent challenge level
  - 40-69%: Guided practice level
  - <40%: Foundational guidance level

### Learner Profiles
- Tracks strengths and struggles per domain
- Records study time and questions mastered
- Adapts difficulty based on performance

## Session Management

Conversations are stored in SQLite with automatic daily rotation to prevent token overflow.

**Session Format**: `ai_tutor_{learner_id}_{YYYYMMDD}`

**Auto-rotation**: Sessions reset daily, limiting context to same-day conversations

**Manual clearing**:
```bash
# View sessions
python scripts/clear_sessions.py

# Clear specific learner
python scripts/clear_sessions.py student123

# Clear all
python scripts/clear_sessions.py all
```


## Data Storage

```
data/
├── raw/                      # Original documents (PDFs, MD, TXT)
├── processed/
│   ├── chunks.jsonl         # Extracted and chunked content
│   ├── profiles/            # Learner profiles (JSON)
│   └── sessions.sqlite      # Conversation history
└── vector_store/
    ├── embeddings.npy       # Vector embeddings
    └── metadata.json        # Chunk metadata
```


## License

MIT
