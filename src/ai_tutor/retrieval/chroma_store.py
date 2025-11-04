from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, List

try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    chromadb = None
    Settings = None

from ai_tutor.data_models import Chunk, ChunkMetadata, RetrievalHit
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
        if chromadb is None:
            raise ImportError(
                "chromadb is required for ChromaVectorStore. "
                "Install it with: pip install chromadb"
            )
        
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
            logger.info(f"Loaded existing ChromaDB collection: {collection_name}")
        except Exception:
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}  # Cosine similarity
            )
            logger.info(f"Created new ChromaDB collection: {collection_name}")

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
            # ChromaDB metadata must be strings, numbers, or booleans
            metadata = {
                "source_path": str(chunk.metadata.source_path),
                "title": chunk.metadata.title or "",
                "doc_id": chunk.metadata.doc_id,
                "page": chunk.metadata.page or "",
                "domain": chunk.metadata.domain or "",
                "section": chunk.metadata.section or "",
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
            If provided, only return chunks from these source files (filenames).
            Filenames are matched case-insensitively against chunk.metadata.source_path.
        """
        # Build where clause for source filtering
        where_clause = None
        if source_filter:
            # Normalize filenames for case-insensitive matching
            normalized_filenames = {Path(f).name.lower() for f in source_filter}
            
            # ChromaDB supports filtering, but we need to handle case-insensitive matching
            # Since ChromaDB doesn't support case-insensitive queries directly,
            # we'll query more results and filter post-query
            where_clause = None  # Will filter after query
        
        # Query ChromaDB - get more results if filtering to ensure we have enough
        query_k = top_k * 3 if source_filter else top_k
        
        try:
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=min(query_k, self.collection.count()),  # Don't exceed collection size
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
            # Convert distance to similarity score
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            # Similarity: 1 - (distance / 2)
            distance = distances[idx]
            similarity = max(0.0, min(1.0, 1.0 - (distance / 2.0)))
            
            # Apply source filter if needed
            if source_filter:
                source_path = metadatas[idx].get("source_path", "")
                source_name = Path(source_path).name.lower()
                normalized_filenames = {Path(f).name.lower() for f in source_filter}
                if source_name not in normalized_filenames:
                    continue
            
            # Reconstruct Chunk object
            metadata_dict = metadatas[idx]
            
            chunk_metadata = ChunkMetadata(
                chunk_id=chunk_id,
                source_path=Path(metadata_dict.get("source_path", "")),
                title=metadata_dict.get("title") or "",
                doc_id=metadata_dict.get("doc_id", ""),
                page=metadata_dict.get("page") or None,
                domain=metadata_dict.get("domain", "general"),
                section=metadata_dict.get("section") or None,
            )
            
            # Create Chunk without embedding (ChromaDB doesn't return embeddings)
            # Embeddings are optional in Chunk, so this is fine
            chunk = Chunk(
                text=documents[idx],
                embedding=None,  # Not needed for retrieval hits
                metadata=chunk_metadata
            )
            
            hits.append(RetrievalHit(chunk=chunk, score=similarity))
            
            # Stop when we have enough filtered results
            if len(hits) >= top_k:
                break
        
        return hits

    def persist(self) -> None:
        """ChromaDB persists automatically, but we can ensure flush."""
        # ChromaDB persistent client auto-saves, no explicit persist needed
        # The PersistentClient handles all persistence automatically
        pass

    @classmethod
    def from_path(cls, path: Path) -> "ChromaVectorStore":
        """Load or create ChromaDB store at the given path."""
        return cls(path)

