"""Streamlit-based UI for the AI tutor."""

from __future__ import annotations

import io
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import streamlit as st
from streamlit.runtime.secrets import StreamlitSecretNotFoundError

from ai_tutor.system import TutorSystem

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

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "documents" not in st.session_state:
        st.session_state.documents = []

    with st.sidebar:
        st.header("Session Settings")
        learner_id = st.text_input("Learner ID", value="s1")

        st.subheader("Upload optional context")
        uploads = st.file_uploader(
            "Add PDFs or text files (not persisted)",
            type=["pdf", "txt", "md"],
            accept_multiple_files=True,
        )
        new_docs: List[Dict[str, str]] = []
        if uploads:
            for upload in uploads:
                try:
                    text = extract_text(upload)
                    if not text.strip():
                        st.warning(f"No extractable text found in {upload.name}.")
                        continue
                    new_docs.append({"name": upload.name, "text": text})
                except Exception as exc:
                    st.error(f"Failed to read {upload.name}: {exc}")
            if new_docs:
                st.session_state.documents = new_docs
        if st.button("Clear uploaded context"):
            st.session_state.documents = []
        if st.session_state.documents:
            st.caption("Active session documents:")
            for doc in st.session_state.documents:
                st.write(f"• {doc['name']}")

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
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        extra_context = summarize_documents(st.session_state.documents)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            citations_container = st.empty()
            with st.spinner("Thinking..."):
                response = system.answer_question(
                    learner_id=learner_id,
                    question=prompt,
                    extra_context=extra_context if extra_context else None,
                )
            placeholder.markdown(format_answer(response.answer))
            if response.citations:
                citations_container.markdown("**Citations:**\n" + "\n".join(f"- {c}" for c in response.citations))
            else:
                citations_container.caption("No citations provided.")

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": response.answer,
                "citations": response.citations,
            }
        )

        st.rerun()


__all__ = [
    "load_system",
    "extract_text",
    "summarize_documents",
    "format_answer",
    "render",
]


if __name__ == "__main__":
    render()
