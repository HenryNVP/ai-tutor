# Chroma MCP Server Example Client

This directory contains an example client that demonstrates how to use the Chroma MCP Server with the OpenAI Agents SDK.

## Quick Start

### 1. Start the MCP Server

In a separate terminal, start the MCP server:

```bash
cd chroma_mcp_server
python server.py
```

The server will start at `http://localhost:8000/mcp` by default.

### 2. Run the Example Client

```bash
cd chroma_mcp_server/chroma_example
python main.py
```

## Configuration

You can configure the client using environment variables:

```bash
# Use a different port
MCP_PORT=8001 python main.py

# Use a custom URL
MCP_URL=http://localhost:8001/mcp python main.py
```

## What It Does

The example client:
1. Connects to the Chroma MCP Server
2. Creates an agent with access to Chroma tools
3. Runs example queries to list collections

## Customization

Modify `main.py` to:
- Add your own queries
- Use different MCP server URLs
- Integrate with your own applications

