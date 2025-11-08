"""Example demonstrating how to connect to a local Chroma MCP server and explore domain-based collections.

This example shows how to:
- List and analyze domain-based collections
- Explore metadata (primary_domain, secondary_domains, tags)
- Query collections by domain
- Get statistics and insights about the database

Environment Variables:
    MCP_PORT: Port number for the MCP server (default: 8000)
    MCP_SERVER_TOKEN: Optional Bearer token for authentication
    MCP_TIMEOUT: HTTP request timeout in seconds (default: 10)
    MCP_AUTO_START: Set to "true", "1", or "yes" to auto-start the server

Usage:
    # Basic usage (server must be running)
    python main.py

    # Auto-start server
    MCP_AUTO_START=true python main.py

    # With authentication
    MCP_SERVER_TOKEN=your_token python main.py

    # Direct database exploration (no MCP server needed)
    python main.py --direct
"""

import asyncio
import os
import shutil
import subprocess
import time
from typing import Any

from agents import Agent, Runner, gen_trace_id, trace
from agents.mcp import MCPServer, MCPServerSse, MCPServerStreamableHttp
from agents.model_settings import ModelSettings

# Direct ChromaDB exploration (without MCP agent)
try:
    import chromadb
    from pathlib import Path
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


def explore_database_direct():
    """Directly explore the ChromaDB database without using MCP agent."""
    if not CHROMADB_AVAILABLE:
        print("chromadb not available for direct exploration")
        return
    
    # Connect to the database
    this_dir = Path(__file__).parent
    chroma_data_dir = this_dir.parent
    client = chromadb.PersistentClient(path=str(chroma_data_dir))
    
    print("=" * 80)
    print("DIRECT CHROMA DATABASE EXPLORATION")
    print("=" * 80)
    
    # List all collections
    collections = client.list_collections()
    print(f"\n[1] Found {len(collections)} collection(s):\n")
    
    domain_collections = {}
    other_collections = []
    total_docs = 0
    
    for collection_obj in collections:
        collection = client.get_collection(name=collection_obj.name)
        count = collection.count()
        total_docs += count
        
        if collection_obj.name.startswith("ai_tutor_"):
            domain = collection_obj.name.replace("ai_tutor_", "")
            domain_collections[domain] = {
                "name": collection_obj.name,
                "count": count,
                "metadata": collection_obj.metadata or {},
            }
        else:
            other_collections.append({
                "name": collection_obj.name,
                "count": count,
                "metadata": collection_obj.metadata or {},
            })
    
    # Display domain collections
    if domain_collections:
        print("Domain-based Collections:")
        print("-" * 80)
        for domain in sorted(domain_collections.keys()):
            info = domain_collections[domain]
            print(f"  {domain:12s} ({info['name']:25s}): {info['count']:5d} documents")
            if info['metadata']:
                print(f"    Metadata: {info['metadata']}")
        print()
    
    # Display other collections
    if other_collections:
        print("Other Collections:")
        print("-" * 80)
        for info in other_collections:
            print(f"  {info['name']:25s}: {info['count']:5d} documents")
            if info['metadata']:
                print(f"    Metadata: {info['metadata']}")
        print()
    
    # Domain distribution
    if domain_collections:
        print("\n[2] Domain Distribution:")
        print("-" * 80)
        print(f"Total documents across all domain collections: {total_docs}")
        print()
        
        for domain in sorted(domain_collections.keys()):
            info = domain_collections[domain]
            percentage = (info['count'] / total_docs * 100) if total_docs > 0 else 0
            bar = "█" * int(percentage / 2)  # Visual bar
            print(f"  {domain:12s}: {info['count']:5d} ({percentage:5.1f}%) {bar}")
    
    # Sample metadata from domain collections
    print("\n[3] Sample Metadata Structure:")
    print("-" * 80)
    for domain in sorted(domain_collections.keys()):
        info = domain_collections[domain]
        if info['count'] > 0:
            collection = client.get_collection(name=info['name'])
            # Get a sample document using get() to avoid embedding dimension issues
            try:
                results = collection.get(limit=1)
                if results['metadatas'] and len(results['metadatas']) > 0:
                    metadata = results['metadatas'][0]
                    print(f"\n  {domain} collection sample metadata:")
                    for key, value in metadata.items():
                        if isinstance(value, str) and len(value) > 100:
                            value = value[:100] + "..."
                        print(f"    {key}: {value}")
                break  # Just show one example
            except Exception as e:
                print(f"  Error getting sample from {domain}: {e}")
                break
    
    # Query examples (note: requires embeddings for custom-embedded collections)
    print("\n[4] Sample Queries:")
    print("-" * 80)
    print("  Note: Collections with custom embeddings (768-dim) require query_embeddings.")
    print("  Skipping text-based queries to avoid dimension mismatch errors.")
    print("  Use the MCP agent with proper embedding generation for queries.")
    
    print("\n" + "=" * 80)
    print("DIRECT EXPLORATION COMPLETE")
    print("=" * 80)


async def run(mcp_server: MCPServer):
    """Run the agent with the provided MCP server to explore the database."""
    agent = Agent(
        name="Database Explorer",
        instructions=(
            "You are a database exploration assistant. Use the Chroma MCP tools to explore "
            "the vector database. Focus on domain-based collections (ai_tutor_math, ai_tutor_physics, "
            "ai_tutor_cs, etc.) and provide detailed analysis including:\n"
            "- Collection statistics\n"
            "- Domain distribution\n"
            "- Metadata analysis (primary_domain, secondary_domains, tags)\n"
            "- Sample queries across different domains\n"
            "Be thorough and provide clear, formatted output."
        ),
        mcp_servers=[mcp_server],
        model_settings=ModelSettings(tool_choice="required"),
    )

    print("=" * 80)
    print("CHROMA DATABASE EXPLORATION")
    print("=" * 80)
    
    # 1. List all collections with detailed information
    print("\n[1] Listing all collections in the database...")
    print("-" * 80)
    message = (
        "List all collections in the database. For each collection, provide:\n"
        "- Collection name\n"
        "- Document count\n"
        "- Collection metadata (especially domain information)\n"
        "- Identify which collections are domain-based (ai_tutor_* collections)"
    )
    result = await Runner.run(starting_agent=agent, input=message)
    print(result.final_output)

    # 2. Get detailed statistics for domain-based collections
    print("\n[2] Analyzing domain-based collections...")
    print("-" * 80)
    message = (
        "For each domain-based collection (ai_tutor_math, ai_tutor_physics, ai_tutor_cs, etc.), "
        "get detailed information including:\n"
        "- Total document count\n"
        "- Collection metadata\n"
        "- If possible, sample a few documents to see their metadata structure"
    )
    result = await Runner.run(starting_agent=agent, input=message)
    print(result.final_output)

    # 3. Explore metadata structure
    print("\n[3] Exploring document metadata structure...")
    print("-" * 80)
    message = (
        "Query one of the domain collections (preferably one with documents) to get sample results. "
        "Show the metadata structure of the returned documents, focusing on:\n"
        "- primary_domain\n"
        "- secondary_domains\n"
        "- domain_tags\n"
        "- domain_confidence\n"
        "- source_path\n"
        "- Any other metadata fields"
    )
    result = await Runner.run(starting_agent=agent, input=message)
    print(result.final_output)

    # 4. Domain distribution analysis
    print("\n[4] Analyzing domain distribution...")
    print("-" * 80)
    message = (
        "Analyze the distribution of documents across domains. For each domain collection:\n"
        "- Count the total documents\n"
        "- Calculate the percentage of total documents\n"
        "- Identify which domains have the most/least documents\n"
        "- Provide a summary table"
    )
    result = await Runner.run(starting_agent=agent, input=message)
    print(result.final_output)

    # 5. Sample queries across different domains
    print("\n[5] Testing queries across different domains...")
    print("-" * 80)
    
    test_queries = [
        ("ai_tutor_math", "What is calculus?"),
        ("ai_tutor_physics", "What is quantum mechanics?"),
        ("ai_tutor_cs", "What is machine learning?"),
    ]
    
    for collection_name, query_text in test_queries:
        print(f"\nQuerying '{collection_name}' with: '{query_text}'")
        message = (
            f"Use the query_with_text tool to query the collection '{collection_name}' "
            f"with the query text: '{query_text}'. "
            f"This will automatically generate the correct 768-dim embeddings. "
            f"Return the top 3 results with their metadata, especially domain information."
        )
        try:
            result = await Runner.run(starting_agent=agent, input=message)
            print(result.final_output)
        except Exception as e:
            print(f"Error querying {collection_name}: {e}")

    # 6. Find collections with specific metadata
    print("\n[6] Finding documents with specific domain characteristics...")
    print("-" * 80)
    message = (
        "Use query_with_text to search for documents with secondary_domains. "
        "Query each domain collection with a generic query like 'example' or 'introduction', "
        "then filter the results to find documents where secondary_domains metadata field is not empty. "
        "Show examples of multi-domain documents if they exist."
    )
    result = await Runner.run(starting_agent=agent, input=message)
    print(result.final_output)

    # 7. Summary and recommendations
    print("\n[7] Generating summary and insights...")
    print("-" * 80)
    message = (
        "Provide a comprehensive summary of the database including:\n"
        "- Total number of collections\n"
        "- Total documents across all collections\n"
        "- Domain distribution summary\n"
        "- Notable patterns or insights\n"
        "- Recommendations for database usage"
    )
    result = await Runner.run(starting_agent=agent, input=message)
    print(result.final_output)
    
    print("\n" + "=" * 80)
    print("EXPLORATION COMPLETE")
    print("=" * 80)


async def main():
    """Main function - connects to the server (optionally starts it if not running)."""
    port = int(os.getenv("MCP_PORT", "8000"))
    server_url = f"http://localhost:{port}/mcp"
    
    # Check if server should be started automatically
    auto_start = os.getenv("MCP_AUTO_START", "false").lower() in ("true", "1", "yes")
    
    process: subprocess.Popen[Any] | None = None
    
    if auto_start:
        # Auto-start the server as a subprocess
        print(f"Auto-starting Chroma MCP server at {server_url} ...")
        
        try:
            this_dir = os.path.dirname(os.path.abspath(__file__))
            server_file = os.path.join(this_dir, "server.py")
            
            # Determine command to use
            use_uv = shutil.which("uv") is not None
            if use_uv:
                cmd = ["uv", "run", server_file]
            else:
                cmd = ["python", server_file]
            
            # Set environment variables
            env = os.environ.copy()
            env["MCP_PORT"] = str(port)
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            # Give it 3 seconds to start
            time.sleep(3)
            
            # Check if the process is still running
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                error_msg = stderr.decode() if stderr else stdout.decode()
                raise RuntimeError(
                    f"Chroma MCP server failed to start:\n{error_msg}"
                )
            
            print("Chroma MCP server started. Running example...\n\n")
        except Exception as e:
            print(f"Error starting Chroma MCP server: {e}")
            if process:
                process.terminate()
            exit(1)
    else:
        # Assume server is already running
        print(f"Connecting to Chroma MCP server at {server_url} ...")
        print("(Make sure the server is running: python server.py)\n")

    try:
        # Try Streamable HTTP first (most common for newer MCP servers)
        # Configure connection parameters
        streamable_params = {
            "url": server_url,
            "timeout": int(os.getenv("MCP_TIMEOUT", "10")),  # HTTP request timeout
        }
        
        # Add authorization header if token is provided
        mcp_token = os.getenv("MCP_SERVER_TOKEN")
        if mcp_token:
            streamable_params["headers"] = {"Authorization": f"Bearer {mcp_token}"}
        
        # Configure Streamable HTTP server with best practices:
        # - cache_tools_list: Cache tool list to reduce API calls
        # - max_retry_attempts: Automatic retries for list_tools() and call_tool()
        # - client_session_timeout_seconds: HTTP read timeout (optional, defaults handled by library)
        # - use_structured_content: Prefer structured content over text (optional)
        # - retry_backoff_seconds_base: Base delay for retry backoff (optional)
        async with MCPServerStreamableHttp(
            name="Chroma MCP Server (Streamable HTTP)",
            params=streamable_params,
            cache_tools_list=True,  # Cache tool list to reduce API calls
            max_retry_attempts=3,  # Automatic retries for network issues
            # Optional: client_session_timeout_seconds=30,  # HTTP read timeout
            # Optional: use_structured_content=True,  # Prefer structured content
            # Optional: retry_backoff_seconds_base=1.0,  # Retry backoff delay
            # Optional: tool_filter=lambda tool: tool.name.startswith("chroma_"),  # Filter tools
        ) as server:
            trace_id = gen_trace_id()
            with trace(workflow_name="Chroma MCP Example", trace_id=trace_id):
                print(
                    f"View trace: https://platform.openai.com/traces/trace?trace_id={trace_id}\n"
                )
                await run(server)
    except Exception as e:
        print(f"Streamable HTTP failed: {e}")
        print("\nTrying SSE transport...")
        # If Streamable HTTP fails, try SSE
        try:
            async with MCPServerSse(
                name="Chroma MCP Server (SSE)",
                params={
                    "url": f"http://localhost:{port}/sse",
                    "timeout": 10,
                    "sse_read_timeout": 300,
                },
                cache_tools_list=True,
            ) as server:
                trace_id = gen_trace_id()
                with trace(workflow_name="Chroma MCP Example", trace_id=trace_id):
                    print(
                        f"View trace: https://platform.openai.com/traces/trace?trace_id={trace_id}\n"
                    )
                    await run(server)
        except Exception as e2:
            print(f"SSE also failed: {e2}")
            print("\nPlease check:")
            print("1. Is your Chroma MCP server running?")
            print("2. Is the URL correct?")
            print("3. What transport protocol does your server use? (SSE or Streamable HTTP)")
    finally:
        if process:
            process.terminate()


if __name__ == "__main__":
    import sys
    
    # Check if user wants direct exploration (faster, no agent needed)
    if len(sys.argv) > 1 and sys.argv[1] == "--direct":
        explore_database_direct()
    else:
        # Use MCP agent for interactive exploration
        asyncio.run(main())

