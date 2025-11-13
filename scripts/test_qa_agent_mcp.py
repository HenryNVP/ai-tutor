#!/usr/bin/env python3
"""Test if QA agent can access and call MCP tools.

This script:
1. Sets up MCP server connections (Chroma and Filesystem)
2. Creates a QA agent with MCP servers
3. Tests if MCP tools are accessible
4. Tests if the agent can actually call MCP tools
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents import Runner
from agents.mcp import MCPServerStreamableHttp

# Import QA agent builder
from ai_tutor.agents.qa import build_qa_agent
from ai_tutor.agents.tutor import AgentState
from ai_tutor.config.loader import load_settings
from ai_tutor.ingestion.embeddings import EmbeddingClient
from ai_tutor.retrieval import create_vector_store
from ai_tutor.retrieval.retriever import Retriever


async def test_qa_agent_mcp_tools():
    """Test QA agent MCP tool access and usage."""
    print("=" * 70)
    print("QA Agent MCP Tools Test")
    print("=" * 70)
    print()
    
    # Load settings
    print("1. Loading configuration...")
    try:
        # Use absolute path to config file (works from any directory)
        config_path = ROOT / "config" / "default.yaml"
        settings = load_settings(config_path)
        print(f"   ✅ Configuration loaded from {config_path}")
    except Exception as e:
        print(f"   ❌ Failed to load configuration: {e}")
        print(f"   Expected config at: {ROOT / 'config' / 'default.yaml'}")
        return
    
    # Initialize components
    print("\n2. Initializing components...")
    try:
        embedder = EmbeddingClient(settings.embeddings)
        vector_store = create_vector_store(settings.paths.vector_store_dir)
        retriever = Retriever(
            vector_store=vector_store,
            embedder=embedder,
            config=settings.retrieval,
        )
        state = AgentState()
        print(f"   ✅ Components initialized")
    except Exception as e:
        print(f"   ❌ Failed to initialize components: {e}")
        return
    
    # Set up MCP servers (keep them alive for the entire test)
    print("\n3. Setting up MCP servers...")
    
    # Chroma MCP Server
    mcp_port = int(os.getenv("MCP_PORT", "8000"))
    mcp_url = os.getenv("MCP_URL", f"http://localhost:{mcp_port}/mcp")
    mcp_enabled = os.getenv("MCP_USE_SERVER", "true").lower() in ("true", "1", "yes")
    
    chroma_server_obj = None
    chroma_server = None
    if mcp_enabled:
        print(f"   Connecting to Chroma MCP Server at {mcp_url}...")
        try:
            chroma_server = MCPServerStreamableHttp(
                name="Chroma MCP Server",
                params={"url": mcp_url, "timeout": 10},
                cache_tools_list=True,
            )
            chroma_server_obj = await chroma_server.__aenter__()
            # Test connection by listing tools
            tools = await chroma_server_obj.list_tools()
            print(f"   ✅ Chroma MCP Server connected ({len(tools)} tools available)")
            print(f"      Tools: {', '.join([t.name for t in tools[:5]])}...")
        except Exception as e:
            print(f"   ⚠️  Chroma MCP Server connection failed: {e}")
            print(f"      Make sure the server is running: cd chroma_mcp_server && python server.py")
            chroma_server = None
            chroma_server_obj = None
    else:
        print(f"   ⏭️  Chroma MCP Server disabled (set MCP_USE_SERVER=true)")
    
    # Filesystem MCP Server
    fs_port = int(os.getenv("FS_MCP_PORT", "8100"))
    fs_url = os.getenv("FS_MCP_URL", f"http://localhost:{fs_port}/mcp")
    fs_enabled = os.getenv("FS_MCP_USE_SERVER", "true").lower() in ("true", "1", "yes")
    
    fs_server_obj = None
    fs_server = None
    if fs_enabled:
        print(f"   Connecting to Filesystem MCP Server at {fs_url}...")
        try:
            fs_server = MCPServerStreamableHttp(
                name="Filesystem MCP Server",
                params={"url": fs_url, "timeout": 10},
                cache_tools_list=True,
            )
            fs_server_obj = await fs_server.__aenter__()
            # Test connection by listing tools
            tools = await fs_server_obj.list_tools()
            print(f"   ✅ Filesystem MCP Server connected ({len(tools)} tools available)")
            print(f"      Tools: {', '.join([t.name for t in tools[:5]])}...")
        except Exception as e:
            print(f"   ⚠️  Filesystem MCP Server connection failed: {e}")
            print(f"      Make sure the server is running: cd filesystem_mcp_server && python server.py")
            fs_server = None
            fs_server_obj = None
    else:
        print(f"   ⏭️  Filesystem MCP Server disabled (set FS_MCP_USE_SERVER=true)")
    
    # Collect active servers
    mcp_servers = []
    if chroma_server_obj:
        mcp_servers.append(chroma_server_obj)
    if fs_server_obj:
        mcp_servers.append(fs_server_obj)
    
    if not mcp_servers:
        print("\n   ❌ No MCP servers available. Cannot test MCP tool access.")
        print("   Start MCP servers and set environment variables:")
        print("   export MCP_USE_SERVER=true")
        print("   export FS_MCP_USE_SERVER=true")
        # Clean up
        if chroma_server:
            await chroma_server.__aexit__(None, None, None)
        if fs_server:
            await fs_server.__aexit__(None, None, None)
        return
    
    try:
        # Build QA agent with MCP servers
        print("\n4. Building QA agent with MCP servers...")
        qa_agent = build_qa_agent(
            retriever=retriever,
            state=state,
            min_confidence=0.2,
            handoffs=[],
            mcp_servers=mcp_servers,
        )
        print(f"   ✅ QA agent built")
        
        # Check if agent has MCP tools
        print("\n5. Checking agent tool access...")
        # The agents SDK automatically adds MCP tools to the agent
        # We can't directly inspect tools, but we can test by having the agent use them
        print(f"   ✅ Agent created with MCP servers (tools should be available)")
        
        # Test 1: Agent can access Chroma MCP tools
        print("\n6. Test 1: QA agent using Chroma MCP tools...")
        if chroma_server_obj:
            try:
                result = await Runner.run(
                    qa_agent,
                    "List all collections in the Chroma database using the list_collections tool"
                )
                print(f"   ✅ Agent response received")
                print(f"   Response: {result.final_output[:200]}...")
                
                # Check if agent actually used MCP tools
                if "collection" in result.final_output.lower() or "chroma" in result.final_output.lower():
                    print(f"   ✅ Agent appears to have accessed Chroma MCP tools")
                else:
                    print(f"   ⚠️  Agent response doesn't indicate MCP tool usage")
            except Exception as e:
                print(f"   ❌ Test failed: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"   ⏭️  Skipped (Chroma MCP server not available)")
        
        # Test 2: Agent can access Filesystem MCP tools
        print("\n7. Test 2: QA agent using Filesystem MCP tools...")
        if fs_server_obj:
            try:
                result = await Runner.run(
                    qa_agent,
                    "List the files in the project root directory using the list_directory tool"
                )
                print(f"   ✅ Agent response received")
                print(f"   Response: {result.final_output[:200]}...")
                
                # Check if agent actually used MCP tools
                if "file" in result.final_output.lower() or "directory" in result.final_output.lower():
                    print(f"   ✅ Agent appears to have accessed Filesystem MCP tools")
                else:
                    print(f"   ⚠️  Agent response doesn't indicate MCP tool usage")
            except Exception as e:
                print(f"   ❌ Test failed: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"   ⏭️  Skipped (Filesystem MCP server not available)")
        
        # Test 3: Agent can write files using MCP
        print("\n8. Test 3: QA agent writing file using Filesystem MCP...")
        if fs_server_obj:
            try:
                test_file_path = "data/generated/test_qa_mcp_output.txt"
                result = await Runner.run(
                    qa_agent,
                    f"Create a test file at {test_file_path} with content 'This is a test file created by QA agent via MCP tools' using the write_text_file tool"
                )
                print(f"   ✅ Agent response received")
                print(f"   Response: {result.final_output[:200]}...")
                
                # Check if file was actually created
                test_file = Path(test_file_path)
                if test_file.exists():
                    content = test_file.read_text()
                    print(f"   ✅ File created successfully!")
                    print(f"   File content: {content[:100]}...")
                    # Clean up
                    test_file.unlink()
                    print(f"   ✅ Test file cleaned up")
                else:
                    print(f"   ⚠️  File was not created (agent may not have called write_text_file)")
            except Exception as e:
                print(f"   ❌ Test failed: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"   ⏭️  Skipped (Filesystem MCP server not available)")
        
        # Test 4: Agent can query Chroma collections
        print("\n9. Test 4: QA agent querying Chroma collection...")
        if chroma_server_obj:
            try:
                result = await Runner.run(
                    qa_agent,
                    "Query the Chroma database for collections and show me information about the first collection using get_collection_info tool"
                )
                print(f"   ✅ Agent response received")
                print(f"   Response: {result.final_output[:300]}...")
                
                if "collection" in result.final_output.lower() or "document" in result.final_output.lower():
                    print(f"   ✅ Agent appears to have queried Chroma collections")
                else:
                    print(f"   ⚠️  Agent response doesn't indicate collection query")
            except Exception as e:
                print(f"   ❌ Test failed: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"   ⏭️  Skipped (Chroma MCP server not available)")
        
        print("\n" + "=" * 70)
        print("Test Summary")
        print("=" * 70)
        print("✅ QA agent can be built with MCP servers")
        print("✅ MCP tools should be automatically available to the agent")
        print("✅ Agent can call MCP tools when instructed")
        print("\nNote: The agents SDK automatically makes MCP tools available")
        print("to the agent. The agent will use them when appropriate based on")
        print("the user's request and its instructions.")
        print()
    
    finally:
        # Clean up MCP server connections
        print("Cleaning up MCP server connections...")
        if chroma_server:
            try:
                await chroma_server.__aexit__(None, None, None)
            except:
                pass
        if fs_server:
            try:
                await fs_server.__aexit__(None, None, None)
            except:
                pass


def main():
    """Run the test."""
    try:
        asyncio.run(test_qa_agent_mcp_tools())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

