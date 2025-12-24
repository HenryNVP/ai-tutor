import pytest
import sys
from pathlib import Path

# Mark as integration test
pytestmark = pytest.mark.integration

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Skip if ai_tutor not available
try:
    from ai_tutor.agents.routing import (
        apply_deterministic_routing,
        extract_source_mentions,
    )
    from ai_tutor.learning.quiz_intent import extract_quiz_num_questions
except ImportError as e:
    pytest.skip(f"ai_tutor not available: {e}", allow_module_level=True)


def test_quiz_routing_detects_topic_and_count() -> None:
    question = "Please create 5 quiz questions about thermodynamics."

    decision = apply_deterministic_routing(question)

    assert decision is not None
    assert decision.target == "quiz"
    assert decision.quiz_count == 5
    assert decision.quiz_topic is not None
    assert "thermodynamics" in decision.quiz_topic


def test_note_routing_extracts_source_filter() -> None:
    question = 'Summarize "Module 2 lecture" into concise notes.'

    decision = apply_deterministic_routing(question)

    assert decision is not None
    assert decision.target == "note"
    assert decision.source_filter == ["Module 2 lecture"]
def test_note_routing_detects_text_file_request() -> None:
    question = "Please create a text file introducing BERT."

    decision = apply_deterministic_routing(question)

    assert decision is not None
    assert decision.target == "note"
    assert decision.source_filter == []



def test_routing_uses_extra_context_hints() -> None:
    question = "What does the uncertainty principle state?"
    extra_context = "SOURCE_FILTER_HINTS: quantum_notes.pdf, Lecture-05.txt"

    decision = apply_deterministic_routing(question, extra_context=extra_context)

    assert decision is not None
    assert decision.target == "qa"
    assert decision.source_filter == ["quantum_notes.pdf", "Lecture-05.txt"]


def test_extract_source_mentions_handles_metadata_hints() -> None:
    payload = (
        "SOURCE_FILTER_HINTS: lecture_04.pdf, week5-notes.md\n"
        'Also referencing "Final Review Sheet" for clarification.'
    )

    references = extract_source_mentions(payload)

    assert set(references) == {"lecture_04.pdf", "week5-notes.md", "Final Review Sheet"}


def test_extract_source_mentions_ignores_generic_tokens() -> None:
    message = "Use my documents and the files please."

    references = extract_source_mentions(message)

    assert references == []


def test_extract_quiz_num_questions_handles_multiple_numbers() -> None:
    message = "Make a quiz with 5 easy and 10 hard questions."

    count = extract_quiz_num_questions(message)

    assert count == 5  # highest explicit quantity should be used

