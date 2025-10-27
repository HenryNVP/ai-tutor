"""Streamlit-based UI for the AI tutor."""

from __future__ import annotations

import io
import os
import re
import tempfile
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from collections import Counter

import streamlit as st
from streamlit.runtime.secrets import StreamlitSecretNotFoundError

from ai_tutor.system import TutorSystem
from ai_tutor.learning.quiz import Quiz, QuizEvaluation

try:  # pragma: no cover - optional dependency
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None  # type: ignore[assignment]


@st.cache_resource(show_spinner=False)
def load_system(api_key: Optional[str]) -> TutorSystem:
    return TutorSystem.from_config(api_key=api_key)


def extract_text(upload: Any) -> str:
    suffix = Path(upload.name).suffix.lower()
    try:
        upload.seek(0)
    except AttributeError:  # pragma: no cover - UploadedFile implements seek but guard anyway
        pass
    data = upload.read()
    if not data:
        return ""
    if suffix == ".pdf":
        if PdfReader is None:
            raise RuntimeError("pypdf is required to read PDF files. Install it or upload text instead.")
        reader = PdfReader(io.BytesIO(data))
        pages: List[str] = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:  # pragma: no cover - best effort extraction
                pages.append("")
        return "\n\n".join(pages)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1", errors="ignore")


def summarize_documents(docs: Iterable[Dict[str, str]], max_chars: int = 6000) -> str:
    parts: List[str] = []
    remaining = max_chars
    for doc in docs:
        text = doc.get("text", "").strip()
        if not text:
            continue
        header = f"[{doc.get('name', 'Document')}]\n"
        available = max(0, remaining - len(header))
        body = text[:available] if available else ""
        parts.append(header + body)
        remaining -= len(header) + len(body) + 2
        if remaining <= 0:
            break
    return "\n\n".join(parts)


def format_answer(text: str) -> str:
    normalized = re.sub(r"(?<=\S)\s+(?=(?:[-•*]|\d+\.)\s)", "\n", text)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    lines = normalized.splitlines()
    formatted: List[str] = []
    for line in lines:
        stripped = line.rstrip()
        is_bullet = stripped.startswith(("-", "*", "•"))
        is_enumeration = bool(re.match(r"^\d+\.\s", stripped))
        if (is_bullet or is_enumeration) and formatted and formatted[-1] != "":
            formatted.append("")
        formatted.append(stripped)
    return "\n".join(formatted)


def format_quiz_context(result: QuizEvaluation) -> str:
    lines = [
        f"Recent quiz: {result.topic}",
        f"Score: {result.correct_count}/{result.total_questions} ({result.score * 100:.0f}%)",
    ]
    for answer in result.answers:
        status = "correct" if answer.is_correct else "incorrect"
        lines.append(f"- Q{answer.index + 1}: {status}")
    if result.review_topics:
        lines.append("Focus areas: " + "; ".join(result.review_topics))
    return "\n".join(lines)


def quiz_to_markdown(quiz: Quiz) -> str:
    """
    Convert a Quiz object to markdown format for download.
    
    Parameters
    ----------
    quiz : Quiz
        The quiz to convert to markdown.
    
    Returns
    -------
    str
        Markdown-formatted quiz content.
    """
    lines = [
        f"# {quiz.topic}",
        "",
    ]
    
    for idx, question in enumerate(quiz.questions):
        lines.append(f"{idx + 1}. {question.question}")
        
        for choice_idx, choice in enumerate(question.choices):
            lines.append(f"{chr(97 + choice_idx)}) {choice}")
        
        # Add answer line with letter
        answer_letter = chr(97 + question.correct_index)
        lines.append(f"Answer: {answer_letter}")
        
        if question.explanation:
            lines.append(f"Explanation: {question.explanation}")
        
        lines.append("")
    
    return "\n".join(lines)


def detect_quiz_request(message: str) -> bool:
    """
    Detect if user is requesting a quiz from their message.
    
    Parameters
    ----------
    message : str
        User's chat message
    
    Returns
    -------
    bool
        True if message is a quiz request
    """
    quiz_keywords = [
        "create a quiz",
        "generate a quiz",
        "make a quiz",
        "create quizzes",  # plural
        "generate quizzes",  # plural
        "make quizzes",  # plural
        "quiz me",
        "test me",
        "practice questions",
        "create questions",
        "generate questions",
        "downloadable quiz",
        "quiz from",
    ]
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in quiz_keywords)


def is_question_about_uploaded_docs(message: str) -> bool:
    """
    Detect if user is asking specifically about uploaded documents.
    
    Parameters
    ----------
    message : str
        User's question
    
    Returns
    -------
    bool
        True if question is specifically about uploaded documents
    """
    upload_keywords = [
        "uploaded",
        "upload",
        "the documents i uploaded",
        "the files i uploaded",
        "these documents",
        "these files",
        "the 2 documents",
        "the 2 files",
        "the two documents",
        "the two files",
        "this document",
        "this file",
    ]
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in upload_keywords)


def filter_hits_by_filenames(hits: List, filenames: List[str]) -> List:
    """
    Filter retrieval hits to only include chunks from specific filenames.
    
    Parameters
    ----------
    hits : List[RetrievalHit]
        List of retrieval hits from vector search
    filenames : List[str]
        List of filenames to filter by (e.g., ["lecture9.pdf", "lecture10.pdf"])
    
    Returns
    -------
    List[RetrievalHit]
        Filtered hits containing only chunks from the specified files
    """
    if not filenames:
        return hits
    
    # Normalize filenames for comparison (case-insensitive, handle paths)
    normalized_filenames = {Path(fn).name.lower() for fn in filenames}
    
    # Debug logging
    import streamlit as st
    import logging
    logger = logging.getLogger(__name__)
    
    # Log to console as well
    logger.info(f"Filtering by filenames: {normalized_filenames}")
    
    with st.expander("🔍 Debug: Filename Matching", expanded=False):
        st.write("**Looking for these files:**")
        for fn in normalized_filenames:
            st.write(f"- `{fn}`")
        st.write("")
        st.write(f"**Found in top {len(hits)} retrieval results (unique sources):**")
        seen_sources = set()
        matches_found = 0
        for hit in hits:  # Check ALL hits
            source_name = Path(hit.chunk.metadata.source_path).name.lower()
            if source_name not in seen_sources:
                seen_sources.add(source_name)
                match = "✅ MATCH" if source_name in normalized_filenames else "❌ no match"
                st.write(f"- `{source_name}` {match}")
                if source_name in normalized_filenames:
                    matches_found += 1
                logger.info(f"Source: {source_name}, Match: {source_name in normalized_filenames}")
        st.write("")
        st.write(f"**Summary:** {matches_found}/{len(normalized_filenames)} uploaded files found in results")
    
    filtered_hits = []
    for hit in hits:
        # Get the source path from chunk metadata
        source_name = Path(hit.chunk.metadata.source_path).name.lower()
        if source_name in normalized_filenames:
            filtered_hits.append(hit)
    
    return filtered_hits


def extract_quiz_num_questions(message: str) -> int:
    """
    Extract the number of questions requested from user message.
    
    Parameters
    ----------
    message : str
        User's message requesting a quiz
    
    Returns
    -------
    int
        Number of questions requested (default: 4, max: 20)
    """
    import re
    
    # Try to extract numbers from patterns like:
    # "create 8 downloadable quizzes", "quiz with 15 questions", "20 question quiz"
    patterns = [
        r"(\d+)\s+(?:question|questions)",
        r"create\s+(\d+)\s+(?:\w+\s+)?(?:quiz|quizzes)",  # Handles optional adjective
        r"generate\s+(\d+)\s+(?:\w+\s+)?(?:quiz|quizzes)",  # Handles optional adjective
        r"make\s+(\d+)\s+(?:\w+\s+)?(?:quiz|quizzes)",  # Handles optional adjective
        r"quiz\s+with\s+(\d+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message.lower())
        if match:
            num = int(match.group(1))
            # If user asks for "10 quizzes", interpret as 10 questions
            # Cap at 20 questions for reasonable generation time
            return min(num, 20)
    
    # Default to 4 questions
    return 4


def extract_quiz_topic(message: str) -> str:
    """
    Extract quiz topic from user message.
    
    Parameters
    ----------
    message : str
        User's message requesting a quiz
    
    Returns
    -------
    str
        Extracted topic or the full message if no specific topic found
    """
    import re
    
    # Try to extract topic after common patterns
    # Updated to handle numbers, adjectives, and plural forms
    patterns = [
        # Handles: "create 8 downloadable quizzes about CNN"
        r"(?:create|generate|make)\s+(?:\d+\s+)?(?:\w+\s+)?quiz(?:zes)?\s+(?:about|on|regarding|for|from)\s+(.+)",
        # Handles: "quiz about CNN"
        r"quiz(?:zes)?\s+(?:about|on|regarding|for|from)\s+(.+)",
        # Handles: "test me on CNN"
        r"test me on\s+(.+)",
        # Handles: "questions about CNN"
        r"questions\s+(?:about|on|regarding|for)\s+(.+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message.lower())
        if match:
            topic = match.group(1).strip()
            # Clean up common endings
            topic = re.sub(r"[.!?]+$", "", topic)
            return topic
    
    # Fallback: return the message without quiz keywords
    cleaned = message.lower()
    for keyword in ["create", "generate", "make", "quiz", "quizzes", "test", "questions", "downloadable"]:
        cleaned = cleaned.replace(keyword, "")
    # Remove numbers at the start
    cleaned = re.sub(r"^\d+\s*", "", cleaned)
    return cleaned.strip() or "general topics"


def analyze_corpus(system: TutorSystem) -> Dict[str, Any]:
    """
    Analyze the ingested corpus to show coverage statistics.
    
    Parameters
    ----------
    system : TutorSystem
        The tutor system with loaded vector store.
    
    Returns
    -------
    dict
        Statistics about the corpus including domains, documents, and sample topics.
    """
    chunks = system.chunk_store.load()
    
    if not chunks:
        return {
            "total_chunks": 0,
            "total_documents": 0,
            "domains": {},
            "documents": [],
            "sample_topics": []
        }
    
    # Analyze domains
    domains = Counter(
        chunk.metadata.domain
        for chunk in chunks
    )
    
    # Analyze documents
    doc_ids = set(chunk.metadata.doc_id for chunk in chunks)
    doc_titles = {}
    for chunk in chunks:
        if chunk.metadata.doc_id not in doc_titles:
            doc_titles[chunk.metadata.doc_id] = chunk.metadata.title
    
    # Get sample topics (first sentence of random chunks)
    import random
    sample_size = min(10, len(chunks))
    sample_chunks = random.sample(chunks, sample_size) if len(chunks) > sample_size else chunks
    sample_topics = []
    for chunk in sample_chunks:
        # Extract first sentence as topic
        text = chunk.text.strip()
        first_sentence = text.split('.')[0][:100]
        if first_sentence:
            sample_topics.append({
                "text": first_sentence + "...",
                "doc": chunk.metadata.title,
                "domain": chunk.metadata.domain
            })
    
    return {
        "total_chunks": len(chunks),
        "total_documents": len(doc_ids),
        "domains": dict(domains),
        "documents": [{"id": doc_id, "title": doc_titles[doc_id]} for doc_id in doc_ids],
        "sample_topics": sample_topics
    }


def render_corpus_management_tab(system: TutorSystem) -> None:
    """Render the corpus management and ingestion tab."""
    st.header("📚 Corpus Management")
    
    # Initialize session state for corpus management
    if "uploaded_files_for_ingestion" not in st.session_state:
        st.session_state.uploaded_files_for_ingestion = []
    if "ingestion_result" not in st.session_state:
        st.session_state.ingestion_result = None
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📤 Upload & Ingest Documents")
        st.markdown("""
        Upload PDF, Markdown, or TXT files to add them to the permanent knowledge base.
        These documents will be chunked, embedded, and stored in the vector database for future retrieval.
        """)
        
        uploaded_files = st.file_uploader(
            "Select files to ingest into vector store",
            type=["pdf", "txt", "md"],
            accept_multiple_files=True,
            key="corpus_uploader"
        )
        
        if uploaded_files:
            st.session_state.uploaded_files_for_ingestion = uploaded_files
            st.success(f"✓ {len(uploaded_files)} file(s) ready for ingestion")
            
            with st.expander("View files to be ingested"):
                for file in uploaded_files:
                    file_size_mb = len(file.getvalue()) / (1024 * 1024)
                    st.write(f"• **{file.name}** ({file_size_mb:.2f} MB)")
        
        if st.button("🚀 Ingest Files into Vector Store", type="primary", disabled=not uploaded_files):
            with st.spinner("Processing and ingesting documents... This may take a few minutes."):
                # Create temporary directory for uploaded files
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    
                    # Save uploaded files to temp directory
                    saved_paths = []
                    for uploaded_file in uploaded_files:
                        file_path = temp_path / uploaded_file.name
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getvalue())
                        saved_paths.append(file_path)
                    
                    # Ingest using the system's ingestion pipeline
                    try:
                        result = system.ingest_directory(temp_path)
                        st.session_state.ingestion_result = {
                            "documents": len(result.documents),
                            "chunks": len(result.chunks),
                            "skipped": [str(p) for p in result.skipped],
                            "success": True
                        }
                        st.success(f"✅ Successfully ingested {len(result.documents)} documents into {len(result.chunks)} chunks!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Ingestion failed: {str(e)}")
                        st.session_state.ingestion_result = {
                            "error": str(e),
                            "success": False
                        }
        
        if st.session_state.ingestion_result and st.session_state.ingestion_result.get("success"):
            result = st.session_state.ingestion_result
            st.info(f"""
            **Last Ingestion Result:**
            - Documents processed: {result['documents']}
            - Chunks created: {result['chunks']}
            - Files skipped: {len(result['skipped'])}
            """)
            if result['skipped']:
                with st.expander("View skipped files"):
                    for skipped in result['skipped']:
                        st.write(f"• {skipped}")
    
    with col2:
        st.subheader("📊 Corpus Analysis")
        st.markdown("View statistics about the ingested knowledge base.")
        
        if st.button("🔍 Analyze Corpus", type="secondary"):
            with st.spinner("Analyzing corpus..."):
                analysis = analyze_corpus(system)
                st.session_state.corpus_analysis = analysis
        
        if "corpus_analysis" in st.session_state:
            analysis = st.session_state.corpus_analysis
            
            if analysis["total_chunks"] == 0:
                st.warning("No documents in corpus. Upload and ingest some files first!")
            else:
                # Display metrics
                metric_col1, metric_col2, metric_col3 = st.columns(3)
                with metric_col1:
                    st.metric("📄 Documents", analysis["total_documents"])
                with metric_col2:
                    st.metric("🧩 Chunks", analysis["total_chunks"])
                with metric_col3:
                    avg_chunks = analysis["total_chunks"] / analysis["total_documents"] if analysis["total_documents"] > 0 else 0
                    st.metric("📏 Avg Chunks/Doc", f"{avg_chunks:.1f}")
                
                # Domain distribution
                st.markdown("**📚 Domain Distribution:**")
                for domain, count in analysis["domains"].items():
                    percentage = (count / analysis["total_chunks"]) * 100
                    st.progress(percentage / 100, text=f"{domain}: {count} chunks ({percentage:.1f}%)")
                
                # Documents list
                with st.expander("📑 Documents in Corpus"):
                    for doc in analysis["documents"]:
                        st.write(f"• {doc['title']} (ID: `{doc['id']}`)")
                
                # Sample topics
                with st.expander("🎯 Sample Topics Coverage"):
                    for topic in analysis["sample_topics"]:
                        st.markdown(f"**{topic['domain'].upper()}** • {topic['doc']}")
                        st.caption(topic['text'])
                        st.divider()


def render_quiz_builder_tab(system: TutorSystem, learner_id: str) -> None:
    """Render the advanced quiz builder tab."""
    st.header("📝 Quiz Builder")
    
    st.info("💡 Generate a quiz here, then switch to the **Chat & Learn** tab to take it interactively!")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("🎯 Generate Quiz")
        
        quiz_topic = st.text_input(
            "Quiz Topic",
            placeholder="e.g., Newton's Laws of Motion",
            key="quiz_builder_topic"
        )
        
        quiz_col1, quiz_col2 = st.columns(2)
        with quiz_col1:
            num_questions = st.slider("Number of Questions", 3, 20, 4, key="quiz_builder_count")
        with quiz_col2:
            difficulty = st.selectbox(
                "Difficulty Level",
                ["foundational", "balanced", "guided", "advanced"],
                index=1,
                key="quiz_builder_difficulty"
            )
        
        use_corpus = st.checkbox(
            "Ground quiz in retrieved passages from corpus",
            value=True,
            help="If checked, quiz questions will be based on relevant passages retrieved from the vector store"
        )
        
        if st.button("✨ Generate Interactive Quiz", type="primary", disabled=not quiz_topic.strip()):
            with st.spinner("Generating quiz from retrieved passages..."):
                try:
                    # Retrieve relevant context if using corpus
                    extra_context = None
                    if use_corpus:
                        from ai_tutor.data_models import Query
                        hits = system.tutor_agent.retriever.retrieve(Query(text=quiz_topic))
                        if hits:
                            context_parts = []
                            for idx, hit in enumerate(hits[:3], 1):
                                context_parts.append(
                                    f"[{idx}] {hit.chunk.metadata.title} (Page {hit.chunk.metadata.page or 'N/A'})\n"
                                    f"{hit.chunk.text}"
                                )
                            extra_context = "\n\n".join(context_parts)
                            st.info(f"📚 Retrieved {len(hits)} relevant passages from corpus")
                    
                    quiz = system.generate_quiz(
                        learner_id=learner_id,
                        topic=quiz_topic,
                        num_questions=num_questions,
                        extra_context=extra_context
                    )
                    # Use unified quiz interface
                    st.session_state.quiz = quiz.model_dump(mode="json")
                    st.session_state.quiz_answers = {}
                    st.session_state.quiz_result = None
                    st.success(f"✅ Generated {len(quiz.questions)}-question quiz on '{quiz.topic}'! Go to **Chat & Learn** tab to take it.")
                except Exception as e:
                    st.error(f"❌ Quiz generation failed: {str(e)}")
    
    with col2:
        st.subheader("📥 Quick Download")
        st.caption("Want to just download a quiz without taking it?")
        
        download_topic = st.text_input(
            "Quiz Topic for Download",
            placeholder="e.g., Binary Search",
            key="quiz_download_topic"
        )
        
        download_num = st.number_input("Number of Questions", min_value=3, max_value=20, value=5, key="quiz_download_num")
        
        if st.button("📄 Generate & Download Only", disabled=not download_topic.strip()):
            with st.spinner("Generating quiz..."):
                try:
                    quiz = system.generate_quiz(
                        learner_id=learner_id,
                        topic=download_topic,
                        num_questions=download_num
                    )
                    quiz_md = quiz_to_markdown(quiz)
                    st.download_button(
                        label="💾 Download Quiz (Markdown)",
                        data=quiz_md,
                        file_name=f"quiz_{quiz.topic.replace(' ', '_')}.md",
                        mime="text/markdown",
                        use_container_width=True,
                        type="primary"
                    )
                    st.success("✅ Quiz ready for download!")
                except Exception as e:
                    st.error(f"❌ Quiz generation failed: {str(e)}")


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
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["💬 Chat & Learn", "📚 Corpus Management", "📝 Quiz Builder"])

    # Tab 2: Corpus Management
    with tab2:
        render_corpus_management_tab(system)
    
    # Tab 3: Quiz Builder
    with tab3:
        learner_id = st.session_state.get("learner_id_global", "s1")
        render_quiz_builder_tab(system, learner_id)
    
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
            
            # Legacy quiz tools (for backward compatibility)
            with st.expander("🎯 Quick Quiz Tools (Legacy)"):
                quiz_topic = st.text_input("Quiz topic", key="quiz_topic_input")
                quiz_questions = st.slider("Questions", min_value=3, max_value=8, value=4, key="quiz_question_count")
                if st.button("Generate quiz", use_container_width=True):
                    if not quiz_topic.strip():
                        st.warning("Enter a quiz topic before generating.")
                    else:
                        quiz = system.generate_quiz(
                            learner_id=learner_id,
                            topic=quiz_topic.strip(),
                            num_questions=quiz_questions,
                        )
                        st.session_state.quiz = quiz.model_dump(mode="json")
                        st.session_state.quiz_answers = {}
                        st.session_state.quiz_result = None
                        st.success(f"Created quiz for {quiz.topic}.")
                        st.rerun()
                if st.button("Clear quiz state", use_container_width=True):
                    st.session_state.quiz = None
                    st.session_state.quiz_answers = {}
                    st.session_state.quiz_result = None
                    st.rerun()

        for message in st.session_state.messages:
            role = message["role"]
            with st.chat_message(role):
                content = str(message.get("content", ""))
                if role == "assistant":
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
            
            # Check if this is a quiz request
            if detect_quiz_request(prompt):
                # Don't append user message again - already appended above
                if not ingestion_happened:
                    with st.chat_message("user"):
                        st.markdown(prompt)
                
                with st.chat_message("assistant"):
                    topic = extract_quiz_topic(prompt)
                    num_questions = extract_quiz_num_questions(prompt)
                    st.info(f"🎯 Generating quiz on: **{topic}** ({num_questions} questions)")
                    
                    # Generate quiz grounded in uploaded documents
                    extra_context = None
                    if st.session_state.chat_files_ingested and st.session_state.chat_uploaded_filenames:
                        # Use filename-based retrieval to ensure we get content from uploaded docs
                        from ai_tutor.data_models import Query
                        with st.spinner("Retrieving relevant passages from your uploaded documents..."):
                            # Strategy: Search using FILENAMES as queries to force retrieval from uploaded docs
                            all_hits = []
                            for filename in st.session_state.chat_uploaded_filenames:
                                # Use filename (without extension) as query
                                query_text = Path(filename).stem.replace('_', ' ').replace('-', ' ')
                                file_hits = system.tutor_agent.retriever.retrieve(Query(text=query_text))
                                all_hits.extend(file_hits)
                            
                            # Also try the topic
                            topic_hits = system.tutor_agent.retriever.retrieve(Query(text=topic))
                            all_hits.extend(topic_hits)
                            
                            # Remove duplicates and filter to only uploaded documents
                            seen_chunk_ids = set()
                            unique_hits = []
                            for hit in all_hits:
                                if hit.chunk.metadata.chunk_id not in seen_chunk_ids:
                                    seen_chunk_ids.add(hit.chunk.metadata.chunk_id)
                                    unique_hits.append(hit)
                            
                            # Filter to only uploaded documents
                            filtered_hits = filter_hits_by_filenames(
                                unique_hits,
                                st.session_state.chat_uploaded_filenames
                            )
                            
                            if filtered_hits:
                                context_parts = []
                                for idx, hit in enumerate(filtered_hits[:10], 1):  # Use more context for quiz generation
                                    context_parts.append(
                                        f"[{idx}] {hit.chunk.metadata.title} (Page {hit.chunk.metadata.page or 'N/A'})\n"
                                        f"{hit.chunk.text}"
                                    )
                                extra_context = "\n\n".join(context_parts)
                                st.caption(f"📚 Retrieved {len(filtered_hits)} passages from your uploaded documents")
                            else:
                                st.warning("⚠️ No passages found in uploaded documents. Quiz may not be grounded in your files.")
                    
                    try:
                        with st.spinner(f"Generating quiz with {num_questions} questions..."):
                            quiz = system.generate_quiz(
                                learner_id=learner_id,
                                topic=topic,
                                num_questions=num_questions,
                                extra_context=extra_context
                            )
                        
                        # Store quiz in unified interface
                        st.session_state.quiz = quiz.model_dump(mode="json")
                        st.session_state.quiz_answers = {}
                        st.session_state.quiz_result = None
                        
                        st.success(f"✅ Quiz generated! Scroll down to take the quiz.")
                        
                        # Add message
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": f"I've created a {len(quiz.questions)}-question quiz on **{quiz.topic}**. Scroll down to take it, and you can edit or download it after completion."
                        })
                    except Exception as e:
                        st.error(f"❌ Quiz generation failed: {str(e)}")
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": f"Sorry, I couldn't generate a quiz. Error: {str(e)}"
                        })
                
                st.rerun()
            
            # Regular Q&A
            else:
                # Don't append user message again - already appended above
                if not ingestion_happened:
                    with st.chat_message("user"):
                        st.markdown(prompt)

                if st.session_state.quiz_result:
                    quiz_result = QuizEvaluation.model_validate(st.session_state.quiz_result)
                    quiz_context = format_quiz_context(quiz_result)
                else:
                    quiz_context = ""

                with st.chat_message("assistant"):
                    placeholder = st.empty()
                    citations_container = st.empty()
                    
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
                                st.warning("No relevant passages found in uploaded documents. Searching broader corpus...")
                                filtered_hits = hits  # Fallback to all results
                            
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
                        # Regular Q&A without filtering
                        with st.spinner("Thinking..."):
                            response = system.answer_question(
                                learner_id=learner_id,
                                question=prompt,
                                extra_context=quiz_context or None,
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
                        st.session_state.quiz_markdown = quiz_to_markdown(quiz)
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
    "detect_quiz_request",
    "is_question_about_uploaded_docs",
    "filter_hits_by_filenames",
    "extract_quiz_num_questions",
    "extract_quiz_topic",
    "quiz_to_markdown",
    "analyze_corpus",
    "render_corpus_management_tab",
    "render_quiz_builder_tab",
    "render",
]


if __name__ == "__main__":
    render()
