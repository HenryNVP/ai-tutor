#!/usr/bin/env python3
"""Diagnostic script to check MCP server configuration and detect duplicate tools."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.mcp import load_mcp_servers, shutdown_mcp_servers


async def check_server_tools(server, server_name: str, port: int):
    """Check and list tools from an MCP server."""
    try:
        tools = await server.list_tools()
        tool_names = {tool.name for tool in tools} if tools else set()
        print(f"\n[{server_name}] Port {port}:")
        print(f"  ✅ Connected successfully")
        print(f"  📦 Tools ({len(tool_names)}): {', '.join(sorted(tool_names))}")
        return tool_names
    except Exception as exc:
        print(f"\n[{server_name}] Port {port}:")
        print(f"  ❌ Failed to list tools: {exc}")
        return set()


async def main():
    """Check all MCP servers for configuration issues."""
    print("=" * 70)
    print("MCP Server Configuration Check")
    print("=" * 70)
    
    # Expected tool sets
    expected_chroma_tools = {
        "query_collection", "add_documents", "list_collections",
        "get_collection_info", "create_collection", "delete_collection",
        "generate_embedding", "query_with_text"
    }
    expected_filesystem_tools = {
        "read_text_file", "write_text_file", "list_directory",
        "create_directory", "delete_path"
    }
    
    print("\nLoading MCP servers...")
    mcp_servers = load_mcp_servers()
    
    if not mcp_servers:
        print("\n❌ No MCP servers connected!")
        print("\nTo start servers:")
        print("  1. Chroma MCP: cd chroma_mcp_server && python server.py")
        print("  2. Filesystem MCP: cd filesystem_mcp_server && python server.py")
        return
    
    print(f"\n✅ Found {len(mcp_servers)} MCP server(s)")
    
    # Check each server
    tool_sets = {}
    for name, server in mcp_servers.items():
        # Determine port from name
        if "chroma" in name.lower():
            port = int(os.getenv("MCP_PORT", "8200"))
        elif "filesystem" in name.lower():
            port = int(os.getenv("FS_MCP_PORT", "8100"))
        else:
            port = 0
        
        tool_names = await check_server_tools(server, name, port)
        tool_sets[name] = tool_names
    
    # Check for duplicates
    if len(tool_sets) >= 2:
        server_names = list(tool_sets.keys())
        set1, set2 = tool_sets[server_names[0]], tool_sets[server_names[1]]
        duplicates = set1 & set2
        
        if duplicates:
            print("\n" + "=" * 70)
            print("❌ CRITICAL ERROR: Duplicate tool names detected!")
            print("=" * 70)
            print(f"\nBoth servers are providing the same tools:")
            print(f"  Duplicate tools: {', '.join(sorted(duplicates))}")
            print(f"\nThis means:")
            print(f"  1. Both servers are running the same code, OR")
            print(f"  2. Both ports are pointing to the same server instance")
            print(f"\nExpected configuration:")
            print(f"  - Chroma MCP (port 8200): Should have Chroma tools")
            print(f"    Expected: {', '.join(sorted(expected_chroma_tools)[:5])}...")
            print(f"  - Filesystem MCP (port 8100): Should have filesystem tools")
            print(f"    Expected: {', '.join(sorted(expected_filesystem_tools))}")
            print(f"\nActual configuration:")
            print(f"  - {server_names[0]}: {len(set1)} tools")
            print(f"  - {server_names[1]}: {len(set2)} tools")
            print(f"\n💡 Solution:")
            print(f"  1. Stop all MCP servers")
            print(f"  2. Start Chroma MCP: cd chroma_mcp_server && python server.py")
            print(f"  3. Start Filesystem MCP: cd filesystem_mcp_server && python server.py")
            print(f"  4. Verify each is running on the correct port")
        else:
            print("\n" + "=" * 70)
            print("✅ No duplicate tools detected - configuration looks correct!")
            print("=" * 70)
    
    # Validate server types
    print("\n" + "=" * 70)
    print("Server Type Validation")
    print("=" * 70)
    
    for name, tool_names in tool_sets.items():
        is_chroma = bool(tool_names & expected_chroma_tools)
        is_filesystem = bool(tool_names & expected_filesystem_tools)
        
        if "chroma" in name.lower():
            if is_chroma:
                print(f"✅ {name}: Correctly identified as Chroma server")
            else:
                print(f"❌ {name}: Expected Chroma tools but found different tools")
        elif "filesystem" in name.lower():
            if is_filesystem:
                print(f"✅ {name}: Correctly identified as Filesystem server")
            else:
                print(f"❌ {name}: Expected Filesystem tools but found different tools")
    
    shutdown_mcp_servers()
    print("\n" + "=" * 70)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

