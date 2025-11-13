"""Example: Testing Filesystem MCP Server with AI Tutor

This script demonstrates how to test the filesystem MCP server integration
with the AI Tutor system.

Usage:
    # Terminal 1: Start Chroma MCP server
    cd chroma_mcp_server
    python server.py

    # Terminal 2: Start Filesystem MCP server
    cd filesystem_mcp_server
    python server.py

    # Terminal 3: Run this test
    python filesystem_mcp_server/test_example.py
"""

import asyncio
import os
from pathlib import Path

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp

from ai_tutor.system import TutorSystem
from ai_tutor.config.loader import load_settings


async def test_filesystem_mcp_direct():
    """Test filesystem MCP server directly with an agent."""
    print("=" * 60)
    print("Test 1: Direct Filesystem MCP Connection")
    print("=" * 60)
    
    # Connect to filesystem MCP server
    fs_port = int(os.getenv("FS_MCP_PORT", "8100"))
    fs_url = f"http://localhost:{fs_port}/mcp"
    
    print(f"Connecting to Filesystem MCP server at {fs_url}...")
    
    async with MCPServerStreamableHttp(
        name="Filesystem MCP Server",
        params={"url": fs_url},
        cache_tools_list=True,
    ) as fs_server:
        # Create an agent with filesystem MCP access
        agent = Agent(
            name="File Explorer",
            instructions="You can read, write, and list files using filesystem tools.",
            mcp_servers=[fs_server],
        )
        
        # Test queries
        test_queries = [
            "List the files in the root directory",
            "Read the README.md file",
            "What files are in the src/ directory?",
        ]
        
        for query in test_queries:
            print(f"\n{'─' * 60}")
            print(f"Query: {query}")
            print(f"{'─' * 60}")
            try:
                result = await Runner.run(agent, query)
                print(f"Response: {result.final_output}\n")
            except Exception as e:
                print(f"Error: {e}\n")


async def test_filesystem_mcp_with_tutor():
    """Test filesystem MCP server integrated with TutorSystem."""
    print("\n" + "=" * 60)
    print("Test 2: Filesystem MCP with TutorSystem")
    print("=" * 60)
    
    # Load settings
    settings = load_settings()
    
    # Connect to both MCP servers
    chroma_port = int(os.getenv("MCP_PORT", "8000"))
    fs_port = int(os.getenv("FS_MCP_PORT", "8100"))
    
    chroma_url = f"http://localhost:{chroma_port}/mcp"
    fs_url = f"http://localhost:{fs_port}/mcp"
    
    print(f"Connecting to Chroma MCP: {chroma_url}")
    print(f"Connecting to Filesystem MCP: {fs_url}\n")
    
    async with MCPServerStreamableHttp(
        name="Chroma MCP Server",
        params={"url": chroma_url},
        cache_tools_list=True,
    ) as chroma_server, MCPServerStreamableHttp(
        name="Filesystem MCP Server",
        params={"url": fs_url},
        cache_tools_list=True,
    ) as fs_server:
        
        # Initialize TutorSystem with both MCP servers
        system = TutorSystem(
            settings=settings,
            mcp_servers={
                "chroma": chroma_server,
                "filesystem": fs_server,
            },
        )
        
        print("✅ TutorSystem initialized with both MCP servers\n")
        
        # Test queries that should use filesystem tools
        test_queries = [
            "What files are in the project root?",
            "Read the README.md file and summarize the key features",
            "List all Python files in the src/ directory",
        ]
        
        learner_id = "test_learner"
        
        for query in test_queries:
            print(f"\n{'─' * 60}")
            print(f"Query: {query}")
            print(f"{'─' * 60}")
            try:
                response = await system.answer_question_async(
                    learner_id=learner_id,
                    question=query,
                    mode="learning",
                )
                print(f"Answer: {response.answer}")
                if response.citations:
                    print(f"\nCitations: {response.citations}")
                print()
            except Exception as e:
                print(f"Error: {e}\n")


def test_filesystem_tools_available():
    """Check if filesystem MCP tools are available."""
    print("\n" + "=" * 60)
    print("Test 3: Check Available Tools")
    print("=" * 60)
    
    import requests
    
    fs_port = int(os.getenv("FS_MCP_PORT", "8100"))
    fs_url = f"http://localhost:{fs_port}/mcp"
    
    try:
        # Try to list tools (this is a simplified check)
        response = requests.get(f"http://localhost:{fs_port}", timeout=2)
        print(f"✅ Filesystem MCP server is running on port {fs_port}")
        print(f"   Server URL: {fs_url}")
        print("\nExpected tools:")
        print("  - list_directory")
        print("  - read_file")
        print("  - write_text_file")
        print("  - delete_path")
    except requests.exceptions.ConnectionError:
        print(f"❌ Filesystem MCP server is NOT running on port {fs_port}")
        print(f"   Start it with: cd filesystem_mcp_server && python server.py")
    except Exception as e:
        print(f"⚠️  Could not verify server status: {e}")


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Filesystem MCP Server Test Suite")
    print("=" * 60)
    print("\nPrerequisites:")
    print("1. Start Chroma MCP server: cd chroma_mcp_server && python server.py")
    print("2. Start Filesystem MCP server: cd filesystem_mcp_server && python server.py")
    print("3. Set environment variables:")
    print("   export MCP_USE_SERVER=true")
    print("   export FS_MCP_USE_SERVER=true")
    print("\nPress Enter to continue or Ctrl+C to exit...")
    input()
    
    # Test 1: Check if server is available
    test_filesystem_tools_available()
    
    # Test 2: Direct connection test
    try:
        await test_filesystem_mcp_direct()
    except Exception as e:
        print(f"❌ Direct connection test failed: {e}")
        print("   Make sure filesystem MCP server is running on port 8100")
    
    # Test 3: Integration with TutorSystem
    try:
        await test_filesystem_mcp_with_tutor()
    except Exception as e:
        print(f"❌ TutorSystem integration test failed: {e}")
        print("   Make sure both MCP servers are running")


if __name__ == "__main__":
    asyncio.run(main())

