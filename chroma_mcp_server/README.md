# Chroma MCP Server

MCP server that exposes ChromaDB vector database operations to AI agents.

## Quick Start

```bash
cd chroma_mcp_server
python server.py
```

Server runs on `http://localhost:8000/mcp` by default.

## Enable in AI Tutor

```bash
export MCP_USE_SERVER=true
export MCP_PORT=8000
streamlit run apps/ui.py
```

## Available Tools

- **`list_collections()`** - List all collections with document counts
- **`query_collection(collection_name, query_texts, n_results)`** - Query documents by text
- **`add_documents(collection_name, documents, ids, metadatas)`** - Add documents to collection
- **`get_collection_info(collection_name)`** - Get collection metadata and stats
- **`create_collection(name, metadata)`** - Create a new collection
- **`delete_collection(collection_name)`** - Delete a collection

## Configuration

```bash
# Change port
MCP_PORT=8001 python server.py

# Change transport
MCP_TRANSPORT=sse python server.py
```

## Database

- **Location**: `chroma_mcp_server/chroma.sqlite3`
- Uses existing ChromaDB database
- All collections and documents are preserved

## Example Usage

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

## Troubleshooting

**Port already in use:**
```bash
MCP_PORT=8001 python server.py
```

**Server not starting:**
- Check if port is available
- Verify `chromadb` and `mcp` packages are installed
- Check database exists at `chroma_mcp_server/chroma.sqlite3`

