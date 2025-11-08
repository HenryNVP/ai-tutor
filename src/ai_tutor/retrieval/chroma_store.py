from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional

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
    """
    ChromaDB-backed vector store with domain-based collections.
    
    This store organizes chunks into separate collections by primary domain,
    enabling efficient domain-specific retrieval and better organization.
    Each domain (math, physics, cs, etc.) has its own collection.
    """

    def __init__(
        self,
        directory: Path,
        collection_name: Optional[str] = None,
        use_domain_collections: bool = True,
    ):
        """
        Initialize ChromaDB client and collections.
        
        Parameters
        ----------
        directory : Path
            Directory where ChromaDB will store its data
        collection_name : Optional[str]
            Legacy single collection name. If provided and use_domain_collections=False,
            uses a single collection. Otherwise, uses domain-based collections.
        use_domain_collections : bool
            If True, uses separate collections per domain. If False, uses a single
            collection (legacy mode).
        """
        if chromadb is None:
            raise ImportError(
                "chromadb is required for ChromaVectorStore. "
                "Install it with: pip install chromadb"
            )
        
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.use_domain_collections = use_domain_collections
        self.collection_name = collection_name or "ai_tutor_chunks"
        
        # Initialize ChromaDB client with persistent storage
        self.client = chromadb.PersistentClient(
            path=str(directory),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Collections cache: domain -> Collection
        self._collections: Dict[str, chromadb.Collection] = {}
        
        if not use_domain_collections:
            # Legacy mode: single collection
            try:
                self._default_collection = self.client.get_collection(name=self.collection_name)
                logger.info(f"Loaded existing ChromaDB collection: {self.collection_name}")
            except Exception:
                self._default_collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info(f"Created new ChromaDB collection: {self.collection_name}")
        else:
            # Domain-based collections: create on demand
            self._default_collection = None
            logger.info("Using domain-based collections")
    
    def _get_collection(self, domain: str) -> chromadb.Collection:
        """
        Get or create collection for a domain.
        
        Parameters
        ----------
        domain : str
            Primary domain name (e.g., "math", "physics", "cs")
        
        Returns
        -------
        chromadb.Collection
            Collection for the specified domain
        """
        if not self.use_domain_collections:
            return self._default_collection
        
        # Normalize domain
        domain = domain.lower() if domain else "general"
        if domain not in ["math", "physics", "cs", "chemistry", "biology", "general"]:
            domain = "general"
        
        collection_name = f"ai_tutor_{domain}"
        
        if collection_name not in self._collections:
            try:
                collection = self.client.get_collection(name=collection_name)
                logger.debug(f"Loaded existing collection: {collection_name}")
            except Exception:
                collection = self.client.create_collection(
                    name=collection_name,
                    metadata={
                        "hnsw:space": "cosine",
                        "domain": domain
                    }
                )
                logger.info(f"Created new collection: {collection_name} for domain: {domain}")
            
            self._collections[collection_name] = collection
        
        return self._collections[collection_name]

    def add(self, chunks: Iterable[Chunk]) -> None:
        """
        Insert or update chunk embeddings in ChromaDB.
        
        Chunks are routed to domain-specific collections based on their
        primary_domain metadata. If use_domain_collections is False,
        all chunks go to a single collection.
        """
        chunks_to_add = [chunk for chunk in chunks if chunk.embedding is not None]
        if not chunks_to_add:
            return
        
        # Group chunks by domain
        chunks_by_domain: Dict[str, List[Chunk]] = defaultdict(list)
        
        for chunk in chunks_to_add:
            # Determine domain: prefer primary_domain, fallback to domain
            domain = getattr(chunk.metadata, "primary_domain", None) or chunk.metadata.domain or "general"
            chunks_by_domain[domain].append(chunk)
        
        # Add chunks to appropriate collections
        for domain, domain_chunks in chunks_by_domain.items():
            collection = self._get_collection(domain)
            
            # Prepare data for ChromaDB
            ids = []
            embeddings = []
            metadatas = []
            documents = []
            
            for chunk in domain_chunks:
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
                    "domain": chunk.metadata.domain or "",  # Legacy field
                    "primary_domain": getattr(chunk.metadata, "primary_domain", domain) or domain,
                    "secondary_domains": ",".join(getattr(chunk.metadata, "secondary_domains", []) or []),
                    "domain_tags": ",".join(getattr(chunk.metadata, "domain_tags", []) or []),
                    "domain_confidence": float(getattr(chunk.metadata, "domain_confidence", 0.5)),
                    "section": chunk.metadata.section or "",
                }
                metadatas.append(metadata)
                
                # Store text as document (required by ChromaDB)
                documents.append(chunk.text)
            
            # Upsert to ChromaDB (updates if exists, inserts if not)
            try:
                collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    documents=documents
                )
                logger.debug(f"Added {len(domain_chunks)} chunks to collection for domain: {domain}")
            except Exception as e:
                logger.error(f"Failed to add chunks to ChromaDB collection '{domain}': {e}")
                raise

    def search(
        self,
        embedding: List[float],
        top_k: int,
        source_filter: List[str] | None = None,
        domain_filter: Optional[str] | None = None,
        search_all_domains: bool = False,
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
        domain_filter : Optional[str] | None
            If provided, only search in the specified domain's collection.
            If None and use_domain_collections=True, searches all collections.
        search_all_domains : bool
            If True and use_domain_collections=True, searches across all domain
            collections and merges results. Default False (searches primary domain
            or all if domain_filter not specified).
        """
        if not self.use_domain_collections:
            # Legacy mode: search single collection
            return self._search_single_collection(
                self._default_collection, embedding, top_k, source_filter
            )
        
        # Domain-based search
        if domain_filter:
            # Search specific domain
            logger.info(f"[ChromaVectorStore] Searching in domain collection: {domain_filter}")
            collection = self._get_collection(domain_filter)
            return self._search_single_collection(
                collection, embedding, top_k, source_filter
            )
        
        # Default behavior: when using domain collections and no domain_filter,
        # search all domains to find the best matches across all collections
        if search_all_domains or (not domain_filter):
            # Search all domain collections and merge results
            all_hits: List[RetrievalHit] = []
            
            # Query each collection (skip general if it's empty, but include it for completeness)
            for domain in ["math", "physics", "cs", "chemistry", "biology", "general"]:
                try:
                    collection = self._get_collection(domain)
                    collection_count = collection.count()
                    
                    # Skip empty collections
                    if collection_count == 0:
                        logger.debug(f"Skipping empty collection: {domain}")
                        continue
                    
                    # Get more results per domain to ensure good coverage
                    hits = self._search_single_collection(
                        collection, embedding, top_k * 2, source_filter
                    )
                    all_hits.extend(hits)
                    logger.debug(f"Found {len(hits)} hits in {domain} collection ({collection_count} total docs)")
                except Exception as e:
                    logger.debug(f"Error searching domain {domain}: {e}")
                    continue
            
            # Sort by score and return top_k
            all_hits.sort(key=lambda x: x.score, reverse=True)
            logger.info(f"Searched all domains, found {len(all_hits)} total hits, returning top {min(top_k, len(all_hits))}")
            return all_hits[:top_k]
        else:
            # Only search general collection if explicitly requested
            collection = self._get_collection("general")
            return self._search_single_collection(
                collection, embedding, top_k, source_filter
            )
    
    def _search_single_collection(
        self,
        collection: chromadb.Collection,
        embedding: List[float],
        top_k: int,
        source_filter: List[str] | None = None,
    ) -> List[RetrievalHit]:
        """Search a single ChromaDB collection."""
        # Query ChromaDB - get more results if filtering to ensure we have enough
        query_k = top_k * 3 if source_filter else top_k
        collection_count = collection.count()
        
        if collection_count == 0:
            return []
        
        try:
            results = collection.query(
                query_embeddings=[embedding],
                n_results=min(query_k, collection_count),
                where=None
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
            
            # Extract domain metadata
            primary_domain = metadata_dict.get("primary_domain") or metadata_dict.get("domain", "general")
            secondary_domains_str = metadata_dict.get("secondary_domains", "")
            secondary_domains = [s.strip() for s in secondary_domains_str.split(",") if s.strip()] if secondary_domains_str else []
            domain_tags_str = metadata_dict.get("domain_tags", "")
            domain_tags = [t.strip() for t in domain_tags_str.split(",") if t.strip()] if domain_tags_str else []
            domain_confidence = float(metadata_dict.get("domain_confidence", 0.5))
            
            chunk_metadata = ChunkMetadata(
                chunk_id=chunk_id,
                source_path=Path(metadata_dict.get("source_path", "")),
                title=metadata_dict.get("title") or "",
                doc_id=metadata_dict.get("doc_id", ""),
                page=metadata_dict.get("page") or None,
                domain=metadata_dict.get("domain", primary_domain),  # Legacy field
                primary_domain=primary_domain,
                secondary_domains=secondary_domains,
                domain_tags=domain_tags,
                domain_confidence=domain_confidence,
                section=metadata_dict.get("section") or None,
            )
            
            # Create Chunk without embedding (ChromaDB doesn't return embeddings)
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
    def from_path(
        cls,
        path: Path,
        use_domain_collections: bool = True,
    ) -> "ChromaVectorStore":
        """
        Load or create ChromaDB store at the given path.
        
        Parameters
        ----------
        path : Path
            Directory path for ChromaDB storage
        use_domain_collections : bool
            If True, uses domain-based collections. Default True.
        
        Returns
        -------
        ChromaVectorStore
            Initialized vector store instance
        """
        return cls(path, use_domain_collections=use_domain_collections)

