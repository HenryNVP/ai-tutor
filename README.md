# 🎓 AI Tutor

An intelligent tutoring system that ingests STEM course materials, answers questions with cited references, generates personalized quizzes, and creates data visualizations—all through natural conversation.

## ✨ Key Features

- **📚 Smart Document Upload** – Upload PDFs/TXT in chat, auto-ingest on first question
- **🤖 Agent-First Architecture** – Intelligent orchestrator routes requests to specialized tools
- **📝 Natural Language Quizzes** – "Create 20 questions from uploaded documents" (3-40 questions)
- **💬 Interactive Quiz Interface** – Take quizzes in chat with immediate feedback
- **📊 Data Visualization** – Upload CSV, request plots: "plot revenue by month"
- **🔍 Source-Filtered Retrieval** – Search specific documents only (320x faster)
- **🎯 Adaptive Learning** – Track progress, adjust difficulty automatically
- **🌐 Web Search** – Falls back to current information when needed

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
- **💬 Chat & Learn** – Q&A, quizzes, visualizations
- **📚 Corpus Management** – Browse and manage documents

## 💬 How to Use

### 1. Ask Questions

```
You: "Explain the Bernoulli equation"
AI: [Provides answer with citations from local documents]
```

### 2. Upload Documents & Generate Quizzes

```
1. In sidebar, upload PDF(s) under "📤 Upload Documents"
2. System auto-ingests when you ask first question
3. Say: "create 20 questions from the uploaded documents"
4. Take the quiz interactively!
5. Click "Edit and Download Quiz" for markdown export
```

### 3. Data Visualization

```
1. In sidebar, upload CSV under "📊 Data Visualization"
2. System shows preview (columns, shape, first 5 rows)
3. Say: "plot revenue by month"
4. System generates matplotlib code and displays chart
5. Click "View generated code" to see Python code
```

### Example Requests

```
# Questions
"Explain R-CNN architecture"
"What is recursion?"
"How does photosynthesis work?"

# Quizzes
"create 10 questions on machine learning"
"quiz me on Newton's Laws"
"create 30 questions from uploaded document"

# Visualizations
"create a bar chart of sales by region"
"show me a histogram of temperatures"
"scatter plot of X vs Y"
"line chart comparing revenue and expenses"
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

**4. Quiz Generation**
- Dynamic question count (3-40)
- Topic extraction from context
- Multiple choice format
- Source-filtered retrieval
- Interactive UI + Markdown export

**5. Visualization Agent**
- CSV dataset inspection
- LLM-powered code generation (matplotlib/seaborn)
- Safe execution environment
- Base64 image encoding
- Code display in UI

**6. Adaptive Learning**
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

### Performance

| Metric | Value |
|--------|-------|
| Question count | 3-40 per quiz |
| Generation time | ~8-15 seconds (10 questions) |
| Retrieval time | 50-200ms (with source filtering) |
| Export format | Markdown |

## 📈 Data Visualization

### Supported Charts

- Line charts
- Bar charts (single/grouped)
- Scatter plots
- Histograms
- Pie charts
- Heatmaps
- Box plots

### Workflow

```
1. Upload: sales_2024.csv (12 rows × 3 columns: month, revenue, expenses)
2. Request: "plot revenue by month"
3. Agent:
   • Inspects dataset (columns, types, sample rows)
   • Generates matplotlib code via LLM
   • Executes in safe environment
   • Returns base64-encoded PNG
4. UI displays plot in chat
5. User clicks "View generated code" to see Python
```

### Performance

| Metric | Time |
|--------|------|
| Dataset inspection | ~50-100ms |
| Code generation (LLM) | ~2-4 seconds |
| Code execution | ~500-1000ms |
| **Total** | **~3-5 seconds** |

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
    source_filter=["lecture9.pdf", "lecture10.pdf"]
)
```

**Benefits:**
- **320x faster** (31 chunks vs 10,000)
- **Better ranking** (no old document competition)
- **100% relevant** to user's files

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

## 🧪 Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src/ai_tutor tests/

# Specific component
pytest tests/test_quiz_generation.py
```

## 📚 Documentation

- **[Demo Guide](docs/demo.md)** – Use cases and workflows
- **[Technical Report](docs/presentation_report.md)** – System architecture
- **[Architecture Diagrams](docs/architecture.puml)** – PlantUML diagrams

## 🔧 Advanced Usage

### CLI Commands

```bash
# Ingest documents
ai-tutor ingest ./data/raw

# Ask a question
ai-tutor ask student123 "What is the Bernoulli equation?"

# Clear conversation history
python scripts/clear_sessions.py student123
```

### Programmatic Usage

```python
from ai_tutor.system import TutorSystem

# Initialize
system = TutorSystem.from_yaml("config/default.yaml")

# Ingest documents
system.ingest_directory("./data/raw")

# Ask a question
response = system.answer_question(
    learner_id="student123",
    question="Explain neural networks",
)

print(response.answer)
print(response.citations)
```

## 🔄 Session Management

Sessions are stored in SQLite with daily rotation:

**Format**: `ai_tutor_{learner_id}_{YYYYMMDD}`

**Auto-rotation**: Prevents token overflow

**Manual clearing**:
```bash
# View all sessions
python scripts/clear_sessions.py

# Clear specific learner
python scripts/clear_sessions.py student123

# Clear all
python scripts/clear_sessions.py all
```

## 🎯 Key Innovations

1. **Agent-First Design** – Natural language over button-based UI
2. **Source Filtering** – Search only relevant documents (320x speedup)
3. **Dynamic Token Allocation** – Auto-scales for 3-40 question quizzes
4. **LLM-Powered Visualization** – Generate plotting code from descriptions
5. **Safe Code Execution** – Restricted environment for plot generation
6. **Citation Transparency** – Every answer traceable to source

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
- Sentence-Transformers for embeddings
- Streamlit for UI framework
- matplotlib/seaborn for visualizations

---

**Built with ❤️ for personalized STEM education**

For questions, open a GitHub issue or contact the maintainers.
