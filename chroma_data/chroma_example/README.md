# Chroma MCP Server Example

A simple example of using MCP (Model Context Protocol) to expose Chroma vector database operations.

> For a quick start guide, see [docs/mcp_simple.md](../../docs/mcp_simple.md)

## What This Does

This example shows how to:
- Create an MCP server that exposes Chroma operations
- Connect to the server using OpenAI Agents SDK
- Query your existing `chroma.sqlite3` database

## Quick Start

### 1. Start Server

```bash
cd chroma_data/chroma_example
python server.py
```

Server runs at `http://localhost:8000/mcp`

### 2. Run Client

In another terminal:

```bash
cd chroma_data/chroma_example
python main.py
```

## Files

- **`server.py`** - MCP server using FastMCP
- **`main.py`** - Client example using OpenAI Agents SDK

## Available Tools

- `list_collections()` - List all collections with counts
- `create_collection(name, metadata)` - Create collection
- `add_documents(...)` - Add documents to collection
- `query_collection(...)` - Query documents
- `get_collection_info(name)` - Get collection info
- `delete_collection(name)` - Delete collection

## Configuration

```bash
# Change port
MCP_PORT=8001 python server.py

# Change transport
MCP_TRANSPORT=sse python server.py

# Auto-start server from client
MCP_AUTO_START=true python main.py
```

## Database

Uses existing database: `chroma_data/chroma.sqlite3`

## Dependencies

- `chromadb` - Chroma vector database
- `mcp` - Model Context Protocol
- `fastmcp` - FastMCP server framework
- `openai-agents` - OpenAI Agents SDK (for client)
