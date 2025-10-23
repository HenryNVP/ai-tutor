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
    if "quiz" not in st.session_state:
        st.session_state.quiz = None
    if "quiz_answers" not in st.session_state:
        st.session_state.quiz_answers = {}
    if "quiz_result" not in st.session_state:
        st.session_state.quiz_result = None

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

        st.subheader("Quiz tools")
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
                    extra_context=summarize_documents(st.session_state.documents) or None,
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
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        extra_context = summarize_documents(st.session_state.documents)

        if st.session_state.quiz_result:
            quiz_result = QuizEvaluation.model_validate(st.session_state.quiz_result)
            quiz_context = format_quiz_context(quiz_result)
        else:
            quiz_context = ""
        combined_context_parts = [
            part for part in (extra_context, quiz_context) if part and part.strip()
        ]
        combined_context = "\n\n".join(combined_context_parts) if combined_context_parts else None

        with st.chat_message("assistant"):
            placeholder = st.empty()
            citations_container = st.empty()
            with st.spinner("Thinking..."):
                response = system.answer_question(
                    learner_id=learner_id,
                    question=prompt,
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
        st.subheader(f"📝 Quiz: {quiz.topic} ({quiz.difficulty.title()})")
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

        if st.button("Submit quiz", type="primary"):
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
                st.session_state.quiz = None
                st.session_state.quiz_answers = {}
                st.success(
                    f"Quiz scored {evaluation.correct_count}/{evaluation.total_questions} "
                    f"({evaluation.score * 100:.0f}%)."
                )
                st.rerun()

    if st.session_state.quiz_result:
        result = QuizEvaluation.model_validate(st.session_state.quiz_result)
        st.subheader("Quiz feedback")
        st.write(
            f"Score: **{result.correct_count}/{result.total_questions}** "
            f"({result.score * 100:.0f}%)."
        )
        if result.review_topics:
            st.info("Suggested practice:")
            for topic in result.review_topics:
                st.write(f"- {topic}")
        with st.expander("Question breakdown", expanded=False):
            for answer in result.answers:
                label = "✅ Correct" if answer.is_correct else "❌ Incorrect"
                st.markdown(f"**Q{answer.index + 1}: {label}**")
                if answer.explanation:
                    st.caption(answer.explanation)
                if answer.references:
                    st.caption("References: " + "; ".join(answer.references))
        if st.button("Dismiss quiz feedback"):
            st.session_state.quiz_result = None
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
