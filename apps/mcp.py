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
                    logger.info("[MCP] Connected to %s", self.name)
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
                        default_port=8000,
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
        for name, manager in _mcp_server_managers.items():
            server = manager.initialize()
            if server is not None:
                connections[name] = server
        return connections


def shutdown_mcp_servers() -> None:
    """Close all MCP connections."""
    with _mcp_lock:
        for manager in _mcp_server_managers.values():
            manager.shutdown()
        _mcp_server_managers.clear()

