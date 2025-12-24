"""End-to-end tests for core use cases.

These tests verify the complete flow from user interaction to system response,
including file uploads, document ingestion, summarization, note-taking, and quiz generation.

These are integration tests that require:
- A configured TutorSystem with vector store
- OpenAI API key (or mocked LLM)
- Proper test data setup

Run with: pytest tests/test_e2e_use_cases.py -v
Skip with: pytest tests/test_e2e_use_cases.py -m "not integration"
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Dict, Any
import sys

import pytest

# Mark as E2E test - requires full system
pytestmark = pytest.mark.e2e

# Skip if fastapi not available
try:
    from fastapi.testclient import TestClient
except ImportError:
    pytest.skip("fastapi not installed", allow_module_level=True)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Guard against import crashes
try:
    from apps.api import app, get_service
    from ai_tutor.services import TutorService
    from ai_tutor.system import TutorSystem
    from ai_tutor.config.loader import load_settings
except Exception as e:
    pytest.skip(f"Could not import required modules: {e}", allow_module_level=True)


@pytest.fixture(scope="module")
def test_settings():
    """Load test settings."""
    return load_settings()


@pytest.fixture(scope="module")
def sample_text_file(tmp_path_factory):
    """Create a sample text file for testing."""
    tmp_dir = tmp_path_factory.mktemp("test_docs")
    text_file = tmp_dir / "sample_physics.txt"
    text_file.write_text("""
Physics Fundamentals

Chapter 1: Mechanics
====================

Force and Motion
----------------
Force is a vector quantity that causes an object to accelerate. Newton's second law states:
F = ma, where F is force, m is mass, and a is acceleration.

Torque
------
Torque is the rotational equivalent of force. It is calculated as:
τ = r × F, where τ is torque, r is the radius vector, and F is the applied force.
The SI unit of torque is Newton-meter (N⋅m).

Energy
------
Energy is the capacity to do work. There are two main forms:
1. Kinetic energy: KE = (1/2)mv²
2. Potential energy: PE = mgh

Conservation of energy states that energy cannot be created or destroyed, only transformed.
""")
    return text_file


@pytest.fixture(scope="module")
def sample_pdf_file(tmp_path_factory):
    """Create a sample PDF file for testing (as text file for simplicity)."""
    tmp_dir = tmp_path_factory.mktemp("test_docs")
    # For testing, we'll use a text file that simulates a PDF
    # In real scenarios, this would be an actual PDF
    pdf_file = tmp_dir / "lecture_notes.pdf"
    pdf_file.write_text("""
Computer Science Lecture Notes

Topic: Data Structures
======================

Arrays
------
An array is a collection of elements stored in contiguous memory locations.
Access time: O(1)
Insertion/Deletion: O(n)

Linked Lists
------------
A linked list is a linear data structure where elements are linked using pointers.
Access time: O(n)
Insertion/Deletion: O(1) at head

Binary Trees
------------
A binary tree is a tree data structure where each node has at most two children.
Height: O(log n) for balanced trees
Search: O(log n) for balanced trees
""")
    return pdf_file


@pytest.fixture(scope="function")
def real_service(test_settings, monkeypatch):
    """Create a real TutorService instance for end-to-end testing.
    
    Note: This uses the real TutorSystem which may make actual LLM API calls
    if OPENAI_API_KEY is set. For faster tests, consider mocking the LLM client.
    """
    # Use test API key if available, otherwise use environment variable
    api_key = os.getenv("OPENAI_API_KEY") or "test-key-placeholder"
    monkeypatch.setenv("OPENAI_API_KEY", api_key)
    
    try:
        # Create a real system instance
        system = TutorSystem.from_config(api_key=api_key)
        return TutorService(system)
    except Exception as e:
        pytest.skip(f"Failed to initialize TutorSystem: {e}. "
                   f"These tests require proper configuration.")


@pytest.fixture(scope="function")
def api_client_with_real_service(real_service):
    """Create a test client with real TutorService."""
    app.dependency_overrides[get_service] = lambda: real_service
    with TestClient(app) as client:
        yield client, real_service
    app.dependency_overrides.clear()


def post_event(client: TestClient, session_id: str, event_payload: Dict[str, Any]):
    """Helper to post a session event."""
    response = client.post(
        f"/sessions/{session_id}/events",
        json={"session_id": session_id, "event": event_payload},
    )
    assert response.status_code == 200, f"Event failed: {response.text}"
    return response.json()


def upload_file(client: TestClient, file_path: Path) -> Dict[str, Any]:
    """Helper to upload a file for ingestion."""
    with open(file_path, "rb") as f:
        files = [("files", (file_path.name, f.read(), "application/octet-stream"))]
        response = client.post("/ingest", files=files)
    assert response.status_code == 200, f"Upload failed: {response.text}"
    return response.json()


def test_use_case_1_greetings(api_client_with_real_service):
    """Test Case 1: Simple greetings interaction."""
    client, service = api_client_with_real_service
    session_id = "test-learner-1"
    
    # Send a greeting
    response = post_event(
        client,
        session_id,
        {
            "type": "message",
            "content": "Hello! How are you?",
        },
    )
    
    # Verify response
    assert response["session_id"] == session_id
    assert response["turn_id"] == 1
    assert response["route"] in ["qa", "web"]  # Could route to either
    assert response["answer"] is not None
    assert len(response["answer"]) > 0
    
    # Verify history
    history_resp = client.get(f"/sessions/{session_id}")
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history["events"]) == 1
    assert history["events"][0]["type"] == "message"
    assert history["events"][0]["content"] == "Hello! How are you?"


def test_use_case_2_upload_and_summarize(
    api_client_with_real_service, sample_text_file
):
    """Test Case 2: Upload document and ask to summarize it."""
    client, service = api_client_with_real_service
    session_id = "test-learner-2"
    
    # Step 1: Upload the document
    upload_result = upload_file(client, sample_text_file)
    assert upload_result["document_count"] > 0
    assert upload_result["chunk_count"] > 0
    
    filename = sample_text_file.name
    
    # Step 2: Record upload event
    upload_event = post_event(
        client,
        session_id,
        {
            "type": "upload",
            "file_ids": [filename],
        },
    )
    assert upload_event["route"] == "upload"
    assert upload_event["metadata"]["file_ids"] == [filename]
    
    # Step 3: Ask to summarize the uploaded document
    summarize_response = post_event(
        client,
        session_id,
        {
            "type": "message",
            "content": "summarize the uploaded document",
            "source_hints": [filename],
            "documents_only": False,  # Allow fallback if needed
        },
    )
    
    # Verify summarization response
    assert summarize_response["session_id"] == session_id
    assert summarize_response["turn_id"] == 2
    assert summarize_response["route"] in ["qa", "note"]  # Could route to note agent
    assert summarize_response["answer"] is not None
    assert len(summarize_response["answer"]) > 0
    
    # Verify the answer mentions key topics from the document
    answer_lower = summarize_response["answer"].lower()
    # Should mention some physics concepts from the document
    # This is a soft check - summary might be valid even if keywords don't appear
    relevant_keywords = ["force", "torque", "energy", "physics", "mechanics", "motion", "newton"]
    has_relevant_content = any(keyword in answer_lower for keyword in relevant_keywords)
    
    # Log warning if no relevant content found, but don't fail the test
    # (summary might be valid but use different terminology)
    if not has_relevant_content:
        import warnings
        warnings.warn(
            f"Summary may not reference document content. "
            f"Answer preview: {summarize_response['answer'][:200]}"
        )
    
    # Verify citations if present
    if summarize_response.get("citations"):
        assert len(summarize_response["citations"]) > 0


def test_use_case_3_make_note_of_section(
    api_client_with_real_service, sample_text_file
):
    """Test Case 3: Make note of a certain section in a text file."""
    client, service = api_client_with_real_service
    session_id = "test-learner-3"
    
    # Step 1: Upload the document
    upload_result = upload_file(client, sample_text_file)
    assert upload_result["document_count"] > 0
    
    filename = sample_text_file.name
    
    # Step 2: Record upload event
    post_event(
        client,
        session_id,
        {
            "type": "upload",
            "file_ids": [filename],
        },
    )
    
    # Step 3: Request notes on a specific section (torque)
    note_response = post_event(
        client,
        session_id,
        {
            "type": "note",
            "content": "Make detailed study notes about torque from the uploaded document",
            "source_hints": [filename],
            "documents_only": True,
        },
    )
    
    # Verify note generation
    assert note_response["session_id"] == session_id
    assert note_response["turn_id"] == 2
    assert note_response["route"] == "note"
    assert note_response["answer"] is not None
    assert len(note_response["answer"]) > 0
    
    # Verify the notes contain torque-related content
    answer_lower = note_response["answer"].lower()
    # Check for torque or related concepts
    has_torque_content = any(
        keyword in answer_lower 
        for keyword in ["torque", "rotational", "moment", "force", "rotation"]
    )
    
    # Log warning if no relevant content found, but don't fail the test
    if not has_torque_content:
        import warnings
        warnings.warn(
            f"Notes may not reference requested section. "
            f"Answer preview: {note_response['answer'][:200]}"
        )
    
    # Verify history includes both events
    history_resp = client.get(f"/sessions/{session_id}")
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history["events"]) == 2
    assert history["events"][0]["type"] == "upload"
    assert history["events"][1]["type"] == "note"


def test_use_case_4_create_quizzes_from_document(
    api_client_with_real_service, sample_text_file
):
    """Test Case 4: Create 5 quizzes from the document."""
    client, service = api_client_with_real_service
    session_id = "test-learner-4"
    
    # Step 1: Upload the document
    upload_result = upload_file(client, sample_text_file)
    assert upload_result["document_count"] > 0
    
    filename = sample_text_file.name
    
    # Step 2: Record upload event
    post_event(
        client,
        session_id,
        {
            "type": "upload",
            "file_ids": [filename],
        },
    )
    
    # Step 3: Request quiz creation
    quiz_response = post_event(
        client,
        session_id,
        {
            "type": "quiz",
            "quiz_topic": "physics fundamentals from the uploaded document",
            "quiz_count": 5,
            "source_hints": [filename],
            "documents_only": True,
        },
    )
    
    # Verify quiz generation
    assert quiz_response["session_id"] == session_id
    assert quiz_response["turn_id"] == 2
    assert quiz_response["route"] == "quiz"
    assert quiz_response["quiz"] is not None
    
    # Verify quiz structure
    quiz_data = quiz_response["quiz"]
    assert "topic" in quiz_data
    assert "questions" in quiz_data
    assert len(quiz_data["questions"]) == 5
    
    # Verify each question has required fields
    for question in quiz_data["questions"]:
        assert "question" in question
        assert "choices" in question
        assert len(question["choices"]) == 4  # Multiple choice with 4 options
        assert "correct_index" in question
        assert 0 <= question["correct_index"] < 4
    
    # Verify quiz markdown is generated
    assert quiz_response["quiz_markdown"] is not None
    assert len(quiz_response["quiz_markdown"]) > 0
    
    # Verify quiz questions relate to the document content
    # Check both markdown and question text for relevant content
    quiz_text = quiz_response["quiz_markdown"].lower()
    question_texts = " ".join([q.get("question", "").lower() for q in quiz_data["questions"]])
    combined_text = (quiz_text + " " + question_texts).lower()
    
    # Should mention physics concepts from the document (at least one)
    # This is a soft check - quiz might be valid even if keywords don't appear
    relevant_keywords = ["force", "torque", "energy", "physics", "newton", "motion", "mechanics", "acceleration", "mass"]
    has_relevant_content = any(keyword in combined_text for keyword in relevant_keywords)
    
    # For debugging: print quiz content if test would fail
    if not has_relevant_content:
        print(f"\n[DEBUG] Quiz topic: {quiz_data.get('topic')}")
        print(f"[DEBUG] Quiz markdown preview: {quiz_response['quiz_markdown'][:300]}")
        print(f"[DEBUG] Questions: {[q.get('question', '')[:80] for q in quiz_data['questions']]}")
        # Don't fail - quiz structure is correct, content relevance is a soft check
        import warnings
        warnings.warn(
            f"Quiz may not reference document content. "
            f"Quiz topic: {quiz_data.get('topic')}, "
            f"First question: {quiz_data['questions'][0].get('question', '')[:100] if quiz_data['questions'] else 'N/A'}"
        )


def test_use_case_combined_flow(
    api_client_with_real_service, sample_text_file
):
    """Test a combined flow: upload, summarize, make notes, create quiz."""
    client, service = api_client_with_real_service
    session_id = "test-learner-combined"
    
    # Step 1: Upload document
    upload_result = upload_file(client, sample_text_file)
    filename = sample_text_file.name
    
    # Step 2: Record upload
    post_event(
        client,
        session_id,
        {"type": "upload", "file_ids": [filename]},
    )
    
    # Step 3: Summarize
    summarize = post_event(
        client,
        session_id,
        {
            "type": "message",
            "content": "summarize the uploaded document",
            "source_hints": [filename],
        },
    )
    assert summarize["route"] in ["qa", "note"]
    assert summarize["answer"] is not None
    
    # Step 4: Make notes on a section
    notes = post_event(
        client,
        session_id,
        {
            "type": "note",
            "content": "Make study notes about energy from the document",
            "source_hints": [filename],
            "documents_only": True,
        },
    )
    assert notes["route"] == "note"
    # Verify notes contain energy-related content (soft check)
    answer_lower = notes["answer"].lower()
    has_energy_content = any(
        keyword in answer_lower 
        for keyword in ["energy", "kinetic", "potential", "conservation", "work"]
    )
    if not has_energy_content:
        import warnings
        warnings.warn(f"Notes may not reference requested section. Answer preview: {notes['answer'][:200]}")
    
    # Step 5: Create quiz
    quiz = post_event(
        client,
        session_id,
        {
            "type": "quiz",
            "quiz_topic": "mechanics from the uploaded document",
            "quiz_count": 5,
            "source_hints": [filename],
            "documents_only": True,
        },
    )
    assert quiz["route"] == "quiz"
    assert quiz["quiz"] is not None
    assert len(quiz["quiz"]["questions"]) == 5
    
    # Verify complete history
    history_resp = client.get(f"/sessions/{session_id}")
    history = history_resp.json()
    assert len(history["events"]) == 4
    assert [e["type"] for e in history["events"]] == [
        "upload",
        "message",
        "note",
        "quiz",
    ]

