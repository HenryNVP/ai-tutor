# Filesystem MCP Server

Python-native MCP server that exposes safe filesystem operations (list, read, write, delete) to AI agents through the Model Context Protocol.

## Quick Start

### 1. Start the Server

```bash
cd filesystem_mcp_server
python server.py
```

The server will start on port **8100** by default and expose tools at `http://localhost:8100/mcp`.

### 2. Enable in Streamlit App

Set environment variables before launching Streamlit:

```bash
export FS_MCP_USE_SERVER=true
export FS_MCP_PORT=8100          # Optional: default is 8100
export FS_MCP_ROOT=/home/henry/Projects/ai-tutor  # Optional: defaults to project root

streamlit run apps/ui.py
```

The UI sidebar will show the connection status (🟢 Enabled / 🟡 Connecting / 🔴 Failed).

### 3. Test It Works

**Quick Test in Streamlit Chat:**
```
What files are in the project root?
```

**Expected:** Agent uses `list_directory` tool and lists files.

**Or run the test script:**
```bash
python filesystem_mcp_server/test_example.py
```

See [`USAGE_EXAMPLES.md`](USAGE_EXAMPLES.md) for more test examples.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FS_MCP_USE_SERVER` | `false` | Set to `true` to enable filesystem MCP |
| `FS_MCP_PORT` | `8100` | TCP port for the HTTP server |
| `FS_MCP_ROOT` | Project root | Absolute path to workspace root (sandbox boundary) |
| `FS_MCP_TRANSPORT` | `streamable-http` | Transport mode: `streamable-http` or `sse` |
| `FS_MCP_ALLOW_HIDDEN` | `false` | If `true`, include hidden files (`.git`, `.env`, etc.) in listings |
| `FS_MCP_MAX_READ_BYTES` | `131072` | Maximum bytes to read from a single file (128 KB default) |

### Example: Custom Configuration

```bash
# Restrict to a specific directory
export FS_MCP_ROOT=/home/henry/Projects/ai-tutor/data

# Allow hidden files
export FS_MCP_ALLOW_HIDDEN=true

# Use a different port
export FS_MCP_PORT=8200

# Start server
cd filesystem_mcp_server
python server.py
```

## Available Tools

Once connected, agents have access to these MCP tools:

### 1. `list_directory`
List files and directories in a path.

**Parameters:**
- `path` (str, optional): Directory path relative to root. Defaults to root.
- `recursive` (bool, default=False): If true, list recursively.
- `max_entries` (int, default=1000): Maximum entries to return.

**Example:**
```python
# List root directory
list_directory()

# List src/ directory
list_directory(path="src")

# Recursive search
list_directory(path="src", recursive=True, max_entries=500)
```

### 2. `read_file`
Read file contents as text.

**Parameters:**
- `path` (str): File path relative to root.

**Example:**
```python
read_file(path="README.md")
read_file(path="src/ai_tutor/system.py")
```

### 3. `write_text_file`
Create or overwrite a text file.

**Parameters:**
- `path` (str): File path relative to root.
- `content` (str): File contents.

**Example:**
```python
write_text_file(
    path="generated/summary.md",
    content="# Summary\n\nThis is a generated file."
)
```

### 4. `delete_path`
Delete a file or directory.

**Parameters:**
- `path` (str): Path relative to root.
- `recursive` (bool, default=False): If true, delete directories recursively.

**Example:**
```python
# Delete a file
delete_path(path="temp.txt")

# Delete a directory
delete_path(path="temp_dir", recursive=True)
```

## Security

- **Sandboxed**: All paths are resolved relative to `FS_MCP_ROOT`. Attempts to access files outside this directory are rejected.
- **Hidden files**: By default, hidden files (starting with `.`) are excluded from listings unless `FS_MCP_ALLOW_HIDDEN=true`.
- **Read limits**: Files larger than `FS_MCP_MAX_READ_BYTES` are truncated to prevent memory issues.

## Integration with Agents

The filesystem MCP server is automatically passed to agents when enabled:

1. **QA Agent**: Can read course materials, config files, or logs for debugging.
2. **Orchestrator**: Can inspect project structure, read documentation, or write generated content.
3. **Custom Agents**: Any agent with MCP access can use filesystem tools.

### Example: Agent Using Filesystem Tools

```python
# In an agent's tool call
result = await agent.run(
    "Read the README.md file and summarize the key features"
)
# Agent will call read_file(path="README.md") automatically
```

## Troubleshooting

### Server Won't Start

```bash
# Check if port is already in use
lsof -i :8100

# Use a different port
export FS_MCP_PORT=8200
python server.py
```

### Connection Failed in UI

1. **Check server is running**: Look for "Starting Filesystem MCP server..." message
2. **Verify port matches**: Ensure `FS_MCP_PORT` in UI matches server port
3. **Check firewall**: Ensure port is accessible
4. **View logs**: Check Streamlit logs for connection errors

### Path Outside Root Error

If you see `Path 'X' is outside of allowed root`, the requested path escapes the sandbox. Ensure:
- `FS_MCP_ROOT` is set correctly
- Paths are relative to the root (e.g., `src/file.py` not `/absolute/path`)

## Use Cases for AI Tutor Application

### 1. Auto-Save Generated Quizzes

**Scenario**: When a user generates a quiz, automatically save it to disk for later review.

**Agent Action**:
```python
# After generating quiz, QA agent can:
write_text_file(
    path="data/generated_quizzes/quiz_2025-01-15_calculus.md",
    content=quiz_markdown
)
```

**Benefits**:
- Quizzes persist across sessions
- Users can review past quizzes
- No need to regenerate if lost
- Integrates with Generated Files Manager

---

### 2. Create Study Guides from Course Materials

**Scenario**: User asks "Create a study guide from the uploaded physics documents."

**Agent Action**:
```python
# Orchestrator routes to QA agent, which:
# 1. Reads uploaded documents
documents = list_directory(path="data/raw", recursive=True)
# 2. Reads relevant files
content = read_file(path="data/raw/physics_chapter1.pdf")
# 3. Generates study guide
study_guide = generate_study_guide(content)
# 4. Saves to disk
write_text_file(
    path="data/study_guides/physics_chapter1_guide.md",
    content=study_guide
)
```

**Benefits**:
- Personalized study materials
- Reusable across sessions
- Can be shared with other learners

---

### 3. Inspect Configuration for Debugging

**Scenario**: User reports "Retrieval isn't working correctly" - agent needs to check config.

**Agent Action**:
```python
# QA agent can read config to understand settings
config = read_file(path="config/default.yaml")
# Check retrieval settings
retrieval_config = parse_yaml(config)["retrieval"]
# Provide diagnostic answer based on actual config
```

**Benefits**:
- Agents can give accurate troubleshooting
- No need to manually check configs
- Can suggest configuration improvements

---

### 4. Read Logs for Error Diagnosis

**Scenario**: User asks "Why did my document ingestion fail?"

**Agent Action**:
```python
# Ingestion agent can read recent logs
logs = list_directory(path="logs")
# Find most recent ingestion log
recent_log = max([f for f in logs if "ingestion" in f.name])
# Read error details
error_log = read_file(path=f"logs/{recent_log.name}")
# Parse and explain error to user
```

**Benefits**:
- Self-diagnosing system
- Faster troubleshooting
- Better error messages for users

---

### 5. Generate Code Examples and Save Them

**Scenario**: User asks "Show me a Python example for calculating derivatives."

**Agent Action**:
```python
# Visualization/QA agent generates code
code_example = """
import numpy as np
from scipy.misc import derivative

def f(x):
    return x**2

# Calculate derivative at x=2
result = derivative(f, 2.0)
print(f"Derivative at x=2: {result}")
"""
# Save to generated files
write_text_file(
    path="data/generated_code/derivative_example.py",
    content=code_example
)
```

**Benefits**:
- Code examples are saved and reusable
- Appears in Generated Files Manager
- Can be downloaded or shared

---

### 6. Archive Old Session Data

**Scenario**: System needs to clean up old quiz files or session data.

**Agent Action**:
```python
# Maintenance agent can:
# 1. List old files
old_quizzes = list_directory(path="data/generated_quizzes")
# 2. Identify files older than 30 days
# 3. Archive or delete
for quiz in old_quizzes:
    if is_older_than_30_days(quiz):
        delete_path(path=f"data/generated_quizzes/{quiz.name}")
```

**Benefits**:
- Automatic cleanup
- Prevents disk space issues
- Keeps workspace organized

---

### 7. Read Project Documentation for Context

**Scenario**: User asks "What features does this tutor support?"

**Agent Action**:
```python
# Orchestrator can read README for accurate feature list
readme = read_file(path="README.md")
# Extract features section
features = extract_features_from_markdown(readme)
# Provide accurate answer based on actual documentation
```

**Benefits**:
- Answers match actual capabilities
- No outdated information
- Can reference specific features

---

### 8. Create Personalized Learning Paths

**Scenario**: User asks "Create a learning plan for machine learning."

**Agent Action**:
```python
# QA agent:
# 1. Reads available course materials
materials = list_directory(path="data/raw", recursive=True)
ml_files = [f for f in materials if "machine_learning" in f.name.lower()]
# 2. Reads course structure
course_structure = read_file(path="data/course_outline.md")
# 3. Generates personalized path
learning_path = generate_learning_path(ml_files, course_structure)
# 4. Saves to user's profile directory
write_text_file(
    path=f"data/processed/profiles/{learner_id}/learning_path_ml.md",
    content=learning_path
)
```

**Benefits**:
- Personalized study plans
- Tracks learner progress
- Adapts to available materials

---

### 9. Inspect Vector Store Structure

**Scenario**: User asks "What documents are in my knowledge base?"

**Agent Action**:
```python
# QA agent can:
# 1. List vector store directory
vector_files = list_directory(path="data/vector_store")
# 2. Read metadata files
metadata = read_file(path="data/vector_store/metadata.json")
# 3. Provide summary of indexed documents
```

**Benefits**:
- Users understand what's indexed
- Helps debug retrieval issues
- Transparent system behavior

---

### 10. Generate Session Summaries

**Scenario**: At end of session, create a summary of what was learned.

**Agent Action**:
```python
# Orchestrator can:
# 1. Read conversation history
session_log = read_file(path=f"logs/session_{learner_id}_{date}.log")
# 2. Generate summary
summary = generate_session_summary(session_log)
# 3. Save to learner profile
write_text_file(
    path=f"data/processed/profiles/{learner_id}/session_summary_{date}.md",
    content=summary
)
```

**Benefits**:
- Learners can review past sessions
- Tracks learning progress
- Identifies knowledge gaps

---

### 11. Update Configuration Based on Usage

**Scenario**: System learns that retrieval top_k=5 is too low, suggests increasing it.

**Agent Action**:
```python
# Analytics agent can:
# 1. Read current config
config = read_file(path="config/default.yaml")
# 2. Analyze usage patterns
# 3. Suggest improvements
# 4. Create updated config (with user approval)
new_config = update_config(config, {"retrieval": {"top_k": 8}})
write_text_file(
    path="config/suggested_default.yaml",
    content=new_config
)
```

**Benefits**:
- Self-improving system
- Optimizes performance
- Learns from usage patterns

---

### 12. Export Generated Content as Archive

**Scenario**: User wants to download all generated quizzes and visualizations.

**Agent Action**:
```python
# Orchestrator can:
# 1. List all generated files
generated = list_directory(path="data/generated", recursive=True)
# 2. Create organized archive structure
# 3. Write manifest file
manifest = create_manifest(generated)
write_text_file(
    path="data/exports/manifest.json",
    content=manifest
)
```

**Benefits**:
- Easy content export
- Organized file structure
- Supports bulk downloads

## Next Steps

- See `docs/mcp_simple.md` for general MCP concepts
- Check `apps/ui.py` for integration details
- Review `src/ai_tutor/agents/qa.py` for agent usage examples

