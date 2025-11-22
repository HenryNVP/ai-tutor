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

## Hybrid Approach

The AI Tutor uses a **hybrid approach** combining direct access and MCP tools:

### Primary: Direct Retriever

**For semantic search:**
- Uses direct Python API to vector store (ChromaDB)
- Fast (~10-50ms), reliable, no network calls
- Searches all domain collections automatically
- Automatic filtering and deduplication
- Structured output (RetrievalHit objects)

**Example:** `retrieve_local_context()` function tool uses direct retriever

### Secondary: MCP Tools

**For specialized use cases:**
- **Chroma MCP**: Collection management, specific collection queries
- **Filesystem MCP**: Full document access, file organization, reading specific sections

**When agents use MCP:**
- Need full document context (not just chunks)
- Need specific document sections
- Need to organize files (e.g., quiz organization)
- Need collection management operations

**Benefits:**
- ✅ Fast primary retrieval (direct API)
- ✅ Complete context when needed (MCP file access)
- ✅ Flexible file organization (filesystem MCP)
- ✅ Best of both worlds

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


## Server-Specific Documentation

- **Chroma MCP**: See `chroma_mcp_server/README.md`
- **Filesystem MCP**: See `filesystem_mcp_server/README.md`

