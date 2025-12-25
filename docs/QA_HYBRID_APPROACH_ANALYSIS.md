# QA Agent Hybrid Approach Analysis

## Current State

### QA Agent (Current)
- **Only uses**: `retrieve_local_context` (semantic search with embeddings)
- **When `source_filter` provided**: Searches within that document using embeddings
- **Problem in demo mode**: Documents are cached but not embedded, so `retrieve_local_context` returns empty results

### Quiz Agent (Already Hybrid)
- **Checks**: `is_uploaded_doc_context = extra_context and len(extra_context) > 500`
- **If uploaded doc**: Uses `extra_context` directly (full document text)
- **If general query**: Uses vector store retrieval (RAG with embeddings)
- **Works in demo mode**: Can use cached documents via `extra_context`

### Note Agent (Already Hybrid)
- **Has two tools**:
  1. `read_raw_document` - Reads from document cache (fast, no chunks)
  2. `fetch_full_document` - Retrieves all chunks from vector store (fallback)
- **Preference**: Uses `read_raw_document` when available (Gemini + cache)
- **Fallback**: Uses `fetch_full_document` if cache unavailable

## Proposed Hybrid Approach for QA Agent

### Strategy
1. **Normal QA** (no document upload) → Use RAG with embeddings
   - Requires chunking/embedding
   - Works across multiple documents
   - Semantic search finds relevant passages

2. **Uploaded Document QA** → Use full document from cache
   - No chunking/embedding needed
   - Faster (no database queries)
   - Better coherence (no chunk boundaries)
   - Similar to Quiz Agent's approach

### Implementation

#### Option 1: Add `read_raw_document` Tool (Similar to Note Agent)
**Pros:**
- Consistent with Note Agent pattern
- Agent can choose between tools
- Works in demo mode (cache available)

**Cons:**
- Agent needs to decide which tool to use
- More complex instructions

#### Option 2: Conditional Tool Selection (Recommended)
**Approach:**
- Add `read_raw_document` tool to QA Agent
- Update instructions to prefer cache when `source_filter` is provided
- Fallback to `retrieve_local_context` if cache unavailable

**Flow:**
```
User asks question with source_filter (uploaded doc)
  ↓
QA Agent checks: Is document in cache?
  ↓ YES → Use read_raw_document (full doc text)
  ↓ NO  → Use retrieve_local_context (semantic search)
```

#### Option 3: Automatic Context Injection (Like Quiz Agent)
**Approach:**
- Check if `source_filter` points to cached document
- If yes, inject full document text into prompt as `extra_context`
- QA Agent uses inline context directly

**Pros:**
- No new tools needed
- Consistent with Quiz Agent
- Simpler agent instructions

**Cons:**
- Requires changes to `TutorAgent._build_agent_prompt`
- Less flexible (can't choose per question)

## Recommendation: Option 2 (Conditional Tool Selection)

### Why?
1. **Flexibility**: Agent can choose based on context
2. **Consistency**: Similar to Note Agent pattern
3. **Demo Mode Compatible**: Works with cached documents
4. **Backward Compatible**: Falls back to RAG if cache unavailable

### Implementation Steps

1. **Add `read_raw_document` tool to QA Agent**
   - Similar to Note Agent's implementation
   - Only available when `document_cache` is provided

2. **Update QA Agent instructions**
   - Prefer `read_raw_document` when `source_filter` is provided
   - Use `retrieve_local_context` for general queries or fallback

3. **Update test expectations**
   - In demo mode, `chunk_count` will be 0
   - Test should check `document_count > 0` instead

4. **Pass `document_cache` to QA Agent**
   - Similar to how Note Agent receives it

## Benefits

### Performance
- **Faster**: No embedding queries for uploaded documents
- **Lower latency**: Direct cache access vs. vector search

### Quality
- **Better coherence**: Full document context vs. chunk boundaries
- **More accurate**: No information loss from chunking

### Simplicity
- **Demo mode**: No need for chunking/embedding
- **Production mode**: Still uses RAG for general queries

## Comparison with Quiz Agent

| Aspect | Quiz Agent | Proposed QA Agent |
|--------|-----------|-------------------|
| Uploaded docs | Uses `extra_context` | Uses `read_raw_document` tool |
| General queries | Uses RAG | Uses RAG |
| Demo mode | Works (via `extra_context`) | Works (via cache) |
| Tool selection | Automatic (service layer) | Agent decides |

## Migration Path

1. ✅ Document cache already exists
2. ✅ `read_raw_document` tool already implemented (Note Agent)
3. ⏳ Add `read_raw_document` to QA Agent
4. ⏳ Update QA Agent instructions
5. ⏳ Update tests to handle demo mode
6. ⏳ Pass `document_cache` to QA Agent

## Test Updates Needed

```python
# Current test (fails in demo mode)
assert upload_result["chunk_count"] > 0

# Updated test (works in demo mode)
assert upload_result["document_count"] > 0
# In demo mode, chunk_count will be 0, but document_count > 0
```

