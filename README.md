# 🎓 AI Tutor

An intelligent tutoring system that ingests STEM course materials, answers questions with cited references, generates personalized quizzes, and creates data visualizations—all through natural conversation.

## ✨ Key Features

- **📚 Smart Document Upload** – Upload PDFs/TXT in chat, auto-ingest on first question
- **🤖 Agent-First Architecture** – Intelligent orchestrator routes requests to specialized tools
- **💬 Natural Language Q&A** – Ask questions with automatic citation tracking
- **📝 Lesson Notes Generation** – "Create lesson notes about [topic]" from uploaded documents
- **🎯 Natural Language Quizzes** – "Create 10 review quizzes from uploaded file" (3-40 questions)
- **💬 Interactive Quiz Interface** – Take quizzes in chat with immediate feedback
- **🗂️ Generated Files Manager** – Rename, delete, preview & download notes/quizzes/charts/code
- **📊 Data Visualization** – Upload CSV, request plots: "plot sales per month"
- **🔍 Source-Filtered Retrieval** – Search specific documents only (320x faster)
- **🎯 Adaptive Learning** – Track progress, adjust difficulty automatically
- **🌐 Web Search** – Falls back to current information when needed
- **⚡ FastAPI Backend** – REST API for questions, quizzes, ingestion, and session resets

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.10+
pip install -r requirements.txt
```

### API Keys & Model Configuration

The system supports both **OpenAI** and **Gemini** models. Set the appropriate API keys:

```bash
# For OpenAI models (e.g., gpt-4o-mini, gpt-4o)
export OPENAI_API_KEY=your_openai_key_here

# For Gemini models (e.g., gemini-2.0-flash, gemini-1.5-pro)
export GEMINI_API_KEY=your_gemini_key_here
```

**Default Configuration** (`config/default.yaml`):
- **Model**: `gemini/gemini-2.0-flash` (recommended for large context window)
- **All Agents**: Use Gemini Flash by default
- **API Key**: Reads from `GEMINI_API_KEY` environment variable

**To use OpenAI instead**, edit `config/default.yaml`:
```yaml
model:
  name: "gpt-4o-mini"  # or "gpt-4o"
  # ... other settings

# Individual agents can also be configured:
note_agent:
  model: "gpt-4o-mini"
  api_key: null  # Uses OPENAI_API_KEY env var
```

### Demo Mode

The system includes demo mode (enabled by default in `config/default.yaml`) which:
- ✅ Disables personalization (faster startup, simpler code)
- ✅ Uses static difficulty/style (consistent experience)
- ✅ Simplified routing (keyword-based only)
- ✅ **Document caching only** – Documents are parsed and cached but not chunked/embedded (faster for large context models like Gemini)
- ✅ Focuses on core RAG capabilities

**Note**: In demo mode, documents are cached for direct access by agents using large context models (e.g., Gemini with 1M+ token context). Full chunking and embedding are skipped for faster processing.

**Alternative**: Use `config/demo.yaml` for minimal configuration:
```bash
# Use demo config (minimal settings)
python -c "from ai_tutor.system import TutorSystem; system = TutorSystem.from_config('config/demo.yaml')"
```

### Launch the Streamlit App

```bash
streamlit run apps/ui.py
```

The app uses `config/default.yaml` by default (demo mode enabled).

The app opens at `http://localhost:8501` with two tabs:
- **💬 Chat & Learn** – Q&A, quizzes, visualizations, generated files manager
- **📚 Corpus Management** – Browse and manage documents

### Launch the FastAPI Backend

```bash
uvicorn apps.api:app --reload --port 8000
```

Endpoints:
- `POST /answer` — answer questions with citations
- `POST /quiz` — create quizzes
- `POST /ingest` — upload & ingest documents
- `POST /sessions/{learner_id}/reset` — clear history
- `GET /health` — health check

### (Optional) Start MCP Servers

Enable richer tool access by launching the MCP servers before opening the UI. **Required for file operations** (e.g., saving lesson notes to files):

```bash
# Terminal 1 — Chroma retrieval tools (collections, queries, etc.)
cd chroma_mcp_server
python server.py
```

```bash
# Terminal 2 — Filesystem workspace tools (list/read/write project files)
cd filesystem_mcp_server
python server.py
```

Then set the environment flags so Streamlit connects automatically:

```bash
export MCP_USE_SERVER=true            # Chroma MCP (port 8000 by default)
export FS_MCP_USE_SERVER=true         # Filesystem MCP (port 8100 by default)
```

You can customise ports and root directories via `MCP_PORT`, `FS_MCP_PORT`, and `FS_MCP_ROOT`. The sidebar shows connection status and restart hints if a server is unavailable.

**Note**: The filesystem MCP server is required for the Note Agent to save lesson notes to files. Without it, the agent can generate notes but cannot save them to disk.

## 💬 How to Use

### Quick Demo Workflow

1. **Greetings** - Start with a simple hello
   ```
   You: "Hello"
   AI: "Hello! I'm your AI tutor. How can I assist you today?"
   ```

2. **Ask General Questions** - No documents needed
   ```
   You: "What is YOLO?"
   AI: [Provides answer with citations if available in knowledge base]
   ```

3. **Upload & Ask About Documents**
   ```
   1. Upload PDF in sidebar: "📤 Upload Documents"
   2. Ask: "What is RegNet?"
   AI: [Retrieves from uploaded document with citations]
   ```

4. **Create Lesson Notes**
   ```
   You: "Create lesson notes about RegNet"
   AI: [Generates structured notes from uploaded documents]
   
   # Or create and save in one step:
   You: "Create a lesson note file about the uploaded document"
   AI: "Notes saved to data/generated/lesson_note_regnet.txt"
   ```

5. **Generate Quizzes from Documents**
   ```
   1. Upload course material in sidebar
   2. Say: "Create 10 review quizzes from the uploaded file"
   AI: [Generates interactive quiz]
   3. Take quiz, get instant feedback
   4. Quiz automatically saved to Generated Files
   ```

6. **Data Visualization**
   ```
   1. Upload CSV in sidebar: "📊 Data Visualization"
   2. Say: "Plot sales per month"
   AI: [Generates chart and displays it]
   3. View generated code, download from Generated Files
   ```

### Example Requests

```
# Questions
"What is YOLO?"
"Explain R-CNN architecture"
"What is recursion?"
"How does photosynthesis work?"

# With Uploaded Documents
"Upload file, ask what is RegNet"
"What does the uploaded document say about neural networks?"

# Lesson Notes
"Create lesson notes about RegNet"
"Create lesson notes from the uploaded file"
"Create a lesson note file about the uploaded document"  # Creates and saves to file
"Summarize the uploaded document"  # Returns summary without saving

# Quizzes
"Create 10 review quizzes from the uploaded file"
"Create 20 questions on machine learning"
"Quiz me on Newton's Laws"

# Visualizations
"Plot sales per month"
"Create a bar chart of sales by region"
"Show me a histogram of temperatures"
"Scatter plot of X vs Y"
"Line chart comparing revenue and expenses"
```

## 🏗️ Architecture

### System Overview

```
User Message → Orchestrator Agent → Specialized Tools/Agents
    ↓
    ├─→ generate_quiz tool → Quiz (3-40 questions)
    ├─→ QA Agent → Retriever → Answer with citations
    ├─→ Visualization Agent → Plot generation
    ├─→ Web Agent → Current information
    └─→ Ingestion Agent → Document processing
```

### Multi-Agent System

The system uses **6 specialized agents** with keyword-based routing:

- **QA Agent** (`qa`) - Answers questions using RAG from documents (default route)
- **Quiz Agent** (`quiz`) - Generates quizzes from document content (3-40 questions)
- **Note Agent** (`note`) - Creates structured study notes and summaries, can save to files
- **Visualization Agent** (`visualization`) - Generates data visualizations from CSV files
- **Web Agent** (`web`) - Fetches current information from the web
- **Ingestion Agent** (`ingestion`) - Processes and stores uploaded documents

Requests are automatically routed based on keywords (e.g., "quiz" → Quiz Agent, "summarize" → Note Agent).

### Core Components

**1. Document Ingestion**
- Supports PDF, TXT, Markdown
- **Document Cache** – Parsed documents stored for direct access (demo mode)
- Semantic chunking (512 tokens) – Full ingestion mode
- Vector embeddings (all-MiniLM-L6-v2) – Full ingestion mode
- Metadata tracking (title, page, source)
- **Demo Mode**: Documents cached only (no chunking/embedding) for faster processing with large context models

**2. Retrieval System**
- ChromaDB vector store (default, production-ready)
- Vector similarity search with cosine distance
- Source filtering for uploaded documents
- Top-k configurable (default: 5-8)
- Citation generation with page numbers
- Automatic persistence (SQLite backend)

**3. Quiz Generation**
- Dynamic question count (3-40)
- Topic extraction from context
- Multiple choice format
- Source-filtered retrieval
- Interactive UI + Markdown export

**4. Adaptive Learning**

**5. Tutor Service Layer**
- Shared backend API used by Streamlit and FastAPI
- Manages retrieval, ingestion, quiz creation, and error handling
- Ensures UI stays presentation-only
- Learner profiling by domain
- Performance tracking
- Difficulty adjustment
- Progress monitoring

## 📊 Quiz Generation

### Capabilities

- **3-40 questions** per quiz
- **Automatic topic extraction** from uploaded documents
- **Document grounding** – Questions based on YOUR files
- **Interactive interface** – Radio buttons, instant feedback
- **Markdown export** – Download and share

### How It Works

```
User: "create 20 questions from the documents"
  ↓
Orchestrator extracts: topic='computer vision', count=20
  ↓
Calls: generate_quiz(topic='computer vision', count=20)
  ↓
Quiz Service:
  • Retrieves content from uploaded docs (source filtering)
  • Calculates max_tokens dynamically: (20 × 150) + 500 = 3500
  • Generates 20 questions with LLM
  ↓
UI displays interactive quiz
  ↓
User takes quiz, gets results & explanations
```


## 📈 Data Visualization

### Workflow

```
1. Upload: data csv file
2. Request: e.g, plot revenue by month
3. Agent:
   • Inspects dataset (columns, types, sample rows)
   • Generates matplotlib code via LLM
   • Executes in safe environment
   • Returns base64-encoded PNG
4. UI displays plot in chat
5. User clicks "View generated code" to see Python
```

## 🔍 Retrieval Features

### Vector Store

- **Embeddings**: `all-MiniLM-L6-v2` (384 dimensions)
- **Storage**: In-memory numpy arrays + metadata
- **Similarity**: Cosine similarity search
- **Metadata**: Title, page, domain, source path

### Source Filtering

Search ONLY uploaded documents:

```python
Query(
    text="machine learning",
    source_filter=["lecture9.pdf"]
)
```

## 📊 Learner Profiles

### Tracked Metrics

- Strengths/struggles per domain (e.g., "Physics-Mechanics")
- Study time and questions mastered
- Quiz performance over time
- Difficulty progression

### Adaptive Adjustment

| Quiz Score | Action | Next Step |
|------------|--------|-----------|
| ≥ 70% | Challenge | Harder topics |
| 40-69% | Guided | Targeted practice |
| < 40% | Foundational | Review basics |

## 🗂️ Data Storage

```
data/
├── raw/                      # Original documents (PDFs, MD, TXT)
├── uploads/                  # CSV files for visualization
├── processed/
│   ├── chunks.jsonl         # Extracted and chunked content (full ingestion mode)
│   ├── documents.jsonl       # Document cache (parsed documents, demo mode)
│   ├── profiles/            # Learner profiles (JSON)
│   └── sessions.sqlite      # Conversation history
├── generated/               # Generated files (notes, quizzes, charts, code)
│   ├── lesson_note_*.txt    # Lesson notes saved by Note Agent
│   └── ...
└── vector_store/
    ├── embeddings.npy       # Vector embeddings (full ingestion mode)
    └── metadata.json        # Chunk metadata
```

## ⚙️ Configuration

Edit `config/default.yaml`:

```yaml
# LLM Configuration
model:
  name: "gemini/gemini-2.0-flash"  # or "gpt-4o-mini" for OpenAI
  temperature: 0.15
  max_output_tokens: 2048

# Individual Agent Configuration
note_agent:
  model: "gemini/gemini-2.0-flash"  # Large context for full document access
  api_key: null  # Uses GEMINI_API_KEY env var if null
  use_full_context: true

qa_agent:
  model: "gemini/gemini-2.0-flash"
  api_key: null
  use_full_context: true

quiz_agent:
  model: "gemini/gemini-2.0-flash"
  api_key: null
  use_full_context: true

# Retrieval Configuration
retrieval:
  top_k: 5  # Auto-increased to 50 for uploaded document queries

# Embedding Model (for full ingestion mode)
embeddings:
  model: "BAAI/bge-base-en"  # Local embeddings (no API calls)
  provider: "sentence-transformers"

# Demo Mode
demo_mode: true  # Caches documents only (no chunking/embedding)
```

**Model Options**:
- **Gemini**: `gemini/gemini-2.0-flash` (recommended, 1M+ token context), `gemini/gemini-1.5-pro`
- **OpenAI**: `gpt-4o-mini`, `gpt-4o`, `gpt-4-turbo`

## 📚 Documentation

- **[Getting Started](docs/GETTING_STARTED.md)** – Quick start, configuration, and Gemini setup
- **[Agents](docs/AGENTS.md)** – All 6 specialized agents
- **[Gemini](docs/GEMINI.md)** – Gemini integration and setup
- **[Architecture](docs/ARCHITECTURE.md)** – System design
- **[Testing](docs/TESTING.md)** – Automated tests
- **[Manual Testing](docs/MANUAL_TESTING.md)** – Manual testing guide
- **[MCP Servers](docs/MCP.md)** – MCP server setup (required for file operations)

## ⚠️ Notes

### Rate Limiting

When using Gemini API, you may encounter rate limit errors (429) during testing or heavy usage. The system includes:
- Automatic retries with exponential backoff (up to 5 retries)
- Delays between requests in E2E tests
- If rate limits persist, wait a few minutes between test runs or check your API quota

### Demo Mode vs Full Ingestion

- **Demo Mode** (default): Documents are cached only (parsed, not chunked/embedded). Ideal for large context models like Gemini that can process full documents.
- **Full Ingestion**: Documents are chunked and embedded for vector search. Use when you need semantic search across many documents.

## 📝 License

MIT License - see [LICENSE](LICENSE) for details
