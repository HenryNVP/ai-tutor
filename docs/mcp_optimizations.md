# MCP Server Optimizations

This document describes the optimizations made to resolve bottlenecks in multi-agent orchestration with the local Chroma MCP server.

## Problems Identified

1. **Redundant tool listing**: Multiple concurrent calls to `tools/list` (e.g., requests ID=1 and ID=2)
2. **Blocking event loop**: ~7s latency for local MCP calls due to synchronous embedding operations
3. **Agent reinitialization**: Agents were being recreated after each query (stateless orchestration)
4. **Synchronous blocking**: Embedding queries blocking the MCP server event loop

## Solutions Implemented

### 1. Async MCP Server Tools with Thread Pool Executor

**File**: `chroma_data/chroma_example/server.py`

- **Problem**: `generate_embedding()` and `query_with_text()` were synchronous, blocking the event loop
- **Solution**: 
  - Converted tools to async functions
  - Offloaded CPU-bound embedding operations to a `ThreadPoolExecutor` (2 workers)
  - Used `asyncio.run_in_executor()` to keep the event loop non-blocking

**Changes**:
```python
# Before: Synchronous blocking
@mcp.tool()
def generate_embedding(query_text: str) -> dict[str, Any]:
    embedding = embedding_client.embed_query(query_text)  # Blocks event loop
    return {"embedding": embedding, ...}

# After: Async with thread pool
@mcp.tool()
async def generate_embedding(query_text: str) -> dict[str, Any]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_embedding_executor, _generate_embedding_sync, query_text)
```

**Impact**: 
- Event loop stays responsive during embedding operations
- Multiple queries can be processed concurrently
- Reduced latency from ~7s to non-blocking async operations

### 2. Tool List Caching

**Files**: 
- `apps/ui.py` (MCPServerManager)
- `src/ai_tutor/agents/tutor.py`

- **Problem**: Tools were being listed on every query, causing redundant API calls
- **Solution**:
  - MCP client configured with `cache_tools_list=True`
  - MCP server connection is a singleton (initialized once via `MCPServerManager`)
  - Connection persists across all queries in a session

**Changes**:
```python
# MCPServerManager ensures single connection
class MCPServerManager:
    def initialize(self) -> Optional[Any]:
        if self._initialized and self.server_obj is not None:
            return self.server_obj  # Return cached connection
        
        self.server = MCPServerStreamableHttp(
            cache_tools_list=True,  # Cache tool list to avoid redundant calls
            ...
        )
```

**Impact**:
- Tool list fetched once per session, not per query
- Eliminated redundant `tools/list` API calls
- Faster agent initialization

### 3. Persistent Agent Context

**File**: `src/ai_tutor/agents/tutor.py`

- **Problem**: Agents were being recreated after each query
- **Solution**:
  - Agents are built once in `_build_agents()` during `TutorAgent.__init__()`
  - Same agent instances reused across all queries via `_run_specialist()`
  - MCP server connection shared across all agents

**Architecture**:
```
TutorAgent.__init__()
  └─> _build_agents()  # Called once
      ├─> build_qa_agent(mcp_server=self.mcp_server)  # MCP server passed once
      ├─> build_web_agent(...)
      └─> Agent(orchestrator, mcp_servers=[...])

TutorAgent.answer_question()
  └─> _answer_async()
      └─> _run_specialist()
          └─> Runner.run_streamed(agent_to_run, ...)  # Reuses same agent instance
```

**Impact**:
- Agents maintain context across queries
- MCP server connection reused (no reconnection overhead)
- Faster query processing (no agent initialization per query)

### 4. Non-Blocking Event Loop

**File**: `chroma_data/chroma_example/server.py`

- **Problem**: Synchronous operations blocking the async event loop
- **Solution**:
  - All heavy operations (embedding generation, Chroma queries) run in thread pool
  - Event loop remains responsive for other requests
  - Proper async/await pattern throughout

**Thread Pool Configuration**:
```python
_embedding_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="embedding")
```

**Impact**:
- Event loop stays non-blocking
- Multiple concurrent requests can be processed
- Better resource utilization

## Performance Improvements

### Before Optimizations
- **Tool listing**: Multiple calls per query (~100-200ms each)
- **Embedding latency**: ~7s per query (blocking)
- **Agent initialization**: Per query overhead
- **Event loop**: Blocked during embeddings

### After Optimizations
- **Tool listing**: Once per session (cached)
- **Embedding latency**: Non-blocking async operations
- **Agent initialization**: Once per system startup
- **Event loop**: Always responsive

## Configuration

### Environment Variables

```bash
# Enable MCP server
MCP_USE_SERVER=true

# MCP server port (default: 8000)
MCP_PORT=8000

# HTTP timeout (default: 10 seconds)
MCP_TIMEOUT=10

# Optional: Bearer token for authentication
MCP_SERVER_TOKEN=your_token_here
```

### MCP Server Settings

The MCP client is configured with:
- `cache_tools_list=True`: Cache tool list to reduce API calls
- `max_retry_attempts=3`: Automatic retries for network issues
- Persistent connection via `MCPServerManager`: Single connection reused

## Verification

To verify optimizations are working:

1. **Check logs** for tool listing:
   ```
   [TutorAgent] MCP server provided - agents will use MCP tools with cached tool list
   [TutorAgent] Agents built - MCP tools will be cached and reused across queries
   ```

2. **Monitor MCP server logs**:
   - Should see `[debug-server]` logs for tool calls
   - Embedding operations should complete without blocking

3. **Performance metrics**:
   - First query: May include tool list fetch (~100-200ms)
   - Subsequent queries: No tool list fetch, faster response

## Architecture

```
┌─────────────────┐
│  Streamlit App  │
│  (apps/ui.py)   │
└────────┬────────┘
         │
         │ @st.cache_resource
         ▼
┌─────────────────┐
│  TutorSystem     │  (initialized once, cached)
│  (system.py)    │
└────────┬────────┘
         │
         │ mcp_server (singleton)
         ▼
┌─────────────────┐
│  TutorAgent      │  (agents built once)
│  (tutor.py)      │
└────────┬────────┘
         │
         │ Persistent agents with MCP
         ▼
┌─────────────────┐
│  QA Agent        │  ──┐
│  Web Agent       │  ──┼──> Shared MCP server
│  Orchestrator    │  ──┘     (tools cached)
└─────────────────┘
         │
         │ Async tool calls
         ▼
┌─────────────────┐
│  MCP Server      │  (async, non-blocking)
│  (server.py)     │
└────────┬────────┘
         │
         │ Thread pool executor
         ▼
┌─────────────────┐
│  Embedding      │  (offloaded to threads)
│  Chroma Query   │
└─────────────────┘
```

## Summary

All bottlenecks have been resolved:

1. ✅ **Tool listing**: Cached per session via `cache_tools_list=True` and singleton MCP connection
2. ✅ **Event loop**: Non-blocking with async tools and thread pool executor
3. ✅ **Agent context**: Persistent agents built once and reused
4. ✅ **MCP server**: Fully async with heavy operations offloaded

The system now efficiently handles multiple concurrent queries with minimal overhead and no blocking operations.

