"""Streamlit-based UI for the AI tutor."""

from __future__ import annotations

import io
import os
import re
import sys
import tempfile
import shutil
import base64
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from collections import Counter

# Add project root to Python path for absolute imports
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st
from streamlit.runtime.secrets import StreamlitSecretNotFoundError

from ai_tutor.system import TutorSystem
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


@st.cache_resource(show_spinner=False)
def load_system(api_key: Optional[str]) -> TutorSystem:
    return TutorSystem.from_config(api_key=api_key)


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

    system = load_system(api_key)
    viz_agent = load_visualization_agent(api_key)
    
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
                        result = system.ingest_directory(temp_path)
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
                    quiz_context = system.format_quiz_context(quiz_result)
                else:
                    quiz_context = ""
                
                # Retrieve content from uploaded documents if they exist
                # This provides context for both Q&A and quiz generation
                uploaded_docs_context = None
                if st.session_state.chat_files_ingested and st.session_state.chat_uploaded_filenames:
                    from ai_tutor.data_models import Query
                    from collections import defaultdict
                    
                    with st.spinner("Retrieving content from your uploaded documents..."):
                        # Strategy: Use source_filter to ONLY search uploaded files
                        # This is MUCH more efficient than searching everything then filtering!
                        all_hits = []
                        
                        # Increase top_k since we're only searching uploaded files (smaller pool)
                        original_top_k = system.tutor_agent.retriever.config.top_k
                        system.tutor_agent.retriever.config.top_k = 50  # More than default, but no need for 200
                        
                        try:
                            # 1. Retrieve using filenames with SOURCE FILTER
                            for filename in st.session_state.chat_uploaded_filenames:
                                # Extract meaningful terms from filename
                                query_text = Path(filename).stem.replace('_', ' ').replace('-', ' ')
                                file_hits = system.tutor_agent.retriever.retrieve(
                                    Query(
                                        text=query_text,
                                        source_filter=st.session_state.chat_uploaded_filenames
                                    )
                                )
                                all_hits.extend(file_hits)
                                
                                # Also try the full filename without extension
                                full_name_query = Path(filename).stem
                                more_hits = system.tutor_agent.retriever.retrieve(
                                    Query(
                                        text=full_name_query,
                                        source_filter=st.session_state.chat_uploaded_filenames
                                    )
                                )
                                all_hits.extend(more_hits)
                            
                            # 2. Also retrieve using the user's actual query with SOURCE FILTER
                            query_hits = system.tutor_agent.retriever.retrieve(
                                Query(
                                    text=prompt,
                                    source_filter=st.session_state.chat_uploaded_filenames
                                )
                            )
                            all_hits.extend(query_hits)
                            
                            # 3. For newly uploaded files, also try broad subject queries with SOURCE FILTER
                            if st.session_state.get('chat_files_just_ingested', False):
                                # Try broad queries that might match the content
                                broad_queries = ["computer science", "engineering", "mathematics", "lecture", "course material"]
                                for broad_query in broad_queries:
                                    broad_hits = system.tutor_agent.retriever.retrieve(
                                        Query(
                                            text=broad_query,
                                            source_filter=st.session_state.chat_uploaded_filenames
                                        )
                                    )
                                    all_hits.extend(broad_hits)
                        finally:
                            # ALWAYS restore original top_k
                            system.tutor_agent.retriever.config.top_k = original_top_k
                        
                        # Remove duplicates - no need to filter since source_filter already did it!
                        seen_chunk_ids = set()
                        filtered_hits = []
                        for hit in all_hits:
                            if hit.chunk.metadata.chunk_id not in seen_chunk_ids:
                                seen_chunk_ids.add(hit.chunk.metadata.chunk_id)
                                filtered_hits.append(hit)
                        
                        # Show debug info about what we found
                        if filtered_hits:
                            st.caption(f"✅ Found {len(filtered_hits)} passages from your uploaded file(s)")
                        
                        if filtered_hits:
                            # Group hits by document for balanced representation
                            hits_by_doc = defaultdict(list)
                            for hit in filtered_hits:
                                doc_title = hit.chunk.metadata.title or "Unknown"
                                hits_by_doc[doc_title].append(hit)
                            
                            # Take passages from each document proportionally
                            passages_per_doc = max(3, 15 // len(hits_by_doc))
                            context_parts = []
                            idx = 1
                            for doc_title, hits in hits_by_doc.items():
                                for hit in hits[:passages_per_doc]:
                                    context_parts.append(
                                        f"[{idx}] {hit.chunk.metadata.title} (Page {hit.chunk.metadata.page or 'N/A'})\n"
                                        f"{hit.chunk.text}"
                                    )
                                    idx += 1
                            
                            uploaded_docs_context = "\n\n".join(context_parts)
                            st.caption(f"📚 Retrieved {len(context_parts)} passages from {len(hits_by_doc)} document(s): {', '.join(hits_by_doc.keys())}")
                            
                            # Add document titles to context to help agent understand topic
                            doc_titles_str = ", ".join(hits_by_doc.keys())
                            uploaded_docs_context = (
                                f"Content from uploaded documents: {doc_titles_str}\n\n"
                                f"{uploaded_docs_context}"
                            )
                        else:
                            st.info("ℹ️ No passages found in uploaded documents. Using general knowledge...")
                
                # Check if question is specifically about uploaded documents
                filter_to_uploaded = (
                    is_question_about_uploaded_docs(prompt) and
                    st.session_state.chat_files_ingested and
                    st.session_state.chat_uploaded_filenames
                )
                
                if filter_to_uploaded:
                        # Do custom retrieval filtered to uploaded documents
                        from ai_tutor.data_models import Query
                        with st.spinner("Searching uploaded documents..."):
                            # Strategy: Search using FILENAMES as queries to force retrieval from uploaded docs
                            # This ensures we get content from the specific files regardless of the user's question
                            all_hits = []
                            for filename in st.session_state.chat_uploaded_filenames:
                                # Use filename (without extension) as query to get relevant chunks
                                query_text = Path(filename).stem.replace('_', ' ').replace('-', ' ')
                                file_hits = system.tutor_agent.retriever.retrieve(Query(text=query_text))
                                all_hits.extend(file_hits)
                            
                            # Also try the user's actual question
                            question_hits = system.tutor_agent.retriever.retrieve(Query(text=prompt))
                            all_hits.extend(question_hits)
                            
                            # Remove duplicates and filter to only uploaded documents
                            seen_chunk_ids = set()
                            unique_hits = []
                            for hit in all_hits:
                                if hit.chunk.metadata.chunk_id not in seen_chunk_ids:
                                    seen_chunk_ids.add(hit.chunk.metadata.chunk_id)
                                    unique_hits.append(hit)
                            
                            filtered_hits = filter_hits_by_filenames(
                                unique_hits,
                                st.session_state.chat_uploaded_filenames
                            )
                            
                            # Show feedback
                            if filtered_hits:
                                st.caption(f"📚 Found {len(filtered_hits)} passages from your uploaded documents")
                            else:
                                st.warning("No relevant passages found in uploaded documents. Using general knowledge...")
                            
                            # Format context from filtered hits
                            context_parts = []
                            citations = []
                            for idx, hit in enumerate(filtered_hits[:5], 1):
                                context_parts.append(
                                    f"[{idx}] {hit.chunk.metadata.title} (Page {hit.chunk.metadata.page or 'N/A'})\n"
                                    f"{hit.chunk.text}"
                                )
                                citations.append(f"{hit.chunk.metadata.title} (Page {hit.chunk.metadata.page or 'N/A'})")
                            custom_context = "\n\n".join(context_parts)
                        
                        # Answer with ONLY filtered context (bypass agent's own retrieval)
                        with st.spinner("Generating answer..."):
                            # Use LLM directly to avoid the agent doing its own retrieval
                            messages = [
                                {
                                    "role": "system",
                                    "content": "You are a helpful AI tutor. Answer the student's question using ONLY the provided context from their uploaded documents. Be clear and educational. If the context doesn't contain enough information, say so."
                                },
                                {
                                    "role": "user",
                                    "content": f"""Context from uploaded documents:
{custom_context}

Student's question: {prompt}

Please answer based only on the provided context."""
                                }
                            ]
                            
                            llm_response = system.llm_client.generate(messages)
                            
                            # Create response object to match expected format
                            from ai_tutor.agents.tutor import TutorResponse
                            response = TutorResponse(
                                answer=llm_response,
                                hits=filtered_hits[:5],  # Include the hits we used
                                citations=citations,
                                style="concise",  # Default style for direct LLM calls
                                next_topic=None,
                                difficulty=None,
                                source="local",  # From uploaded documents
                                quiz=None
                            )
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
                    
                    # If this is a quiz request, create quiz directly via backend wrappers
                    if system.detect_quiz_request(enhanced_prompt):
                        num_questions = system.extract_quiz_num_questions(enhanced_prompt)
                        topic = system.extract_quiz_topic(enhanced_prompt)
                        effective_topic = (
                            "Uploaded documents" if topic == "uploaded documents" and uploaded_docs_context else topic
                        )
                        with st.spinner("Creating quiz..."):
                            quiz_obj = system.create_quiz(
                                learner_id=learner_id,
                                topic=effective_topic,
                                num_questions=num_questions,
                                difficulty=None,
                                extra_context=uploaded_docs_context or combined_context,
                            )
                        st.session_state.quiz = quiz_obj.model_dump(mode="json")
                        st.session_state.quiz_answers = {}
                        st.session_state.quiz_result = None
                        st.rerun()
                    else:
                        with st.spinner("Thinking..."):
                            response = system.answer_question(
                                learner_id=learner_id,
                                question=enhanced_prompt,
                                extra_context=combined_context,
                            )
                
                placeholder.markdown(format_answer(response.answer))
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

            for idx, question in enumerate(quiz.questions):
                st.markdown(f"**Q{idx + 1}. {question.question}**")
                answer_choices = [f"{chr(65 + opt)}. {text}" for opt, text in enumerate(question.choices)]
                display_options = ["Not answered"] + answer_choices
                current = st.session_state.quiz_answers.get(idx, -1)
                selection = st.radio(
                    "Choose one",
                    options=display_options,
                    index=current + 1 if current >= 0 else 0,
                    key=f"quiz_q_{idx}",
                    horizontal=True,
                )
                st.session_state.quiz_answers[idx] = display_options.index(selection) - 1
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
