# Getting Started

## Quick Start

### Prerequisites

```bash
# Python 3.10+
pip install -r requirements.txt

# Set API keys
export OPENAI_API_KEY=your_key_here      # For OpenAI models
export GEMINI_API_KEY=your_key_here      # For Gemini models
```

### Launch the App

```bash
streamlit run apps/ui.py
```

### Launch FastAPI Backend

```bash
uvicorn apps.api:app --reload --port 8080
```

## Configuration

Demo mode is **enabled by default** in `config/default.yaml`. It simplifies the system by:
- ✅ Disabling personalization (faster startup)
- ✅ Using static "stepwise" style (consistent experience)
- ✅ Documents cached (no chunking/embedding in demo mode)

**Edit `config/default.yaml` to customize:**
```yaml
model:
  name: "gemini/gemini-2.0-flash"  # Main model

demo_mode: true  # Enable demo mode

note_agent:
  model: "gemini/gemini-2.0-flash"  # Agent-specific models
  use_full_context: true
```

## Core Use Cases

### 1. Basics & Conversation
- **Action**: Type "Hello" or "Hi there"
- **Expectation**: Friendly greeting and capability overview

### 2. Document QA (RAG)
- **Action**: Upload PDF in sidebar, then ask "What is RegNet?"
- **Expectation**: Answer cited from uploaded document

### 3. Generate Study Notes
- **Action**: Ask "Create lesson notes about RegNet from the file"
- **Expectation**: Structured Markdown output, saved to sidebar

### 4. Generate Quiz
- **Action**: Ask "Create 5 review quizzes from the uploaded file"
- **Expectation**: Interactive quiz UI with immediate feedback

### 5. Data Visualization
- **Action**: Upload CSV, ask "Plot sales per month"
- **Expectation**: Python code generated and executed, chart appears

## Configuration

### Demo Mode vs Production

**Demo Mode** (`demo_mode: true`):
- No personalization
- Static "stepwise" style
- Faster startup
- Focus on RAG capabilities

**Production Mode** (`demo_mode: false`):
- Full personalization
- Adaptive difficulty
- Progress tracking
- Style selection based on mastery

### Config Files

- `config/default.yaml` - Full configuration (demo mode enabled by default)
- `config/demo.yaml` - Minimal configuration for quick demos

## MCP Servers (Optional)

MCP servers provide tool access for agents. For basic demo, they're not required.

If using MCP servers:
```bash
# Terminal 1: Filesystem MCP
python filesystem_mcp_server/server.py

# Terminal 2: ChromaDB MCP
python chroma_mcp_server/server.py

# Terminal 3: Streamlit UI
streamlit run apps/ui.py
```

## Next Steps

- See [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- See [TESTING.md](TESTING.md) for automated testing
- See [MANUAL_TESTING.md](MANUAL_TESTING.md) for manual testing guide
- See [README.md](../README.md) for full documentation

