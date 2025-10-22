"""Minimal Streamlit interface for quiz generation and evaluation."""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import streamlit as st
from streamlit.runtime.secrets import StreamlitSecretNotFoundError

from ai_tutor.learning.quiz import Quiz, QuizEvaluation
from ai_tutor.system import TutorSystem


@st.cache_resource(show_spinner=False)
def load_system(api_key: Optional[str]) -> TutorSystem:
    return TutorSystem.from_config(api_key=api_key)


def _get_api_key() -> Optional[str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return api_key
    try:
        return st.secrets["OPENAI_API_KEY"]
    except (KeyError, StreamlitSecretNotFoundError):
        return None


def _label_choice(index: int, text: str) -> str:
    labels = ["A", "B", "C", "D"]
    prefix = labels[index] if index < len(labels) else chr(ord("A") + index)
    return f"{prefix}. {text}"


def render() -> None:
    st.set_page_config(page_title="Tutor Quiz", page_icon="📝", layout="wide")
    st.title("📝 Quiz Builder")

    api_key = _get_api_key()
    if not api_key:
        st.error(
            "OPENAI_API_KEY is not set. Provide it via environment variable or Streamlit secrets."
        )
        st.stop()

    system = load_system(api_key)

    if "quiz" not in st.session_state:
        st.session_state.quiz = None
    if "answers" not in st.session_state:
        st.session_state.answers = {}
    if "result" not in st.session_state:
        st.session_state.result = None

    with st.sidebar:
        st.header("Learner")
        learner_id = st.text_input("Learner ID", value="student123")
        num_questions = st.slider("Number of questions", min_value=3, max_value=8, value=4)
        if st.button("Reset session"):
            st.session_state.quiz = None
            st.session_state.answers = {}
            st.session_state.result = None
            st.experimental_rerun()

    topic = st.text_input("Quiz topic", placeholder="e.g., Newton's laws of motion")
    extra_context = st.text_area(
        "Optional session notes",
        placeholder="Add any extra details to guide the quiz (optional)",
    )

    if st.button("Generate quiz", disabled=not topic.strip()):
        quiz = system.generate_quiz(
            learner_id=learner_id.strip(),
            topic=topic.strip(),
            num_questions=num_questions,
            extra_context=extra_context.strip() or None,
        )
        st.session_state.quiz = quiz.model_dump(mode="json")
        st.session_state.answers = {}
        st.session_state.result = None

    if not st.session_state.quiz:
        st.info("Generate a quiz to get started.")
        return

    quiz = Quiz.model_validate(st.session_state.quiz)
    st.subheader(f"{quiz.topic} ({quiz.difficulty.title()})")
    st.caption("Select an answer for each question, then submit once.")

    for idx, question in enumerate(quiz.questions):
        st.markdown(f"**Q{idx + 1}. {question.question}**")
        options = ["Not answered"] + [
            _label_choice(choice_idx, choice_text)
            for choice_idx, choice_text in enumerate(question.choices)
        ]
        stored_index = st.session_state.answers.get(idx, 0)
        selection = st.radio(
            "Select an option",
            options=options,
            index=stored_index,
            key=f"quiz_question_{idx}",
            horizontal=True,
        )
        st.session_state.answers[idx] = options.index(selection)
        st.markdown("---")

    if st.button("Submit answers"):
        submitted_indices: List[int] = []
        for idx in range(len(quiz.questions)):
            option_index = st.session_state.answers.get(idx, 0)
            submitted_indices.append(option_index - 1)
        result = system.evaluate_quiz(
            learner_id=learner_id.strip(),
            quiz_payload=quiz,
            answers=submitted_indices,
        )
        st.session_state.result = result.model_dump(mode="json")

    if st.session_state.result:
        result = QuizEvaluation.model_validate(st.session_state.result)
        st.success(
            f"Score: {result.correct_count}/{result.total_questions} "
            f"({result.score * 100:.0f}%)"
        )
        if result.review_topics:
            st.warning("Topics to review:")
            for item in result.review_topics:
                st.write(f"- {item}")

        with st.expander("Detailed feedback", expanded=False):
            for answer in result.answers:
                status = "✅ Correct" if answer.is_correct else "❌ Incorrect"
                st.markdown(f"**Q{answer.index + 1}: {status}**")
                if answer.explanation:
                    st.caption(answer.explanation)
                if answer.references:
                    st.caption("References: " + "; ".join(answer.references))


__all__ = ["render"]


if __name__ == "__main__":
    render()
