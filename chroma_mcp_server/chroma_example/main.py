"""Example client for Chroma MCP Server

This demonstrates how to use the Chroma MCP Server with the OpenAI Agents SDK.
"""

import asyncio
import os
from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp


async def main():
    """Run example queries against the Chroma MCP Server."""
    # Get server URL from environment or use default
    mcp_url = os.getenv("MCP_URL", "http://localhost:8000/mcp")
    mcp_port = os.getenv("MCP_PORT", "8000")
    
    # If MCP_URL not set, construct from port
    if mcp_url == "http://localhost:8000/mcp" and mcp_port != "8000":
        mcp_url = f"http://localhost:{mcp_port}/mcp"
    
    print(f"Connecting to MCP server at {mcp_url}...")
    
    async with MCPServerStreamableHttp(
        name="Chroma MCP Server",
        params={"url": mcp_url},
        cache_tools_list=True,
    ) as server:
        agent = Agent(
            name="Chroma Assistant",
            instructions="Use Chroma tools to query the database. Be concise and helpful.",
            mcp_servers=[server],
        )
        
        # Example queries
        queries = [
            "List all collections",
            "What collections exist?",
        ]
        
        for query in queries:
            print(f"\n{'='*60}")
            print(f"Query: {query}")
            print(f"{'='*60}")
            result = await Runner.run(agent, query)
            print(f"Response: {result.final_output}\n")


if __name__ == "__main__":
    asyncio.run(main())

