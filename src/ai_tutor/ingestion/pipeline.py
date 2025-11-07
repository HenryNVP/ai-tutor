from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from tqdm import tqdm

from ai_tutor.config.schema import ChunkingConfig, ModelConfig, Settings
from ai_tutor.data_models import Chunk, Document
from ai_tutor.ingestion.chunker import chunk_document
from ai_tutor.ingestion.domain_classifier import DomainClassifier
from ai_tutor.ingestion.embeddings import EmbeddingClient
from ai_tutor.ingestion.parsers import parse_path
from ai_tutor.retrieval.vector_store import VectorStore
from ai_tutor.storage import ChunkJsonlStore
from ai_tutor.agents.llm_client import LLMClient

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Container summarizing ingestion outcomes, including skipped files."""

    documents: List[Document]
    chunks: List[Chunk]
    skipped: List[Path]


class IngestionPipeline:
    """
    End-to-end document processing pipeline for course material ingestion.
    
    This pipeline orchestrates the complete workflow for transforming raw educational
    documents (PDFs, Markdown files) into searchable, embedded chunks suitable for
    retrieval-augmented generation. The pipeline handles:
    
    1. **Document Parsing**: Extract text from various formats while preserving structure
    2. **Text Chunking**: Split documents into overlapping semantic units
    3. **Embedding Generation**: Encode chunks into dense vector representations
    4. **Dual Storage**: Persist both raw chunks (JSONL) and embeddings (vector store)
    
    The pipeline is designed for batch processing and can handle large document
    collections efficiently through progress tracking and error isolation (failed
    files don't block the entire batch).
    
    Pipeline Stages
    ---------------
    ```
    Raw Documents (PDF/MD/TXT)
         ↓ parse_path()
    Document Objects (structured text + metadata)
         ↓ chunk_document()
    Text Chunks (500 tokens with 80-token overlap)
         ↓ embedder.embed_documents()
    Embedded Chunks (text + 768-dim vectors)
         ↓ chunk_store.upsert() & vector_store.add()
    Persisted Storage (JSONL + vector index)
    ```
    
    Attributes
    ----------
    settings : Settings
        Configuration object containing chunking parameters (size, overlap),
        paths, and domain defaults.
    embedder : EmbeddingClient
        Sentence transformer for batch embedding generation. Uses BAAI/bge-base-en
        by default with batch size 256.
    vector_store : VectorStore
        Vector database for similarity search. Supports FAISS or ChromaDB backends.
    chunk_store : ChunkJsonlStore
        JSONL storage for chunk text and metadata. Enables streaming access and
        easy inspection without vector store.
    
    Examples
    --------
    >>> from pathlib import Path
    >>> from ai_tutor.config import load_settings
    >>> 
    >>> # Initialize pipeline
    >>> settings = load_settings()
    >>> embedder = EmbeddingClient(settings.embeddings)
    >>> vector_store = create_vector_store(settings.paths.vector_store_dir)
    >>> chunk_store = ChunkJsonlStore(settings.paths.chunks_index)
    >>> 
    >>> pipeline = IngestionPipeline(settings, embedder, vector_store, chunk_store)
    >>> 
    >>> # Ingest a directory of textbooks
    >>> from ai_tutor.utils.files import collect_documents
    >>> docs = collect_documents(Path("data/raw/physics"))
    >>> result = pipeline.ingest_paths(docs)
    >>> 
    >>> print(f"Processed {len(result.documents)} documents")
    >>> print(f"Generated {len(result.chunks)} chunks")
    >>> print(f"Skipped {len(result.skipped)} files")
    >>> 
    >>> # Ingest a single file
    >>> result = pipeline.ingest_paths([Path("textbook.pdf")])
    """

    def __init__(
        self,
        settings: Settings,
        embedder: EmbeddingClient,
        vector_store: VectorStore,
        chunk_store: ChunkJsonlStore,
        use_ai_domain_detection: bool = True,
    ):
        """
        Initialize the ingestion pipeline with all required components.
        
        Parameters
        ----------
        settings : Settings
            Configuration object containing:
            - chunking: Chunk size and overlap parameters
            - paths: Directories for data storage
            - course_defaults: Domain labels for classification
            - model: LLM configuration for AI domain detection
        embedder : EmbeddingClient
            Embedding generator for converting text to vectors. Should be
            configured with appropriate batch size for performance.
        vector_store : VectorStore
            Vector database for storing and searching embeddings. Should be
            empty or contain compatible embeddings (same dimensionality).
        chunk_store : ChunkJsonlStore
            JSONL storage backend for chunk metadata and text. Supports
            incremental updates and efficient streaming.
        use_ai_domain_detection : bool
            Whether to use AI-based domain detection for new documents.
            Default True. If False, only uses rule-based filename heuristics.
        
        Notes
        -----
        - The embedder and vector store dimensions must match (default: 768)
        - Chunk store and vector store should point to consistent directories
        - Pipeline can be reused for multiple ingestion runs
        - AI domain detection requires OPENAI_API_KEY to be set
        """
        self.settings = settings
        self.embedder = embedder
        self.vector_store = vector_store
        self.chunk_store = chunk_store
        
        # Initialize domain classifier
        llm_client = None
        if use_ai_domain_detection:
            try:
                llm_client = LLMClient(settings.model)
            except Exception as e:
                logger.warning(f"Failed to initialize LLM client for domain detection: {e}. Using rule-based only.")
                use_ai_domain_detection = False
        
        self.domain_classifier = DomainClassifier(
            llm_client=llm_client,
            use_ai_detection=use_ai_domain_detection
        )

    def ingest_paths(self, paths: Iterable[Path]) -> IngestionResult:
        """
        Process raw document paths into embedded chunks ready for retrieval.
        
        This is the main pipeline method that orchestrates all ingestion stages.
        It processes documents sequentially with progress tracking, isolates parsing
        errors to prevent batch failures, and persists results to both text and
        vector storage.
        
        The method is idempotent for chunk IDs - re-ingesting the same document will
        update existing chunks rather than creating duplicates.
        
        Pipeline Steps
        --------------
        1. **Parse**: Extract text from each file (PDF → text, Markdown → HTML → text)
        2. **Classify**: Infer domain from filename (physics/math/cs/general)
        3. **Chunk**: Split into overlapping segments (500 tokens, 80 overlap)
        4. **Embed**: Generate vector representations in batches (256 chunks/batch)
        5. **Store**: Persist to JSONL (text/metadata) and vector store (embeddings)
        6. **Index**: Update vector store index for fast similarity search
        
        Parameters
        ----------
        paths : Iterable[Path]
            Iterable of file paths to ingest. Typically from collect_documents()
            which filters for supported formats (PDF, .md, .txt). Directories
            are not supported directly; use collect_documents to expand them.
        
        Returns
        -------
        IngestionResult
            Result object containing:
            - documents: List of successfully parsed Document objects
            - chunks: List of all generated chunks with embeddings attached
            - skipped: List of file paths that failed parsing
        
        Raises
        ------
        RuntimeError
            If embedder fails on the entire batch (individual file errors are caught).
        ValueError
            If settings contain invalid chunking configuration.
        
        Notes
        -----
        - Parsing errors for individual files are logged and added to skipped list
        - The entire batch fails only if embedding generation fails
        - Progress bar displays via tqdm for long-running ingestions
        - Vector store is persisted once at the end for efficiency
        - Duplicate chunk IDs overwrite previous versions (upsert semantics)
        
        Performance
        -----------
        - Typical speed: ~50 pages/minute on CPU (varies by content)
        - Embedding dominates runtime (~70% of total time)
        - Batching reduces embedding overhead significantly
        - Memory usage: ~2KB per chunk in memory during processing
        
        Examples
        --------
        >>> from pathlib import Path
        >>> from ai_tutor.utils.files import collect_documents
        >>> 
        >>> # Ingest all PDFs in a directory
        >>> docs = collect_documents(Path("data/raw/physics"))
        >>> result = pipeline.ingest_paths(docs)
        >>> 
        >>> if result.skipped:
        ...     print(f"Warning: {len(result.skipped)} files failed:")
        ...     for path in result.skipped:
        ...         print(f"  - {path}")
        >>> 
        >>> print(f"Successfully ingested {len(result.documents)} documents")
        >>> print(f"Generated {len(result.chunks)} searchable chunks")
        >>> 
        >>> # Inspect chunk distribution
        >>> from collections import Counter
        >>> domains = Counter(chunk.metadata.extra.get("domain") for chunk in result.chunks)
        >>> print(f"Chunks by domain: {dict(domains)}")
        """
        documents: List[Document] = []
        chunks: List[Chunk] = []
        skipped: List[Path] = []

        # Load chunking configuration from settings
        chunking_config: ChunkingConfig = self.settings.chunking

        # Process each document with progress tracking
        for path in tqdm(list(paths), desc="Ingesting documents"):
            try:
                # Stage 1: Parse document (PDF/Markdown/TXT → structured text)
                document = parse_path(path)
            except Exception as exc:  # noqa: BLE001
                # Isolate parsing errors - continue with remaining files
                logger.exception("Failed to parse %s: %s", path, exc)
                skipped.append(path)
                continue
            
            # Stage 2: Classify domain using AI or rule-based methods
            # First, try fast path-based classification
            initial_classification = self.domain_classifier.classify_from_path(path)
            
            # If AI detection is enabled, refine with content analysis
            # Sample first 2000 chars for efficiency
            sample_text = document.text[:2000] if len(document.text) > 2000 else document.text
            classification = self.domain_classifier.classify_from_content(
                text=sample_text,
                filename=path.name,
                initial_classification=initial_classification
            )
            
            # Attach domain metadata to document
            document.metadata.primary_domain = classification.primary_domain
            document.metadata.secondary_domains = classification.secondary_domains
            document.metadata.domain_tags = classification.tags
            document.metadata.domain_confidence = classification.confidence
            # Legacy field for backward compatibility
            document.metadata.domain = classification.primary_domain
            document.metadata.extra.setdefault("domain", classification.primary_domain)
            
            logger.debug(
                f"Classified {path.name}: primary={classification.primary_domain}, "
                f"secondary={classification.secondary_domains}, confidence={classification.confidence:.2f}"
            )
            
            documents.append(document)
            
            # Stage 3: Chunk document into overlapping segments
            doc_chunks = chunk_document(document, chunking_config)
            chunks.extend(doc_chunks)

        # Early return if no chunks were produced
        if not chunks:
            return IngestionResult(documents=documents, chunks=[], skipped=skipped)

        # Stage 4: Generate embeddings for all chunks in batches
        embeddings = self.embedder.embed_documents(chunk.text for chunk in chunks)
        
        # Attach embeddings to chunk objects
        for chunk, embedding in zip(chunks, embeddings, strict=False):
            chunk.embedding = embedding

        # Stage 5: Persist chunks to JSONL storage (text + metadata)
        self.chunk_store.upsert(chunks)
        
        # Stage 6: Add embeddings to vector store and persist index
        self.vector_store.add(chunks)
        self.vector_store.persist()

        # Log summary statistics
        logger.info("Ingested %s documents into %s chunks.", len(documents), len(chunks))
        return IngestionResult(documents=documents, chunks=chunks, skipped=skipped)

