# MCP (Model Context Protocol) Guide

## Overview

MCP allows AI agents to interact with external tools and data sources through a standardized interface. The AI Tutor uses two MCP servers:

1. **Chroma MCP Server** - Vector database operations (port 8000)
2. **Filesystem MCP Server** - File operations (port 8100)

## Quick Start

### 1. Start MCP Servers

**Chroma MCP Server:**
```bash
cd chroma_mcp_server
python server.py
# Runs on http://localhost:8000/mcp
```

**Filesystem MCP Server:**
```bash
cd filesystem_mcp_server
python server.py
# Runs on http://localhost:8100/mcp
```

### 2. Enable in Streamlit

```bash
# Enable Chroma MCP
export MCP_USE_SERVER=true
export MCP_PORT=8000

# Enable Filesystem MCP
export FS_MCP_USE_SERVER=true
export FS_MCP_PORT=8100

# Start Streamlit
streamlit run apps/ui.py
```

Check the sidebar for connection status (🟢 Enabled / 🔴 Failed).

## How It Works

### Connection Flow

```
UI Layer (MCPServerManager)
    ↓ Creates MCPServerStreamableHttp
TutorSystem
    ↓ Receives dictionary of servers
TutorAgent
    ↓ Passes to individual agents
Agents (QA, Orchestrator)
    ↓ Use MCP tools during execution
```

### Agent Integration

Agents automatically receive MCP tools when servers are enabled:

```python
# In TutorAgent
self.qa_agent = build_qa_agent(
    ...,
    mcp_servers=list(self.mcp_servers.values())
)

# Agents SDK automatically:
# 1. Lists tools from MCP servers
# 2. Makes them available to agent
# 3. Agent can call tools during execution
```

## Available Tools

### Chroma MCP Tools

- `list_collections()` - List all collections
- `query_collection(collection_name, query_texts, n_results)` - Query documents
- `add_documents(collection_name, documents, ids, metadatas)` - Add documents
- `get_collection_info(collection_name)` - Get collection info
- `create_collection(name, metadata)` - Create collection
- `delete_collection(collection_name)` - Delete collection

### Filesystem MCP Tools

- `list_directory(path, recursive, max_entries)` - List files
- `read_file(path)` - Read file contents
- `write_text_file(path, content)` - Create/update text files
- `delete_path(path)` - Delete files/directories

## Configuration

### Environment Variables

**Chroma MCP:**
- `MCP_USE_SERVER` - Set to `true` to enable
- `MCP_PORT` - Server port (default: 8000)
- `MCP_URL` - Server URL (default: `http://localhost:8000/mcp`)

**Filesystem MCP:**
- `FS_MCP_USE_SERVER` - Set to `true` to enable
- `FS_MCP_PORT` - Server port (default: 8100)
- `FS_MCP_ROOT` - Workspace root directory
- `FS_MCP_ALLOW_HIDDEN` - Allow hidden files (default: false)
- `FS_MCP_MAX_READ_BYTES` - Max file read size (default: 131072)

## Usage Examples

### Using MCP in Code

```python
from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp

async with MCPServerStreamableHttp(
    name="Chroma MCP Server",
    params={"url": "http://localhost:8000/mcp"},
    cache_tools_list=True,
) as server:
    agent = Agent(
        name="Assistant",
        instructions="Use Chroma tools to query the database.",
        mcp_servers=[server],
    )
    
    result = await Runner.run(agent, "List all collections")
    print(result.final_output)
```

### Testing in Streamlit

**Test Chroma MCP:**
```
List all collections in the database
```

**Test Filesystem MCP:**
```
What files are in the project root?
Read the README.md file
```

## Performance

### Tool List Caching

- First `list_tools()` call: ~10 seconds
- Subsequent calls: ~0ms (cached)
- Enabled by default: `cache_tools_list=True`

### Pre-warming

The UI automatically pre-warms tool lists in the background to avoid blocking the first query.

## Troubleshooting

### Connection Failed

1. **Check servers are running:**
   ```bash
   curl http://localhost:8000  # Chroma
   curl http://localhost:8100  # Filesystem
   ```

2. **Check environment variables:**
   ```bash
   echo $MCP_USE_SERVER
   echo $FS_MCP_USE_SERVER
   ```

3. **Check ports:**
   ```bash
   lsof -i :8000  # Chroma
   lsof -i :8100  # Filesystem
   ```

### Port Already in Use

```bash
# Use different ports
export MCP_PORT=8001
export FS_MCP_PORT=8101
```

### Tools Not Appearing

- Make sure servers are started BEFORE launching Streamlit
- Check that environment variables are set
- Restart Streamlit after setting environment variables

## Architecture

```
┌─────────────┐
│   Agent     │  (QA, Orchestrator)
│             │
└──────┬──────┘
       │ HTTP/JSON-RPC
       │
┌──────▼──────┐
│ MCP Server  │  (FastMCP)
│             │
└──────┬──────┘
       │
┌──────▼──────┐
│   Backend   │  (ChromaDB / Filesystem)
│             │
└─────────────┘
```

## Key Concepts

### Transport Types

- **Streamable HTTP** (default): Modern, efficient transport
- **SSE**: Server-Sent Events, good for long connections
- **stdio**: Standard input/output, used for local processes

### JSON-RPC

MCP uses JSON-RPC 2.0 protocol for all communication:
- Requests: `{"jsonrpc": "2.0", "method": "tools/list", "id": 1}`
- Responses: `{"jsonrpc": "2.0", "result": [...], "id": 1}`

## Server-Specific Documentation

- **Chroma MCP**: See `chroma_mcp_server/README.md`
- **Filesystem MCP**: See `filesystem_mcp_server/README.md`

## Next Steps

1. Start both MCP servers
2. Enable in Streamlit with environment variables
3. Test with queries in the chat interface
4. Check server-specific READMEs for detailed tool documentation

