from __future__ import annotations

import logging
import os
from pathlib import Path

from ai_tutor.retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)


def create_vector_store(path: Path) -> VectorStore:
    """
    Instantiate the vector store implementation based on environment variable.
    
    Environment Variables:
    - VECTOR_STORE_TYPE: "chroma" (default) or "faiss"
    
    Parameters
    ----------
    path : Path
        Directory where the vector store will be persisted
        
    Returns
    -------
    VectorStore
        Vector store instance (ChromaVectorStore or FAISSVectorStore)
        
    Raises
    ------
    ImportError
        If the requested vector store backend is not installed
    RuntimeError
        If no valid vector store backend is available
    """
    store_type = os.getenv("VECTOR_STORE_TYPE", "chroma").lower()
    
    if store_type == "chroma":
        try:
            from ai_tutor.retrieval.chroma_store import ChromaVectorStore
            return ChromaVectorStore.from_path(path)
        except ImportError as e:
            logger.error(
                "ChromaDB is required but not installed. "
                "Install with: pip install chromadb"
            )
            raise RuntimeError(
                "ChromaDB vector store is required but not available. "
                "Install it with: pip install chromadb"
            ) from e
    elif store_type == "faiss":
        try:
            from ai_tutor.retrieval.faiss_store import FAISSVectorStore
            return FAISSVectorStore.from_path(path)
        except ImportError as e:
            logger.error(
                "FAISS is required but not installed. "
                "Install with: pip install faiss-cpu"
            )
            raise RuntimeError(
                "FAISS vector store is required but not available. "
                "Install it with: pip install faiss-cpu"
            ) from e
    else:
        logger.error(
            f"Unknown vector store type: {store_type}. "
            "Supported types: 'chroma', 'faiss'"
        )
        raise ValueError(
            f"Unknown vector store type: {store_type}. "
            "Supported types: 'chroma' (default), 'faiss'"
        )
