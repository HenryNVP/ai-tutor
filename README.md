# 🎓 AI Tutor

A local-first AI tutoring system with **agent-first architecture** that ingests STEM course materials, answers questions with cited references, and generates personalized interactive quizzes through natural conversation.

## ✨ Key Features

- **🤖 Agent-First Architecture** – Intelligent orchestrator agent routes requests to specialized tools and agents
- **📚 Smart Document Upload** – Upload PDFs in chat, auto-ingest, and generate quizzes from your documents
- **🔍 Source-Filtered Retrieval** – Semantic search with metadata filtering for precise document-based queries
- **📝 Natural Language Quiz Generation** – "Create 20 quizzes from uploaded documents" generates 3-40 questions instantly
- **💬 Interactive Quiz Interface** – Take quizzes in chat with immediate feedback and explanations
- **📊 Adaptive Learning** – Learner profiles track progress and adjust difficulty automatically
- **🎯 Multi-Agent Routing** – Questions automatically routed to QA, Web Search, or Ingestion agents

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.10+
pip install -r requirements.txt

# Set your OpenAI API key
export OPENAI_API_KEY=your_key_here
```

### Launch the App

```bash
streamlit run apps/ui.py
```

The app opens at `http://localhost:8501` with two tabs:
- **💬 Chat & Learn** – Ask questions, upload documents, generate quizzes
- **📚 Corpus Management** – Browse and manage ingested documents

## 💬 How to Use

### Ask Questions

```
You: "Explain the Bernoulli equation"
AI: [Provides answer with citations from local documents]
```

### Upload Documents & Generate Quizzes

```
1. Click "📎 Attach Files" in chat
2. Upload PDF(s) (auto-ingests on first message)
3. Say: "create 20 quizzes from the uploaded documents"
4. Take the quiz interactively in chat!
```

### More Examples

```
"create 10 quizzes on machine learning"
"quiz me on Newton's Laws"
"create 30 questions from uploaded document"
"test my knowledge of calculus"
"explain R-CNN architecture"
```

## 🏗️ Architecture

### Agent-First Design

The system uses an **orchestrator agent** that intelligently routes requests and calls tools:

```
User Message
    ↓
Orchestrator Agent
    ↓
    ├─→ generate_quiz tool → Quiz Service → Interactive quiz
    ├─→ QA Agent → Retriever → Answer with citations
    ├─→ Web Agent → Search → Current information
    └─→ Ingestion Agent → Document processing
```

### Routing Logic

**Quiz Requests** → `generate_quiz` tool
- "create 20 quizzes on X"
- "quiz me on Y"
- "test my knowledge"
- Automatically extracts topic and count
- Supports 3-40 questions

**STEM Questions** → QA Agent
- Physics, math, chemistry, biology, CS
- Retrieves from local documents
- Falls back to web if needed
- Always provides citations

**Current Events** → Web Agent
- News, recent events
- Real-time web search
- Returns URLs as sources

**Document Upload** → Ingestion Agent
- Processes PDFs, text files
- Creates searchable chunks
- Enables document-based quizzes

### Key Innovations

1. **Source Filtering** – Retrieval searches ONLY uploaded documents (not entire corpus)
2. **Dynamic max_tokens** – Automatically scales for large quizzes (up to 40 questions)
3. **Count Extraction** – Agent correctly extracts "create 20 quizzes" → count=20
4. **Topic Inference** – Auto-infers topic from uploaded documents
5. **Tool Enforcement** – Agent ALWAYS uses tools, never answers quiz requests with text

## 📝 Quiz Generation

### Features

- **3-40 questions** per quiz (agent-enforced range)
- **Automatic topic extraction** from context
- **Document grounding** – Questions based on YOUR uploaded files
- **Interactive interface** – Select answers, get immediate feedback
- **Markdown download** – Export quizzes in formatted markdown

### How It Works

```
User: "create 20 quizzes from the documents"
  ↓
Agent extracts: topic='computer science', count=20
  ↓
Agent calls: generate_quiz(topic='computer science', count=20)
  ↓
Quiz Service:
  • Retrieves content from uploaded documents (source filtering)
  • Calculates max_tokens = (20 × 150) + 500 = 3500
  • Generates 20 questions with LLM
  • Returns quiz to agent
  ↓
UI displays interactive quiz with 20 questions
  ↓
User takes quiz, gets results & explanations
```

### Generation Examples

```bash
# From uploaded documents
"create 20 comprehensive quizzes from the uploaded document"

# On specific topics
"create 10 quizzes on neural networks"
"quiz me on thermodynamics"

# With difficulty hints
"create 15 challenging quizzes on calculus"
"test my beginner knowledge of Python"

# Default (4 questions)
"quiz me"
```

## 🔍 Retrieval System

### Vector Store

- **Embeddings**: `all-MiniLM-L6-v2` sentence-transformer
- **Storage**: Simple in-memory vector store with FAISS-like cosine similarity
- **Metadata**: Title, page, domain, source path
- **Filtering**: Can restrict search to specific source files

### Source Filtering (New!)

When you upload documents, the system can search ONLY those files:

```python
Query(
    text="machine learning",
    source_filter=["lecture9.pdf", "lecture10.pdf"]
)
```

**Benefits:**
- 320x faster (searches 31 chunks instead of 10,000)
- Better ranking (no competition from old docs)
- Guaranteed relevance to uploaded files

## 📊 Learner Profiles

### Automatic Tracking

- **Strengths/Struggles** per domain (e.g., "Physics-Mechanics")
- **Study time** and **questions mastered**
- **Difficulty level** adjusted based on quiz performance

### Performance-Based Adaptation

| Quiz Score | New Difficulty | Next Action |
|------------|----------------|-------------|
| ≥ 70% | Challenge | Harder topics |
| 40-69% | Guided | Targeted practice |
| < 40% | Foundational | Review basics |

## 🗂️ Data Storage

```
data/
├── raw/                      # Original documents (PDFs, MD, TXT)
├── processed/
│   ├── chunks.jsonl         # Extracted and chunked content
│   ├── profiles/            # Learner profiles (JSON)
│   └── sessions.sqlite      # Conversation history
└── vector_store/
    ├── embeddings.npy       # Vector embeddings (all-MiniLM-L6-v2)
    └── metadata.json        # Chunk metadata with source paths
```

## ⚙️ Configuration

Edit `config/default.yaml`:

```yaml
model:
  name: gpt-4o-mini
  temperature: 0.7
  max_output_tokens: 1024  # Default (overridden for large quizzes)

retrieval:
  top_k: 8  # Results per query
  embedding_model: all-MiniLM-L6-v2

quiz:
  default_questions: 4
  max_questions: 40  # Enforced limit
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_quiz_generation.py

# With coverage
pytest --cov=src/ai_tutor tests/
```

## 📚 Documentation

- **Architecture**: See `docs/presentation_report.md` for detailed system design
- **Configuration**: See `config/default.yaml` for all settings
- **API Reference**: See docstrings in `src/ai_tutor/`

## 🔧 Advanced Usage

### CLI Commands

```bash
# Ingest documents
ai-tutor ingest ./data/raw

# Ask a question (CLI mode)
ai-tutor ask student123 "What is the Bernoulli equation?"

# Clear conversation history
python scripts/clear_sessions.py student123
```

### Programmatic Usage

```python
from ai_tutor.system import TutorSystem

# Initialize system
system = TutorSystem.from_yaml("config/default.yaml")

# Ingest documents
system.ingest_directory("./data/raw")

# Ask a question
response = system.answer(
    learner_id="student123",
    question="Explain neural networks",
    mode="chat"
)

# Generate a quiz (legacy API, use chat instead!)
# quiz = system.tutor_agent.quiz_service.generate_quiz(...)
```

## 🔄 Session Management

Conversations are stored in SQLite with automatic daily rotation:

**Session Format**: `ai_tutor_{learner_id}_{YYYYMMDD}`

**Auto-rotation**: Sessions reset daily to prevent token overflow

**Manual clearing**:
```bash
# View all sessions
python scripts/clear_sessions.py

# Clear specific learner
python scripts/clear_sessions.py student123

# Clear all
python scripts/clear_sessions.py all
```

## 🎯 What's New

### Recent Improvements

1. **Agent-First Architecture** – Everything routed through intelligent orchestrator
2. **Source Filtering** – Search only uploaded documents (320x faster)
3. **Dynamic max_tokens** – Auto-scales for 3-40 question quizzes
4. **Improved Count Extraction** – Agent correctly parses "create 20 quizzes"
5. **Tool Call Enforcement** – Agent never answers with text, always uses tools
6. **Removed Legacy Code** – Deleted 157 lines of button-based quiz UI

### Migration from Legacy

**Old (Removed):**
- Quiz Builder tab with forms
- Quick Quiz Tools in sidebar
- Button-based generation

**New (Use This):**
- Natural language in chat
- "create 20 quizzes on topic"
- Upload docs → generate from them

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

MIT License - see [LICENSE](LICENSE) for details

## 🙏 Acknowledgments

- OpenAI API for LLM capabilities
- Sentence-Transformers for local embeddings
- Streamlit for rapid UI development
- FAISS-inspired vector similarity search

---

**Built with ❤️ using Python, OpenAI, and local-first principles**

For questions or issues, please open a GitHub issue or contact the maintainers.
