# Embedding Dimension Mismatch Issue Explained

## The Problem

When querying ChromaDB collections that were created with custom embeddings (768-dimensional vectors from `BAAI/bge-base-en`), queries fail with an error like:

```
Embedding dimension mismatch: expected 768, got 384
```

## Root Cause

### How Documents Were Stored (Indexing)

1. **During Ingestion:**
   - Documents are processed through `IngestionPipeline`
   - Text chunks are embedded using `EmbeddingClient` with model `BAAI/bge-base-en`
   - This model produces **768-dimensional** embeddings
   - These embeddings are stored directly in ChromaDB via `collection.upsert(embeddings=...)`

```python
# From ingestion pipeline
embedding = embedder.embed_query(chunk.text)  # Returns 768-dim vector
collection.upsert(
    ids=[chunk_id],
    embeddings=[embedding],  # 768-dim vector stored
    documents=[chunk.text],
    metadatas=[metadata]
)
```

### How Queries Work (Two Approaches)

#### Approach 1: Using `query_texts` (FAILS)

When you call:
```python
collection.query(query_texts=["What is calculus?"])
```

ChromaDB's behavior:
1. ChromaDB doesn't have an embedding function configured for this collection
2. It falls back to its **default embedding function**
3. The default function uses a different model (typically `all-MiniLM-L6-v2`)
4. This default model produces **384-dimensional** embeddings
5. ChromaDB tries to compare:
   - Query: 384-dim vector
   - Stored documents: 768-dim vectors
6. **Result: Dimension mismatch error!**

```
Error: Cannot compare 384-dim query vector with 768-dim document vectors
```

#### Approach 2: Using `query_embeddings` (WORKS)

When you call:
```python
# Generate 768-dim embedding first
embedding = embedder.embed_query("What is calculus?")  # 768-dim
collection.query(query_embeddings=[embedding])  # Uses 768-dim
```

This works because:
1. You generate the embedding using the **same model** (`BAAI/bge-base-en`)
2. You get a **768-dimensional** vector
3. ChromaDB compares:
   - Query: 768-dim vector
   - Stored documents: 768-dim vectors
4. **Result: Success!** Dimensions match.

## Visual Representation

```
┌─────────────────────────────────────────────────────────────┐
│                    DOCUMENT INDEXING                        │
├─────────────────────────────────────────────────────────────┤
│ Text: "Calculus is the study of..."                         │
│   ↓                                                          │
│ EmbeddingClient (BAAI/bge-base-en)                          │
│   ↓                                                          │
│ [0.123, -0.456, 0.789, ..., 0.234]  ← 768 dimensions      │
│   ↓                                                          │
│ ChromaDB Collection                                          │
│   └─ Stored as: 768-dim vector                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    QUERY (WRONG WAY)                         │
├─────────────────────────────────────────────────────────────┤
│ Query: "What is calculus?"                                  │
│   ↓                                                          │
│ collection.query(query_texts=["What is calculus?"])          │
│   ↓                                                          │
│ ChromaDB Default Embedding Function                         │
│   ↓                                                          │
│ [0.111, -0.222, 0.333, ..., 0.444]  ← 384 dimensions ❌    │
│   ↓                                                          │
│ ERROR: Dimension mismatch!                                  │
│   Expected: 768, Got: 384                                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    QUERY (CORRECT WAY)                       │
├─────────────────────────────────────────────────────────────┤
│ Query: "What is calculus?"                                  │
│   ↓                                                          │
│ EmbeddingClient (BAAI/bge-base-en)                          │
│   ↓                                                          │
│ [0.123, -0.456, 0.789, ..., 0.234]  ← 768 dimensions ✅    │
│   ↓                                                          │
│ collection.query(query_embeddings=[embedding])                │
│   ↓                                                          │
│ SUCCESS: Dimensions match!                                   │
└─────────────────────────────────────────────────────────────┘
```

## Why ChromaDB Has a Default Embedding Function

ChromaDB provides a default embedding function for convenience:
- Allows quick prototyping without setting up embedding models
- Uses `all-MiniLM-L6-v2` (384-dim) by default
- Works well for simple use cases

However, when you:
- Store embeddings manually (like we do)
- Use a different embedding model
- Need specific embedding dimensions

The default function becomes a problem because it assumes you want to use its default model.

## The Solution

We fixed this by adding two new tools to the MCP server:

### 1. `generate_embedding(query_text)`
Generates a 768-dim embedding using the same model as indexing:
```python
embedding = embedding_client.embed_query("What is calculus?")
# Returns: [0.123, -0.456, ..., 0.234]  (768 dimensions)
```

### 2. `query_with_text(collection_name, query_text)`
Convenience function that:
1. Generates the embedding automatically
2. Queries the collection
3. Returns formatted results

```python
results = query_with_text("ai_tutor_math", "What is calculus?")
# Internally:
#   1. embedding = embed_query("What is calculus?")  # 768-dim
#   2. collection.query(query_embeddings=[embedding])  # Works!
```

## Technical Details

### Embedding Model: BAAI/bge-base-en

- **Dimensions:** 768
- **Provider:** sentence-transformers
- **Normalized:** Yes (for cosine similarity)
- **Model Size:** ~110MB

### ChromaDB Default: all-MiniLM-L6-v2

- **Dimensions:** 384
- **Provider:** sentence-transformers (ChromaDB's default)
- **Normalized:** Yes
- **Model Size:** ~23MB

### Why Dimensions Must Match

Vector similarity search (cosine similarity, dot product, etc.) requires:
- Same number of dimensions in query and document vectors
- Mathematical operations (dot product, cosine) only work on same-sized vectors

```
Cosine Similarity = (A · B) / (||A|| × ||B||)

Where:
- A = query vector (must be same size as B)
- B = document vector
- · = dot product (requires same dimensions)
```

## Best Practices

1. **Always use the same embedding model** for indexing and querying
2. **Store embeddings explicitly** when using custom models
3. **Use `query_embeddings`** instead of `query_texts` for custom-embedded collections
4. **Document your embedding model** in collection metadata

## Summary

- **Problem:** Collections use 768-dim embeddings, but `query_texts` tries to use 384-dim default embeddings
- **Root Cause:** ChromaDB's default embedding function uses a different model
- **Solution:** Generate embeddings explicitly using the same model, then use `query_embeddings`
- **Prevention:** Always use `query_embeddings` when collections have custom embeddings

