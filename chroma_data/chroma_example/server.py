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
    query_texts: list[str],
    n_results: int = 5,
    where: dict[str, Any] | None = None,
) -> str:
    """Query a collection for similar documents.
    
    Args:
        collection_name: The name of the collection to query.
        query_texts: List of query text strings to search for.
        n_results: Number of results to return per query. Defaults to 5.
        where: Optional metadata filter dictionary.
    
    Returns:
        A formatted string with query results including documents, distances, and metadata.
    """
    print(
        f"[debug-server] query_collection(collection_name={collection_name}, "
        f"query_texts_count={len(query_texts)}, n_results={n_results})"
    )
    
    try:
        collection = chroma_client.get_collection(name=collection_name)
        
        results = collection.query(
            query_texts=query_texts,
            n_results=n_results,
            where=where,
        )
        
        if not results["ids"] or not results["ids"][0]:
            return f"No results found in collection '{collection_name}' for the query."
        
        result_text = f"Query results from collection '{collection_name}':\n\n"
        
        for i, query_text in enumerate(query_texts):
            result_text += f"Query {i + 1}: {query_text}\n"
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
    """Get information about a collection including document count.
    
    Args:
        collection_name: The name of the collection to inspect.
    
    Returns:
        A formatted string with collection information.
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
        
        return result
    except Exception as e:
        return f"Error getting info for collection '{collection_name}': {str(e)}"


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

