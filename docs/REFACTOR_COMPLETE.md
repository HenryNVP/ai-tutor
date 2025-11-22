# Refactor Complete: Simplified Architecture

## Summary

Successfully simplified the architecture by flattening the database to a single collection and fixing critical retrieval bugs.

## Key Changes

### 1. Single Collection Architecture
- **Before:** Multiple domain-based collections (`ai_tutor_cs`, `ai_tutor_math`, etc.)
- **After:** Single collection `ai_tutor_master`
- **Benefit:** No routing errors, simpler code

### 2. Full Document Retrieval
- **Before:** Semantic search only returned "best matching" chunks
- **After:** `fetch_full_document` tool retrieves ALL chunks in sequential order
- **Benefit:** Complete summaries covering entire documents

### 3. Pre-Query Filtering
- **Before:** Post-query filtering in Python (chunks from target docs pushed out)
- **After:** ChromaDB `where` clause pre-filters by `source_path`
- **Benefit:** 100% accuracy, faster queries

### 4. Removed Global Cache
- **Before:** Module-level cache that never expired
- **After:** Direct ChromaDB calls (fast enough for local use)
- **Benefit:** No stale data bugs

## Migration

**Existing Data:** Re-ingest documents to populate `ai_tutor_master` collection, or set `use_domain_collections=True` to keep using old collections.

**New Documents:** Automatically stored in `ai_tutor_master` with `chunk_index` for sequential retrieval.

## Files Modified

- `src/ai_tutor/retrieval/factory.py` - Default to single collection
- `src/ai_tutor/retrieval/chroma_store.py` - Added `fetch_full_document`, pre-filtering
- `src/ai_tutor/data_models/document.py` - Added `chunk_index` field
- `src/ai_tutor/ingestion/chunker.py` - Store `chunk_index`
- `src/ai_tutor/agents/note.py` - Added `fetch_full_document` tool
- `src/ai_tutor/agents/retrieval_tools.py` - Removed global cache

## Testing

- Upload multi-page document → Summarize → Verify all chunks retrieved
- Q&A still uses semantic search (unchanged)
- Multiple documents work correctly
