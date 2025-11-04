# Vector Store Implementation Guide

This guide shows how to implement ChromaDB and FAISS backends for the AI Tutor system.

## Architecture

The `VectorStore` abstract base class defines the interface:
- `add(chunks)` - Insert/update embeddings
- `search(embedding, top_k, source_filter)` - Query with optional filtering
- `persist()` - Save to disk
- `from_path(path)` - Load from disk

## Implementation 1: ChromaDB

### File: `src/ai_tutor/retrieval/chroma_store.py`

```python
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, List

import chromadb
from chromadb.config import Settings

from ai_tutor.data_models import Chunk, RetrievalHit
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


class ChromaVectorStore(VectorStore):
    """ChromaDB-backed vector store with persistent storage."""

    def __init__(self, directory: Path, collection_name: str = "ai_tutor_chunks"):
        """
        Initialize ChromaDB client and collection.
        
        Parameters
        ----------
        directory : Path
            Directory where ChromaDB will store its data
        collection_name : str
            Name of the ChromaDB collection
        """
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        
        # Initialize ChromaDB client with persistent storage
        self.client = chromadb.PersistentClient(
            path=str(directory),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        try:
            self.collection = self.client.get_collection(name=collection_name)
            logger.info(f"Loaded existing collection: {collection_name}")
        except Exception:
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}  # Cosine similarity
            )
            logger.info(f"Created new collection: {collection_name}")

    def add(self, chunks: Iterable[Chunk]) -> None:
        """Insert or update chunk embeddings in ChromaDB."""
        chunks_to_add = [chunk for chunk in chunks if chunk.embedding is not None]
        if not chunks_to_add:
            return
        
        # Prepare data for ChromaDB
        ids = []
        embeddings = []
        metadatas = []
        documents = []  # ChromaDB requires a "document" field
        
        for chunk in chunks_to_add:
            chunk_id = chunk.metadata.chunk_id
            ids.append(chunk_id)
            embeddings.append(chunk.embedding)
            
            # Store chunk metadata
            metadata = {
                "source_path": chunk.metadata.source_path,
                "title": chunk.metadata.title or "",
                "doc_id": chunk.metadata.doc_id,
                "page": chunk.metadata.page or 0,
                "domain": chunk.metadata.domain or "",
            }
            metadatas.append(metadata)
            
            # Store text as document (required by ChromaDB)
            documents.append(chunk.text)
        
        # Upsert to ChromaDB (updates if exists, inserts if not)
        try:
            self.collection.upsert(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents
            )
            logger.debug(f"Added {len(chunks_to_add)} chunks to ChromaDB")
        except Exception as e:
            logger.error(f"Failed to add chunks to ChromaDB: {e}")
            raise

    def search(
        self,
        embedding: List[float],
        top_k: int,
        source_filter: List[str] | None = None
    ) -> List[RetrievalHit]:
        """
        Search ChromaDB for similar vectors.
        
        Parameters
        ----------
        embedding : List[float]
            Query embedding vector
        top_k : int
            Number of results to return
        source_filter : List[str] | None
            If provided, only return chunks from these source files
        """
        # Build where clause for source filtering
        where_clause = None
        if source_filter:
            from pathlib import Path
            # Normalize filenames for case-insensitive matching
            normalized_filenames = {Path(f).name.lower() for f in source_filter}
            
            # ChromaDB supports filtering, but we need to handle filename matching
            # Since we can't do case-insensitive matching directly, we'll filter post-query
            # For now, we'll do a broader search and filter results
            where_clause = None  # Will filter after query
        
        # Query ChromaDB
        try:
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=top_k * 2 if source_filter else top_k,  # Get more if filtering
                where=where_clause
            )
        except Exception as e:
            logger.error(f"ChromaDB query failed: {e}")
            return []
        
        if not results["ids"] or not results["ids"][0]:
            return []
        
        # Build RetrievalHit objects
        hits: List[RetrievalHit] = []
        ids = results["ids"][0]
        distances = results["distances"][0]
        metadatas = results["metadatas"][0]
        documents = results["documents"][0]
        
        for idx, chunk_id in enumerate(ids):
            # Convert distance to similarity score (ChromaDB uses distance, we want similarity)
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            # Similarity: 1 - (distance / 2)
            distance = distances[idx]
            similarity = 1.0 - (distance / 2.0)
            
            # Apply source filter if needed
            if source_filter:
                from pathlib import Path
                source_path = metadatas[idx].get("source_path", "")
                source_name = Path(source_path).name.lower()
                normalized_filenames = {Path(f).name.lower() for f in source_filter}
                if source_name not in normalized_filenames:
                    continue
            
            # Reconstruct Chunk object
            metadata_dict = metadatas[idx]
            from ai_tutor.data_models import ChunkMetadata
            
            chunk_metadata = ChunkMetadata(
                chunk_id=chunk_id,
                source_path=metadata_dict.get("source_path", ""),
                title=metadata_dict.get("title"),
                doc_id=metadata_dict.get("doc_id", ""),
                page=metadata_dict.get("page") or None,
                domain=metadata_dict.get("domain") or None,
            )
            
            # Reconstruct embedding from distance (approximate)
            # Note: ChromaDB doesn't return embeddings, so we'd need to store them separately
            # For now, we'll need to modify the approach or store embeddings in chunk_store
            chunk = Chunk(
                text=documents[idx],
                embedding=None,  # ChromaDB doesn't return embeddings
                metadata=chunk_metadata
            )
            
            hits.append(RetrievalHit(chunk=chunk, score=similarity))
            
            # Stop when we have enough filtered results
            if len(hits) >= top_k:
                break
        
        return hits

    def persist(self) -> None:
        """ChromaDB persists automatically, but we can ensure flush."""
        # ChromaDB persistent client auto-saves, but we can trigger a sync
        try:
            self.client.persist()
        except AttributeError:
            # Persistent client doesn't have persist() method, it's automatic
            pass

    @classmethod
    def from_path(cls, path: Path) -> "ChromaVectorStore":
        """Load or create ChromaDB store at the given path."""
        return cls(path)
```

**Note:** ChromaDB doesn't return embeddings in query results. You'll need to either:
1. Store embeddings separately in `chunk_store` and reconstruct Chunk objects
2. Modify the approach to store embeddings in ChromaDB metadata (not recommended)

---

## Implementation 2: FAISS

### File: `src/ai_tutor/retrieval/faiss_store.py`

```python
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Iterable, List

import faiss
import numpy as np

from ai_tutor.data_models import Chunk, RetrievalHit
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


class FAISSVectorStore(VectorStore):
    """FAISS-backed vector store with persistent storage."""

    def __init__(self, directory: Path, index_type: str = "flat"):
        """
        Initialize FAISS index.
        
        Parameters
        ----------
        directory : Path
            Directory where FAISS index and metadata are stored
        index_type : str
            Type of FAISS index: "flat" (exact) or "ivf" (approximate, faster)
        """
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.index_path = self.directory / "faiss.index"
        self.metadata_path = self.directory / "faiss_metadata.json"
        self.index_type = index_type
        
        self._chunks: Dict[str, Chunk] = {}
        self._chunk_ids: List[str] = []
        self._index: faiss.Index | None = None
        self._dimension: int | None = None
        
        self._load()

    def _load(self) -> None:
        """Load FAISS index and metadata from disk."""
        if self.index_path.exists() and self.metadata_path.exists():
            try:
                # Load metadata
                with self.metadata_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._chunk_ids = data.get("chunk_ids", [])
                    chunks_dict = data.get("chunks", {})
                    self._chunks = {
                        chunk_id: Chunk.model_validate(chunks_dict[chunk_id])
                        for chunk_id in self._chunk_ids
                        if chunk_id in chunks_dict
                    }
                    self._dimension = data.get("dimension")
                
                # Load FAISS index
                if self._dimension:
                    self._index = faiss.read_index(str(self.index_path))
                    logger.info(f"Loaded FAISS index with {self._index.ntotal} vectors")
            except Exception as e:
                logger.error(f"Failed to load FAISS index: {e}")
                self._index = None
        else:
            logger.info("No existing FAISS index found, will create new one")

    def _ensure_index(self, dimension: int) -> None:
        """Ensure FAISS index exists with correct dimension."""
        if self._index is None or self._dimension != dimension:
            self._dimension = dimension
            
            if self.index_type == "ivf" and len(self._chunk_ids) > 1000:
                # Use IVF (Inverted File Index) for approximate search (faster)
                nlist = min(100, len(self._chunk_ids) // 10)  # Number of clusters
                quantizer = faiss.IndexFlatL2(dimension)
                self._index = faiss.IndexIVFFlat(quantizer, dimension, nlist)
                self._index.nprobe = 10  # Number of clusters to search
            else:
                # Use Flat index for exact search
                # Normalize for cosine similarity
                self._index = faiss.IndexFlatIP(dimension)  # Inner product for normalized vectors
            
            # If we have existing chunks, add them to the new index
            if self._chunks:
                embeddings = np.array([
                    self._chunks[chunk_id].embedding
                    for chunk_id in self._chunk_ids
                    if chunk_id in self._chunks and self._chunks[chunk_id].embedding is not None
                ], dtype=np.float32)
                if len(embeddings) > 0:
                    self._index.train(embeddings) if hasattr(self._index, 'train') else None
                    self._index.add(embeddings)
                    logger.info(f"Reconstructed FAISS index with {len(embeddings)} vectors")

    def add(self, chunks: Iterable[Chunk]) -> None:
        """Insert or update chunk embeddings in FAISS index."""
        chunks_to_add = [chunk for chunk in chunks if chunk.embedding is not None]
        if not chunks_to_add:
            return
        
        # Determine dimension from first chunk
        dimension = len(chunks_to_add[0].embedding)
        self._ensure_index(dimension)
        
        # Separate new chunks from updates
        new_chunks = []
        update_indices = []
        
        for chunk in chunks_to_add:
            chunk_id = chunk.metadata.chunk_id
            if chunk_id in self._chunk_ids:
                # Update existing (we'll need to rebuild index for updates)
                idx = self._chunk_ids.index(chunk_id)
                update_indices.append((idx, chunk))
            else:
                new_chunks.append(chunk)
        
        # Handle updates by rebuilding index (FAISS doesn't support in-place updates well)
        if update_indices:
            logger.warning("FAISS updates require index rebuild - this may be slow")
            # For simplicity, we'll just re-add everything
            # In production, you might want a more sophisticated update strategy
            embeddings = np.array([
                self._chunks[chunk_id].embedding if chunk_id in self._chunks
                else next((c.embedding for c in chunks_to_add if c.metadata.chunk_id == chunk_id), None)
                for chunk_id in self._chunk_ids
                if chunk_id in self._chunks or any(c.metadata.chunk_id == chunk_id for c in chunks_to_add)
            ], dtype=np.float32)
            
            # Rebuild index
            if self.index_type == "ivf":
                nlist = min(100, len(self._chunk_ids) // 10)
                quantizer = faiss.IndexFlatL2(dimension)
                self._index = faiss.IndexIVFFlat(quantizer, dimension, nlist)
                self._index.nprobe = 10
            else:
                self._index = faiss.IndexFlatIP(dimension)
            
            if len(embeddings) > 0:
                self._index.train(embeddings) if hasattr(self._index, 'train') else None
                self._index.add(embeddings)
        
        # Add new chunks
        if new_chunks:
            embeddings = np.array([chunk.embedding for chunk in new_chunks], dtype=np.float32)
            
            # Normalize embeddings for cosine similarity (using inner product)
            faiss.normalize_L2(embeddings)
            
            if self._index.ntotal == 0 and hasattr(self._index, 'train'):
                # Train IVF index if needed
                self._index.train(embeddings)
            
            self._index.add(embeddings)
            
            # Update metadata
            for chunk in new_chunks:
                chunk_id = chunk.metadata.chunk_id
                self._chunks[chunk_id] = chunk
                self._chunk_ids.append(chunk_id)
            
            logger.debug(f"Added {len(new_chunks)} new chunks to FAISS index")

    def search(
        self,
        embedding: List[float],
        top_k: int,
        source_filter: List[str] | None = None
    ) -> List[RetrievalHit]:
        """Search FAISS index for similar vectors."""
        if self._index is None or self._index.ntotal == 0:
            return []
        
        # Convert query to numpy array and normalize
        query = np.array([embedding], dtype=np.float32)
        faiss.normalize_L2(query)
        
        # Search FAISS
        k = min(top_k * 3 if source_filter else top_k, self._index.ntotal)
        distances, indices = self._index.search(query, k)
        
        # Build results
        hits: List[RetrievalHit] = []
        for idx, distance in zip(indices[0], distances[0]):
            if idx < 0:  # FAISS returns -1 for invalid results
                continue
            
            chunk_id = self._chunk_ids[idx]
            chunk = self._chunks.get(chunk_id)
            
            if chunk is None:
                continue
            
            # Apply source filter
            if source_filter:
                from pathlib import Path
                source_path = chunk.metadata.source_path
                source_name = Path(source_path).name.lower()
                normalized_filenames = {Path(f).name.lower() for f in source_filter}
                if source_name not in normalized_filenames:
                    continue
            
            # Convert distance to similarity (for cosine similarity with normalized vectors)
            # Inner product of normalized vectors = cosine similarity
            similarity = float(distance)
            
            hits.append(RetrievalHit(chunk=chunk, score=similarity))
            
            if len(hits) >= top_k:
                break
        
        return hits

    def persist(self) -> None:
        """Save FAISS index and metadata to disk."""
        if self._index is not None:
            faiss.write_index(self._index, str(self.index_path))
        
        with self.metadata_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "chunk_ids": self._chunk_ids,
                    "chunks": {
                        chunk_id: chunk.model_dump(mode="json")
                        for chunk_id, chunk in self._chunks.items()
                    },
                    "dimension": self._dimension,
                    "index_type": self.index_type,
                },
                f,
                indent=2,
            )

    @classmethod
    def from_path(cls, path: Path) -> "FAISSVectorStore":
        """Load or create FAISS store at the given path."""
        return cls(path)
```

---

## Updating Factory

Update `src/ai_tutor/retrieval/factory.py`:

```python
from __future__ import annotations

import os
from pathlib import Path

from ai_tutor.retrieval.simple_store import SimpleVectorStore
from ai_tutor.retrieval.vector_store import VectorStore


def create_vector_store(path: Path) -> VectorStore:
    """
    Instantiate the vector store implementation based on environment variable.
    
    Environment Variables:
    - VECTOR_STORE_TYPE: "simple" (default), "chroma", or "faiss"
    """
    store_type = os.getenv("VECTOR_STORE_TYPE", "simple").lower()
    
    if store_type == "chroma":
        from ai_tutor.retrieval.chroma_store import ChromaVectorStore
        return ChromaVectorStore.from_path(path)
    elif store_type == "faiss":
        from ai_tutor.retrieval.faiss_store import FAISSVectorStore
        return FAISSVectorStore.from_path(path)
    else:
        # Default to SimpleVectorStore
        return SimpleVectorStore.from_path(path)
```

---

## Configuration

Add to `config/default.yaml`:

```yaml
# Vector Store Configuration
vector_store:
  type: "simple"  # Options: "simple", "chroma", "faiss"
  index_type: "flat"  # For FAISS: "flat" or "ivf"
```

---

## Migration Notes

1. **ChromaDB**: Stores embeddings internally, but you'll need to reconstruct Chunk objects from metadata
2. **FAISS**: Very fast, but requires manual index persistence
3. **Both**: Support `source_filter` but implementation differs

---

## Testing

After implementation, test with:
```bash
# Test ChromaDB
VECTOR_STORE_TYPE=chroma python -m pytest tests/

# Test FAISS
VECTOR_STORE_TYPE=faiss python -m pytest tests/
```

