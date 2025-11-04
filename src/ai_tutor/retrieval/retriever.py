from __future__ import annotations

import logging
from typing import List

from ai_tutor.config.schema import RetrievalConfig
from ai_tutor.data_models import Query, RetrievalHit
from ai_tutor.ingestion.embeddings import EmbeddingClient
from ai_tutor.retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)


class Retriever:
    """
    Coordinate query embedding and vector similarity search.
    
    This class provides a simple interface for retrieval-augmented generation (RAG)
    by handling the two-stage process of:
    1. Encoding the query text into a dense vector embedding
    2. Searching the vector store for the most similar document chunks
    
    The retriever uses the same embedding model for both indexing and querying,
    ensuring semantic consistency. All configuration (top_k, similarity thresholds)
    is centralized in the RetrievalConfig object.
    
    Workflow
    --------
    1. User submits natural language query
    2. Retriever embeds query using sentence transformer
    3. Vector store performs cosine similarity search
    4. Top-k most similar chunks are returned with scores
    5. Chunks are used as context for LLM answer generation
    
    Attributes
    ----------
    config : RetrievalConfig
        Configuration object specifying top_k (number of results to return) and
        any other retrieval parameters.
    embedder : EmbeddingClient
        Sentence transformer client for encoding queries into dense vectors.
        Must use the same model as was used for document indexing.
    vector_store : VectorStore
        Indexed vector database (FAISS, ChromaDB, or other) containing document
        chunk embeddings and metadata.
    
    Examples
    --------
    >>> from ai_tutor.config.schema import RetrievalConfig
    >>> from ai_tutor.ingestion.embeddings import EmbeddingClient
    >>> from ai_tutor.retrieval.chroma_store import ChromaVectorStore
    >>> from ai_tutor.data_models import Query
    >>> from pathlib import Path
    >>> 
    >>> # Initialize components
    >>> config = RetrievalConfig(top_k=5)
    >>> embedder = EmbeddingClient(embedding_config)
    >>> vector_store = ChromaVectorStore(Path("data/vector_store"))
    >>> 
    >>> # Create retriever
    >>> retriever = Retriever(config, embedder, vector_store)
    >>> 
    >>> # Retrieve relevant chunks
    >>> query = Query(text="What is Newton's second law?")
    >>> hits = retriever.retrieve(query)
    >>> 
    >>> # Inspect results
    >>> for hit in hits:
    ...     print(f"Score: {hit.score:.3f}")
    ...     print(f"Text: {hit.chunk.text[:100]}...")
    ...     print(f"Source: {hit.chunk.metadata.title}, Page {hit.chunk.metadata.page}")
    ...     print()
    """

    def __init__(
        self,
        config: RetrievalConfig,
        embedder: EmbeddingClient,
        vector_store: VectorStore,
    ):
        """
        Initialize the retriever with configuration and dependencies.
        
        Parameters
        ----------
        config : RetrievalConfig
            Retrieval configuration specifying top_k and other search parameters.
        embedder : EmbeddingClient
            Embedding client for encoding queries. Must use the same model that
            was used to index documents (typically BAAI/bge-base-en).
        vector_store : VectorStore
            Vector database containing indexed document chunks. Must be pre-loaded
            with embeddings before retrieval can succeed.
        
        Notes
        -----
        - The embedder and vector store must use compatible embedding dimensions
        - Vector store should be loaded/persisted before retrieval attempts
        - Configuration changes (e.g., top_k) take effect immediately
        """
        self.config = config
        self.embedder = embedder
        self.vector_store = vector_store

    def retrieve(self, query: Query) -> List[RetrievalHit]:
        """
        Embed a query and retrieve the most similar document chunks.
        
        This is the primary retrieval method used throughout the system. It
        encodes the query text into a dense vector using the sentence transformer,
        then performs cosine similarity search against all indexed chunks to find
        the top-k most relevant passages.
        
        The returned hits include both the chunk content/metadata and the similarity
        score, enabling downstream components to filter by confidence and cite sources.
        
        Parameters
        ----------
        query : Query
            Query object containing the text to search for. The text field is
            embedded and used for similarity matching.
        
        Returns
        -------
        List[RetrievalHit]
            List of retrieval results, each containing:
            - chunk: Document chunk with text and metadata (title, page, domain)
            - score: Cosine similarity score in range [0, 1], where 1 is perfect match
            
            Results are sorted by descending score (most relevant first).
            Length is min(top_k, total_chunks_in_store).
        
        Raises
        ------
        ValueError
            If query.text is empty or None.
        RuntimeError
            If vector store is not loaded or contains no embeddings.
        
        Notes
        -----
        - Embedding computation is cached by the EmbeddingClient for identical queries
        - Similarity scores are cosine similarity (normalized dot product)
        - No post-filtering is applied; callers should check scores against thresholds
        - Logs the number of hits retrieved for monitoring/debugging
        
        Examples
        --------
        >>> retriever = Retriever(config, embedder, vector_store)
        >>> query = Query(text="Explain the Bernoulli equation")
        >>> hits = retriever.retrieve(query)
        >>> 
        >>> # Filter by minimum confidence score
        >>> MIN_SCORE = 0.2
        >>> relevant_hits = [hit for hit in hits if hit.score >= MIN_SCORE]
        >>> 
        >>> # Extract text for LLM context
        >>> context_chunks = [hit.chunk.text for hit in relevant_hits]
        >>> 
        >>> # Format citations
        >>> citations = [
        ...     f"[{i+1}] {hit.chunk.metadata.title} (Page {hit.chunk.metadata.page})"
        ...     for i, hit in enumerate(relevant_hits)
        ... ]
        """
        # Encode query text into dense vector using sentence transformer
        embedding = self.embedder.embed_query(query.text)
        
        # Perform similarity search in vector store
        # Pass source_filter if provided to restrict search to specific files
        hits = self.vector_store.search(
            embedding, 
            self.config.top_k,
            source_filter=query.source_filter
        )
        
        # Log retrieval statistics for monitoring
        if query.source_filter:
            logger.info(
                "Retrieved %s hits (filtered to sources: %s).", 
                len(hits), 
                query.source_filter
            )
        else:
            logger.info("Retrieved %s hits.", len(hits))
        
        return hits
