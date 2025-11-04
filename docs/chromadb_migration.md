# ChromaDB Migration Guide

This guide explains how to migrate from `SimpleVectorStore` to `ChromaVectorStore`.

## Overview

The AI Tutor system now uses **ChromaDB** as the default vector store backend. ChromaDB provides:
- ✅ Better performance for medium to large datasets
- ✅ Built-in persistence (SQLite backend)
- ✅ Excellent metadata filtering
- ✅ Production-ready scalability

## Migration Steps

### 1. Verify ChromaDB Installation

ChromaDB is already in your `pyproject.toml` dependencies. Verify it's installed:

```bash
pip install chromadb>=0.4.24
```

### 2. Set Environment Variable (Optional)

By default, the system now uses ChromaDB. You can override this with:

```bash
# Use ChromaDB (default)
export VECTOR_STORE_TYPE=chroma

# Or fall back to SimpleVectorStore
export VECTOR_STORE_TYPE=simple
```

### 3. Migration Path

**Option A: Fresh Start (Recommended for new deployments)**

ChromaDB will create a new database automatically. Simply start using the system:

```bash
streamlit run apps/ui.py
```

The system will automatically use ChromaDB and create a new collection.

**Option B: Migrate Existing Data**

If you have existing data in `SimpleVectorStore`, you have two options:

1. **Re-ingest documents** (recommended):
   - ChromaDB uses a different storage format
   - Re-ingest documents to ensure compatibility
   - Old data remains in `data/vector_store/embeddings.npy` (can be deleted)

2. **Keep both stores**:
   - Old `SimpleVectorStore` data remains untouched
   - New ChromaDB data is stored in `data/vector_store/chroma.sqlite3`
   - You can switch between them using `VECTOR_STORE_TYPE`

### 4. Data Location

ChromaDB stores data in:
```
data/vector_store/
├── chroma.sqlite3        # ChromaDB database
└── [collection files]   # ChromaDB collection data
```

The old `SimpleVectorStore` files remain:
```
data/vector_store/
├── embeddings.npy        # Old numpy array (can be deleted)
└── metadata.json         # Old metadata (can be deleted)
```

### 5. Verify Migration

After starting the system, check logs for:

```
INFO: Created new ChromaDB collection: ai_tutor_chunks
```

Or if loading existing data:

```
INFO: Loaded existing ChromaDB collection: ai_tutor_chunks
```

## Configuration

No configuration changes needed! The system automatically uses ChromaDB by default.

## Troubleshooting

### Import Error

If you see:
```
ImportError: chromadb is required for ChromaVectorStore
```

Install ChromaDB:
```bash
pip install chromadb
```

### Fallback to SimpleVectorStore

If ChromaDB is not available, the system automatically falls back to `SimpleVectorStore` with a warning:

```
WARNING: ChromaDB not available, falling back to SimpleVectorStore
```

### Performance

ChromaDB may be slightly slower on first query (initialization), but subsequent queries are faster than `SimpleVectorStore`.

### Data Migration

ChromaDB and SimpleVectorStore use different formats. To migrate:
1. Keep old data in `data/vector_store/`
2. Re-ingest documents (they'll be stored in ChromaDB)
3. Delete old `.npy` and `metadata.json` files after verification

## Rollback

To rollback to SimpleVectorStore:

```bash
export VECTOR_STORE_TYPE=simple
```

Or remove the environment variable and change the default in `src/ai_tutor/retrieval/factory.py`:

```python
store_type = os.getenv("VECTOR_STORE_TYPE", "simple").lower()  # Change "chroma" to "simple"
```

## Benefits of ChromaDB

1. **Better Performance**: Optimized for vector search
2. **Automatic Persistence**: No manual save/load needed
3. **Metadata Filtering**: Built-in support for filtering by source files
4. **Scalability**: Handles larger datasets more efficiently
5. **Production Ready**: Used by many production RAG systems

## Next Steps

- Test the system with ChromaDB
- Re-ingest documents if needed
- Monitor performance improvements
- Consider FAISS for even faster searches on very large datasets

