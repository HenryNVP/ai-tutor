"""Shared MCP server management for backend services."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class MCPServerManager:
    """Manages a single MCP connection in a background thread."""

    def __init__(
        self,
        *,
        name: str,
        env_prefix: str,
        default_port: int,
        start_hint: str,
    ):
        self.name = name
        self.env_prefix = env_prefix
        self.default_port = default_port
        self.start_hint = start_hint

        self.server: Optional[Any] = None
        self.server_obj: Optional[Any] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self._initialized = False
        self._connection_error: Optional[str] = None
        self._connection_event = threading.Event()
        self._connection_start_time: Optional[float] = None

    def initialize(self) -> Optional[Any]:
        """Initialize MCP server connection in the background."""
        if self._initialized and self.server_obj is not None:
            return self.server_obj

        if self._connection_error:
            return None

        use_flag = f"{self.env_prefix}_USE_SERVER"
        use_mcp = os.getenv(use_flag, "true").lower() in ("true", "1", "yes")
        if not use_mcp:
            return None

        try:
            from agents.mcp import MCPServerStreamableHttp

            port_env = f"{self.env_prefix}_PORT"
            # For filesystem server, don't fall back to MCP_PORT to avoid connecting to wrong server
            if self.env_prefix == "FS_MCP":
                port = int(os.getenv(port_env, str(self.default_port)))
            else:
                # For chroma and other servers, allow fallback to MCP_PORT
                port = int(os.getenv(port_env, os.getenv("MCP_PORT", str(self.default_port))))
            server_url = os.getenv(
                f"{self.env_prefix}_URL",
                f"http://localhost:{port}/mcp",
            )

            # Quick reachability check (any HTTP response counts)
            base_url = server_url.rsplit("/mcp", 1)[0]
            try:
                response = requests.get(base_url, timeout=2)
                logger.debug(
                    "[MCP] %s server probe returned %s",
                    self.name,
                    response.status_code,
                )
            except requests.exceptions.ConnectionError:
                self._connection_error = (
                    f"{self.name} not running on port {port}. "
                    f"Start it with:\n{self.start_hint}"
                )
                logger.warning("[MCP] Connection refused on port %s for %s", port, self.name)
                return None
            except requests.exceptions.Timeout:
                self._connection_error = f"{self.name} timed out on port {port}"
                logger.warning("[MCP] Timeout connecting to port %s for %s", port, self.name)
                return None
            except Exception:
                # Non-fatal. The server might still be alive even if probe failed.
                logger.debug("[MCP] Probe error for %s, continuing", self.name, exc_info=True)

            streamable_params = {
                "url": server_url,
                "timeout": int(os.getenv(f"{self.env_prefix}_TIMEOUT", os.getenv("MCP_TIMEOUT", "10"))),
            }
            mcp_token = os.getenv(f"{self.env_prefix}_SERVER_TOKEN", os.getenv("MCP_SERVER_TOKEN"))
            if mcp_token:
                streamable_params["headers"] = {"Authorization": f"Bearer {mcp_token}"}

            self.server = MCPServerStreamableHttp(
                name=self.name,
                params=streamable_params,
                cache_tools_list=True,
                max_retry_attempts=3,
                client_session_timeout_seconds=streamable_params["timeout"],
            )
            logger.info("[MCP] %s configured (tool list caching enabled)", self.name)

            def _run_server():
                try:
                    self.loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self.loop)

                    async def _connect_with_timeout():
                        return await asyncio.wait_for(self.server.__aenter__(), timeout=10.0)

                    self.server_obj = self.loop.run_until_complete(_connect_with_timeout())
                    self._connection_error = None
                    
                    # Validate that the server provides the expected tools
                    try:
                        tools = self.loop.run_until_complete(self.server_obj.list_tools())
                        tool_names = {tool.name for tool in tools} if tools else set()
                        
                        # Expected tools for each server type
                        expected_chroma_tools = {
                            "query_collection", "add_documents", "list_collections",
                            "get_collection_info", "create_collection", "delete_collection",
                            "generate_embedding", "query_with_text"
                        }
                        expected_filesystem_tools = {
                            "read_text_file", "write_text_file", "list_directory",
                            "create_directory", "delete_path"
                        }
                        
                        # Validate server type based on tools
                        is_chroma = bool(tool_names & expected_chroma_tools)
                        is_filesystem = bool(tool_names & expected_filesystem_tools)
                        
                        if "chroma" in self.name.lower() and not is_chroma:
                            logger.warning(
                                "[MCP] Chroma server on port %d doesn't have expected Chroma tools. "
                                "Found tools: %s. This might be the wrong server.",
                                port,
                                sorted(tool_names)[:10],
                            )
                        elif "filesystem" in self.name.lower() and not is_filesystem:
                            logger.warning(
                                "[MCP] Filesystem server on port %d doesn't have expected filesystem tools. "
                                "Found tools: %s. This might be the wrong server.",
                                port,
                                sorted(tool_names)[:10],
                            )
                        
                        logger.info(
                            "[MCP] Connected to %s on port %d (%d tools: %s)",
                            self.name,
                            port,
                            len(tool_names),
                            ", ".join(sorted(tool_names)[:5]) + ("..." if len(tool_names) > 5 else ""),
                        )
                        # Store tool names for duplicate detection
                        self._tool_names = tool_names
                    except Exception as tool_check_exc:
                        logger.warning(
                            "[MCP] Connected to %s but failed to list tools: %s",
                            self.name,
                            tool_check_exc,
                        )
                        self._tool_names = set()
                    
                    self._connection_event.set()

                    async def _keep_alive():
                        while True:
                            await asyncio.sleep(60)

                    self.loop.create_task(_keep_alive())
                    self.loop.run_forever()
                except Exception as exc:  # pragma: no cover - defensive logging
                    self._connection_error = str(exc)
                    self._connection_event.set()
                    logger.error("[MCP] Connection failed for %s: %s", self.name, exc, exc_info=True)

            import time

            self._connection_start_time = time.time()
            self.thread = threading.Thread(target=_run_server, daemon=True)
            self.thread.start()

            if self._connection_event.wait(timeout=10.0) and not self._connection_error:
                self._initialized = True
                return self.server_obj

            if not self._connection_error:
                self._connection_error = (
                    f"Connection timeout after 10 seconds. "
                    f"Is {self.name} running on port {port}? Start it with:\n{self.start_hint}"
                )
            self._initialized = True
            return None

        except ImportError:
            self._connection_error = "MCP library not available"
            return None
        except Exception as exc:  # pragma: no cover - defensive
            self._connection_error = str(exc)
            return None

    def shutdown(self) -> None:
        """Gracefully close the MCP connection."""
        if self.loop and self.loop.is_running() and self.server:
            async def _close():
                try:
                    await self.server.__aexit__(None, None, None)
                except Exception as exc:
                    logger.warning("[MCP] Error shutting down %s: %s", self.name, exc)

            future = asyncio.run_coroutine_threadsafe(_close(), self.loop)
            try:
                future.result(timeout=5)
            except Exception as exc:
                logger.warning("[MCP] Shutdown future error for %s: %s", self.name, exc)
            self.loop.call_soon_threadsafe(self.loop.stop)

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

        self.server = None
        self.server_obj = None
        self.loop = None
        self.thread = None
        self._initialized = False
        self._connection_event.clear()
        self._connection_error = None
        self._tool_names = set()


_mcp_server_managers: Dict[str, MCPServerManager] = {}
_mcp_lock = threading.Lock()


def load_mcp_servers() -> Dict[str, Any]:
    """Return active MCP connections for backend services."""
    with _mcp_lock:
        if not _mcp_server_managers:
            _mcp_server_managers.update(
                {
                    "chroma": MCPServerManager(
                        name="Chroma MCP Server",
                        env_prefix="MCP",
                        default_port=8200,  # Updated to match chroma_mcp_server default
                        start_hint="cd chroma_mcp_server\npython server.py",
                    ),
                    "filesystem": MCPServerManager(
                        name="Filesystem MCP Server",
                        env_prefix="FS_MCP",
                        default_port=8100,
                        start_hint="cd filesystem_mcp_server\npython server.py",
                    ),
                }
            )

        connections: Dict[str, Any] = {}
        tool_names_by_server: Dict[str, set] = {}
        
        for name, manager in _mcp_server_managers.items():
            server = manager.initialize()
            if server is not None:
                connections[name] = server
                # Collect tool names for validation
                if hasattr(manager, "_tool_names") and manager._tool_names:
                    tool_names_by_server[name] = manager._tool_names
        
        # Validate that servers don't have duplicate tools
        if len(tool_names_by_server) > 1:
            all_tool_sets = list(tool_names_by_server.values())
            if len(all_tool_sets) >= 2:
                # Check for overlaps
                set1, set2 = all_tool_sets[0], all_tool_sets[1]
                duplicates = set1 & set2
                if duplicates:
                    server_names = list(tool_names_by_server.keys())
                    logger.error(
                        "[MCP] CRITICAL: Duplicate tool names detected between servers!\n"
                        "  Server 1 (%s): %d tools\n"
                        "  Server 2 (%s): %d tools\n"
                        "  Duplicate tools: %s\n"
                        "  This usually means both servers are running the same code or pointing to the same instance.\n"
                        "  Expected:\n"
                        "    - Chroma MCP (port 8200): query_collection, add_documents, list_collections, etc.\n"
                        "    - Filesystem MCP (port 8100): read_text_file, write_text_file, list_directory, etc.\n"
                        "  Check that you have started the correct server on each port.",
                        server_names[0],
                        len(set1),
                        server_names[1],
                        len(set2),
                        sorted(duplicates),
                    )
                    # Don't fail here - let the agent SDK handle it, but log the issue clearly
        
        return connections


def shutdown_mcp_servers() -> None:
    """Close all MCP connections."""
    with _mcp_lock:
        for manager in _mcp_server_managers.values():
            manager.shutdown()
        _mcp_server_managers.clear()

