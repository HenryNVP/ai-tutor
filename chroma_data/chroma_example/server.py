"""Chroma MCP Server Example

This server demonstrates how to expose Chroma vector database operations
via the Model Context Protocol (MCP).

It provides tools for:
- Managing collections
- Adding documents with embeddings
- Querying collections
- Retrieving collection information
"""

import os
from pathlib import Path
from typing import Any

import chromadb
from mcp.server.fastmcp import FastMCP

# Try to import embedding client for query generation
try:
    import sys
    # Add parent directory to path to import ai_tutor modules
    parent_dir = Path(__file__).parent.parent.parent
    if str(parent_dir / "src") not in sys.path:
        sys.path.insert(0, str(parent_dir / "src"))
    
    from ai_tutor.ingestion.embeddings import EmbeddingClient
    from ai_tutor.config.schema import EmbeddingConfig
    from ai_tutor.config.loader import load_settings
    
    # Initialize embedding client
    try:
        settings = load_settings()
        embedding_client = EmbeddingClient(settings.embeddings)
        EMBEDDING_AVAILABLE = True
    except Exception:
        embedding_client = None
        EMBEDDING_AVAILABLE = False
except ImportError:
    embedding_client = None
    EMBEDDING_AVAILABLE = False

# Create server
mcp = FastMCP("Chroma MCP Server")

# Initialize Chroma client using the new API
# Using PersistentClient for local persistence
# Point to the chroma_data directory which contains chroma.sqlite3
this_dir = Path(__file__).parent
chroma_data_dir = this_dir.parent  # Go up one level to chroma_data directory

chroma_client = chromadb.PersistentClient(
    path=str(chroma_data_dir),  # Use chroma_data directory containing chroma.sqlite3
)


@mcp.tool()
def list_collections() -> str:
    """List all collections in the Chroma database.
    
    Returns a formatted string with all collection names, document counts, and their metadata.
    """
    print("[debug-server] list_collections()")
    
    try:
        collections = chroma_client.list_collections()
        if not collections:
            return "No collections found in the database."
        
        result = f"Found {len(collections)} collection(s):\n\n"
        for collection_obj in collections:
            collection = chroma_client.get_collection(name=collection_obj.name)
            count = collection.count()
            result += f"- {collection_obj.name}\n"
            result += f"  Document count: {count}\n"
            if collection_obj.metadata:
                result += f"  Metadata: {collection_obj.metadata}\n"
            result += "\n"
        
        return result
    except Exception as e:
        return f"Error listing collections: {str(e)}"


@mcp.tool()
def create_collection(name: str, metadata: dict[str, Any] | None = None) -> str:
    """Create a new collection in Chroma.
    
    Args:
        name: The name of the collection to create.
        metadata: Optional metadata dictionary for the collection.
    
    Returns:
        A confirmation message with the collection name.
    """
    print(f"[debug-server] create_collection(name={name}, metadata={metadata})")
    
    try:
        # Check if collection already exists
        existing = chroma_client.get_collection(name=name)
        return f"Collection '{name}' already exists. Use add_documents to add data to it."
    except Exception:
        pass  # Collection doesn't exist, we can create it
    
    try:
        chroma_client.create_collection(name=name, metadata=metadata or {})
        return f"Collection '{name}' created successfully."
    except Exception as e:
        return f"Error creating collection '{name}': {str(e)}"


@mcp.tool()
def add_documents(
    collection_name: str,
    documents: list[str],
    ids: list[str] | None = None,
    metadatas: list[dict[str, Any]] | None = None,
) -> str:
    """Add documents to a collection.
    
    Args:
        collection_name: The name of the collection to add documents to.
        documents: List of document texts to add.
        ids: Optional list of unique IDs for each document. If not provided, IDs will be auto-generated.
        metadatas: Optional list of metadata dictionaries, one per document.
    
    Returns:
        A confirmation message with the number of documents added.
    """
    print(
        f"[debug-server] add_documents(collection_name={collection_name}, "
        f"documents_count={len(documents)})"
    )
    
    try:
        # Get or create the collection
        try:
            collection = chroma_client.get_collection(name=collection_name)
        except Exception:
            # Collection doesn't exist, create it
            collection = chroma_client.create_collection(name=collection_name)
        
        # Add documents
        collection.add(
            documents=documents,
            ids=ids,
            metadatas=metadatas,
        )
        
        return f"Successfully added {len(documents)} document(s) to collection '{collection_name}'."
    except Exception as e:
        return f"Error adding documents to collection '{collection_name}': {str(e)}"


@mcp.tool()
def query_collection(
    collection_name: str,
    query_texts: list[str] | None = None,
    query_embeddings: list[list[float]] | None = None,
    n_results: int = 5,
    where: dict[str, Any] | None = None,
) -> str:
    """Query a collection for similar documents.
    
    Note: Collections created with custom embeddings (e.g., 768-dim from BAAI/bge-base-en)
    require query_embeddings instead of query_texts to avoid dimension mismatch errors.
    
    Args:
        collection_name: The name of the collection to query.
        query_texts: List of query text strings to search for. May fail if collection uses custom embeddings.
        query_embeddings: List of embedding vectors to search for. Use this for collections with custom embeddings.
        n_results: Number of results to return per query. Defaults to 5.
        where: Optional metadata filter dictionary.
    
    Returns:
        A formatted string with query results including documents, distances, and metadata.
    """
    print(
        f"[debug-server] query_collection(collection_name={collection_name}, "
        f"query_texts_count={len(query_texts) if query_texts else 0}, "
        f"query_embeddings_count={len(query_embeddings) if query_embeddings else 0}, "
        f"n_results={n_results})"
    )
    
    try:
        collection = chroma_client.get_collection(name=collection_name)
        
        # Use query_embeddings if provided, otherwise try query_texts
        if query_embeddings:
            results = collection.query(
                query_embeddings=query_embeddings,
                n_results=n_results,
                where=where,
            )
            query_items = query_embeddings
        elif query_texts:
            try:
                results = collection.query(
                    query_texts=query_texts,
                    n_results=n_results,
                    where=where,
                )
                query_items = query_texts
            except Exception as e:
                if "dimension" in str(e).lower() or "embedding" in str(e).lower():
                    return (
                        f"Error: Embedding dimension mismatch. This collection uses custom embeddings. "
                        f"Please use query_embeddings instead of query_texts. Error: {str(e)}"
                    )
                raise
        else:
            return "Error: Either query_texts or query_embeddings must be provided."
        
        if not results["ids"] or not results["ids"][0]:
            return f"No results found in collection '{collection_name}' for the query."
        
        result_text = f"Query results from collection '{collection_name}':\n\n"
        
        for i, query_item in enumerate(query_items):
            query_desc = f"Query {i + 1}" if query_texts else f"Embedding query {i + 1}"
            if query_texts:
                query_desc += f": {query_item}"
            result_text += f"{query_desc}\n"
            result_text += "-" * 50 + "\n"
            
            if i < len(results["ids"]):
                ids = results["ids"][i]
                documents = results["documents"][i] if results["documents"] else [None] * len(ids)
                distances = results["distances"][i] if results["distances"] else [None] * len(ids)
                metadatas = results["metadatas"][i] if results["metadatas"] else [None] * len(ids)
                
                for j, doc_id in enumerate(ids):
                    result_text += f"\nResult {j + 1} (ID: {doc_id}):\n"
                    if distances[j] is not None:
                        result_text += f"  Distance: {distances[j]:.4f}\n"
                    if documents[j]:
                        result_text += f"  Document: {documents[j][:200]}...\n" if len(documents[j]) > 200 else f"  Document: {documents[j]}\n"
                    if metadatas[j]:
                        result_text += f"  Metadata: {metadatas[j]}\n"
            
            result_text += "\n"
        
        return result_text
    except Exception as e:
        return f"Error querying collection '{collection_name}': {str(e)}"


@mcp.tool()
def get_collection_info(collection_name: str) -> str:
    """Get information about a collection including document count and sample documents.
    
    Args:
        collection_name: The name of the collection to inspect.
    
    Returns:
        A formatted string with collection information including sample documents.
    """
    print(f"[debug-server] get_collection_info(collection_name={collection_name})")
    
    try:
        collection = chroma_client.get_collection(name=collection_name)
        
        # Get collection count
        count = collection.count()
        
        result = f"Collection: {collection_name}\n"
        result += f"Document count: {count}\n"
        
        if collection.metadata:
            result += f"Metadata: {collection.metadata}\n"
        
        # Get sample documents using get() instead of query() to avoid embedding dimension issues
        if count > 0:
            result += "\nSample documents (first 3):\n"
            try:
                samples = collection.get(limit=min(3, count))
                if samples['ids']:
                    for i, doc_id in enumerate(samples['ids'][:3]):
                        result += f"\n  Document {i + 1} (ID: {doc_id}):\n"
                        if samples.get('documents') and i < len(samples['documents']):
                            doc_text = samples['documents'][i]
                            result += f"    Text: {doc_text[:200]}...\n" if len(doc_text) > 200 else f"    Text: {doc_text}\n"
                        if samples.get('metadatas') and i < len(samples['metadatas']):
                            result += f"    Metadata: {samples['metadatas'][i]}\n"
            except Exception as e:
                result += f"  (Could not retrieve samples: {str(e)})\n"
        
        return result
    except Exception as e:
        return f"Error getting info for collection '{collection_name}': {str(e)}"


@mcp.tool()
def generate_embedding(query_text: str) -> dict[str, Any]:
    """Generate a 768-dimensional embedding vector for a query text.
    
    This is useful for querying collections that use custom embeddings (BAAI/bge-base-en, 768-dim).
    
    Args:
        query_text: The text to embed.
    
    Returns:
        A dictionary with the embedding vector and metadata.
    """
    print(f"[debug-server] generate_embedding(query_text='{query_text[:50]}...')")
    
    if not EMBEDDING_AVAILABLE or embedding_client is None:
        return {
            "error": "Embedding client not available. Cannot generate embeddings.",
            "embedding": None,
            "dimension": None,
        }
    
    try:
        embedding = embedding_client.embed_query(query_text)
        return {
            "embedding": embedding,
            "dimension": len(embedding),
            "model": "BAAI/bge-base-en",
            "query_text": query_text,
        }
    except Exception as e:
        return {
            "error": str(e),
            "embedding": None,
            "dimension": None,
        }


@mcp.tool()
def query_with_text(
    collection_name: str,
    query_text: str,
    n_results: int = 5,
    where: dict[str, Any] | None = None,
) -> str:
    """Query a collection using text (automatically generates embeddings).
    
    This tool generates 768-dim embeddings for the query text and then queries the collection.
    Works with collections that use BAAI/bge-base-en embeddings.
    
    Args:
        collection_name: The name of the collection to query.
        query_text: The query text to search for.
        n_results: Number of results to return. Defaults to 5.
        where: Optional metadata filter dictionary.
    
    Returns:
        A formatted string with query results.
    """
    print(
        f"[debug-server] query_with_text(collection_name={collection_name}, "
        f"query_text='{query_text[:50]}...', n_results={n_results})"
    )
    
    if not EMBEDDING_AVAILABLE or embedding_client is None:
        return (
            f"Error: Embedding client not available. Cannot generate embeddings for query. "
            f"Please use query_collection with query_embeddings parameter instead."
        )
    
    try:
        # Generate embedding
        embedding = embedding_client.embed_query(query_text)
        
        # Query using the embedding
        collection = chroma_client.get_collection(name=collection_name)
        results = collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where,
        )
        
        if not results["ids"] or not results["ids"][0]:
            return f"No results found in collection '{collection_name}' for the query: '{query_text}'"
        
        result_text = f"Query results from collection '{collection_name}':\n"
        result_text += f"Query: '{query_text}'\n"
        result_text += "-" * 50 + "\n"
        
        ids = results["ids"][0]
        documents = results["documents"][0] if results["documents"] else [None] * len(ids)
        distances = results["distances"][0] if results["distances"] else [None] * len(ids)
        metadatas = results["metadatas"][0] if results["metadatas"] else [None] * len(ids)
        
        for j, doc_id in enumerate(ids):
            result_text += f"\nResult {j + 1} (ID: {doc_id}):\n"
            if distances[j] is not None:
                # Convert distance to similarity score
                similarity = max(0.0, min(1.0, 1.0 - (distances[j] / 2.0)))
                result_text += f"  Similarity: {similarity:.4f} (Distance: {distances[j]:.4f})\n"
            if documents[j]:
                result_text += f"  Document: {documents[j][:200]}...\n" if len(documents[j]) > 200 else f"  Document: {documents[j]}\n"
            if metadatas[j]:
                result_text += f"  Metadata: {metadatas[j]}\n"
        
        return result_text
    except Exception as e:
        return f"Error querying collection '{collection_name}': {str(e)}"


@mcp.tool()
def delete_collection(collection_name: str) -> str:
    """Delete a collection from Chroma.
    
    Args:
        collection_name: The name of the collection to delete.
    
    Returns:
        A confirmation message.
    """
    print(f"[debug-server] delete_collection(collection_name={collection_name})")
    
    try:
        chroma_client.delete_collection(name=collection_name)
        return f"Collection '{collection_name}' deleted successfully."
    except Exception as e:
        return f"Error deleting collection '{collection_name}': {str(e)}"


if __name__ == "__main__":
    # Run with Streamable HTTP transport (recommended for newer MCP servers)
    # Change to "sse" if you need Server-Sent Events transport
    transport_type = os.getenv("MCP_TRANSPORT", "streamable-http")
    port = os.getenv("MCP_PORT", os.getenv("PORT", "8000"))
    
    # Configure port if specified (for HTTP/SSE transports)
    if port != "8000":
        os.environ["PORT"] = port
    
    print(f"Starting Chroma MCP server on port {port} with {transport_type} transport...")
    print(f"Connect to: http://localhost:{port}/mcp")
    print("Press Ctrl+C to stop the server.\n")
    
    mcp.run(transport=transport_type)

