# MCP (Model Context Protocol) - Simple Guide

## What is MCP?

MCP (Model Context Protocol) is a protocol that allows AI agents to interact with external tools and data sources through a standardized interface. It uses JSON-RPC over HTTP or stdio.

## Quick Start

### 1. Start the MCP Server

The server exposes Chroma vector database operations as MCP tools.

```bash
cd chroma_data/chroma_example
python server.py
```

Server will start at `http://localhost:8000/mcp`

### 2. Run the Client

In a separate terminal:

```bash
cd chroma_data/chroma_example
python main.py
```

## Architecture

```
┌─────────────┐
│   Client    │  (main.py - OpenAI Agent)
│             │
└──────┬──────┘
       │ JSON-RPC (HTTP)
       │
┌──────▼──────┐
│ MCP Server  │  (server.py - FastMCP)
│             │
└──────┬──────┘
       │
┌──────▼──────┐
│   ChromaDB  │  (chroma.sqlite3)
│             │
└─────────────┘
```

## Available Tools

The server exposes these Chroma operations:

- **`list_collections()`** - List all collections with document counts
- **`create_collection(name, metadata)`** - Create a new collection
- **`add_documents(collection_name, documents, ids, metadatas)`** - Add documents
- **`query_collection(collection_name, query_texts, n_results)`** - Query documents
- **`get_collection_info(collection_name)`** - Get collection info
- **`delete_collection(collection_name)`** - Delete a collection

## Configuration

### Server Configuration

```bash
# Change port
MCP_PORT=8001 python server.py

# Change transport (streamable-http or sse)
MCP_TRANSPORT=sse python server.py
```

### Client Configuration

```bash
# Connect to different port
MCP_PORT=8001 python main.py

# Auto-start server (instead of connecting to existing)
MCP_AUTO_START=true python main.py
```

## Using MCP in Your Code

### Basic Example

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

## Database Location

The server uses your existing Chroma database:
- **Location**: `chroma_data/chroma.sqlite3`
- All collections and documents are preserved

## Troubleshooting

### Port Already in Use

```bash
# Use a different port
MCP_PORT=8001 python server.py
```

### Server Not Starting

- Check if port is available
- Verify `chromadb` and `mcp` packages are installed
- Check database exists at `chroma_data/chroma.sqlite3`

### Client Can't Connect

- Make sure server is running first
- Check server URL matches client configuration
- Verify port numbers match

## Key Concepts

### Transport Types

- **Streamable HTTP** (default): Modern, efficient transport
- **SSE**: Server-Sent Events, good for long connections
- **stdio**: Standard input/output, used for local processes

### JSON-RPC

MCP uses JSON-RPC 2.0 protocol:
- Requests: `{"jsonrpc": "2.0", "method": "tools/list", "id": 1}`
- Responses: `{"jsonrpc": "2.0", "result": [...], "id": 1}`

All communication happens over this protocol.

## Files

- **`server.py`**: MCP server implementation (FastMCP)
- **`main.py`**: Client example using OpenAI Agents SDK
- **`chroma.sqlite3`**: Your Chroma database

## Next Steps

1. Explore the tools by running `main.py`
2. Modify `server.py` to add custom tools
3. Integrate MCP into your own applications

