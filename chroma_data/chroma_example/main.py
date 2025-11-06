"""Example demonstrating how to connect to a local Chroma MCP server.

This example shows how to connect to a Chroma MCP server running locally.
Chroma MCP servers typically use either SSE or Streamable HTTP transport.
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


async def run(mcp_server: MCPServer):
    """Run the agent with the provided MCP server."""
    agent = Agent(
        name="Assistant",
        instructions="Use the Chroma MCP tools to answer questions about the vector database.",
        mcp_servers=[mcp_server],
        model_settings=ModelSettings(tool_choice="required"),
    )

    # List all collections
    message = "List all collections in the database."
    print(f"Running: {message}")
    result = await Runner.run(starting_agent=agent, input=message)
    print(result.final_output)

    # Create a collection and add some documents
    message = "Create a collection called 'test_docs' and add 3 sample documents about Python programming."
    print(f"\n\nRunning: {message}")
    result = await Runner.run(starting_agent=agent, input=message)
    print(result.final_output)

    # Query the collection
    message = "Query the 'test_docs' collection for information about Python."
    print(f"\n\nRunning: {message}")
    result = await Runner.run(starting_agent=agent, input=message)
    print(result.final_output)


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
        async with MCPServerStreamableHttp(
            name="Chroma MCP Server (Streamable HTTP)",
            params={
                "url": server_url,
            },
            cache_tools_list=True,
            max_retry_attempts=3,
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
    asyncio.run(main())

