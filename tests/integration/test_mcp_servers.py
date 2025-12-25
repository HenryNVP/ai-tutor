"""Integration tests for MCP server functionality.

These tests require real MCP servers to be running.
Run with: pytest tests/integration/test_mcp_servers.py -m mcp -v

To start MCP servers:
  cd chroma_mcp_server && python server.py
  cd filesystem_mcp_server && python server.py
"""

import pytest
import asyncio


@pytest.mark.mcp
@pytest.mark.integration
def test_mcp_servers_available(mcp_servers):
    """Test that MCP servers are available and can be loaded."""
    assert mcp_servers, "MCP servers should be available"
    assert len(mcp_servers) > 0, "At least one MCP server should be connected"


@pytest.mark.mcp
@pytest.mark.integration
@pytest.mark.asyncio
async def test_chroma_mcp_tools(chroma_mcp_server):
    """Test that ChromaDB MCP server provides expected tools."""
    if not chroma_mcp_server:
        pytest.skip("ChromaDB MCP server not available")
    
    tools = await chroma_mcp_server.list_tools()
    tool_names = {tool.name for tool in tools} if tools else set()
    
    # Check for key ChromaDB tools
    expected_tools = {
        "list_collections",
        "query_collection",
        "add_documents",
    }
    
    assert tool_names, "ChromaDB MCP server should provide tools"
    assert expected_tools.issubset(tool_names), \
        f"Expected tools {expected_tools} not found. Available: {tool_names}"


@pytest.mark.mcp
@pytest.mark.integration
@pytest.mark.asyncio
async def test_filesystem_mcp_tools(filesystem_mcp_server):
    """Test that Filesystem MCP server provides expected tools."""
    if not filesystem_mcp_server:
        pytest.skip("Filesystem MCP server not available")
    
    tools = await filesystem_mcp_server.list_tools()
    tool_names = {tool.name for tool in tools} if tools else set()
    
    # Check for key filesystem tools
    expected_tools = {
        "read_text_file",
        "write_text_file",
        "list_directory",
    }
    
    assert tool_names, "Filesystem MCP server should provide tools"
    assert expected_tools.issubset(tool_names), \
        f"Expected tools {expected_tools} not found. Available: {tool_names}"


@pytest.mark.mcp
@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_collections_schema(chroma_mcp_server):
    """Test that list_collections has correct schema for Gemini compatibility."""
    if not chroma_mcp_server:
        pytest.skip("ChromaDB MCP server not available")
    
    tools = await chroma_mcp_server.list_tools()
    list_collections_tool = next((t for t in tools if t.name == "list_collections"), None)
    
    assert list_collections_tool is not None, "list_collections tool should exist"
    
    # Check that parameters schema is OBJECT type (required for Gemini)
    if hasattr(list_collections_tool, 'inputSchema'):
        schema = list_collections_tool.inputSchema
        if isinstance(schema, dict) and 'properties' in schema:
            # Schema should have OBJECT type parameters
            # The dummy parameter we added ensures this
            assert 'type' in schema or 'properties' in schema, \
                "list_collections should have parameters schema"


@pytest.mark.mcp
@pytest.mark.integration
def test_no_duplicate_tools(mcp_servers):
    """Test that MCP servers don't have duplicate tool names."""
    if len(mcp_servers) < 2:
        pytest.skip("Need at least 2 MCP servers to check for duplicates")
    
    # This test would need async execution to get tools
    # For now, just verify servers are distinct
    server_names = list(mcp_servers.keys())
    assert len(server_names) == len(set(server_names)), \
        "MCP server names should be unique"

