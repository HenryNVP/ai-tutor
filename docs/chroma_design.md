# ChromaDB Design Documentation

## Overview

The AI Tutor system uses **ChromaDB** as its primary vector database for storing and retrieving document embeddings. ChromaDB provides persistent storage using SQLite as the backend, making it ideal for local development and production deployments.

## Architecture

### Storage Location

- **Default Path**: `data/vector_store/` (configurable via `config/default.yaml`)
- **Notebook Path**: `chroma_mcp_server/` (used in Google Colab notebooks)
- **Database File**: `chroma.sqlite3` (SQLite database)
- **Collection Directories**: UUID-named directories for each collection's index files

### Client Configuration

```python
# PersistentClient with local file storage
client = chromadb.PersistentClient(
    path=str(directory),
    settings=Settings(anonymized_telemetry=False)
)
```

## Collection Structure

### Default Collection

- **Name**: `ai_tutor_chunks`
- **Similarity Metric**: Cosine distance (`hnsw:space: cosine`)
- **Purpose**: Stores all document chunks with their embeddings

### Collection Metadata

```python
{
    "hnsw:space": "cosine"  # HNSW index with cosine similarity
}
```

## Data Model

### Chunk Storage Schema

Each chunk is stored in ChromaDB with the following structure:

#### Required Fields

1. **`id`** (string)
   - Unique identifier: `chunk.metadata.chunk_id`
   - Format: Hash-based ID derived from chunk text, document ID, and chunk index

2. **`embedding`** (list[float])
   - Vector representation: 768-dimensional (BAAI/bge-base-en model)
   - Normalized for cosine similarity
   - Stored in HNSW index for fast approximate nearest neighbor search

3. **`document`** (string)
   - Chunk text content: `chunk.text`
   - Required by ChromaDB API

#### Metadata Fields

All metadata stored as strings, numbers, or booleans (ChromaDB requirement):

```python
{
    "source_path": str(chunk.metadata.source_path),  # Full file path
    "title": chunk.metadata.title or "",             # Document title
    "doc_id": chunk.metadata.doc_id,                # Document ID
    "page": chunk.metadata.page or "",               # Page number/label
    "domain": chunk.metadata.domain or "",           # Domain: math/physics/cs/general
    "section": chunk.metadata.section or "",         # Section identifier
}
```

### Example Chunk Record

```python
{
    "id": "abc123def456...",
    "embedding": [0.123, -0.456, 0.789, ...],  # 768 dimensions
    "document": "The derivative of a function...",
    "metadata": {
        "source_path": "/path/to/calculus_textbook.pdf",
        "title": "Calculus Volume 1",
        "doc_id": "doc_xyz789",
        "page": "42",
        "domain": "math",
        "section": "Chapter 3.2"
    }
}
```

## Operations

### Insertion (Upsert)

```python
collection.upsert(
    ids=[chunk_id1, chunk_id2, ...],
    embeddings=[embedding1, embedding2, ...],
    metadatas=[metadata1, metadata2, ...],
    documents=[text1, text2, ...]
)
```

- **Upsert semantics**: Updates existing chunks if ID exists, inserts if new
- **Batch processing**: All chunks from a document are added in one operation
- **Automatic persistence**: ChromaDB persists immediately

### Query (Search)

```python
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=top_k,
    where=where_clause  # Optional metadata filtering
)
```

**Response Structure**:
```python
{
    "ids": [[chunk_id1, chunk_id2, ...]],
    "distances": [[0.15, 0.23, ...]],  # Cosine distances
    "metadatas": [[metadata1, metadata2, ...]],
    "documents": [[text1, text2, ...]]
}
```

**Distance to Similarity Conversion**:
- ChromaDB cosine distance: `0` = identical, `2` = opposite
- Similarity score: `1.0 - (distance / 2.0)`
- Range: `0.0` (opposite) to `1.0` (identical)

### Source Filtering

The system supports filtering by source filename:

```python
# Query more results, then filter post-query
query_k = top_k * 3 if source_filter else top_k

# Filter results by matching source_path filenames
if source_filter:
    source_name = Path(metadata["source_path"]).name.lower()
    if source_name not in normalized_filenames:
        continue
```

**Note**: ChromaDB doesn't support case-insensitive queries directly, so the system:
1. Queries 3x more results when filtering
2. Filters results post-query by filename matching
3. Returns top_k filtered results

## Index Structure

### HNSW (Hierarchical Navigable Small World)

- **Algorithm**: HNSW for approximate nearest neighbor search
- **Space**: Cosine similarity
- **Performance**: Fast retrieval even with large collections (100K+ chunks)
- **Storage**: Stored in collection-specific UUID directories

### Collection Directory Structure

```
chroma_mcp_server/
├── chroma.sqlite3          # Main SQLite database
└── <collection-uuid>/      # Collection index directory
    ├── data_level0.bin     # HNSW index data
    ├── header.bin          # Index header
    ├── length.bin          # Vector lengths
    └── link_lists.bin      # HNSW graph structure
```

## Integration Points

### 1. Ingestion Pipeline

```python
# In IngestionPipeline.ingest_paths()
vector_store.add(chunks)      # Add chunks to ChromaDB
vector_store.persist()        # Ensure persistence (auto-saved)
```

### 2. Retrieval System

```python
# In Retriever.retrieve()
hits = vector_store.search(
    embedding=query_embedding,
    top_k=config.top_k,
    source_filter=source_filenames  # Optional
)
```

### 3. System Initialization

```python
# In TutorSystem.__init__()
vector_store = create_vector_store(settings.paths.vector_store_dir)
# Creates ChromaVectorStore with collection "ai_tutor_chunks"
```

## Configuration

### Environment Variables

- `VECTOR_STORE_TYPE`: `"chroma"` (default) or `"faiss"`

### YAML Configuration

```yaml
paths:
  vector_store_dir: "data/vector_store"  # ChromaDB storage location

embeddings:
  model: "BAAI/bge-base-en"              # Embedding model (768 dims)
  normalize: true                         # Normalize for cosine similarity
```

## Performance Characteristics

### Storage

- **Embedding Size**: 768 floats × 4 bytes = ~3KB per chunk
- **Metadata**: ~200-500 bytes per chunk
- **Text**: Variable (typically 500-2000 characters)
- **Total**: ~5-10KB per chunk on disk

### Query Performance

- **Latency**: <10ms for top-5 queries (typical)
- **Scalability**: Handles 100K+ chunks efficiently
- **Memory**: Index loaded into memory for fast access

### Batch Operations

- **Ingestion Speed**: ~50-100 chunks/second (CPU)
- **Embedding Generation**: Dominates ingestion time (~70%)
- **Batch Size**: 256 chunks per embedding batch (configurable)

## Data Persistence

### Automatic Persistence

- ChromaDB `PersistentClient` automatically saves all changes
- No explicit `persist()` call needed (but provided for API consistency)
- SQLite transactions ensure data integrity

### Backup Strategy

1. **Database File**: `chroma.sqlite3` contains all metadata
2. **Collection Directories**: UUID directories contain index files
3. **Backup**: Copy entire `chroma_mcp_server/` directory for full backup

## Limitations & Considerations

### 1. Metadata Types

- ChromaDB only supports: strings, numbers, booleans
- Complex objects must be serialized to strings
- Path objects converted to strings

### 2. Case-Insensitive Filtering

- ChromaDB doesn't support case-insensitive metadata queries
- System implements post-query filtering for source filenames
- Queries 3x more results when filtering to ensure enough matches

### 3. Embedding Dimensions

- Fixed at 768 dimensions (BAAI/bge-base-en)
- Changing embedding model requires re-indexing all chunks

### 4. Collection Management

- Currently uses single collection: `ai_tutor_chunks`
- All documents stored in one collection
- Domain filtering done via metadata, not separate collections

## Future Enhancements

### Potential Improvements

1. **Multi-Collection Support**
   - Separate collections per domain (math, physics, cs)
   - Easier domain-specific queries

2. **Metadata Indexing**
   - Index metadata fields for faster filtering
   - Support complex where clauses

3. **Embedding Model Flexibility**
   - Support multiple embedding dimensions
   - Model versioning in metadata

4. **Collection Versioning**
   - Track collection schema versions
   - Migration support for schema changes

## Troubleshooting

### Common Issues

1. **Collection Not Found**
  - Collection auto-created on first use
  - Check `chroma_mcp_server/` directory exists

2. **Import Errors**
   - Ensure `chromadb` is installed: `pip install chromadb`
   - Check Python version compatibility

3. **Performance Issues**
   - Large collections may need HNSW parameter tuning
   - Consider increasing `ef_construction` and `ef_search`

4. **Storage Growth**
   - ChromaDB doesn't automatically compact
   - Consider periodic re-indexing for large deletions

## References

- **ChromaDB Documentation**: https://docs.trychroma.com/
- **HNSW Algorithm**: https://arxiv.org/abs/1603.09320
- **Implementation**: `src/ai_tutor/retrieval/chroma_store.py`

