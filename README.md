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

# Set your OpenAI API key
export OPENAI_API_KEY=your_key_here
```

### Launch the Streamlit App

```bash
streamlit run apps/ui.py
```

The app opens at `http://localhost:8501` with two tabs:
- **💬 Chat & Learn** – Q&A, quizzes, visualizations, generated files manager
- **📚 Corpus Management** – Browse and manage documents

### Launch the FastAPI Backend

```bash
uvicorn apps.api:app --reload --port 8080
```

Endpoints (see [`docs/backend_api.md`](docs/backend_api.md) for details):
- `POST /answer` — answer questions with citations
- `POST /quiz` — create quizzes
- `POST /ingest` — upload & ingest documents
- `POST /sessions/{learner_id}/reset` — clear history
- `GET /health` — health check

### (Optional) Start MCP Servers

Enable richer tool access by launching the MCP servers before opening the UI:

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
   You: "Save these notes to a file"
   AI: "Notes saved to data/generated/regnet_notes.txt"
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

### Core Components

**1. Document Ingestion**
- Supports PDF, TXT, Markdown
- Semantic chunking (512 tokens)
- Vector embeddings (all-MiniLM-L6-v2)
- Metadata tracking (title, page, source)

**2. Retrieval System**
- ChromaDB vector store (default, production-ready)
- Vector similarity search with cosine distance
- Source filtering for uploaded documents
- Top-k configurable (default: 5-8)
- Citation generation with page numbers
- Automatic persistence (SQLite backend)

**3. QA Agent**
- Retrieval-augmented generation
- Context-aware responses
- Multi-document support
- Automatic citation tracking

**4. Note Agent**
- Automatic context retrieval from uploaded documents
- Structured note generation (headings, bullet points, key takeaways)
- File saving capability
- Supports both topic-based and document-based note creation

**5. Quiz Generation**
- Dynamic question count (3-40)
- Topic extraction from context
- Multiple choice format
- Source-filtered retrieval
- Interactive UI + Markdown export

**6. Visualization Agent**
- CSV dataset inspection
- LLM-powered code generation (matplotlib/seaborn)
- Safe execution environment
- Base64 image encoding
- Code display in UI

**7. Adaptive Learning**

**8. Tutor Service Layer**
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
│   ├── chunks.jsonl         # Extracted and chunked content
│   ├── profiles/            # Learner profiles (JSON)
│   └── sessions.sqlite      # Conversation history
└── vector_store/
    ├── embeddings.npy       # Vector embeddings
    └── metadata.json        # Chunk metadata
```

## ⚙️ Configuration

Edit `config/default.yaml`:

```yaml
model:
  name: gpt-4o-mini
  temperature: 0.7
  max_output_tokens: 1024  # Auto-adjusted for large quizzes

retrieval:
  top_k: 8
  embedding_model: all-MiniLM-L6-v2

quiz:
  default_questions: 4
  max_questions: 40
```

## 📚 Documentation

- **[Demo Guide](docs/demo.md)** – Step-by-step use cases including:
  - Greetings and general questions
  - Document upload and Q&A
  - Lesson notes generation
  - Quiz creation from documents
  - Data visualization workflows

- **[Architecture Diagrams](docs/architecture.puml)** – PlantUML diagrams

## 📝 License

MIT License - see [LICENSE](LICENSE) for details
