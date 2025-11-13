# Filesystem MCP Server - Usage Examples

## Quick Test Setup

### 1. Start Both MCP Servers

**Terminal 1 - Chroma MCP:**
```bash
cd chroma_mcp_server
python server.py
# Should start on port 8000
```

**Terminal 2 - Filesystem MCP:**
```bash
cd filesystem_mcp_server
python server.py
# Should start on port 8100
```

### 2. Enable in Streamlit

**Terminal 3 - Streamlit App:**
```bash
export MCP_USE_SERVER=true
export FS_MCP_USE_SERVER=true
streamlit run apps/ui.py
```

## Testing in Streamlit UI

Once both servers are running and enabled, try these queries in the chat:

### Example 1: List Project Files
```
What files are in the project root directory?
```

**Expected behavior:**
- Orchestrator or QA agent uses `list_directory` tool
- Returns list of files and directories

### Example 2: Read Documentation
```
Read the README.md file and tell me what this project does
```

**Expected behavior:**
- Agent uses `read_file(path="README.md")` tool
- Summarizes the README content

### Example 3: Explore Source Code
```
What Python files are in the src/ai_tutor/agents directory?
```

**Expected behavior:**
- Agent uses `list_directory(path="src/ai_tutor/agents")` tool
- Lists all Python files in that directory

### Example 4: Read Configuration
```
What's in the config/default.yaml file?
```

**Expected behavior:**
- Agent uses `read_file(path="config/default.yaml")` tool
- Shows or summarizes the configuration

### Example 5: Check Logs
```
What's in the most recent log file?
```

**Expected behavior:**
- Agent uses `list_directory(path="logs")` to find logs
- Then uses `read_file` to read the most recent one

## Testing with Python Script

Run the test script:

```bash
python filesystem_mcp_server/test_example.py
```

This will:
1. Check if servers are running
2. Test direct filesystem MCP connection
3. Test integration with TutorSystem

## Verifying Tools Are Available

### Check in Streamlit UI

1. Open Streamlit app
2. Check sidebar - should show:
   - `MCP Server: 🟢 Enabled` (Chroma)
   - `MCP Server: 🟢 Enabled` (Filesystem)

### Check via API

```python
from agents.mcp import MCPServerStreamableHttp

async with MCPServerStreamableHttp(
    name="Filesystem MCP Server",
    params={"url": "http://localhost:8100/mcp"},
) as server:
    # List available tools
    tools = await server.list_tools()
    for tool in tools:
        print(f"- {tool.name}: {tool.description}")
```

Expected output:
```
- list_directory: List files and directories...
- read_file: Read file contents...
- write_text_file: Create or overwrite a text file...
- delete_path: Delete a file or directory...
```

## Common Issues

### "Connection Failed" in UI

1. **Check servers are running:**
   ```bash
   # Check Chroma MCP
   curl http://localhost:8000
   
   # Check Filesystem MCP
   curl http://localhost:8100
   ```

2. **Check environment variables:**
   ```bash
   echo $MCP_USE_SERVER
   echo $FS_MCP_USE_SERVER
   ```

3. **Check ports:**
   ```bash
   lsof -i :8000  # Chroma MCP
   lsof -i :8100  # Filesystem MCP
   ```

### Tools Not Appearing

- Make sure both servers are started BEFORE launching Streamlit
- Check that `FS_MCP_USE_SERVER=true` is set
- Restart Streamlit after setting environment variables

### Agent Not Using Filesystem Tools

- Verify orchestrator and QA agent have MCP servers (check logs)
- Try explicit queries like "read the README file"
- Check agent instructions mention filesystem tools

## Advanced Testing

### Test Write Operation

```python
# In a Python script or agent query:
"Create a test file called test_output.txt with content 'Hello from MCP'"
```

**Expected:**
- Agent uses `write_text_file(path="test_output.txt", content="...")`
- File is created in project root

### Test Delete Operation

```python
"Delete the test_output.txt file"
```

**Expected:**
- Agent uses `delete_path(path="test_output.txt")`
- File is removed

### Test Recursive Directory Listing

```python
"List all files recursively in the src/ directory"
```

**Expected:**
- Agent uses `list_directory(path="src", recursive=True)`
- Returns all files in subdirectories

## Monitoring Tool Usage

Enable debug logging to see tool calls:

```bash
export LOG_LEVEL=DEBUG
streamlit run apps/ui.py
```

Look for log messages like:
```
[QA Agent] Calling tool: list_directory
[QA Agent] Tool result: {...}
```

## Next Steps

Once verified, agents can:
- Auto-save generated quizzes to disk
- Read configuration files for debugging
- Create study guides and save them
- Inspect project structure
- Manage generated files automatically

See `filesystem_mcp_server/README.md` for detailed use cases.

