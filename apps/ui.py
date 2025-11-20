"""Streamlit-based UI for the AI tutor."""

from __future__ import annotations

import io
import logging
import os
import re
import sys
import tempfile
import uuid
import base64
import asyncio
import threading
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional
from collections import Counter

logger = logging.getLogger(__name__)

# Add project root to Python path for absolute imports
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st
from streamlit.runtime.secrets import StreamlitSecretNotFoundError

# No direct service imports; UI uses HTTP session client
from apps.chat_helpers import (
    format_answer,
    is_question_about_uploaded_docs,
    extract_document_hints,
)
from apps.session_client import SessionClient
from apps.file_utils import extract_text, summarize_documents
from ai_tutor.learning.quiz import Quiz, QuizEvaluation
from ai_tutor.learning.quiz_utils import quiz_to_markdown
from ai_tutor.agents.visualization import VisualizationAgent
from ai_tutor.agents.llm_client import LLMClient
from ai_tutor.config.loader import load_settings
from ai_tutor.data_models.session import SessionResponse, SessionHistoryResponse

try:  # pragma: no cover - optional dependency
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None  # type: ignore[assignment]


# Global MCP server managers keyed by logical name
_mcp_server_managers: Dict[str, MCPServerManager] = {}
_mcp_server_lock = threading.Lock()


def _prepare_uploaded_files(
    uploaded_files: List[Any],
    session_client: SessionClient,
) -> tuple[List[str], Optional[Dict[str, Any]]]:
    """
    Save uploaded files and ingest them immediately.
    
    Returns filenames that were ingested and the ingestion result.
    """
    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: List[Path] = []

    for uploaded_file in uploaded_files:
        if not uploaded_file.name:
            continue
        file_bytes = uploaded_file.getvalue()
        file_path = upload_dir / uploaded_file.name
        file_path.write_bytes(file_bytes)
        saved_paths.append(file_path)

    ingestion_result = None
    if saved_paths:
        ingestion_result = session_client.ingest_files(saved_paths)

    ingested_filenames = [path.name for path in saved_paths]
    return ingested_filenames, ingestion_result


class MCPServerManager:
    """Manages MCP server lifecycle in a background thread for Streamlit.
    
    This class ensures:
    - MCP server connection is initialized once and reused across all queries
    - Tool list is cached to avoid redundant API calls
    - Event loop stays non-blocking with async operations
    """
    
    def __init__(
        self,
        *,
        name: str,
        env_prefix: str,
        default_port: int,
        start_hint: str,
    ):
        self.server = None
        self.server_obj = None
        self.loop = None
        self.thread = None
        self._initialized = False
        self._connection_error = None  # Track connection errors
        self._connection_event = threading.Event()  # Signal when connection is ready
        self._connection_start_time = None  # Track when connection attempt started
        self.name = name
        self.env_prefix = env_prefix
        self.default_port = default_port
        self.start_hint = start_hint
    
    def initialize(self) -> Optional[Any]:
        """Initialize MCP server connection in background thread.
        
        Returns the same server instance on subsequent calls to ensure
        persistent connection and tool list caching.
        """
        if self._initialized and self.server_obj is not None:
            return self.server_obj
        
        if self._connection_error:
            # Connection previously failed, don't retry automatically
            return None
        
        use_flag = f"{self.env_prefix}_USE_SERVER"
        use_mcp = os.getenv(use_flag, "true").lower() in ("true", "1", "yes")
        if not use_mcp:
            return None
        
        try:
            from agents.mcp import MCPServerStreamableHttp
            import requests
            
            port_env = f"{self.env_prefix}_PORT"
            port = int(os.getenv(port_env, os.getenv("MCP_PORT", str(self.default_port))))
            server_url = os.getenv(
                f"{self.env_prefix}_URL",
                f"http://localhost:{port}/mcp",
            )
            
            # Check if server is reachable before attempting connection
            # Note: Root URL returns 404, but /mcp endpoint exists (requires SSE format)
            try:
                # Try to reach the server (any response means it's running)
                # We check root because /mcp requires specific headers
                base_url = server_url.rsplit("/mcp", 1)[0]
                response = requests.get(base_url, timeout=2)
                # Any HTTP response (even 404) means server is running
                logger.debug(f"[MCP] Server check: {response.status_code} from {base_url} (server is running)")
            except requests.exceptions.ConnectionError:
                self._connection_error = (
                    f"{self.name} not running on port {port}. "
                    f"Start it with:\n{self.start_hint}"
                )
                logger.warning(f"[MCP] Connection refused on port {port} for {self.name}")
                return None
            except requests.exceptions.Timeout:
                self._connection_error = f"{self.name} timed out on port {port}"
                logger.warning(f"[MCP] Timeout connecting to port {port} for {self.name}")
                return None
            except Exception as e:
                # Other errors might be OK (server might be running but endpoint different)
                logger.debug(f"[MCP] Server check exception for {self.name} (may be OK): {e}")
                pass
            
            streamable_params = {
                "url": server_url,
                "timeout": int(
                    os.getenv(f"{self.env_prefix}_TIMEOUT", os.getenv("MCP_TIMEOUT", "10"))
                ),
            }
            
            mcp_token = os.getenv(f"{self.env_prefix}_SERVER_TOKEN", os.getenv("MCP_SERVER_TOKEN"))
            if mcp_token:
                streamable_params["headers"] = {"Authorization": f"Bearer {mcp_token}"}
            
            self.server = MCPServerStreamableHttp(
                name=self.name,
                params=streamable_params,
                cache_tools_list=True,  # CRITICAL: Cache tool list to prevent redundant tools/list calls
                max_retry_attempts=3,
                # Add timeout to prevent hanging
                client_session_timeout_seconds=int(
                    os.getenv(f"{self.env_prefix}_TIMEOUT", os.getenv("MCP_TIMEOUT", "10"))
                ),
            )
            logger.info(f"[MCP] {self.name} configured with tool list caching and timeout enabled")
            
            # Create event loop in background thread
            def _run_server():
                try:
                    self.loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self.loop)
                    
                    # Add timeout to connection attempt
                    async def _connect_with_timeout():
                        try:
                            return await asyncio.wait_for(
                                self.server.__aenter__(),
                                timeout=10.0  # 10 second timeout for connection
                            )
                        except asyncio.TimeoutError:
                            raise RuntimeError("MCP server connection timed out after 10 seconds")
                    
                    self.server_obj = self.loop.run_until_complete(_connect_with_timeout())
                    self._connection_error = None
                    logger.info(f"[MCP] Successfully connected to {self.name}")
                    
                    # Pre-warm tool list in background to avoid blocking first query
                    # This fetches the tool list eagerly so the first agent query doesn't wait
                    async def _prewarm_tools():
                        try:
                            import time
                            prewarm_start = time.time()
                            # Try to access tools property or trigger tool list fetch
                            # MCPServerStreamableHttp with cache_tools_list=True will cache the result
                            if hasattr(self.server_obj, 'list_tools'):
                                tools = await self.server_obj.list_tools()
                                prewarm_duration = time.time() - prewarm_start
                                logger.info(
                                    f"[MCP] {self.name} pre-warmed tool list: "
                                    f"{len(tools) if tools else 0} tools cached in {prewarm_duration:.3f}s"
                                )
                            elif hasattr(self.server_obj, 'tools'):
                                # Access tools property to trigger fetch
                                tools = self.server_obj.tools
                                prewarm_duration = time.time() - prewarm_start
                                logger.info(
                                    f"[MCP] {self.name} pre-warmed tool list via property: "
                                    f"{len(tools) if tools else 0} tools cached in {prewarm_duration:.3f}s"
                                )
                            elif hasattr(self.server, 'list_tools'):
                                # Try on the server object itself
                                tools = await self.server.list_tools()
                                prewarm_duration = time.time() - prewarm_start
                                logger.info(
                                    f"[MCP] {self.name} pre-warmed tool list via server: "
                                    f"{len(tools) if tools else 0} tools cached in {prewarm_duration:.3f}s"
                                )
                            else:
                                # Tool list will be fetched on first use (cached by cache_tools_list=True)
                                logger.debug(f"[MCP] {self.name} will fetch tool list on first use (cached thereafter)")
                        except Exception as e:
                            # Non-critical - tool list will be fetched on first use anyway
                            logger.debug(
                                f"[MCP] {self.name} tool list pre-warming skipped "
                                f"(will fetch on first use): {e}"
                            )
                    
                    # Pre-warm tools in background (non-blocking)
                    # This happens after connection is established but before first query
                    self.loop.create_task(_prewarm_tools())
                    
                    self._connection_event.set()  # Signal connection ready
                    
                    # Keep connection alive with a periodic task
                    async def _keep_alive():
                        while True:
                            await asyncio.sleep(60)  # Check every minute
                    self.loop.create_task(_keep_alive())
                    self.loop.run_forever()
                except Exception as e:
                    self._connection_error = str(e)
                    self._connection_event.set()  # Signal even on error
                    logger.error(f"[MCP] Server connection failed: {e}", exc_info=True)
            
            import time
            self._connection_start_time = time.time()
            self.thread = threading.Thread(target=_run_server, daemon=True)
            self.thread.start()
            
            # Wait for initialization (up to 10 seconds)
            if self._connection_event.wait(timeout=10.0):
                # Connection attempt completed (success or failure)
                if self._connection_error:
                    # Connection failed
                    self._initialized = True  # Mark as initialized so we don't retry
                    return None
                # Connection succeeded
                self._initialized = True
                return self.server_obj
            else:
                # Timeout - connection took too long, mark as failed
                if not self._connection_error:
                    # Check if thread is still alive (might have failed silently)
                    if not self.thread.is_alive():
                        self._connection_error = "Connection thread died unexpectedly"
                    else:
                        self._connection_error = (
                            f"Connection timeout after 10 seconds. "
                            f"Is {self.name} running on port {port}? Start it with:\n{self.start_hint}"
                        )
                self._initialized = True  # Mark as initialized to prevent retries
                return None
            
        except ImportError:
            self._connection_error = "MCP library not available"
            return None
        except Exception as e:
            self._connection_error = str(e)
            return None
    
    def get_server(self) -> Optional[Any]:
        """Get the MCP server object."""
        return self.server_obj
    
    def is_enabled(self) -> bool:
        """Return True if this server is enabled via environment variables."""
        use_flag = f"{self.env_prefix}_USE_SERVER"
        return os.getenv(use_flag, "false").lower() in ("true", "1", "yes")
    
    def get_status(self) -> str:
        """Get connection status string."""
        import time
        
        if self._connection_error:
            return "🔴 Failed"
        elif self.server_obj is not None:
            return "🟢 Enabled"
        elif self._initialized:
            # Initialized but no server_obj means it failed or timed out
            if self._connection_error:
                return "🔴 Failed"
            # Still connecting but initialized - check if it's been too long
            if self._connection_start_time:
                elapsed = time.time() - self._connection_start_time
                if elapsed > 15.0:  # More than 15 seconds total
                    if not self._connection_error:
                        self._connection_error = "Connection taking too long. Is the MCP server running?"
                    return "🔴 Failed"
            return "🟡 Connecting..."
        else:
            # Not initialized yet - check if thread is running
            if self.thread and self.thread.is_alive():
                # Check how long we've been waiting
                if self._connection_start_time:
                    elapsed = time.time() - self._connection_start_time
                    if elapsed > 15.0:
                        if not self._connection_error:
                            self._connection_error = "Connection taking too long. Is the MCP server running?"
                        self._initialized = True
                        return "🔴 Failed"
                return "🟡 Connecting..."
            else:
                return "🟡 Connecting..."
    
    def test_connection(self) -> tuple[bool, str]:
        """Test MCP connection by attempting to list tools.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.is_enabled():
            return False, "MCP server is not enabled (check environment variables)"
        
        if self._connection_error:
            return False, f"Connection error: {self._connection_error}"
        
        if self.server_obj is None:
            return False, "Server not connected. Status: " + self.get_status()
        
        # Try to list tools as a connection test
        try:
            # Check if we can access the server object
            if hasattr(self.server_obj, 'list_tools'):
                # This is async, but we're in sync context
                # The connection is already established, so just check if object exists
                return True, "✅ Connection successful - server object available"
            elif hasattr(self.server_obj, 'tools'):
                # Access tools property (might trigger fetch)
                tools = getattr(self.server_obj, 'tools', None)
                if tools is not None:
                    tool_count = len(tools) if isinstance(tools, (list, dict)) else "unknown"
                    return True, f"✅ Connection successful - {tool_count} tools available"
                else:
                    return True, "✅ Connection successful - tools property exists"
            else:
                return True, "✅ Connection successful - server object exists"
        except Exception as e:
            return False, f"❌ Connection test failed: {str(e)}"


def _get_mcp_servers() -> Dict[str, Any]:
    """Get or create MCP server connections keyed by server name."""
    global _mcp_server_managers
    
    with _mcp_server_lock:
        if not _mcp_server_managers:
            _mcp_server_managers = {
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
        
        connections: Dict[str, Any] = {}
        for name, manager in _mcp_server_managers.items():
            server = manager.initialize()
            if server is not None:
                connections[name] = server
        return connections


def _default_api_base_url() -> str:
    """Resolve the default API base URL from secrets or environment."""
    base = os.getenv("AI_TUTOR_API_BASE") or os.getenv("API_BASE_URL") or "http://localhost:8000"
    try:
        base = st.secrets.get("API_BASE_URL", base)
    except StreamlitSecretNotFoundError:
        pass
    return base


@st.cache_resource(show_spinner=False)
def load_session_client(api_base_url: str, learner_id: str) -> SessionClient:
    """Create an HTTP SessionClient for the given learner."""
    return SessionClient(api_base_url=api_base_url, session_id=learner_id)


@st.cache_resource(show_spinner=False)
def load_visualization_agent(_api_key: Optional[str]) -> VisualizationAgent:
    """Initialize visualization agent with cached settings."""
    settings = load_settings()
    llm_client = LLMClient(config=settings.model)
    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    return VisualizationAgent(llm_client, upload_dir)


def _ensure_generated_files_state() -> None:
    """Initialize generated files tracking in session state."""
    if "generated_files" not in st.session_state:
        st.session_state.generated_files = []
    if "generated_files_preview_id" not in st.session_state:
        st.session_state.generated_files_preview_id = None


def _add_generated_file(
    name: str,
    content: Any,
    *,
    kind: str,
    mime: str,
    binary: bool,
    language: Optional[str] = None,
    set_preview: bool = True,
    auto_save: bool = True,
) -> None:
    """
    Register a newly generated file in session state and optionally save to disk.
    
    Args:
        name: Filename
        content: File content (bytes for binary, str for text)
        kind: File type ("image", "code", "text")
        mime: MIME type
        binary: Whether content is binary
        language: Programming language (for code files)
        set_preview: Whether to set this file as the preview
        auto_save: Whether to automatically save to disk (default: True)
    """
    _ensure_generated_files_state()
    
    # Determine save directory based on file kind
    kind_to_dir = {
        "image": "visualizations",
        "code": "code",
        "text": "quizzes",  # Quiz markdown files
    }
    save_subdir = kind_to_dir.get(kind, "other")
    
    # Auto-save to disk if enabled
    file_path = None
    if auto_save:
        try:
            # Create organized directory structure: data/generated/{kind}/
            base_dir = Path("data/generated") / save_subdir
            base_dir.mkdir(parents=True, exist_ok=True)
            
            # Save file
            file_path = base_dir / name
            if binary:
                if isinstance(content, str):
                    # If binary flag is set but content is string, encode it
                    content = content.encode("utf-8")
                file_path.write_bytes(content)
            else:
                # Text file
                text_content = content if isinstance(content, str) else str(content)
                file_path.write_text(text_content, encoding="utf-8")
            
            logger.info(f"Auto-saved generated file: {file_path} ({kind}, {len(content) if binary else len(str(content))} bytes)")
        except Exception as e:
            logger.error(f"Failed to auto-save generated file {name}: {e}", exc_info=True)
            # Continue even if save fails - file is still in session state
    
    # Register in session state
    file_entry = {
        "id": str(uuid.uuid4()),
        "name": name,
        "kind": kind,
        "mime": mime,
        "content": content,
        "binary": binary,
        "language": language,
        "selected": True,
        "deleted": False,
        "created_at": datetime.utcnow().isoformat(),
        "file_path": str(file_path) if file_path else None,  # Store disk path
    }
    st.session_state.generated_files.append(file_entry)
    if set_preview:
        st.session_state.generated_files_preview_id = file_entry["id"]


def _messages_from_history(history: SessionHistoryResponse) -> List[Dict[str, Any]]:
    """Convert session history into chat messages for display."""
    messages: List[Dict[str, Any]] = []
    responses = history.responses
    for idx, event in enumerate(history.events):
        if event.type != "upload":
            user_text = event.content or f"{event.type.title()} request"
            messages.append({"role": "user", "content": user_text})
        if idx < len(responses):
            resp = responses[idx]
            content = resp.answer or f"{resp.route.title()} update"
            messages.append(
                {
                    "role": "assistant",
                    "content": content,
                    "citations": resp.citations,
                    "route": resp.route,
                }
            )
    return messages


def _update_file_on_disk(file: Dict[str, Any], new_content: Any) -> None:
    """Update a file's content on disk if it exists."""
    file_path = file.get("file_path")
    if file_path and Path(file_path).exists():
        try:
            if file.get("binary", False):
                # Binary file
                if isinstance(new_content, str):
                    new_content = new_content.encode("utf-8")
                Path(file_path).write_bytes(new_content)
            else:
                # Text file
                text_content = new_content if isinstance(new_content, str) else str(new_content)
                Path(file_path).write_text(text_content, encoding="utf-8")
            logger.info(f"Updated file on disk: {file_path}")
        except Exception as e:
            logger.error(f"Failed to update file on disk {file_path}: {e}", exc_info=True)


def _visible_generated_files() -> List[Dict[str, Any]]:
    """Return non-deleted generated files."""
    _ensure_generated_files_state()
    return [file for file in st.session_state.generated_files if not file.get("deleted")]


def _build_zip_archive(files: List[Dict[str, Any]]) -> bytes:
    """Create a ZIP archive containing the provided files."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for file in files:
            data = file["content"]
            if not file.get("binary", False):
                if isinstance(data, str):
                    data = data.encode("utf-8")
                else:
                    data = str(data).encode("utf-8")
            zf.writestr(file["name"], data)
    buffer.seek(0)
    return buffer.getvalue()


def render_generated_files_manager() -> None:
    """Render the generated files manager UI components."""
    _ensure_generated_files_state()
    visible_files = _visible_generated_files()

    if not visible_files:
        st.caption("No generated files yet. Visualizations and other outputs will appear here.")
        return

    valid_ids = {file["id"] for file in visible_files}
    preview_id = st.session_state.get("generated_files_preview_id")
    if preview_id not in valid_ids:
        st.session_state.generated_files_preview_id = next(iter(valid_ids), None)

    for file in visible_files:
        cols = st.columns([0.55, 0.15, 0.15, 0.15], gap="small")
        new_name = cols[0].text_input(
            "Filename",
            value=file["name"],
            key=f"generated_file_name_{file['id']}",
            label_visibility="collapsed",
        )
        if new_name and new_name != file["name"]:
            # Rename on disk if file exists
            old_file_path = file.get("file_path")
            if old_file_path and Path(old_file_path).exists():
                try:
                    # Determine new path based on file kind
                    kind_to_dir = {
                        "image": "visualizations",
                        "code": "code",
                        "text": "quizzes",
                    }
                    save_subdir = kind_to_dir.get(file["kind"], "other")
                    base_dir = Path("data/generated") / save_subdir
                    new_file_path = base_dir / new_name
                    
                    # Rename file on disk
                    Path(old_file_path).rename(new_file_path)
                    file["file_path"] = str(new_file_path)
                    logger.info(f"Renamed file on disk: {old_file_path} -> {new_file_path}")
                except Exception as e:
                    logger.error(f"Failed to rename file on disk: {e}", exc_info=True)
            file["name"] = new_name

        data = file["content"]
        if file.get("binary", False):
            download_data = data
        else:
            download_data = data if isinstance(data, str) else str(data)
        cols[1].download_button(
            "⬇️",
            data=download_data,
            file_name=file["name"],
            mime=file["mime"],
            key=f"generated_file_download_{file['id']}",
            use_container_width=True,
            help="Download this file",
        )

        if cols[2].button("👁️", key=f"generated_file_preview_{file['id']}", help="Preview this file"):
            st.session_state.generated_files_preview_id = file["id"]

        if cols[3].button("🗑️", key=f"generated_file_delete_{file['id']}", help="Remove this file from the list"):
            # Delete from disk if file exists
            file_path = file.get("file_path")
            if file_path and Path(file_path).exists():
                try:
                    Path(file_path).unlink()
                    logger.info(f"Deleted file from disk: {file_path}")
                except Exception as e:
                    logger.error(f"Failed to delete file from disk: {e}", exc_info=True)
            
            file["deleted"] = True
            if st.session_state.generated_files_preview_id == file["id"]:
                st.session_state.generated_files_preview_id = None
            st.rerun()

        size_bytes = len(file["content"]) if file.get("binary") else len(str(file["content"]).encode("utf-8"))
        size_kb = size_bytes / 1024
        
        # Show file info with disk path if available
        file_path = file.get("file_path")
        if file_path:
            # Show relative path for cleaner display
            try:
                rel_path = Path(file_path).relative_to(Path.cwd())
                st.caption(f"{file['kind'].title()} • {size_kb:.1f} KB • 💾 {rel_path}")
            except ValueError:
                # If relative path fails, show full path
                st.caption(f"{file['kind'].title()} • {size_kb:.1f} KB • 💾 {file_path}")
        else:
            st.caption(f"{file['kind'].title()} • {size_kb:.1f} KB • ⚠️ Not saved to disk")

    st.markdown("---")

    if visible_files:
        all_zip = _build_zip_archive(visible_files)
        st.download_button(
            "📦 Download All (ZIP)",
            data=all_zip,
            file_name="generated_all.zip",
            mime="application/zip",
            key="download_all_generated_files",
            use_container_width=True,
        )

    preview_file = next(
        (file for file in visible_files if file["id"] == st.session_state.generated_files_preview_id),
        None,
    )
    if preview_file:
        st.markdown("---")
        st.markdown(f"**Preview: {preview_file['name']}**")
        if preview_file["kind"] == "image":
            st.image(preview_file["content"], use_container_width=True)
        elif preview_file["kind"] == "code":
            st.code(preview_file["content"], language=preview_file.get("language", "text"))
        else:
            st.write(preview_file["content"])


 


 


 


 


def is_visualization_request(text: str) -> bool:
    """
    Detect if the user is asking for data visualization.
    
    Parameters
    ----------
    text : str
        User's message
    
    Returns
    -------
    bool
        True if request involves creating a plot/chart/graph
    """
    viz_keywords = [
        "plot", "chart", "graph", "visualize", "visualization", 
        "histogram", "scatter", "bar chart", "line chart", 
        "pie chart", "heatmap", "box plot", "show me a", "draw"
    ]
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in viz_keywords)


 


 


 


 


def render() -> None:
    st.set_page_config(page_title="AI Tutor", page_icon="🎓", layout="wide")
    st.title("🎓 AI Tutor Demo")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets["OPENAI_API_KEY"]
        except (KeyError, StreamlitSecretNotFoundError):
            api_key = None

    if not api_key:
        st.error(
            "OPENAI_API_KEY is not set. Add it to your environment or `.streamlit/secrets.toml` before running the app."
        )
        st.stop()

    viz_agent = load_visualization_agent(api_key)
    
    # Show MCP status if any server is enabled
    enabled_managers = [
        manager for manager in _mcp_server_managers.values() if manager.is_enabled()
    ]
    if enabled_managers:
        with st.sidebar:
            st.subheader("🛠 MCP Servers")
            for manager in enabled_managers:
                status = manager.get_status()
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.caption(f"{manager.name}: {status}")
                with col2:
                    # Test connection button
                    if st.button("Test", key=f"test_{manager.name}", help="Test MCP connection"):
                        success, message = manager.test_connection()
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
                
                if "Failed" in status:
                    if manager._connection_error:
                        st.error(manager._connection_error)
                    st.caption("Start command:")
                    st.code(manager.start_hint, language="bash")
                elif status == "🟢 Enabled":
                    # Show connection test result if available
                    if manager._connection_error:
                        # Show any non-fatal warnings (e.g., earlier timeouts)
                        st.info(manager._connection_error)
                    # Show server info
                    port_env = f"{manager.env_prefix}_PORT"
                    port = int(os.getenv(port_env, os.getenv("MCP_PORT", str(manager.default_port))))
                    st.caption(f"Port: {port}")
    
    # Chat & Learn experience
    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "chat_uploaded_files" not in st.session_state:
        st.session_state.chat_uploaded_files = []
    if "chat_uploaded_filenames" not in st.session_state:
        st.session_state.chat_uploaded_filenames = []  # Track ingested filenames
    if "chat_upload_processing_done" not in st.session_state:
        st.session_state.chat_upload_processing_done = False
    if "chat_files_just_ingested" not in st.session_state:
        st.session_state.chat_files_just_ingested = False
    if "quiz" not in st.session_state:
        st.session_state.quiz = None
    if "quiz_answers" not in st.session_state:
        st.session_state.quiz_answers = {}
    if "quiz_result" not in st.session_state:
        st.session_state.quiz_result = None
    # Visualization state
    if "uploaded_csv" not in st.session_state:
        st.session_state.uploaded_csv = None
    if "csv_filename" not in st.session_state:
        st.session_state.csv_filename = None
    _ensure_generated_files_state()

    session_client: SessionClient | None = None
    with st.sidebar:
        st.header("Session Settings")
        default_api_base = st.session_state.get("api_base_url", _default_api_base_url())
        api_base_url = st.text_input("API Base URL", value=default_api_base)
        st.session_state.api_base_url = api_base_url
        learner_id = st.text_input(
            "Learner ID",
            value=st.session_state.get("learner_id_global", "s1"),
        )
        st.session_state.learner_id_global = learner_id
        if api_base_url:
            try:
                session_client = load_session_client(api_base_url, learner_id)
            except Exception as exc:
                st.error(f"Failed to initialize session client: {exc}")
                session_client = None
        else:
            st.warning("Provide an API base URL to connect to the tutor backend.")
            session_client = None

        st.subheader("📤 Upload Documents")
        st.caption("Upload documents for Q&A and quiz generation. They will be automatically ingested when you ask questions.")
        
        uploaded_files = st.file_uploader(
            "Add PDFs, Markdown, or TXT files",
            type=["pdf", "txt", "md"],
            accept_multiple_files=True,
            key="chat_file_uploader"
        )
        
        # Update session state when files are uploaded
        if uploaded_files:
            # Check if these are new files (different from what's already stored)
            if not st.session_state.chat_uploaded_files or \
               len(uploaded_files) != len(st.session_state.chat_uploaded_files) or \
               any(new.name != old.name for new, old in zip(uploaded_files, st.session_state.chat_uploaded_files)):
                # New files uploaded - reset ingestion flag
                st.session_state.chat_uploaded_files = uploaded_files
                st.session_state.chat_uploaded_filenames = []
                st.session_state.chat_upload_processing_done = False
                st.session_state.chat_files_just_ingested = False
        else:
            # No files in uploader - clear session state
            if st.session_state.chat_uploaded_files:
                st.session_state.chat_uploaded_files = []
                st.session_state.chat_uploaded_filenames = []
                st.session_state.chat_upload_processing_done = False
                st.session_state.chat_files_just_ingested = False
        
        # Show status
        if st.session_state.chat_uploaded_files:
            st.success(f"✅ {len(st.session_state.chat_uploaded_files)} file(s) uploaded!")
            
            with st.expander("View uploaded files"):
                for file in st.session_state.chat_uploaded_files:
                    file_size_mb = len(file.getvalue()) / (1024 * 1024)
                    st.write(f"• {file.name} ({file_size_mb:.2f} MB)")
        
        st.subheader("🗂️ Generated Files")
        with st.expander("Manage generated files", expanded=False):
            render_generated_files_manager()
        st.divider()
        
        # CSV Upload for Visualization
        st.subheader("📊 Data Visualization")
        st.caption("Upload a CSV file to create plots and charts")
        
        uploaded_csv = st.file_uploader(
            "Upload CSV file",
            type=["csv"],
            key="csv_uploader",
            help="Upload a CSV file and then ask to plot/visualize the data"
        )
        
        if uploaded_csv:
            # Save CSV to uploads directory
            upload_dir = Path("data/uploads")
            upload_dir.mkdir(parents=True, exist_ok=True)
            csv_path = upload_dir / uploaded_csv.name
            csv_path.write_bytes(uploaded_csv.getvalue())
            
            st.session_state.uploaded_csv = csv_path
            st.session_state.csv_filename = uploaded_csv.name
            st.success(f"✅ Uploaded: {uploaded_csv.name}")
            
            # Show preview
            with st.expander("Preview data"):
                import pandas as pd
                df = pd.read_csv(csv_path)
                st.write(f"**Shape:** {df.shape[0]} rows × {df.shape[1]} columns")
                st.write(f"**Columns:** {', '.join(df.columns.tolist())}")
                st.dataframe(df.head(5), use_container_width=True)
        elif st.session_state.csv_filename:
            st.info(f"📁 Current file: {st.session_state.csv_filename}")
            if st.button("🗑️ Clear CSV"):
                st.session_state.uploaded_csv = None
                st.session_state.csv_filename = None
                st.rerun()
        
        st.divider()
        
        if session_client is None:
            st.error("Session API client is unavailable. Check the base URL and try again.")
            st.stop()
        
        history = None
        if session_client:
            try:
                history = session_client.get_history()
            except Exception as exc:
                history = None
                logger.warning("Failed to fetch session history: %s", exc)
        if history:
            st.session_state.messages = _messages_from_history(history)
        
        for message in st.session_state.messages:
            role = message["role"]
            with st.chat_message(role):
                content = str(message.get("content", ""))
                if role == "assistant":
                    # Check if this is a visualization message
                    if message.get("image_base64"):
                        st.markdown(content)
                        img_data = base64.b64decode(message["image_base64"])
                        st.image(img_data, use_container_width=True)
                        if message.get("code"):
                            with st.expander("📝 View generated code"):
                                st.code(message["code"], language="python")
                    else:
                        st.markdown(format_answer(content))
                        citations = message.get("citations")
                        if isinstance(citations, (list, tuple)) and citations:
                            st.markdown("**Citations:**")
                            for cite in citations:
                                st.markdown(f"- {cite}")
                else:
                    st.markdown(content)

        prompt = st.chat_input("Ask the tutor a question...")
        if prompt:
            # Prepare uploaded files before answering
            ingestion_happened = False
            ingestion_result = None
            if st.session_state.chat_uploaded_files and not st.session_state.chat_upload_processing_done:
                with st.spinner("Uploading documents..."):
                    try:
                        ingested_filenames, ingestion_result = _prepare_uploaded_files(
                            st.session_state.chat_uploaded_files,
                            session_client,
                        )
                    except Exception as exc:
                        st.error(f"❌ Failed to process uploaded files: {exc}")
                        logger.exception("Error preparing uploaded files")
                        st.stop()

                st.session_state.chat_uploaded_filenames = ingested_filenames
                st.session_state.chat_upload_processing_done = True
                ingestion_happened = bool(ingested_filenames)
                st.session_state.chat_files_just_ingested = ingestion_happened
                if ingestion_happened and session_client:
                    try:
                        session_client.post_event(
                            event_type="upload",
                            file_ids=ingested_filenames,
                        )
                    except Exception as exc:
                        logger.warning("Failed to record upload event: %s", exc)
            
            # Now add user message to history
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # If ingestion just happened, show a system message about it
            if ingestion_happened and ingestion_result:
                with st.chat_message("assistant"):
                    doc_count = ingestion_result.get("document_count", 0)
                    chunk_count = ingestion_result.get("chunk_count", 0)
                    st.success(
                        f"✅ Ingested {doc_count} document(s) into "
                        f"{chunk_count} chunks! Now answering your question..."
                    )

            doc_hints = extract_document_hints(
                prompt,
                st.session_state.chat_uploaded_filenames or [],
            )
            documents_only = bool(doc_hints and is_question_about_uploaded_docs(prompt))
            
            # Check if this is a visualization request
            is_viz_request = is_visualization_request(prompt) and st.session_state.csv_filename
            
            if is_viz_request:
                st.warning("Visualization handling currently bypasses session API. TODO: convert to session events.")
            else:
                if not ingestion_happened:
                    with st.chat_message("user"):
                        st.markdown(prompt)
            
            with st.chat_message("assistant"):
                placeholder = st.empty()
                citations_container = st.empty()
                
                with st.spinner("Thinking..."):
                    try:
                        event_type = "message"
                        quiz_topic = None
                        quiz_count = None
                        if "quiz" in prompt.lower():
                            event_type = "quiz"
                            quiz_topic = prompt
                            quiz_count = 5

                        session_response = session_client.post_event(
                            event_type=event_type,
                            content=prompt,
                            quiz_topic=quiz_topic,
                            quiz_count=quiz_count,
                            source_hints=doc_hints or None,
                            documents_only=documents_only,
                        )
                    except Exception as e:
                        error_msg = str(e)
                        st.error(f"❌ Error generating answer: {error_msg}")
                        logger.exception("Error in answer_question")
                        session_response = SessionResponse(
                            session_id=learner_id,
                            turn_id=0,
                            route="error",
                            answer=f"I encountered an error: {error_msg}",
                            citations=[],
                            source="error",
                            quiz=None,
                            metadata={},
                        )
                
                if session_response.answer:
                    placeholder.markdown(format_answer(session_response.answer))
                else:
                    placeholder.error("No answer was generated. Please try again.")
                    
                if session_response.citations:
                    citations_container.markdown(
                        "**Citations:**\n" + "\n".join(f"- {c}" for c in session_response.citations)
                    )
                else:
                    citations_container.caption("No citations provided.")

                if session_response.quiz:
                    quiz_model = Quiz.model_validate(session_response.quiz)
                    st.session_state.quiz = quiz_model.model_dump(mode="json")
                    st.session_state.quiz_markdown = session_response.quiz_markdown
                    st.session_state.quiz_answers = {}
                    st.session_state.quiz_result = None
                    if session_response.quiz_markdown:
                        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                        _add_generated_file(
                            name=f"quiz_{quiz_model.topic.replace(' ', '_')}_{timestamp}.md",
                            content=session_response.quiz_markdown,
                            kind="text",
                            mime="text/markdown",
                            binary=False,
                            language="markdown",
                            set_preview=False,
                        )

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": session_response.answer,
                        "citations": session_response.citations,
                        "route": session_response.route,
                    }
                )

                st.rerun()

        if st.session_state.quiz:
            quiz = Quiz.model_validate(st.session_state.quiz)
            st.divider()
            
            # Header with close button
            col_header, col_close = st.columns([5, 1])
            with col_header:
                st.subheader(f"📝 Quiz: {quiz.topic} ({quiz.difficulty.title()})")
            with col_close:
                if st.button("❌ Close", use_container_width=True, key="close_quiz_top"):
                    st.session_state.quiz = None
                    st.session_state.quiz_answers = {}
                    st.session_state.quiz_result = None
                    if "quiz_markdown" in st.session_state:
                        del st.session_state.quiz_markdown
                    if "quiz_edit_mode" in st.session_state:
                        del st.session_state.quiz_edit_mode
                    st.rerun()
            
            st.caption("Select answers for each question and submit when ready.")

            # Use columns to reduce layout recalculations
            with st.container():
                for idx, question in enumerate(quiz.questions):
                    # Pre-compute display options to avoid recalculation
                    if f"quiz_options_{idx}" not in st.session_state:
                        answer_choices = [f"{chr(65 + opt)}. {text}" for opt, text in enumerate(question.choices)]
                        st.session_state[f"quiz_options_{idx}"] = ["Not answered"] + answer_choices
                    
                    display_options = st.session_state[f"quiz_options_{idx}"]
                    current = st.session_state.quiz_answers.get(idx, -1)
                    
                    selection = st.radio(
                        f"Q{idx + 1}. {question.question}",
                        options=display_options,
                        index=current + 1 if current >= 0 else 0,
                        key=f"quiz_q_{idx}",
                        horizontal=False,  # Display each option on a new line
                    )
                    # Update session state from selection
                    selected_index = display_options.index(selection) - 1
                    if selected_index >= 0:
                        st.session_state.quiz_answers[idx] = selected_index
                    st.markdown("---")

            col_submit, col_edit_download = st.columns([2, 1])
            with col_submit:
                if st.button("Submit Quiz", type="primary", use_container_width=True):
                    answers = [st.session_state.quiz_answers.get(idx, -1) for idx in range(len(quiz.questions))]
                    if any(choice < 0 or choice > 3 for choice in answers):
                        st.warning("Answer every question before submitting.")
                    else:
                        try:
                            session_response = session_client.submit_quiz(
                                quiz_payload=quiz.model_dump(mode="json"),
                                answers=answers,
                            )
                        except Exception as exc:
                            st.error(f"Failed to submit quiz: {exc}")
                            logger.exception("Quiz submission failed")
                        else:
                            evaluation_data = session_response.metadata.get("evaluation", {})
                            evaluation = QuizEvaluation.model_validate(evaluation_data)
                            st.session_state.quiz_result = evaluation.model_dump(mode="json")
                            st.session_state.quiz_completed = quiz.model_dump(mode="json")
                            st.session_state.quiz = None
                            st.session_state.quiz_answers = {}
                            st.session_state.quiz_markdown = session_response.quiz_markdown
                            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                            if session_response.quiz_markdown:
                                _add_generated_file(
                                    name=f"quiz_{quiz.topic.replace(' ', '_')}_{timestamp}.md",
                                    content=session_response.quiz_markdown,
                                    kind="text",
                                    mime="text/markdown",
                                    binary=False,
                                    language="markdown",
                                    set_preview=False,
                                )
                            st.session_state.quiz_edit_mode = False
                            st.success(
                                f"Quiz scored {evaluation.correct_count}/{evaluation.total_questions} "
                                f"({evaluation.score * 100:.0f}%)."
                            )
                            st.rerun()
            
            with col_edit_download:
                # Initialize session state for pre-submit edit mode
                if "pre_submit_edit_mode" not in st.session_state:
                    st.session_state.pre_submit_edit_mode = False
                
                # Toggle edit/download mode
                if st.button("✏️ Edit & Download", use_container_width=True, key="student_pre_submit_edit_toggle"):
                    st.session_state.pre_submit_edit_mode = not st.session_state.pre_submit_edit_mode
                    if st.session_state.pre_submit_edit_mode:
                        # Initialize markdown when entering edit mode
                        st.session_state.pre_submit_quiz_markdown = quiz_to_markdown(quiz)
                    st.rerun()
            
            # Show edit/download interface if enabled
            if st.session_state.get("pre_submit_edit_mode", False):
                st.divider()
                st.markdown("### ✏️ Edit Quiz")
                st.caption("Edit the quiz content below and download when ready.")
                
                edited_quiz = st.text_area(
                    "Quiz Content (Markdown)",
                    value=st.session_state.get("pre_submit_quiz_markdown", quiz_to_markdown(quiz)),
                    height=300,
                    key="pre_submit_quiz_editor"
                )
                st.session_state.pre_submit_quiz_markdown = edited_quiz
                current_file_prefix = f"quiz_{quiz.topic.replace(' ', '_')}_"
                for file in st.session_state.generated_files:
                    if file.get("deleted"):
                        continue
                    if (
                        file.get("kind") == "text"
                        and file.get("language") == "markdown"
                        and file.get("name", "").startswith(current_file_prefix)
                    ):
                        file["content"] = edited_quiz
                        # Update file on disk
                        _update_file_on_disk(file, edited_quiz)
                
                col_download, col_close = st.columns([1, 1])
                with col_download:
                    st.download_button(
                        label="💾 Download Quiz",
                        data=edited_quiz,
                        file_name=f"quiz_{quiz.topic.replace(' ', '_')}.md",
                        mime="text/markdown",
                        use_container_width=True,
                        key="student_download_edited_quiz"
                    )
                with col_close:
                    if st.button("✓ Done", use_container_width=True, key="student_close_edit"):
                        st.session_state.pre_submit_edit_mode = False
                        st.rerun()

        if st.session_state.quiz_result:
            result = QuizEvaluation.model_validate(st.session_state.quiz_result)
            st.divider()
            st.subheader("📊 Quiz Results")
            
            st.write(
                f"Score: **{result.correct_count}/{result.total_questions}** "
                f"({result.score * 100:.0f}%)."
            )
            
            if result.review_topics:
                st.info("💡 Suggested practice:")
                for topic in result.review_topics:
                    st.write(f"- {topic}")
            
            with st.expander("📝 Question breakdown", expanded=False):
                for answer in result.answers:
                    label = "✅ Correct" if answer.is_correct else "❌ Incorrect"
                    st.markdown(f"**Q{answer.index + 1}: {label}**")
                    if answer.explanation:
                        st.caption(answer.explanation)
                    if answer.references:
                        st.caption("References: " + "; ".join(answer.references))
            
            # Edit and Download Section
            st.divider()
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                if "quiz_edit_mode" not in st.session_state:
                    st.session_state.quiz_edit_mode = False
                
                if st.button("✏️ Edit Quiz" if not st.session_state.quiz_edit_mode else "👁️ Preview Quiz", 
                            use_container_width=True):
                    st.session_state.quiz_edit_mode = not st.session_state.quiz_edit_mode
                    st.rerun()
            
            with col2:
                if "quiz_markdown" in st.session_state:
                    st.download_button(
                        label="💾 Download Quiz (MD)",
                        data=st.session_state.quiz_markdown,
                        file_name=f"quiz_{Quiz.model_validate(st.session_state.quiz_completed).topic.replace(' ', '_')}.md",
                        mime="text/markdown",
                        use_container_width=True
                    )
            
            with col3:
                if st.button("❌ Close Quiz", use_container_width=True):
                    st.session_state.quiz_result = None
                    if "quiz_completed" in st.session_state:
                        del st.session_state.quiz_completed
                    if "quiz_markdown" in st.session_state:
                        del st.session_state.quiz_markdown
                    if "quiz_edit_mode" in st.session_state:
                        del st.session_state.quiz_edit_mode
                    st.rerun()
            
            # Show edit or preview mode
            if st.session_state.get("quiz_edit_mode", False):
                st.markdown("### ✏️ Edit Quiz Markdown")
                if "quiz_markdown" in st.session_state:
                    edited_markdown = st.text_area(
                        "Quiz Content",
                        value=st.session_state.quiz_markdown,
                        height=400,
                        key="quiz_markdown_editor"
                    )
                    if edited_markdown != st.session_state.quiz_markdown:
                        st.session_state.quiz_markdown = edited_markdown
                        # Update corresponding file in generated_files and on disk
                        quiz_topic = Quiz.model_validate(st.session_state.quiz_completed).topic.replace(' ', '_')
                        current_file_prefix = f"quiz_{quiz_topic}_"
                        for file in st.session_state.generated_files:
                            if file.get("deleted"):
                                continue
                            if (
                                file.get("kind") == "text"
                                and file.get("language") == "markdown"
                                and file.get("name", "").startswith(current_file_prefix)
                            ):
                                file["content"] = edited_markdown
                                # Update file on disk
                                _update_file_on_disk(file, edited_markdown)
                                break
            else:
                st.markdown("### 👁️ Quiz Preview")
                if "quiz_markdown" in st.session_state:
                    with st.container(border=True):
                        st.markdown(st.session_state.quiz_markdown)
        


__all__ = [
    "extract_text",
    "summarize_documents",
    "format_answer",
    "format_quiz_context",
    "is_question_about_uploaded_docs",
    "filter_hits_by_filenames",
    
    
    "render",
]


if __name__ == "__main__":
    render()
