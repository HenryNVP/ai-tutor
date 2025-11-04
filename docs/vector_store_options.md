# Vector Store Options for AI Tutor

This document compares persistent vector storage options for the AI Tutor system. The current implementation uses `SimpleVectorStore` (numpy-based), but you have `chromadb` and `faiss-cpu` already in dependencies.

## Current Implementation

**SimpleVectorStore** (numpy + sklearn)
- ✅ Already working
- ✅ Simple, no external dependencies
- ❌ Slow for large datasets (O(n) cosine similarity)
- ❌ Loads entire index into memory
- ❌ Not optimized for production scale

## Recommended Options

### 1. **ChromaDB** ⭐ (Recommended for Production)

**Pros:**
- ✅ Already in `pyproject.toml` dependencies
- ✅ Built-in persistence (SQLite backend)
- ✅ Excellent Python API
- ✅ Metadata filtering (perfect for `source_filter`)
- ✅ Good performance for medium datasets
- ✅ Easy to switch from SimpleVectorStore

**Cons:**
- ⚠️ Can be slower than FAISS for very large datasets
- ⚠️ Memory usage scales with dataset size

**Use Case:** Best for production deployments with moderate datasets (< 1M vectors)

**Installation:** Already installed (`chromadb>=0.4.24`)

---

### 2. **FAISS** ⭐ (Recommended for Performance)

**Pros:**
- ✅ Already in `pyproject.toml` dependencies
- ✅ Extremely fast (Facebook's optimized library)
- ✅ Supports GPU acceleration (faiss-gpu)
- ✅ Multiple index types (IVF, HNSW, etc.)
- ✅ Best for large-scale datasets

**Cons:**
- ⚠️ More complex API
- ⚠️ Need to handle persistence manually (save/load index files)
- ⚠️ Metadata filtering requires custom implementation

**Use Case:** Best for large datasets (> 100K vectors) or when speed is critical

**Installation:** Already installed (`faiss-cpu>=1.7.4`)

---

### 3. **Qdrant** (Cloud-Ready Option)

**Pros:**
- ✅ Excellent performance
- ✅ Built-in persistence
- ✅ REST API (can run as separate service)
- ✅ Advanced filtering capabilities
- ✅ Cloud-hosted option available

**Cons:**
- ❌ Not in current dependencies (needs installation)
- ⚠️ Requires separate service for production (optional)

**Use Case:** Best for distributed deployments or cloud-native architecture

**Installation:** `pip install qdrant-client`

---

### 4. **Weaviate** (Feature-Rich)

**Pros:**
- ✅ Very feature-rich (graphQL, multiple vectorizers)
- ✅ Built-in persistence
- ✅ Good for complex metadata queries

**Cons:**
- ❌ Heavyweight (might be overkill)
- ❌ Requires separate service
- ❌ Not in current dependencies

**Use Case:** Best for complex multi-tenant scenarios

---

### 5. **LanceDB** (Modern Alternative)

**Pros:**
- ✅ Fast (uses Apache Arrow/Parquet)
- ✅ SQL-like query interface
- ✅ Good for analytics workloads

**Cons:**
- ❌ Newer, less mature ecosystem
- ❌ Not in current dependencies

**Use Case:** Best for analytics-heavy use cases

---

## Recommendation Matrix

| Use Case | Recommended | Reason |
|----------|------------|--------|
| **Quick migration** | **ChromaDB** | Already installed, easiest transition |
| **Maximum performance** | **FAISS** | Already installed, fastest for large datasets |
| **Production scale** | **Qdrant** | Best balance of features and performance |
| **Current setup** | **ChromaDB** | Minimal changes, good performance |

---

## Implementation Priority

1. **ChromaDB** - Easiest migration, already in dependencies
2. **FAISS** - If you need maximum speed
3. **Qdrant** - If you want cloud-ready solution

---

## Next Steps

See `docs/vector_store_implementation.md` for code examples implementing ChromaDB and FAISS backends.

