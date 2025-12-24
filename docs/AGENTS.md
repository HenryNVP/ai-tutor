# AI Tutor Agents - Detailed Documentation

## Quick Reference

For a quick overview of all agents, see the [Multi-Agent System section](../README.md#multi-agent-system) in the README.

## Available Agents

### 1. **QA Agent** (`qa_agent`)
**Route**: `"qa"` (default)

**Purpose**: Answers questions using Retrieval-Augmented Generation (RAG) from local documents.

**Capabilities**:
- Semantic search in vector store
- Answers with citations from uploaded documents
- Source-filtered retrieval (search specific documents)
- Falls back to web search if no local results found

**Trigger Keywords**:
- Generic questions (default route)
- Questions with document references
- "What is...", "Explain...", "How does..."

**Tools**:
- `retrieve_local_context` - Semantic search in ChromaDB
- MCP tools (if MCP servers available)

**Example Requests**:
- "What is RegNet?"
- "Explain neural networks from the uploaded file"
- "What does the document say about momentum?"

---

### 2. **Quiz Agent** (`quiz_agent`)
**Route**: `"quiz"`

**Purpose**: Generates quizzes and assessments from document content.

**Capabilities**:
- Creates multiple-choice questions (3-40 questions)
- Extracts topics from requests
- Uses QuizService for generation
- Supports adaptive difficulty (in production mode)

**Trigger Keywords**:
- "quiz", "quizzes", "test me", "test myself"
- "practice questions", "create questions"
- "generate quiz", "quiz me on"

**Tools**:
- QuizService integration
- Document retrieval for quiz content

**Example Requests**:
- "Create 5 quiz questions about physics"
- "Test me on RegNet"
- "Generate 10 review quizzes from the uploaded file"

---

### 3. **Note Agent** (`note_agent`)
**Route**: `"note"`

**Purpose**: Creates structured study notes and summaries from documents.

**Capabilities**:
- Generates comprehensive notes from full documents
- Creates structured Markdown output
- Saves notes to files
- Synthesizes information from multiple sources

**Trigger Keywords**:
- "summarize", "summary"
- "create notes", "write notes", "take notes"
- "create text file", "write a file"
- "lesson notes", "study notes"

**Tools**:
- `fetch_full_document` - Retrieves all chunks from a document
- `retrieve_local_context` - Semantic search for topic research
- `write_text_file` (via MCP) - Saves notes to files

**Example Requests**:
- "Create lesson notes about RegNet"
- "Summarize the uploaded document"
- "Create a text file introducing BERT"
- "Save these notes to a file"

---

### 4. **Visualization Agent** (`visualization_agent`)
**Route**: `"visualization"`

**Purpose**: Generates data visualizations from CSV files.

**Capabilities**:
- Creates plots, charts, and graphs
- Generates Python code (matplotlib/seaborn)
- Executes code and displays charts
- Saves visualizations to files

**Trigger Keywords**:
- "plot", "chart", "graph"
- "visualize", "visualization"
- "create a bar chart", "line chart", etc.

**Tools**:
- Code generation and execution
- File system access for saving charts

**Example Requests**:
- "Plot sales per month"
- "Create a bar chart of expenses"
- "Visualize the trends in the data"

---

### 5. **Web Agent** (`web_agent`)
**Route**: `"web"`

**Purpose**: Fetches current information from the web.

**Capabilities**:
- Web search for current events
- Answers questions requiring up-to-date information
- Provides URL citations

**Trigger Keywords**:
- "news", "current events"
- "what's happening", "latest update"
- "search the web for"

**Tools**:
- `WebSearchTool` - Web search functionality

**Example Requests**:
- "What's the news today?"
- "Tell me about current events"
- "Search for recent developments in AI"

---

### 6. **Ingestion Agent** (`ingestion_agent`)
**Route**: `"ingestion"`

**Purpose**: Processes and ingests new documents into the system.

**Capabilities**:
- Processes PDF, TXT, MD files
- Chunks documents
- Generates embeddings
- Stores in vector store (ChromaDB)

**Trigger Keywords**:
- "upload", "ingest"
- "add document", "process file"

**Tools**:
- Document processing pipeline
- Embedding generation
- Vector store indexing

**Example Requests**:
- "Upload a new document"
- "Ingest this file"
- "Add document to corpus"

---

## Routing Mechanism

### Keyword-Based Routing

Requests are routed using **deterministic keyword detection** (simplified, no LLM fallback):

1. **Quiz Detection**: Checks for quiz-related keywords → routes to Quiz Agent
2. **Note Detection**: Checks for note/summarize keywords → routes to Note Agent
3. **Visualization Detection**: Checks for plot/chart keywords → routes to Visualization Agent
4. **Ingestion Detection**: Checks for upload/ingest keywords → routes to Ingestion Agent
5. **Web Detection**: Checks for news/current events keywords → routes to Web Agent
6. **Default**: Routes to QA Agent for all other requests

### Routing Decision Flow

```
User Request
    ↓
Keyword Detection
    ↓
┌─────────────────────────────────┐
│ apply_deterministic_routing()   │
└─────────────────────────────────┘
    ↓
Match Found? ──Yes──→ Route to Specific Agent
    ↓ No
Default to QA Agent
```

### Source Filtering

All agents support **source-filtered retrieval**:
- Pre-filter by document filename
- Faster retrieval (320x speedup)
- More accurate results

**Example**:
```python
# Only search in specific document
question = "What is RegNet?"
source_hints = ["CMPE249_Lecture7.pdf"]
documents_only = True
```

---

## Agent State Management

Agents share state via `AgentState`:
- `last_quiz`: Most recent quiz generated
- `last_note`: Most recent notes created
- `last_visualization`: Most recent chart/plot
- `last_source`: Source of last retrieval

This allows agents to reference each other's outputs.

---

## MCP Integration

Agents can use **MCP (Model Context Protocol) servers** for enhanced tool access:

- **ChromaDB MCP**: Direct vector store access
- **Filesystem MCP**: File read/write operations

**Benefits**:
- Cached tool lists (faster)
- Persistent connections
- Enhanced capabilities

**Note**: MCP servers are optional - agents work without them using direct API access.

---

## Demo Mode Behavior

In **demo mode** (`demo_mode: true`):
- ✅ All agents work normally
- ✅ Routing works as expected
- ❌ Personalization disabled (Quiz Agent uses static difficulty)
- ❌ No profile updates

In **production mode** (`demo_mode: false`):
- ✅ Full personalization
- ✅ Adaptive difficulty in Quiz Agent
- ✅ Progress tracking
- ✅ Profile updates

---

## Testing Agents

See [MANUAL_TESTING.md](MANUAL_TESTING.md) for step-by-step testing instructions for each agent.

### Quick Test Commands

```bash
# Test QA Agent
curl -X POST "http://localhost:8080/answer" \
  -d '{"learner_id": "test", "question": "What is momentum?"}'
# Expected route: "qa"

# Test Quiz Agent
curl -X POST "http://localhost:8080/answer" \
  -d '{"learner_id": "test", "question": "create 5 quizzes"}'
# Expected route: "quiz"

# Test Note Agent
curl -X POST "http://localhost:8080/answer" \
  -d '{"learner_id": "test", "question": "summarize the document"}'
# Expected route: "note"

# Test Visualization Agent
curl -X POST "http://localhost:8080/answer" \
  -d '{"learner_id": "test", "question": "plot sales data"}'
# Expected route: "visualization"
```

---

## QA Agent vs Note Agent

For a detailed comparison of QA and Note agents, see [QA_VS_NOTE_AGENTS.md](QA_VS_NOTE_AGENTS.md).

**Quick Summary**:
- **QA Agent**: Quick answers to specific questions (3-6 sentences, semantic search only)
- **Note Agent**: Comprehensive study notes (full documents, structured Markdown, can save files)

**Should They Be Combined?** See [AGENT_COMBINATION_ANALYSIS.md](AGENT_COMBINATION_ANALYSIS.md) for analysis.

**Recommendation**: Keep separate - they serve different purposes with different tools and strategies.

## See Also

- [QA_VS_NOTE_AGENTS.md](QA_VS_NOTE_AGENTS.md) - Detailed comparison of QA vs Note agents
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture overview
- [MANUAL_TESTING.md](MANUAL_TESTING.md) - Manual testing guide
- [GETTING_STARTED.md](GETTING_STARTED.md) - Quick start guide

