from .factory import create_vector_store
from .vector_store import VectorStore

__all__ = ["VectorStore", "create_vector_store"]

# Optional imports for ChromaDB and FAISS stores
try:
    from .chroma_store import ChromaVectorStore
    __all__.append("ChromaVectorStore")
except ImportError:
    pass

try:
    from .faiss_store import FAISSVectorStore
    __all__.append("FAISSVectorStore")
except ImportError:
    pass
