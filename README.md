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
# Ingest documents
ai-tutor ingest ./data/raw

# Ask questions (with citations!)
ai-tutor ask student123 "What is the Bernoulli equation?"

# Run quiz app (Streamlit interface)
streamlit run apps/quiz.py

# Run web interface
python scripts/tutor_web.py
```

### Python API

```python
from ai_tutor.system import TutorSystem

system = TutorSystem.from_config()

# Answer questions
response = system.answer_question(
    learner_id="student123",
    question="Explain Newton's first law",
    mode="learning"
)
print(response.answer)
print(response.citations)

# Generate quiz
quiz = system.generate_quiz(
    learner_id="student123",
    topic="Thermodynamics",
    num_questions=5
)

# Evaluate quiz (auto-updates profile)
evaluation = system.evaluate_quiz(
    learner_id="student123",
    quiz_payload=quiz,
    answers=[0, 2, 1, 3, 1]  # Answer indices
)
```

## Architecture

### Multi-Agent System

Questions are routed to specialized agents based on content:

```
User Question
    ↓
Orchestrator Agent (routing only)
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

**Current Events / General Knowledge**
- Route to Web Agent
- Searches the web
- Returns URLs as sources

**System Questions** (help, progress, etc.)
- Answered directly by orchestrator

### Components

```
src/ai_tutor/
├── agents/           # Multi-agent system (orchestrator, QA, web, ingestion)
├── learning/         # Quiz generation, evaluation, profiles, personalization
├── retrieval/        # Vector store and semantic search
├── ingestion/        # Document parsing and chunking
└── system.py         # Main TutorSystem facade
```

## Quiz System

### Generate Personalized Quizzes

The system creates quizzes adapted to learner level:

```python
quiz = system.generate_quiz(
    learner_id="student123",
    topic="Newton's laws of motion",
    num_questions=4
)

# Quiz includes:
# - 4 multiple choice questions
# - Correct answer indices
# - Explanations for each answer
# - References to course materials
```

### Automatic Profile Updates

Quiz results automatically update learner profiles:

| Score | Strength Δ | Struggle Δ | Difficulty Level |
|-------|-----------|-----------|------------------|
| ≥70%  | +0.12     | -0.08     | Independent challenge |
| 40-69%| +0.06     | 0.00      | Guided practice |
| <40%  | +0.02     | +0.10     | Foundational guidance |

Profiles track:
- Domain strengths and struggles (0.0-1.0 scale)
- Questions answered correctly per domain
- Total study time
- Preferred difficulty level

### Quiz App UI

Run the Streamlit interface:

```bash
streamlit run apps/quiz.py
```

Features:
- Generate quizzes on any topic
- Real-time profile display in sidebar
- Detailed feedback with explanations
- Automatic profile updates based on quiz performance

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

## Configuration

Edit `config/default.yaml`:

```yaml
model:
  name: gpt-4o-mini        # All agents use this model
  temperature: 0.7
  max_output_tokens: 2048

embeddings:
  provider: sentence-transformers
  model_name: BAAI/bge-base-en

retrieval:
  top_k: 8                 # Number of chunks to retrieve

chunking:
  chunk_size: 800          # Characters per chunk
  overlap: 200             # Overlap between chunks
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

## Test handoff behavior with DEBUG logging
### Logging

Set log level in `config/default.yaml`:

```yaml
logging:
  level: DEBUG  # See agent handoffs, tool calls, profile updates
  use_json: false
```

DEBUG logs show:
- Agent handoff events
- Tool calls (`retrieve_local_context`, `web_search`)
- Session creation and rotation  
- Profile updates after quizzes


ai-tutor --help
ai-tutor ingest ./data/raw
ai-tutor ask student123 "your question here"
```

## Technical Notes

### Models


All agents use **gpt-4o-mini**:


### Agent Behavior

- **Orchestrator**: Routes only, never answers directly
- **QA Agent**: Must call `retrieve_local_context` before answering
- **Web Agent**: Must call `web_search` before answering
- All specialist agents provide citations

### Session Limits

- Daily rotation: `ai_tutor_student123_20251023`
- Prevents unbounded context growth
- SQLite persistence across restarts

## Requirements

- Python 3.10+
- OpenAI API key
- Dependencies in `requirements.txt`

## License

MIT

## Project Structure

```
ai-tutor/
├── apps/
│   ├── quiz.py              # Streamlit quiz interface
│   └── ui.py                # Additional UI components
├── scripts/
│   ├── clear_sessions.py    # Session management CLI
│   └── tutor_web.py         # Web interface
├── src/ai_tutor/
│   ├── agents/              # Multi-agent system
│   ├── learning/            # Quiz & personalization
│   ├── retrieval/           # Vector store & search
│   ├── ingestion/           # Document processing
│   └── system.py            # Main TutorSystem
├── config/
│   └── default.yaml         # Configuration
└── data/
    ├── raw/                 # Original documents
    ├── processed/           # Chunks, profiles, sessions
    └── vector_store/        # Embeddings
```