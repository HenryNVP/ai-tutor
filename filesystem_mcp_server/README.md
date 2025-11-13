# Filesystem MCP Server

MCP server that exposes safe filesystem operations (list, read, write, delete) to AI agents.

## Quick Start

```bash
cd filesystem_mcp_server
python server.py
```

Server runs on `http://localhost:8100/mcp` by default.

## Enable in AI Tutor

```bash
export FS_MCP_USE_SERVER=true
export FS_MCP_PORT=8100
streamlit run apps/ui.py
```

## Available Tools

- **`list_directory(path, recursive, max_entries)`** - List files and directories
- **`read_file(path)`** - Read file contents (max 128 KB)
- **`write_text_file(path, content)`** - Create or update text files
- **`delete_path(path)`** - Delete files or directories

## Configuration

```bash
# Change port
export FS_MCP_PORT=8200

# Restrict to specific directory
export FS_MCP_ROOT=/path/to/workspace

# Allow hidden files
export FS_MCP_ALLOW_HIDDEN=true

# Change max read size
export FS_MCP_MAX_READ_BYTES=262144  # 256 KB
```

## Security

- All operations are sandboxed to `FS_MCP_ROOT` (default: project root)
- Path sanitization prevents directory traversal attacks
- Hidden files excluded by default (set `FS_MCP_ALLOW_HIDDEN=true` to allow)
- File read size limited (default: 128 KB)

## Example Usage

```python
from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp

async with MCPServerStreamableHttp(
    name="Filesystem MCP Server",
    params={"url": "http://localhost:8100/mcp"},
    cache_tools_list=True,
) as server:
    agent = Agent(
        name="Assistant",
        instructions="Use filesystem tools to manage files.",
        mcp_servers=[server],
    )
    
    result = await Runner.run(agent, "List files in the project root")
    print(result.final_output)
```

## Testing

**Quick test in Streamlit:**
```
What files are in the project root?
Read the README.md file
```

**Or run test script:**
```bash
python filesystem_mcp_server/test_example.py
```

## Troubleshooting

**Port already in use:**
```bash
export FS_MCP_PORT=8200
python server.py
```

**Permission errors:**
- Check `FS_MCP_ROOT` directory exists and is readable
- Verify write permissions if using `write_text_file`
