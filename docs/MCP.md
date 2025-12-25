# MCP Servers (Optional)

MCP servers provide additional tools for agents. **Not required for basic functionality.**

## Quick Start

### 1. Start Servers

**Terminal 1 - Chroma MCP:**
```bash
cd chroma_mcp_server
python server.py
# Port 8000 (default)
```

**Terminal 2 - Filesystem MCP:**
```bash
cd filesystem_mcp_server
python server.py
# Port 8100 (default)
```

### 2. Enable in Application

```bash
export MCP_USE_SERVER=true      # Chroma MCP
export FS_MCP_USE_SERVER=true   # Filesystem MCP

streamlit run apps/ui.py
```

## What They Provide

**Chroma MCP:**
- Collection management
- Document queries
- Vector database operations

**Filesystem MCP:**
- Read/write files
- List directories
- File organization

## Configuration

**Ports:**
```bash
export MCP_PORT=8000           # Chroma MCP port (default: 8000)
export FS_MCP_PORT=8100        # Filesystem MCP port (default: 8100)
```

**Filesystem Root:**
```bash
export FS_MCP_ROOT=/path/to/workspace  # Default: project root
```

## Notes

- MCP servers are **optional** - system works without them
- Primary retrieval uses direct API (faster)
- MCP tools used for specialized operations (full document access, file management)
- Sidebar shows connection status
