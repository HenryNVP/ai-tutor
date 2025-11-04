from __future__ import annotations

import logging
import os
from pathlib import Path

from ai_tutor.retrieval.simple_store import SimpleVectorStore
from ai_tutor.retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)


def create_vector_store(path: Path) -> VectorStore:
    """
    Instantiate the vector store implementation based on environment variable.
    
    Environment Variables:
    - VECTOR_STORE_TYPE: "simple", "chroma" (default), or "faiss"
    
    Parameters
    ----------
    path : Path
        Directory where the vector store will be persisted
        
    Returns
    -------
    VectorStore
        Vector store instance (SimpleVectorStore, ChromaVectorStore, or FAISSVectorStore)
    """
    store_type = os.getenv("VECTOR_STORE_TYPE", "chroma").lower()
    
    if store_type == "chroma":
        try:
            from ai_tutor.retrieval.chroma_store import ChromaVectorStore
            return ChromaVectorStore.from_path(path)
        except ImportError:
            logger.warning(
                "ChromaDB not available, falling back to SimpleVectorStore. "
                "Install with: pip install chromadb"
            )
            return SimpleVectorStore.from_path(path)
    elif store_type == "faiss":
        try:
            from ai_tutor.retrieval.faiss_store import FAISSVectorStore
            return FAISSVectorStore.from_path(path)
        except ImportError:
            logger.warning(
                "FAISS not available, falling back to SimpleVectorStore. "
                "Install with: pip install faiss-cpu"
            )
            return SimpleVectorStore.from_path(path)
    else:
        # Default to SimpleVectorStore
        return SimpleVectorStore.from_path(path)
