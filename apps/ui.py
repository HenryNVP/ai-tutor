"""Streamlit-based UI for the AI tutor."""

from __future__ import annotations

import io
import logging
import os
import re
import sys
import tempfile
import shutil
import base64
import asyncio
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from collections import Counter

logger = logging.getLogger(__name__)

# Add project root to Python path for absolute imports
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st
from streamlit.runtime.secrets import StreamlitSecretNotFoundError

from ai_tutor.system import TutorSystem
from ai_tutor.services.tutor_service import TutorService
from apps.chat_helpers import (
    format_answer,
    is_question_about_uploaded_docs,
    filter_hits_by_filenames,
)
from apps.corpus_tab import render_corpus_management_tab
from apps.file_utils import extract_text, summarize_documents
from ai_tutor.learning.quiz import Quiz, QuizEvaluation
from ai_tutor.agents.visualization import VisualizationAgent
from ai_tutor.agents.llm_client import LLMClient
from ai_tutor.config.loader import load_settings

try:  # pragma: no cover - optional dependency
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None  # type: ignore[assignment]


# Global MCP server manager
_mcp_server_manager = None
_mcp_server_lock = threading.Lock()


class MCPServerManager:
    """Manages MCP server lifecycle in a background thread for Streamlit.
    
    This class ensures:
    - MCP server connection is initialized once and reused across all queries
    - Tool list is cached to avoid redundant API calls
    - Event loop stays non-blocking with async operations
    """
    
    def __init__(self):
        self.server = None
        self.server_obj = None
        self.loop = None
        self.thread = None
        self._initialized = False
        self._connection_error = None  # Track connection errors
        self._connection_event = threading.Event()  # Signal when connection is ready
        self._connection_start_time = None  # Track when connection attempt started
    
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
        
        use_mcp = os.getenv("MCP_USE_SERVER", "false").lower() in ("true", "1", "yes")
        if not use_mcp:
            return None
        
        try:
            from agents.mcp import MCPServerStreamableHttp
            import requests
            
            port = int(os.getenv("MCP_PORT", "8000"))
            server_url = f"http://localhost:{port}/mcp"
            
            # Check if server is reachable before attempting connection
            # Note: Root URL returns 404, but /mcp endpoint exists (requires SSE format)
            try:
                # Try to reach the server (any response means it's running)
                # We check root because /mcp requires specific headers
                base_url = f"http://localhost:{port}"
                response = requests.get(base_url, timeout=2)
                # Any HTTP response (even 404) means server is running
                logger.debug(f"[MCP] Server check: {response.status_code} from {base_url} (server is running)")
            except requests.exceptions.ConnectionError:
                self._connection_error = f"MCP server not running on port {port}. Start it with: cd chroma_data/chroma_example && python server.py"
                logger.warning(f"[MCP] Connection refused on port {port} - server not running")
                return None
            except requests.exceptions.Timeout:
                self._connection_error = f"MCP server timeout on port {port}"
                logger.warning(f"[MCP] Timeout connecting to port {port}")
                return None
            except Exception as e:
                # Other errors might be OK (server might be running but endpoint different)
                logger.debug(f"[MCP] Server check exception (may be OK): {e}")
                pass
            
            streamable_params = {
                "url": server_url,
                "timeout": int(os.getenv("MCP_TIMEOUT", "10")),
            }
            
            mcp_token = os.getenv("MCP_SERVER_TOKEN")
            if mcp_token:
                streamable_params["headers"] = {"Authorization": f"Bearer {mcp_token}"}
            
            self.server = MCPServerStreamableHttp(
                name="Chroma MCP Server",
                params=streamable_params,
                cache_tools_list=True,  # CRITICAL: Cache tool list to prevent redundant tools/list calls
                max_retry_attempts=3,
                # Add timeout to prevent hanging
                client_session_timeout_seconds=int(os.getenv("MCP_TIMEOUT", "10")),
            )
            logger.info("[MCP] MCP server configured with tool list caching and timeout enabled")
            
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
                    logger.info("[MCP] Successfully connected to MCP server")
                    
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
                                logger.info(f"[MCP] Pre-warmed tool list: {len(tools) if tools else 0} tools cached in {prewarm_duration:.3f}s")
                            elif hasattr(self.server_obj, 'tools'):
                                # Access tools property to trigger fetch
                                tools = self.server_obj.tools
                                prewarm_duration = time.time() - prewarm_start
                                logger.info(f"[MCP] Pre-warmed tool list via property: {len(tools) if tools else 0} tools cached in {prewarm_duration:.3f}s")
                            elif hasattr(self.server, 'list_tools'):
                                # Try on the server object itself
                                tools = await self.server.list_tools()
                                prewarm_duration = time.time() - prewarm_start
                                logger.info(f"[MCP] Pre-warmed tool list via server: {len(tools) if tools else 0} tools cached in {prewarm_duration:.3f}s")
                            else:
                                # Tool list will be fetched on first use (cached by cache_tools_list=True)
                                logger.debug("[MCP] Tool list will be fetched on first use (will be cached)")
                        except Exception as e:
                            # Non-critical - tool list will be fetched on first use anyway
                            logger.debug(f"[MCP] Tool list pre-warming skipped (will fetch on first use): {e}")
                    
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
                        self._connection_error = f"Connection timeout after 10 seconds. Is the MCP server running on port {port}? Start it with: cd chroma_data/chroma_example && python server.py"
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


def _get_mcp_server() -> Optional[Any]:
    """Get or create MCP server connection."""
    global _mcp_server_manager
    
    with _mcp_server_lock:
        if _mcp_server_manager is None:
            _mcp_server_manager = MCPServerManager()
        
        return _mcp_server_manager.initialize()


@st.cache_resource(show_spinner=False)
def load_system(api_key: Optional[str]) -> TutorSystem:
    """Load TutorSystem with optional MCP server support."""
    mcp_server = _get_mcp_server()
    return TutorSystem.from_config(api_key=api_key, mcp_server=mcp_server)


@st.cache_resource(show_spinner=False)
def load_service(api_key: Optional[str]) -> TutorService:
    """Load TutorService - the clean API layer for UI interactions."""
    system = load_system(api_key)
    return TutorService(system)


@st.cache_resource(show_spinner=False)
def load_visualization_agent(_api_key: Optional[str]) -> VisualizationAgent:
    """Initialize visualization agent with cached settings."""
    settings = load_settings()
    llm_client = LLMClient(config=settings.model)
    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    return VisualizationAgent(llm_client, upload_dir)


 


 


 


 


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

    system = load_system(api_key)  # Keep for corpus management tab
    service = load_service(api_key)  # Use service layer for chat operations
    viz_agent = load_visualization_agent(api_key)
    
    # Show MCP status if enabled
    use_mcp = os.getenv("MCP_USE_SERVER", "false").lower() in ("true", "1", "yes")
    if use_mcp:
        if _mcp_server_manager:
            mcp_status = _mcp_server_manager.get_status()
            if "Failed" in mcp_status:
                with st.sidebar:
                    st.caption(f"MCP Server: {mcp_status}")
                    if _mcp_server_manager._connection_error:
                        st.error(_mcp_server_manager._connection_error)
                    st.caption("To start the MCP server, run in a terminal:")
                    port = os.getenv("MCP_PORT", "8000")
                    st.code(f"cd chroma_data/chroma_example\npython server.py", language="bash")
                    st.caption("Or set MCP_USE_SERVER=false to use direct vector store access.")
            else:
                with st.sidebar:
                    st.caption(f"MCP Server: {mcp_status}")
        else:
            with st.sidebar:
                st.caption("MCP Server: 🟡 Connecting...")
    
    # Create tabs
    tab1, tab2 = st.tabs(["💬 Chat & Learn", "📚 Corpus Management"])

    # Tab 2: Corpus Management
    with tab2:
        render_corpus_management_tab(system)
    
    # Tab 1: Chat & Learn (enhanced with auto-ingestion and quiz preview)
    with tab1:
        # Initialize session state
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "chat_uploaded_files" not in st.session_state:
            st.session_state.chat_uploaded_files = []
        if "chat_uploaded_filenames" not in st.session_state:
            st.session_state.chat_uploaded_filenames = []  # Track filenames for filtering
        if "chat_files_ingested" not in st.session_state:
            st.session_state.chat_files_ingested = False
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

        with st.sidebar:
            st.header("Session Settings")
            learner_id = st.text_input("Learner ID", value="s1")
            st.session_state.learner_id_global = learner_id

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
                    st.session_state.chat_files_ingested = False
            else:
                # No files in uploader - clear session state
                if st.session_state.chat_uploaded_files:
                    st.session_state.chat_uploaded_files = []
                    st.session_state.chat_uploaded_filenames = []
                    st.session_state.chat_files_ingested = False
            
            # Show status
            if st.session_state.chat_uploaded_files:
                if st.session_state.chat_files_ingested:
                    st.success(f"✅ {len(st.session_state.chat_uploaded_files)} file(s) ingested and ready!")
                else:
                    st.info(f"📁 {len(st.session_state.chat_uploaded_files)} file(s) ready. Ask a question to auto-ingest!")
                
                with st.expander("View uploaded files"):
                    for file in st.session_state.chat_uploaded_files:
                        file_size_mb = len(file.getvalue()) / (1024 * 1024)
                        st.write(f"• {file.name} ({file_size_mb:.2f} MB)")
            
            if st.button("🗑️ Clear uploaded documents"):
                st.session_state.chat_uploaded_files = []
                st.session_state.chat_uploaded_filenames = []
                st.session_state.chat_files_ingested = False
                st.rerun()
            
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
            # Check if files need ingestion - do it BEFORE processing the question
            ingestion_happened = False
            if st.session_state.chat_uploaded_files and not st.session_state.chat_files_ingested:
                ingestion_happened = True
                
                # Track filenames for filtering
                uploaded_filenames = [f.name for f in st.session_state.chat_uploaded_files]
                
                # Create temp directory and ingest files
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    
                    # Save uploaded files
                    for uploaded_file in st.session_state.chat_uploaded_files:
                        file_path = temp_path / uploaded_file.name
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getvalue())
                    
                    # Ingest
                    try:
                        result = service.ingest_directory(temp_path)
                        st.session_state.chat_files_ingested = True
                        st.session_state.chat_uploaded_filenames = uploaded_filenames  # Store for filtering
                    except Exception as e:
                        st.error(f"❌ Ingestion failed: {str(e)}")
                        st.stop()
            
            # Now add user message to history
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # If ingestion just happened, show a system message about it
            if ingestion_happened:
                with st.chat_message("user"):
                    st.markdown(prompt)
                with st.chat_message("assistant"):
                    st.success(f"✅ Ingested {len(result.documents)} document(s) into {len(result.chunks)} chunks! Now answering your question...")
            
            # Check if this is a visualization request
            is_viz_request = is_visualization_request(prompt) and st.session_state.csv_filename
            
            if is_viz_request:
                # Handle visualization request
                if not ingestion_happened:
                    with st.chat_message("user"):
                        st.markdown(prompt)
                
                with st.chat_message("assistant"):
                    with st.spinner("Creating visualization..."):
                        try:
                            viz_result = viz_agent.create_visualization(
                                csv_filename=st.session_state.csv_filename,
                                user_request=prompt
                            )
                            
                            if viz_result.get("success"):
                                st.success("✅ Visualization created!")
                                
                                # Display the plot
                                img_data = base64.b64decode(viz_result["image_base64"])
                                st.image(img_data, use_container_width=True)
                                
                                # Show generated code in expander
                                with st.expander("📝 View generated code"):
                                    st.code(viz_result["code"], language="python")
                                
                                # Add to message history with plot data
                                st.session_state.messages.append({
                                    "role": "assistant",
                                    "content": "Here's your visualization:",
                                    "image_base64": viz_result["image_base64"],
                                    "code": viz_result["code"]
                                })
                            else:
                                error_msg = viz_result.get("error", "Unknown error")
                                st.error(f"❌ Failed to create visualization: {error_msg}")
                                st.session_state.messages.append({
                                    "role": "assistant",
                                    "content": f"I encountered an error creating the visualization: {error_msg}"
                                })
                        
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": f"I encountered an error: {str(e)}"
                            })
                
                st.rerun()
            
            # Let agent handle everything - it will use tools as needed
            # Don't append user message again - already appended above
            if not ingestion_happened:
                with st.chat_message("user"):
                    st.markdown(prompt)
            
            with st.chat_message("assistant"):
                placeholder = st.empty()
                citations_container = st.empty()
                
                # Check for quiz context from previous interactions
                if st.session_state.quiz_result:
                    quiz_result = QuizEvaluation.model_validate(st.session_state.quiz_result)
                    quiz_context = service.format_quiz_context(quiz_result)
                else:
                    quiz_context = ""
                
                # Retrieve content from uploaded documents if they exist
                # This provides context for both Q&A and quiz generation
                uploaded_docs_context = None
                if st.session_state.chat_files_ingested and st.session_state.chat_uploaded_filenames:
                    with st.spinner("Retrieving content from your uploaded documents..."):
                        # Build queries from filenames and user prompt
                        queries = []
                        for filename in st.session_state.chat_uploaded_filenames:
                            # Extract meaningful terms from filename
                            query_text = Path(filename).stem.replace('_', ' ').replace('-', ' ')
                            queries.append(query_text)
                            # Also try the full filename without extension
                            queries.append(Path(filename).stem)
                        
                        # Add user's actual query
                        queries.append(prompt)
                        
                        # For newly uploaded files, also try broad subject queries
                        if st.session_state.get('chat_files_just_ingested', False):
                            broad_queries = ["computer science", "engineering", "mathematics", "lecture", "course material"]
                            queries.extend(broad_queries)
                        
                        # Use service layer for retrieval (handles config, filtering, deduplication)
                        filtered_hits = service.retrieve_multiple_queries(
                            queries=queries,
                            filenames=st.session_state.chat_uploaded_filenames,
                            top_k=50
                        )
                        
                        # Show debug info about what we found
                        if filtered_hits:
                            st.caption(f"✅ Found {len(filtered_hits)} passages from your uploaded file(s)")
                        
                        if filtered_hits:
                            # Use service layer for formatting (handles grouping, balancing, citations)
                            context, citations = service.format_context_from_hits(
                                hits=filtered_hits,
                                max_passages=15
                            )
                            
                            # Get document titles for context header
                            from collections import defaultdict
                            hits_by_doc = defaultdict(list)
                            for hit in filtered_hits:
                                doc_title = hit.chunk.metadata.title or "Unknown"
                                hits_by_doc[doc_title].append(hit)
                            
                            doc_titles_str = ", ".join(hits_by_doc.keys())
                            uploaded_docs_context = (
                                f"Content from uploaded documents: {doc_titles_str}\n\n"
                                f"{context}"
                            )
                            st.caption(f"📚 Retrieved {len(citations)} passages from {len(hits_by_doc)} document(s): {', '.join(hits_by_doc.keys())}")
                        else:
                            st.info("ℹ️ No passages found in uploaded documents. Using general knowledge...")
                
                # Check for quiz requests FIRST (before other processing)
                is_quiz_request = service.detect_quiz_request(prompt)
                
                if is_quiz_request:
                    # Handle quiz creation
                    num_questions = service.extract_quiz_num_questions(prompt)
                    topic = service.extract_quiz_topic(prompt)
                    
                    # If quiz is about uploaded documents, use that context
                    effective_topic = topic
                    quiz_context = None
                    
                    if topic == "uploaded documents" or is_question_about_uploaded_docs(prompt):
                        # Use uploaded documents context
                        if uploaded_docs_context:
                            quiz_context = uploaded_docs_context
                            effective_topic = "Uploaded documents"
                        elif st.session_state.chat_files_ingested and st.session_state.chat_uploaded_filenames:
                            # Retrieve content from uploaded documents for quiz using service layer
                            queries = []
                            for filename in st.session_state.chat_uploaded_filenames:
                                query_text = Path(filename).stem.replace('_', ' ').replace('-', ' ')
                                queries.append(query_text)
                            
                            # Use service layer for retrieval
                            filtered_hits = service.retrieve_multiple_queries(
                                queries=queries,
                                filenames=st.session_state.chat_uploaded_filenames,
                                top_k=50
                            )
                            
                            # Additional filtering
                            filtered_hits = filter_hits_by_filenames(
                                filtered_hits,
                                st.session_state.chat_uploaded_filenames
                            )
                            
                            if filtered_hits:
                                # Use service layer for formatting
                                quiz_context, _ = service.format_context_from_hits(
                                    hits=filtered_hits,
                                    max_passages=15
                                )
                                effective_topic = "Uploaded documents"
                    
                    # Use quiz context if available, otherwise uploaded docs context
                    extra_context = quiz_context or uploaded_docs_context
                    
                    with st.spinner("Creating quiz..."):
                        quiz_obj = service.create_quiz(
                            learner_id=learner_id,
                            topic=effective_topic,
                            num_questions=num_questions,
                            difficulty=None,
                            extra_context=extra_context,
                        )
                    st.session_state.quiz = quiz_obj.model_dump(mode="json")
                    st.session_state.quiz_answers = {}
                    st.session_state.quiz_result = None
                    st.rerun()
                
                # Check if question is specifically about uploaded documents (but not a quiz request)
                filter_to_uploaded = (
                    is_question_about_uploaded_docs(prompt) and
                    st.session_state.chat_files_ingested and
                    st.session_state.chat_uploaded_filenames and
                    not is_quiz_request
                )
                
                if filter_to_uploaded:
                        # Do custom retrieval filtered to uploaded documents
                        with st.spinner("Searching uploaded documents..."):
                            # Build queries from filenames and user question
                            queries = []
                            for filename in st.session_state.chat_uploaded_filenames:
                                query_text = Path(filename).stem.replace('_', ' ').replace('-', ' ')
                                queries.append(query_text)
                            queries.append(prompt)  # Add user's question
                            
                            # Use service layer for retrieval (handles filtering, deduplication)
                            filtered_hits = service.retrieve_multiple_queries(
                                queries=queries,
                                filenames=st.session_state.chat_uploaded_filenames,
                                top_k=50
                            )
                            
                            # Additional filtering by filenames (service handles source_filter, but double-check)
                            filtered_hits = filter_hits_by_filenames(
                                filtered_hits,
                                st.session_state.chat_uploaded_filenames
                            )
                            
                            # Show feedback
                            if filtered_hits:
                                st.caption(f"📚 Found {len(filtered_hits)} passages from your uploaded documents")
                            else:
                                st.warning("No relevant passages found in uploaded documents. Using general knowledge...")
                            
                            # Format context using service layer
                            custom_context, citations = service.format_context_from_hits(
                                hits=filtered_hits[:5],
                                max_passages=5
                            )
                        
                        # Answer with ONLY filtered context using service layer
                        with st.spinner("Generating answer..."):
                            response = service.answer_with_context(
                                learner_id=learner_id,
                                question=prompt,
                                context=custom_context
                            )
                            # Add hits to response for display
                            response.hits = filtered_hits[:5]
                            response.citations = citations
                else:
                    # Regular Q&A - let agent handle it
                    # Combine quiz context and uploaded docs context
                    combined_context = None
                    if uploaded_docs_context and quiz_context:
                        combined_context = f"{uploaded_docs_context}\n\n{quiz_context}"
                    elif uploaded_docs_context:
                        combined_context = uploaded_docs_context
                    elif quiz_context:
                        combined_context = quiz_context
                    
                    # If user mentions "documents" and we have uploaded files, enhance the prompt
                    enhanced_prompt = prompt
                    if uploaded_docs_context and ("document" in prompt.lower() or "file" in prompt.lower() or "pdf" in prompt.lower()):
                        # Extract document titles from context
                        if st.session_state.chat_uploaded_filenames:
                            doc_names = [Path(f).stem.replace('_', ' ').replace('-', ' ') for f in st.session_state.chat_uploaded_filenames]
                            enhanced_prompt = f"{prompt} (Note: User has uploaded documents about: {', '.join(doc_names)})"
                    
                    with st.spinner("Thinking..."):
                        try:
                            # Use service layer for Q&A
                            response = service.answer_question(
                                learner_id=learner_id,
                                question=enhanced_prompt,
                                extra_context=combined_context,
                            )
                        except Exception as e:
                            error_msg = str(e)
                            st.error(f"❌ Error generating answer: {error_msg}")
                            logger.exception("Error in answer_question")
                            # Use service layer to create error response
                            response = service.create_error_response(error_msg)
                
                if response.answer:
                    placeholder.markdown(format_answer(response.answer))
                else:
                    placeholder.error("No answer was generated. Please try again.")
                if response.citations:
                    citations_container.markdown("**Citations:**\n" + "\n".join(f"- {c}" for c in response.citations))
                else:
                    citations_container.caption("No citations provided.")

                if response.quiz:
                    st.session_state.quiz = response.quiz.model_dump(mode="json")
                    st.session_state.quiz_answers = {}
                    st.session_state.quiz_result = None

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": response.answer,
                        "citations": response.citations,
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
                        horizontal=True,
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
                        evaluation = system.evaluate_quiz(
                            learner_id=learner_id,
                            quiz_payload=quiz,
                            answers=answers,
                        )
                        st.session_state.quiz_result = evaluation.model_dump(mode="json")
                        st.session_state.quiz_completed = quiz.model_dump(mode="json")
                        st.session_state.quiz = None
                        st.session_state.quiz_answers = {}
                        # Initialize markdown for download
                        st.session_state.quiz_markdown = system.quiz_to_markdown(quiz)
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
                        st.session_state.pre_submit_quiz_markdown = system.quiz_to_markdown(quiz)
                    st.rerun()
            
            # Show edit/download interface if enabled
            if st.session_state.get("pre_submit_edit_mode", False):
                st.divider()
                st.markdown("### ✏️ Edit Quiz")
                st.caption("Edit the quiz content below and download when ready.")
                
                edited_quiz = st.text_area(
                    "Quiz Content (Markdown)",
                    value=st.session_state.get("pre_submit_quiz_markdown", system.quiz_to_markdown(quiz)),
                    height=300,
                    key="pre_submit_quiz_editor"
                )
                st.session_state.pre_submit_quiz_markdown = edited_quiz
                
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
                    st.session_state.quiz_markdown = edited_markdown
            else:
                st.markdown("### 👁️ Quiz Preview")
                if "quiz_markdown" in st.session_state:
                    with st.container(border=True):
                        st.markdown(st.session_state.quiz_markdown)
        


__all__ = [
    "load_system",
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
