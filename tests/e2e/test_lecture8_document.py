"""End-to-end tests using CMPE249 Lecture8 document.

These tests verify the complete flow with a real PDF document:
- Document upload and ingestion
- Question answering (QA)
- Quiz generation
- Document summarization
- Note generation

Document: data/uploads/CMPE249 Lecture8 final0916.pdf
Content: Deep learning object detection (FPN, PANet, BiFPN, R-CNN, YOLO, etc.)

Run with: pytest tests/e2e/test_lecture8_document.py -m e2e -v
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, Any

import pytest

# Mark as E2E test - requires full system
pytestmark = pytest.mark.e2e

# Skip if fastapi not available
try:
    from fastapi.testclient import TestClient
except ImportError:
    pytest.skip("fastapi not installed", allow_module_level=True)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
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
def lecture8_pdf():
    """Fixture for the Lecture8 PDF document."""
    # Try multiple possible locations
    possible_paths = [
        PROJECT_ROOT / "data" / "uploads" / "CMPE249 Lecture8 final0916.pdf",
        PROJECT_ROOT / "data" / "raw" / "CMPE249Fa25Shared-2025" / "CMPE249Fa25Shared" / "CMPE249 Lecture8 final0916.pdf",
    ]
    
    for pdf_path in possible_paths:
        if pdf_path.exists():
            return pdf_path
    
    # If not found, skip the test
    pytest.skip(f"Lecture8 PDF not found. Tried: {[str(p) for p in possible_paths]}")


@pytest.fixture(scope="function")
def real_service(monkeypatch):
    """Create a real TutorService instance for end-to-end testing."""
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY") or "test-key-placeholder"
    monkeypatch.setenv("OPENAI_API_KEY", api_key)
    monkeypatch.setenv("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    
    try:
        system = TutorSystem.from_config(api_key=api_key)
        return TutorService(system)
    except Exception as e:
        pytest.skip(f"Failed to initialize TutorSystem: {e}. "
                   f"These tests require proper configuration and API keys.")


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
        files = [("files", (file_path.name, f.read(), "application/pdf"))]
        response = client.post("/ingest", files=files)
    assert response.status_code == 200, f"Upload failed: {response.text}"
    return response.json()


def test_lecture8_qa_questions(api_client_with_real_service, lecture8_pdf):
    """Test Case: QA - Ask questions about the Lecture8 document content."""
    client, service = api_client_with_real_service
    session_id = "test-lecture8-qa"
    
    # Step 1: Upload the document
    upload_result = upload_file(client, lecture8_pdf)
    assert upload_result["document_count"] > 0
    # In demo mode, chunk_count will be 0 (documents are cached, not chunked)
    # Check document_count instead, which should always be > 0 if upload succeeded
    if upload_result.get("chunk_count", 0) == 0:
        # Demo mode: documents cached but not chunked - this is expected
        print("Note: Demo mode detected - documents cached but not chunked")
    
    filename = lecture8_pdf.name
    
    # Step 2: Record upload event
    post_event(
        client,
        session_id,
        {
            "type": "upload",
            "file_ids": [filename],
        },
    )
    
    # Step 3: Ask questions about the document content
    qa_questions = [
        "What is BiFPN?",
        "How does R-CNN work?",
        "What is the difference between FPN and PANet?",
        "Explain weighted feature fusion in BiFPN",
    ]
    
    for i, question in enumerate(qa_questions, start=2):
        qa_response = post_event(
            client,
            session_id,
            {
                "type": "message",
                "content": question,
                "source_hints": [filename],
                "documents_only": True,
            },
        )
        
        # Verify QA response
        assert qa_response["session_id"] == session_id
        assert qa_response["turn_id"] == i
        # Questions should route to QA, not ingestion (content questions should not trigger ingestion)
        assert qa_response["route"] != "ingestion", \
            f"Question '{question}' should not route to ingestion (it's a content question)"
        assert qa_response["route"] in ["qa", "note"], \
            f"Expected route 'qa' or 'note' for question: {question}, got: {qa_response['route']}"
        assert qa_response["answer"] is not None
        assert len(qa_response["answer"]) > 50, f"Answer too short for: {question}"
        
        # Verify answer contains relevant content (soft check)
        answer_lower = qa_response["answer"].lower()
        # Check for relevant keywords based on question
        if "bifpn" in question.lower():
            relevant_keywords = ["bifpn", "bidirectional", "feature", "pyramid", "weighted", "fusion"]
        elif "r-cnn" in question.lower() or "rcnn" in question.lower():
            relevant_keywords = ["r-cnn", "region", "proposal", "cnn", "bounding", "box"]
        elif "fpn" in question.lower() and "panet" in question.lower():
            relevant_keywords = ["fpn", "panet", "top-down", "bottom-up", "path"]
        elif "weighted" in question.lower() or "fusion" in question.lower():
            relevant_keywords = ["weighted", "fusion", "learnable", "weight", "normalize"]
        else:
            relevant_keywords = ["feature", "network", "detection"]
        
        has_relevant_content = any(keyword in answer_lower for keyword in relevant_keywords)
        
        if not has_relevant_content:
            import warnings
            warnings.warn(
                f"QA answer may not reference document content for: {question}\n"
                f"Answer preview: {qa_response['answer'][:200]}"
            )
        
        # Verify citations if present
        if qa_response.get("citations"):
            assert len(qa_response["citations"]) > 0


def test_lecture8_quiz_generation(api_client_with_real_service, lecture8_pdf):
    """Test Case: Generate quiz from Lecture8 document."""
    client, service = api_client_with_real_service
    session_id = "test-lecture8-quiz"
    
    # Step 1: Upload the document
    upload_result = upload_file(client, lecture8_pdf)
    assert upload_result["document_count"] > 0
    
    filename = lecture8_pdf.name
    
    # Step 2: Record upload event
    post_event(
        client,
        session_id,
        {
            "type": "upload",
            "file_ids": [filename],
        },
    )
    
    # Step 3: Request quiz creation on object detection topics
    quiz_response = post_event(
        client,
        session_id,
        {
            "type": "quiz",
            "quiz_topic": "object detection methods from the uploaded document",
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
    
    # Verify quiz questions relate to object detection content
    quiz_text = quiz_response["quiz_markdown"].lower()
    question_texts = " ".join([q.get("question", "").lower() for q in quiz_data["questions"]])
    combined_text = (quiz_text + " " + question_texts).lower()
    
    # Should mention object detection concepts from the document
    relevant_keywords = [
        "r-cnn", "rcnn", "yolo", "ssd", "fpn", "panet", "bifpn",
        "object detection", "bounding box", "region proposal",
        "feature pyramid", "detection", "cnn"
    ]
    has_relevant_content = any(keyword in combined_text for keyword in relevant_keywords)
    
    if not has_relevant_content:
        import warnings
        warnings.warn(
            f"Quiz may not reference document content. "
            f"Quiz topic: {quiz_data.get('topic')}, "
            f"First question: {quiz_data['questions'][0].get('question', '')[:100] if quiz_data['questions'] else 'N/A'}"
        )


def test_lecture8_summarize(api_client_with_real_service, lecture8_pdf):
    """Test Case: Summarize the Lecture8 document."""
    client, service = api_client_with_real_service
    session_id = "test-lecture8-summarize"
    
    # Step 1: Upload the document
    upload_result = upload_file(client, lecture8_pdf)
    assert upload_result["document_count"] > 0
    
    filename = lecture8_pdf.name
    
    # Step 2: Record upload event
    post_event(
        client,
        session_id,
        {
            "type": "upload",
            "file_ids": [filename],
        },
    )
    
    # Step 3: Request summary
    summarize_response = post_event(
        client,
        session_id,
        {
            "type": "message",
            "content": "summarize the uploaded document",
            "source_hints": [filename],
            "documents_only": True,
        },
    )
    
    # Verify summarization response
    assert summarize_response["session_id"] == session_id
    assert summarize_response["turn_id"] == 2
    assert summarize_response["route"] in ["qa", "note"]  # Could route to note agent
    assert summarize_response["answer"] is not None
    assert len(summarize_response["answer"]) > 100, "Summary should be substantial"
    
    # Verify the answer mentions key topics from the document
    answer_lower = summarize_response["answer"].lower()
    # Should mention some object detection concepts
    relevant_keywords = [
        "object detection", "r-cnn", "yolo", "fpn", "bifpn", "panet",
        "deep learning", "cnn", "feature", "pyramid", "detection"
    ]
    has_relevant_content = any(keyword in answer_lower for keyword in relevant_keywords)
    
    if not has_relevant_content:
        import warnings
        warnings.warn(
            f"Summary may not reference document content. "
            f"Answer preview: {summarize_response['answer'][:300]}"
        )
    
    # Verify citations if present
    if summarize_response.get("citations"):
        assert len(summarize_response["citations"]) > 0


def test_lecture8_note_generation(api_client_with_real_service, lecture8_pdf):
    """Test Case: Generate notes from Lecture8 document."""
    client, service = api_client_with_real_service
    session_id = "test-lecture8-notes"
    
    # Step 1: Upload the document
    upload_result = upload_file(client, lecture8_pdf)
    assert upload_result["document_count"] > 0
    
    filename = lecture8_pdf.name
    
    # Step 2: Record upload event
    post_event(
        client,
        session_id,
        {
            "type": "upload",
            "file_ids": [filename],
        },
    )
    
    # Step 3: Request notes on BiFPN section
    note_response = post_event(
        client,
        session_id,
        {
            "type": "note",
            "content": "Make detailed study notes about BiFPN (Bidirectional Feature Pyramid Network) from the uploaded document",
            "source_hints": [filename],
            "documents_only": True,
        },
    )
    
    # Verify note generation
    assert note_response["session_id"] == session_id
    assert note_response["turn_id"] == 2
    assert note_response["route"] == "note"
    assert note_response["answer"] is not None
    assert len(note_response["answer"]) > 100, "Notes should be substantial"
    
    # Verify the notes contain BiFPN-related content
    answer_lower = note_response["answer"].lower()
    # Check for BiFPN or related concepts
    has_bifpn_content = any(
        keyword in answer_lower 
        for keyword in ["bifpn", "bidirectional", "feature pyramid", "weighted fusion", "learnable weight"]
    )
    
    if not has_bifpn_content:
        import warnings
        warnings.warn(
            f"Notes may not reference requested section (BiFPN). "
            f"Answer preview: {note_response['answer'][:300]}"
        )
    
    # Verify history includes both events
    history_resp = client.get(f"/sessions/{session_id}")
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history["events"]) == 2
    assert history["events"][0]["type"] == "upload"
    assert history["events"][1]["type"] == "note"


def test_lecture8_combined_flow(api_client_with_real_service, lecture8_pdf):
    """Test combined flow: upload, QA, summarize, notes, quiz."""
    client, service = api_client_with_real_service
    session_id = "test-lecture8-combined"
    
    # Step 1: Upload document
    upload_result = upload_file(client, lecture8_pdf)
    filename = lecture8_pdf.name
    
    # Step 2: Record upload
    post_event(
        client,
        session_id,
        {"type": "upload", "file_ids": [filename]},
    )
    
    # Step 3: QA - Ask about R-CNN
    qa_response = post_event(
        client,
        session_id,
        {
            "type": "message",
            "content": "What is R-CNN and how does it work?",
            "source_hints": [filename],
            "documents_only": True,
        },
    )
    assert qa_response["route"] == "qa"
    assert qa_response["answer"] is not None
    
    # Step 4: Summarize
    summarize = post_event(
        client,
        session_id,
        {
            "type": "message",
            "content": "summarize the uploaded document",
            "source_hints": [filename],
            "documents_only": True,
        },
    )
    assert summarize["route"] in ["qa", "note"]
    assert summarize["answer"] is not None
    
    # Step 5: Make notes on FPN
    notes = post_event(
        client,
        session_id,
        {
            "type": "note",
            "content": "Make study notes about Feature Pyramid Networks (FPN) from the document",
            "source_hints": [filename],
            "documents_only": True,
        },
    )
    assert notes["route"] == "note"
    assert notes["answer"] is not None
    
    # Step 6: Create quiz
    quiz = post_event(
        client,
        session_id,
        {
            "type": "quiz",
            "quiz_topic": "object detection methods from the uploaded document",
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
    assert len(history["events"]) == 5
    assert [e["type"] for e in history["events"]] == [
        "upload",
        "message",  # QA
        "message",  # Summarize
        "note",
        "quiz",
    ]

