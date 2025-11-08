# Fixes for Blocking Issues Preventing Answer Generation

## Root Causes Identified

1. **Redundant MCP Tool List Requests**: Multiple simultaneous `tools/list` calls (id=1 and id=2) causing server contention
2. **Embedding Model CPU Load**: Large model (BAAI/bge-base-en) loading on CPU during startup, starving event loop
3. **Event Loop Starvation**: CPU-bound operations blocking async event loop
4. **No Timeouts**: Agent execution could hang indefinitely waiting for MCP server

## Fixes Applied

### 1. Deferred Embedding Model Loading ✅

**File**: `src/ai_tutor/system.py`

- **Before**: Model loaded synchronously at startup, blocking CPU and starving event loop
- **After**: Model loading deferred to first use (lazy loading)
- **Impact**: Startup is non-blocking, event loop stays responsive

```python
# Before: Blocking startup
self.embedder._ensure_model()  # Blocks for several seconds

# After: Lazy loading
# Model loads on first embed_query() call
```

### 2. MCP Tool List Caching ✅

**Files**: 
- `apps/ui.py` (MCPServerManager)
- `src/ai_tutor/agents/tutor.py`

- **Before**: Each agent might fetch tools independently
- **After**: 
  - `cache_tools_list=True` on MCP client
  - All agents share the SAME MCP server instance
  - Tools cached per session
- **Impact**: Tool list fetched once, not per agent or per query

### 3. Timeouts Added ✅

**File**: `src/ai_tutor/agents/tutor.py`

- **Before**: Agent execution could hang indefinitely
- **After**: 
  - 60 second timeout on main agent run
  - 30 second timeout on fallback
  - Proper timeout error handling
- **Impact**: System fails fast instead of hanging forever

```python
result = await asyncio.wait_for(
    Runner.run(agent_to_run, input=prompt, session=session),
    timeout=60.0  # Prevents infinite hangs
)
```

### 4. MCP Server Timeout Configuration ✅

**File**: `apps/ui.py`

- **Before**: No explicit timeout on MCP client
- **After**: `client_session_timeout_seconds` configured
- **Impact**: MCP requests timeout instead of hanging

### 5. Non-Streaming Execution ✅

**File**: `src/ai_tutor/agents/tutor.py`

- **Before**: Streaming might miss final output
- **After**: Using `Runner.run()` (non-streaming) for reliable output capture
- **Impact**: Always captures complete final output

## Verification Steps

1. **Check startup logs**:
   ```
   Embedding model will be loaded on first use (lazy loading)
   [MCP] MCP server configured with tool list caching and timeout enabled
   [TutorAgent] All agents share the same MCP server instance
   ```

2. **Monitor for redundant tool list calls**:
   - Should see only ONE `tools/list` call per session
   - Not multiple simultaneous calls (id=1 and id=2)

3. **Check for timeouts**:
   - If MCP server is slow, should see timeout errors instead of hanging
   - System should fail fast with clear error messages

4. **CPU usage**:
   - Startup should not spike CPU to 100%
   - Embedding model loads on first query, not at startup

## Expected Behavior

- **Startup**: Fast, non-blocking, no CPU spike
- **First Query**: Embedding model loads (one-time cost)
- **Subsequent Queries**: Fast, no redundant tool list calls
- **MCP Server Issues**: Timeout after 60 seconds with clear error

## If Still Blocking

If the system still hangs, check:

1. **MCP Server Status**: Is it running and responsive?
   ```bash
   curl http://localhost:8000
   ```

2. **Tool List Calls**: Check MCP server logs for redundant calls
   - Should see only one `tools/list` per session

3. **CPU Usage**: Check if embedding model is loading during query
   - First query will have CPU spike (expected)
   - Subsequent queries should not

4. **Network Latency**: Check localhost latency
   - Should be < 10ms for localhost
   - If high, MCP server might be overloaded

