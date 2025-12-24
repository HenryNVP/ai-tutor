# Manual Testing Guide

## Overview

This guide provides step-by-step instructions for manually testing the AI Tutor system, focusing on:
- **Main use cases**: Document Q&A, quiz generation, note creation, data visualization
- **Multi-agent system**: How requests are routed to specialized agents (QA, Quiz, Note, Visualization, Web, Ingestion)

## Prerequisites

1. **Start the FastAPI backend**:
   ```bash
   uvicorn apps.api:app --reload --port 8080
   ```
   Verify: Visit `http://localhost:8080/docs` - Swagger UI should load

2. **Start the Streamlit UI** (optional, for interactive testing):
   ```bash
   streamlit run apps/ui.py
   ```
   Verify: Visit `http://localhost:8501` - UI should load

3. **Set API key**:
   ```bash
   export OPENAI_API_KEY=your_key_here
   ```

4. **(Optional) Start MCP servers** (for enhanced tool access):
   ```bash
   # Terminal 1: ChromaDB MCP
   cd chroma_mcp_server && python server.py
   
   # Terminal 2: Filesystem MCP
   cd filesystem_mcp_server && python server.py
   ```

## Testing the Multi-Agent System

The AI Tutor uses an **agent-first architecture** where requests are automatically routed to specialized agents:

- **QA Agent** (`qa`) - Answers questions with RAG (Retrieval-Augmented Generation)
- **Quiz Agent** (`quiz`) - Generates quizzes from documents
- **Note Agent** (`note`) - Creates study notes and summaries
- **Visualization Agent** (`visualization`) - Generates data visualizations from CSV files
- **Web Agent** (`web`) - Fetches current information from the web
- **Ingestion Agent** (`ingestion`) - Processes and stores uploaded documents

See [AGENTS.md](AGENTS.md) for detailed information about each agent.

### Routing Mechanism

Requests are routed using **keyword-based detection**:
- Keywords like "quiz", "test me" → **Quiz Agent**
- Keywords like "summarize", "notes", "create notes" → **Note Agent**
- Keywords like "plot", "chart", "visualize" → **Visualization Agent**
- Keywords like "upload", "ingest" → **Ingestion Agent**
- Generic questions → **QA Agent** (default)

---

## Use Case 1: Document Q&A (QA Agent)

**Purpose**: Test the QA agent's ability to answer questions using RAG from uploaded documents.

### Step 1: Upload a Document

**Via API**:
```bash
curl -X POST "http://localhost:8080/ingest" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@/path/to/lecture.pdf"
```

**Via Streamlit UI**:
- Go to **📚 Corpus Management** tab
- Click "Upload Document"
- Select a PDF file (e.g., `CMPE249_Lecture7.pdf`)
- Wait for green checkmark ✅

**Expected Result**: 
- Document is chunked and embedded
- Stored in ChromaDB vector store
- Response: `{"status": "success", "message": "Document ingested"}`

### Step 2: Ask a Question

**Via API**:
```bash
curl -X POST "http://localhost:8080/answer" \
  -H "Content-Type: application/json" \
  -d '{
    "learner_id": "test_user",
    "question": "What is RegNet?"
  }'
```

**Via Streamlit UI**:
- Go to **💬 Chat & Learn** tab
- Type: `What is RegNet?`

**Expected Result**:
- **Route**: `"qa"` (QA Agent handles this)
- **Answer**: Detailed explanation with citations
- **Citations**: References to specific chunks from the uploaded document
- **Response includes**: `answer`, `citations`, `route: "qa"`, `style: "stepwise"`

### Step 3: Verify Source-Filtered Retrieval

**Test**: Ask a question that should only use the uploaded document:

```bash
curl -X POST "http://localhost:8080/answer" \
  -H "Content-Type: application/json" \
  -d '{
    "learner_id": "test_user",
    "question": "What is RegNet?",
    "source_hints": ["CMPE249_Lecture7.pdf"],
    "documents_only": true
  }'
```

**Expected Result**:
- Only searches within the specified document
- Faster retrieval (pre-filtered by source)
- Citations only from that document

---

## Use Case 2: Quiz Generation (Quiz Agent)

**Purpose**: Test the Quiz Agent's ability to generate quizzes from document content.

### Step 1: Request Quiz Generation

**Via API**:
```bash
curl -X POST "http://localhost:8080/quiz" \
  -H "Content-Type: application/json" \
  -d '{
    "learner_id": "test_user",
    "topic": "RegNet architecture",
    "num_questions": 5
  }'
```

**Via Streamlit UI**:
- Type: `Create 5 quiz questions about RegNet from the uploaded file`

**Expected Result**:
- **Route**: `"quiz"` (Quiz Agent handles this)
- **Response**: Quiz object with:
  - `topic`: "RegNet architecture"
  - `questions`: Array of 5 questions
  - Each question has: `question`, `choices`, `correct_index`, `explanation`

### Step 2: Verify Quiz Content

**Check**:
- Questions are relevant to the topic
- Questions reference content from uploaded documents
- Each question has 4 multiple-choice options
- `correct_index` indicates the correct answer (0-3)
- Explanations are provided

### Step 3: Evaluate Quiz Answers

**Via API**:
```bash
# First, get the quiz (from Step 1)
QUIZ_RESPONSE='{"quiz": {...}, "questions": [...]}'

curl -X POST "http://localhost:8080/quiz/evaluate" \
  -H "Content-Type: application/json" \
  -d '{
    "learner_id": "test_user",
    "quiz": QUIZ_RESPONSE,
    "answers": [0, 1, 2, 0, 1]
  }'
```

**Expected Result**:
- **Evaluation object** with:
  - `total_questions`: 5
  - `correct_count`: Number of correct answers
  - `score`: Percentage (0.0-1.0)
  - `answers`: Array with detailed results per question
  - `review_topics`: Suggested topics for review (if score < 70%)

### Step 4: Test Routing Detection

**Test different quiz request patterns**:

```bash
# Pattern 1: Explicit quiz request
curl -X POST "http://localhost:8080/answer" \
  -d '{"learner_id": "test", "question": "create a quiz about physics"}'
# Expected route: "quiz"

# Pattern 2: Test me
curl -X POST "http://localhost:8080/answer" \
  -d '{"learner_id": "test", "question": "test me on RegNet"}'
# Expected route: "quiz"

# Pattern 3: Practice questions
curl -X POST "http://localhost:8080/answer" \
  -d '{"learner_id": "test", "question": "generate practice questions"}'
# Expected route: "quiz"
```

**Expected Result**: All route to `"quiz"` agent

---

## Use Case 3: Note Generation (Note Agent)

**Purpose**: Test the Note Agent's ability to create structured study notes from documents.

### Step 1: Request Note Creation

**Via API**:
```bash
curl -X POST "http://localhost:8080/answer" \
  -H "Content-Type: application/json" \
  -d '{
    "learner_id": "test_user",
    "question": "Create lesson notes about RegNet from the uploaded file"
  }'
```

**Via Streamlit UI**:
- Type: `Create lesson notes about RegNet from the uploaded file`

**Expected Result**:
- **Route**: `"note"` (Note Agent handles this)
- **Answer**: Structured Markdown notes with:
  - Headers and subheaders
  - Bullet points
  - Key concepts explained
  - References to source document

### Step 2: Verify Note Structure

**Check**:
- Notes are well-organized (headers, sections)
- Content is comprehensive (uses `fetch_full_document` tool)
- Content is relevant to the requested topic
- Citations/references included

### Step 3: Save Notes to File

**Via Streamlit UI**:
- After notes are generated, type: `Save these notes to a file`

**Expected Result**:
- **Route**: `"note"` (Note Agent handles save requests)
- File created in `data/generated/text/`
- Filename based on topic (e.g., `regnet_notes.txt`)
- Response: `"Notes saved to data/generated/text/regnet_notes.txt"`
- File appears in **🗂️ Generated Files** sidebar

### Step 4: Test Note Routing Patterns

**Test different note request patterns**:

```bash
# Pattern 1: Summarize
curl -X POST "http://localhost:8080/answer" \
  -d '{"learner_id": "test", "question": "summarize the document"}'
# Expected route: "note"

# Pattern 2: Create notes
curl -X POST "http://localhost:8080/answer" \
  -d '{"learner_id": "test", "question": "create study notes"}'
# Expected route: "note"

# Pattern 3: Text file
curl -X POST "http://localhost:8080/answer" \
  -d '{"learner_id": "test", "question": "create a text file about BERT"}'
# Expected route: "note"
```

**Expected Result**: All route to `"note"` agent

---

## Use Case 4: Data Visualization (Visualization Agent)

**Purpose**: Test the Visualization Agent's ability to generate plots from CSV data.

### Step 1: Upload CSV File

**Via API**:
```bash
curl -X POST "http://localhost:8080/ingest" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@/path/to/sales_2024.csv"
```

**Via Streamlit UI**:
- Upload CSV file in sidebar
- Wait for green checkmark ✅

### Step 2: Request Visualization

**Via API**:
```bash
curl -X POST "http://localhost:8080/answer" \
  -H "Content-Type: application/json" \
  -d '{
    "learner_id": "test_user",
    "question": "Plot sales per month"
  }'
```

**Via Streamlit UI**:
- Type: `Plot sales per month`

**Expected Result**:
- **Route**: `"visualization"` (Visualization Agent handles this)
- **Answer**: Python code generated (matplotlib/seaborn)
- Code is executed automatically
- Chart image appears in response
- Chart saved to `data/generated/visualizations/`

### Step 3: Verify Visualization

**Check**:
- Chart is generated correctly
- Data is plotted accurately
- Chart type matches request (bar, line, scatter, etc.)
- File saved in generated files directory

### Step 4: Test Visualization Routing

**Test different visualization patterns**:

```bash
# Pattern 1: Plot
curl -X POST "http://localhost:8080/answer" \
  -d '{"learner_id": "test", "question": "plot the data"}'
# Expected route: "visualization"

# Pattern 2: Chart
curl -X POST "http://localhost:8080/answer" \
  -d '{"learner_id": "test", "question": "create a chart"}'
# Expected route: "visualization"

# Pattern 3: Visualize
curl -X POST "http://localhost:8080/answer" \
  -d '{"learner_id": "test", "question": "visualize trends"}'
# Expected route: "visualization"
```

**Expected Result**: All route to `"visualization"` agent

---

## Use Case 5: Session Management

**Purpose**: Test session persistence and event tracking.

### Step 1: Create Session Events

**Via API**:
```bash
# Event 1: Message
curl -X POST "http://localhost:8080/sessions/test_user/events" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_user",
    "event": {
      "type": "message",
      "content": "Hello tutor!"
    }
  }'

# Event 2: Upload
curl -X POST "http://localhost:8080/sessions/test_user/events" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_user",
    "event": {
      "type": "upload",
      "file_ids": ["lecture.pdf"]
    }
  }'

# Event 3: Quiz
curl -X POST "http://localhost:8080/sessions/test_user/events" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_user",
    "event": {
      "type": "quiz",
      "quiz_topic": "physics",
      "quiz_count": 5
    }
  }'
```

**Expected Result**:
- Each event returns a `SessionResponse` with:
  - `session_id`: "test_user"
  - `turn_id`: Incremental (1, 2, 3...)
  - `route`: Agent that handled the event
  - `answer`: Response content
  - `metadata`: Event-specific data

### Step 2: Retrieve Session History

**Via API**:
```bash
curl -X GET "http://localhost:8080/sessions/test_user"
```

**Expected Result**:
- `SessionHistoryResponse` with:
  - `session_id`: "test_user"
  - `events`: Array of all events
  - `responses`: Array of all responses
  - Events and responses are in chronological order

### Step 3: Reset Session

**Via API**:
```bash
curl -X POST "http://localhost:8080/sessions/test_user/reset"
```

**Expected Result**:
- Session cleared
- History reset
- New events start from `turn_id: 1`

---

## Use Case 6: Multi-Agent Routing Verification

**Purpose**: Verify that requests are correctly routed to the appropriate agents.

### Test Matrix

| Request | Expected Route | Agent |
|---------|---------------|-------|
| "What is momentum?" | `qa` | QA Agent |
| "Create 5 quizzes" | `quiz` | Quiz Agent |
| "Summarize the document" | `note` | Note Agent |
| "Plot sales data" | `visualization` | Visualization Agent |
| "Upload a document" | `ingestion` | Ingestion Agent |
| "What's the news today?" | `web` | Web Agent |

### Test Script

```bash
# Test all routing patterns
ENDPOINT="http://localhost:8080/answer"

# QA Agent
curl -X POST "$ENDPOINT" \
  -d '{"learner_id": "test", "question": "What is momentum?"}'
# Check: response.route == "qa"

# Quiz Agent
curl -X POST "$ENDPOINT" \
  -d '{"learner_id": "test", "question": "create 5 quizzes about physics"}'
# Check: response.route == "quiz"

# Note Agent
curl -X POST "$ENDPOINT" \
  -d '{"learner_id": "test", "question": "summarize the document"}'
# Check: response.route == "note"

# Visualization Agent
curl -X POST "$ENDPOINT" \
  -d '{"learner_id": "test", "question": "plot sales per month"}'
# Check: response.route == "visualization"
```

**Expected Result**: Each request routes to the correct agent

---

## Use Case 7: Demo Mode Verification

**Purpose**: Verify that demo mode disables personalization correctly.

### Step 1: Check Demo Mode Settings

**Verify config**:
```bash
grep "demo_mode" config/default.yaml
# Should show: demo_mode: true
```

### Step 2: Test Personalization Disabled

**Via API**:
```bash
curl -X POST "http://localhost:8080/answer" \
  -H "Content-Type: application/json" \
  -d '{
    "learner_id": "test_user",
    "question": "What is force?"
  }'
```

**Expected Result** (in demo mode):
- `style`: `"stepwise"` (static, not adaptive)
- `next_topic`: `null` (no personalization)
- `difficulty`: `null` (no personalization)
- No profile updates

### Step 3: Compare with Production Mode

**If testing production mode** (`demo_mode: false`):
- `style`: May vary based on learner profile
- `next_topic`: Suggested topic
- `difficulty`: Adaptive difficulty level
- Profile updates saved

---

## Testing Checklist

### Core Functionality
- [ ] Document upload and ingestion works
- [ ] Q&A with citations works
- [ ] Quiz generation works
- [ ] Note creation works
- [ ] Data visualization works
- [ ] Session management works

### Multi-Agent Routing
- [ ] QA Agent routes correctly
- [ ] Quiz Agent routes correctly
- [ ] Note Agent routes correctly
- [ ] Visualization Agent routes correctly
- [ ] Default routing to QA works

### Demo Mode
- [ ] Demo mode disables personalization
- [ ] Static style used in demo mode
- [ ] No profile updates in demo mode

### Error Handling
- [ ] Invalid requests handled gracefully
- [ ] Missing documents handled correctly
- [ ] API errors return proper status codes

---

## Troubleshooting

### Issue: Routes to wrong agent
**Check**: Keyword detection in `src/ai_tutor/agents/routing.py`
**Solution**: Verify keyword patterns match request

### Issue: No citations in Q&A
**Check**: Document was ingested successfully
**Solution**: Re-upload document, check vector store

### Issue: Quiz questions not relevant
**Check**: Topic matches document content
**Solution**: Use more specific topic or ensure document contains topic

### Issue: Notes not comprehensive
**Check**: Note Agent uses `fetch_full_document` tool
**Solution**: Verify MCP servers running (if using MCP)

### Issue: Visualization fails
**Check**: CSV file format is valid
**Solution**: Ensure CSV has headers and numeric data

---

## API Testing Tools

### Swagger UI
- Visit: `http://localhost:8080/docs`
- Interactive API testing
- Try endpoints directly

### Postman
- Import OpenAPI spec from `/docs/openapi.json`
- Create test collection
- Run automated tests

### curl
- Use examples above
- Script multiple requests
- Verify responses

---

## Next Steps

After manual testing:
1. Run automated tests: `pytest tests/ -v`
2. Check test coverage: `pytest tests/ --cov`
3. Review logs for errors
4. Document any issues found

See also:
- [GETTING_STARTED.md](GETTING_STARTED.md) - Quick start guide
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [TESTING.md](TESTING.md) - Automated testing

