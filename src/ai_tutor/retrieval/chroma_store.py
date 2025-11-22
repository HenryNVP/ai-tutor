from __future__ import annotations

import logging
from collections import defaultdict
import re
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
    ChromaDB-backed vector store with single master collection.
    
    REFACTORED: Uses a single collection (ai_tutor_master) instead of domain-based
    collections. Domain is stored as metadata for optional filtering, but all chunks
    are in one collection for simpler retrieval.
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
        # REFACTOR: Default to single master collection
        self.collection_name = collection_name or "ai_tutor_master"
        
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
        
        # REFACTOR: Use single collection instead of grouping by domain
        if self.use_domain_collections:
            # Legacy: Group chunks by domain
            chunks_by_domain: Dict[str, List[Chunk]] = defaultdict(list)
            for chunk in chunks_to_add:
                domain = getattr(chunk.metadata, "primary_domain", None) or chunk.metadata.domain or "general"
                chunks_by_domain[domain].append(chunk)
            collections_to_use = [(self._get_collection(domain), domain_chunks) for domain, domain_chunks in chunks_by_domain.items()]
        else:
            # New: Single collection for all chunks
            collections_to_use = [(self._default_collection, chunks_to_add)]
        
        # Add chunks to collection(s)
        for collection, domain_chunks in collections_to_use:
            
            # Prepare data for ChromaDB
            ids = []
            embeddings = []
            metadatas = []
            documents = []
            
            for chunk in domain_chunks:
                chunk_id = chunk.metadata.chunk_id
                ids.append(chunk_id)
                embeddings.append(chunk.embedding)
                
                # Get domain from chunk metadata (for both single and multi-collection modes)
                chunk_domain = getattr(chunk.metadata, "primary_domain", None) or chunk.metadata.domain or "general"
                
                # Store chunk metadata
                # ChromaDB metadata must be strings, numbers, or booleans
                chunk_index = getattr(chunk.metadata, "chunk_index", None)
                metadata = {
                    "source_path": str(chunk.metadata.source_path),
                    "title": chunk.metadata.title or "",
                    "doc_id": chunk.metadata.doc_id,
                    "page": chunk.metadata.page or "",
                    "chunk_index": chunk_index if chunk_index is not None else -1,  # REFACTOR: Store chunk_index for sequential retrieval
                    "domain": chunk.metadata.domain or "",  # Legacy field
                    "primary_domain": getattr(chunk.metadata, "primary_domain", chunk_domain) or chunk_domain,
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
                # Get collection name for logging
                collection_name = getattr(collection, "name", "unknown")
                logger.debug(f"Added {len(domain_chunks)} chunks to collection: {collection_name}")
            except Exception as e:
                collection_name = getattr(collection, "name", "unknown")
                logger.error(f"Failed to add chunks to ChromaDB collection '{collection_name}': {e}")
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
        # REFACTOR: Use ChromaDB where clause for pre-filtering when source_filter is provided
        # This ensures 100% accuracy - only chunks from requested files are retrieved
        where_clause = None
        if source_filter:
            # REFACTOR: Build where clause to filter by source_path at database level
            # ChromaDB supports $in for multiple values, but we'll try each path variation
            # For simplicity, use the first source_filter filename and try common variations
            # If multiple files, we'll query separately or use post-filtering
            primary_source = source_filter[0]
            source_paths = [
                primary_source,
                Path(primary_source).name,
                f"data/uploads/{primary_source}",
                f"data/uploads/{Path(primary_source).name}",
            ]
            
            # Try the most likely path first (just filename)
            # ChromaDB where clause: {"source_path": {"$eq": value}}
            where_clause = {"source_path": {"$eq": Path(primary_source).name}}
            
            logger.debug(
                "[ChromaStore] Using pre-filter where clause for source_path variations: %s",
                source_paths
            )
        
        # Query ChromaDB - get more results if filtering to ensure we have enough
        query_k = top_k * 3 if source_filter else top_k
        collection_count = collection.count()
        
        if collection_count == 0:
            return []
        
        try:
            # REFACTOR: Pass where clause to ChromaDB for pre-filtering
            results = collection.query(
                query_embeddings=[embedding],
                n_results=min(query_k, collection_count),
                where=where_clause  # Pre-filter at database level
            )
        except Exception as e:
            logger.error(f"ChromaDB query failed: {e}")
            return []
        
        # CRITICAL FIX: Track if we need to use post-filtering
        # If where clause returned 0 results, fall back to post-filtering by filename
        use_post_filter = False
        if not results["ids"] or not results["ids"][0]:
            # If where clause returned 0 results, it might be because
            # the stored path is different (e.g., temp path /tmp/aitutor_ingest_*/filename.pdf)
            # Fall back to querying without where clause and post-filtering by filename
            if source_filter and where_clause:
                logger.debug(
                    "[ChromaStore] Where clause returned 0 results, falling back to post-filtering by filename"
                )
                use_post_filter = True
                try:
                    # Query without where clause to get all results, then post-filter
                    results = collection.query(
                        query_embeddings=[embedding],
                        n_results=min(query_k * 5, collection_count),  # Get more results for filtering
                        where=None  # No pre-filter
                    )
                except Exception as e:
                    logger.error(f"ChromaDB fallback query failed: {e}")
                    return []
            
            if not results["ids"] or not results["ids"][0]:
                return []
        
        # Build RetrievalHit objects
        hits: List[RetrievalHit] = []
        ids = results["ids"][0]
        distances = results["distances"][0]
        metadatas = results["metadatas"][0]
        documents = results["documents"][0]
        
        # REFACTOR: If where clause was used and returned results, all results are already filtered
        # If where clause returned 0 results, we fall back to post-filtering
        # Only do post-filtering if where clause wasn't used or returned 0 results
        if source_filter and (where_clause is None or use_post_filter):
            # Fallback: Post-filter if where clause wasn't supported or returned 0 results
            # CRITICAL: Match by filename only (handles temp paths like /tmp/aitutor_ingest_*/filename.pdf)
            normalized_filter_names = set()
            normalized_filter_keys = set()
            for name in source_filter:
                filename = Path(name).name.lower()
                normalized_filter_names.add(filename)
                normalized_filter_keys.add(_normalize_filename(filename))
                normalized_filter_names.add(name.lower())
                normalized_filter_keys.add(_normalize_filename(name.lower()))
                # Also try base name without extension for partial matching
                base_name = Path(filename).stem.lower()
                normalized_filter_names.add(base_name)
            
            logger.debug(
                "[ChromaStore] Using post-filter (where clause failed or not supported): names=%s",
                normalized_filter_names
            )

        for idx, chunk_id in enumerate(ids):
            # Convert distance to similarity score
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            # Similarity: 1 - (distance / 2)
            distance = distances[idx]
            similarity = max(0.0, min(1.0, 1.0 - (distance / 2.0)))
            
            # REFACTOR: Post-filter if where clause wasn't used or returned 0 results
            # CRITICAL: Match by filename only (handles temp paths)
            if source_filter and (where_clause is None or use_post_filter):
                # Fallback post-filtering - match by filename only (works for temp paths)
                source_path = metadatas[idx].get("source_path", "")
                source_name = Path(source_path).name.lower()
                source_key = _normalize_filename(source_name)
                source_base = Path(source_name).stem.lower()
                source_path_lower = source_path.lower()
                
                # Match if filename matches (handles temp paths like /tmp/aitutor_ingest_*/filename.pdf)
                matches = (
                    source_name in normalized_filter_names
                    or source_key in normalized_filter_keys
                    or source_base in normalized_filter_names
                    or source_path_lower in normalized_filter_names
                    or any(Path(filter_name).name.lower() == source_name for filter_name in source_filter)
                )
                
                if not matches:
                    logger.debug("[ChromaStore] Chunk filtered out (post-filter): source_path=%s", source_path)
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
            
            chunk_index = metadata_dict.get("chunk_index")
            chunk_metadata = ChunkMetadata(
                chunk_id=chunk_id,
                source_path=Path(metadata_dict.get("source_path", "")),
                title=metadata_dict.get("title") or "",
                doc_id=metadata_dict.get("doc_id", ""),
                page=metadata_dict.get("page") or None,
                chunk_index=int(chunk_index) if chunk_index is not None and chunk_index != -1 else None,  # REFACTOR: Restore chunk_index
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

    def fetch_full_document(
        self,
        source_filter: List[str],
    ) -> List[RetrievalHit]:
        """
        REFACTOR: Get ALL chunks from specified documents in sequential order.
        
        This is for summarization where you need complete document content,
        not just semantically similar chunks. Returns chunks sorted by chunk_index.
        
        Parameters
        ----------
        source_filter : List[str]
            List of filenames or source paths to retrieve chunks from.
            
        Returns
        -------
        List[RetrievalHit]
            All chunks from the specified documents, sorted by chunk_index.
            Score is set to 1.0 (all chunks equally relevant for summaries).
        """
        all_hits: List[RetrievalHit] = []
        
        # REFACTOR: Get the collection (single collection in refactored design)
        if self.use_domain_collections:
            # Legacy: search all domain collections
            domains = ["math", "physics", "cs", "chemistry", "biology", "general"]
            collections_to_search = [(self._get_collection(domain), domain) for domain in domains]
        else:
            # New: single collection
            collections_to_search = [(self._default_collection, "master")]
        
        for collection, domain_name in collections_to_search:
            try:
                
                # Build where clause for source_path filtering
                # Try multiple path variations to match stored paths
                source_paths = []
                for name in source_filter:
                    # Add original
                    source_paths.append(name)
                    # Add filename only (most important - matches temp paths)
                    filename_only = Path(name).name
                    source_paths.append(filename_only)
                    # Add with data/uploads prefix (common for uploaded files)
                    source_paths.append(f"data/uploads/{name}")
                    source_paths.append(f"data/uploads/{filename_only}")
                    # REFACTOR: Add variations for ingestion paths (data/raw/...)
                    # Documents ingested from data/raw/ will have full paths stored
                    source_paths.append(f"data/raw/{name}")
                    source_paths.append(f"data/raw/{filename_only}")
                    # CRITICAL: Add temp path variations (UI uploads use /tmp/aitutor_ingest_*/)
                    # The filename_only should match the temp path's filename
                    source_paths.append(f"/tmp/aitutor_ingest_*/{filename_only}")
                    # Also try matching just the filename in any temp directory
                    # (fuzzy matching will handle this, but try exact match first)
                
                # Use ChromaDB get() with where clause to get ALL chunks
                # Try each source path variation
                found_chunks = False
                for source_path in source_paths:
                    try:
                        # ChromaDB get() with where clause
                        results = collection.get(
                            where={"source_path": {"$eq": source_path}},
                            include=["documents", "metadatas"]
                        )
                        
                        if results["ids"]:
                            logger.info(
                                "[ChromaStore] fetch_full_document: Found %d chunks for source_path=%s",
                                len(results["ids"]),
                                source_path
                            )
                            
                            # Build RetrievalHit objects
                            for idx, chunk_id in enumerate(results["ids"]):
                                metadata_dict = results["metadatas"][idx]
                                chunk_text = results["documents"][idx]
                                
                                # Extract metadata
                                primary_domain = metadata_dict.get("primary_domain") or metadata_dict.get("domain", "general")
                                secondary_domains_str = metadata_dict.get("secondary_domains", "")
                                secondary_domains = [s.strip() for s in secondary_domains_str.split(",") if s.strip()] if secondary_domains_str else []
                                domain_tags_str = metadata_dict.get("domain_tags", "")
                                domain_tags = [t.strip() for t in domain_tags_str.split(",") if t.strip()] if domain_tags_str else []
                                domain_confidence = float(metadata_dict.get("domain_confidence", 0.5))
                                chunk_index = metadata_dict.get("chunk_index")
                                
                                chunk_metadata = ChunkMetadata(
                                    chunk_id=chunk_id,
                                    source_path=Path(metadata_dict.get("source_path", "")),
                                    title=metadata_dict.get("title") or "",
                                    doc_id=metadata_dict.get("doc_id", ""),
                                    page=metadata_dict.get("page") or None,
                                    chunk_index=int(chunk_index) if chunk_index is not None and chunk_index != -1 else None,
                                    domain=metadata_dict.get("domain", primary_domain),
                                    primary_domain=primary_domain,
                                    secondary_domains=secondary_domains,
                                    domain_tags=domain_tags,
                                    domain_confidence=domain_confidence,
                                    section=metadata_dict.get("section") or None,
                                )
                                
                                chunk = Chunk(
                                    text=chunk_text,
                                    embedding=None,
                                    metadata=chunk_metadata
                                )
                                
                                # Score = 1.0 (all chunks equally relevant for summaries)
                                all_hits.append(RetrievalHit(chunk=chunk, score=1.0))
                            
                            # Found chunks, break from source_path loop
                            found_chunks = True
                            break
                    except Exception as e:
                        logger.debug(
                            "[ChromaStore] Error fetching chunks for source_path=%s: %s",
                            source_path,
                            e
                        )
                        continue
                
                # REFACTOR: If exact matches failed, try fuzzy matching by getting all chunks and filtering
                if not found_chunks and source_filter:
                    logger.info(
                        "[ChromaStore] Exact path matching failed, trying fuzzy filename matching for: %s",
                        source_filter
                    )
                    try:
                        # Get chunks with reasonable limit for fuzzy matching (performance optimization)
                        # Use 2000 limit instead of 10000 to avoid memory issues with large collections
                        # If document not found in first 2000 chunks, it's likely not in the collection
                        FUZZY_MATCH_LIMIT = 2000
                        all_data = collection.get(include=["documents", "metadatas"], limit=FUZZY_MATCH_LIMIT)
                        
                        # Normalize filter names for matching
                        filter_names = set()
                        for name in source_filter:
                            filename_only = Path(name).name
                            filter_names.add(filename_only.lower())
                            filter_names.add(name.lower())
                            # CRITICAL: Also match just the filename part (handles temp paths like /tmp/aitutor_ingest_*/filename.pdf)
                            # Extract base filename without extension for broader matching
                            base_name = Path(filename_only).stem.lower()
                            filter_names.add(base_name)
                            # Also try partial matches (e.g., "Lecture7" should match "CMPE249 Lecture7 final0911.pdf")
                            if "lecture" in name.lower():
                                import re
                                lecture_match = re.search(r'lecture\s*(\d+)', name, re.IGNORECASE)
                                if lecture_match:
                                    filter_names.add(f"lecture{lecture_match.group(1)}")
                                    filter_names.add(f"lecture {lecture_match.group(1)}")
                        
                        # Filter chunks by filename
                        for idx, chunk_id in enumerate(all_data["ids"]):
                            metadata_dict = all_data["metadatas"][idx]
                            stored_path = metadata_dict.get("source_path", "").lower()
                            stored_filename = Path(stored_path).name.lower()
                            stored_base = Path(stored_filename).stem.lower()
                            
                            # Check if any filter name matches
                            # CRITICAL: Match against filename, base name, or full path
                            matches = False
                            for filter_name in filter_names:
                                # Match against full filename
                                if filter_name in stored_filename or stored_filename in filter_name:
                                    matches = True
                                    break
                                # Match against base name (without extension)
                                if filter_name in stored_base or stored_base in filter_name:
                                    matches = True
                                    break
                                # Match against full path (handles temp directories)
                                if filter_name in stored_path:
                                    matches = True
                                    break
                            
                            if matches:
                                chunk_text = all_data["documents"][idx]
                                
                                # Extract metadata (same as above)
                                primary_domain = metadata_dict.get("primary_domain") or metadata_dict.get("domain", "general")
                                secondary_domains_str = metadata_dict.get("secondary_domains", "")
                                secondary_domains = [s.strip() for s in secondary_domains_str.split(",") if s.strip()] if secondary_domains_str else []
                                domain_tags_str = metadata_dict.get("domain_tags", "")
                                domain_tags = [t.strip() for t in domain_tags_str.split(",") if t.strip()] if domain_tags_str else []
                                domain_confidence = float(metadata_dict.get("domain_confidence", 0.5))
                                chunk_index = metadata_dict.get("chunk_index")
                                
                                chunk_metadata = ChunkMetadata(
                                    chunk_id=chunk_id,
                                    source_path=Path(metadata_dict.get("source_path", "")),
                                    title=metadata_dict.get("title") or "",
                                    doc_id=metadata_dict.get("doc_id", ""),
                                    page=metadata_dict.get("page") or None,
                                    chunk_index=int(chunk_index) if chunk_index is not None and chunk_index != -1 else None,
                                    domain=metadata_dict.get("domain", primary_domain),
                                    primary_domain=primary_domain,
                                    secondary_domains=secondary_domains,
                                    domain_tags=domain_tags,
                                    domain_confidence=domain_confidence,
                                    section=metadata_dict.get("section") or None,
                                )
                                
                                chunk = Chunk(
                                    text=chunk_text,
                                    embedding=None,
                                    metadata=chunk_metadata
                                )
                                
                                all_hits.append(RetrievalHit(chunk=chunk, score=1.0))
                        
                        if all_hits:
                            logger.info(
                                "[ChromaStore] fetch_full_document: Found %d chunks using fuzzy matching",
                                len(all_hits)
                            )
                    except Exception as e:
                        logger.debug(
                            "[ChromaStore] Fuzzy matching failed: %s",
                            e
                        )
                
            except Exception as e:
                logger.debug(f"[ChromaStore] Error in fetch_full_document for domain {domain_name}: {e}")
                continue
        
        # Sort by chunk_index to maintain document order
        all_hits.sort(
            key=lambda hit: (
                hit.chunk.metadata.chunk_index if hit.chunk.metadata.chunk_index is not None else 999999,
                hit.chunk.metadata.doc_id,
            )
        )
        
        logger.info(
            "[ChromaStore] fetch_full_document: Returning %d chunks (sorted by chunk_index)",
            len(all_hits)
        )
        
        return all_hits

    def persist(self) -> None:
        """ChromaDB persists automatically, but we can ensure flush."""
        # ChromaDB persistent client auto-saves, no explicit persist needed
        # The PersistentClient handles all persistence automatically
        pass

    @classmethod
    def from_path(
        cls,
        path: Path,
        use_domain_collections: bool = False,
        collection_name: str = "ai_tutor_master",
    ) -> "ChromaVectorStore":
        """
        Load or create ChromaDB store at the given path.
        
        REFACTORED: Defaults to single collection (ai_tutor_master) for simplicity.
        
        Parameters
        ----------
        path : Path
            Directory path for ChromaDB storage
        use_domain_collections : bool
            If True, uses domain-based collections. Default False (single collection).
        collection_name : str
            Name of the collection. Default "ai_tutor_master".
        
        Returns
        -------
        ChromaVectorStore
            Initialized vector store instance
        """
        return cls(path, use_domain_collections=use_domain_collections, collection_name=collection_name)


def _normalize_filename(value: str) -> str:
    """Normalize filenames by removing punctuation, spaces, and extensions."""
    if not value:
        return ""
    stem = Path(value).stem.lower()
    return re.sub(r"[^a-z0-9]", "", stem)

