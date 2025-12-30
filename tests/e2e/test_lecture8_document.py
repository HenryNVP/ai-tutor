"""End-to-end tests using CMPE249 Lecture8 document.

These tests verify the complete flow with a real PDF document:
- Document upload and ingestion
- Question answering (QA)
- Quiz generation
- Document summarization
- Note generation
- Complete E2E flow: greetings -> upload -> summarize -> QA -> create lesson note file -> create quizzes

Document: data/uploads/CMPE249 Lecture8 final0916.pdf
Content: Deep learning object detection (FPN, PANet, BiFPN, R-CNN, YOLO, etc.)

Main Test:
- test_lecture8_complete_flow: Full E2E workflow covering all main use cases

Note on Rate Limiting:
- These tests use the Gemini API which has rate limits (429 errors).
- If tests fail with rate limit errors, wait a few minutes between test runs.
- The tests include delays and automatic retries, but persistent 429 errors indicate
  the API key may be at its limit or burst throttling is active.

Run with: pytest tests/e2e/test_lecture8_document.py -m e2e -v
"""

from __future__ import annotations

import os
import sys
import time
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
        PROJECT_ROOT / "data" / "test" / "CMPE249 Lecture8 final0916.pdf",
        PROJECT_ROOT / "data" / "uploads" / "CMPE249 Lecture8 final0916.pdf",
        PROJECT_ROOT / "data" / "raw" / "CMPE249Fa25Shared-2025" / "CMPE249Fa25Shared" / "CMPE249 Lecture8 final0916.pdf",
    ]
    
    for pdf_path in possible_paths:
        if pdf_path.exists():
            return pdf_path
    
    # If not found, skip the test
    pytest.skip(f"Lecture8 PDF not found. Tried: {[str(p) for p in possible_paths]}")


@pytest.fixture(scope="function")
def real_service(monkeypatch, request):
    """Create a real TutorService instance for end-to-end testing."""
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY") or "test-key-placeholder"
    monkeypatch.setenv("OPENAI_API_KEY", api_key)
    monkeypatch.setenv("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    
    # Enable MCP servers for filesystem tools (write_text_file)
    # Note: For tests marked with @pytest.mark.mcp, conftest.py will handle MCP server setup
    monkeypatch.setenv("FS_MCP_USE_SERVER", "true")
    monkeypatch.setenv("FS_MCP_PORT", "8100")
    
    try:
        # Load MCP servers (including filesystem server for write_text_file tool)
        from apps.mcp import load_mcp_servers
        mcp_servers = load_mcp_servers()
        
        # Check if filesystem server is available (needed for write_text_file)
        # Only check if test is marked with @pytest.mark.mcp (real servers expected)
        if request.node.get_closest_marker("mcp"):
            if not mcp_servers or "filesystem" not in mcp_servers:
                pytest.skip(
                    "Filesystem MCP server not available. "
                    "Start it with: cd filesystem_mcp_server && python server.py"
                )
        
        system = TutorSystem.from_config(api_key=api_key, mcp_servers=mcp_servers if mcp_servers else None)
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


@pytest.mark.mcp  # Mark as MCP test to enable real MCP servers (needed for write_text_file)
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
    
    # When agent saves a file, it returns a short message with the file path
    # Check if response indicates file was saved
    answer_lower = note_response["answer"].lower()
    saved_file_path = note_response.get("saved_file_path")
    
    if saved_file_path or "saved to" in answer_lower or "data/generated" in answer_lower:
        # File was saved - verify file exists and has content
        if saved_file_path:
            file_path = Path(saved_file_path)
        else:
            # Extract path from answer message
            import re
            path_match = re.search(r'data/generated/[^\s]+', note_response["answer"])
            if path_match:
                file_path = Path(path_match.group())
            else:
                file_path = None
        
        if file_path and file_path.exists():
            file_content = file_path.read_text()
            assert len(file_content) > 100, f"Saved notes file should be substantial, got {len(file_content)} chars"
            
            # Verify the notes contain BiFPN-related content
            content_lower = file_content.lower()
            has_bifpn_content = any(
                keyword in content_lower 
                for keyword in ["bifpn", "bidirectional", "feature pyramid", "weighted fusion", "learnable weight"]
            )
            if not has_bifpn_content:
                import warnings
                warnings.warn(
                    f"Saved notes file may not reference requested section (BiFPN). "
                    f"File preview: {file_content[:300]}"
                )
        else:
            import warnings
            warnings.warn(
                f"Response indicates file was saved but file not found. "
                f"Answer: {note_response['answer']}"
            )
    else:
        # No file saved - check if answer contains notes content directly
        assert len(note_response["answer"]) > 100, "Notes should be substantial if not saved to file"
        
        # Verify the notes contain BiFPN-related content
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


@pytest.mark.mcp  # Mark as MCP test to enable real MCP servers (needed for write_text_file)
def test_lecture8_complete_flow(api_client_with_real_service, lecture8_pdf):
    """Test complete E2E flow: greetings -> upload -> summarize -> QA -> create lesson note file -> create quizzes."""
    client, service = api_client_with_real_service
    session_id = "test-lecture8-complete-flow"
    
    # Step 1: Greetings - Initial greeting message
    greeting_response = post_event(
        client,
        session_id,
        {
            "type": "message",
            "content": "Hello! I'm ready to learn about deep learning object detection.",
        },
    )
    assert greeting_response["session_id"] == session_id
    assert greeting_response["turn_id"] == 1
    assert greeting_response["answer"] is not None
    assert len(greeting_response["answer"]) > 0
    print(f"✅ Step 1 - Greetings: {greeting_response['answer'][:100]}...")
    
    # Delay after greeting to avoid burst throttling
    time.sleep(5)
    
    # Step 2: Upload document
    upload_result = upload_file(client, lecture8_pdf)
    assert upload_result["document_count"] > 0
    filename = lecture8_pdf.name
    print(f"✅ Step 2 - Upload: {upload_result['document_count']} document(s) uploaded")
    
    # Delay after upload to avoid burst throttling
    time.sleep(5)
    
    # Record upload event
    upload_event = post_event(
        client,
        session_id,
        {"type": "upload", "file_ids": [filename]},
    )
    assert upload_event["session_id"] == session_id
    assert upload_event["turn_id"] == 2
    
    # Longer delay before summarize to avoid burst throttling
    # Gemini may throttle rapid requests even with delays
    time.sleep(10)
    
    # Step 3: Summarize the uploaded document
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
    assert summarize_response["session_id"] == session_id
    assert summarize_response["turn_id"] == 3
    assert summarize_response["route"] in ["qa", "note"], \
        f"Expected route 'qa' or 'note' for summarize, got: {summarize_response['route']}"
    assert summarize_response["answer"] is not None
    
    # Handle case where agent might save a file instead of returning summary directly
    answer_lower = summarize_response["answer"].lower()
    saved_file_path = summarize_response.get("saved_file_path")
    
    if saved_file_path or "saved to" in answer_lower or "data/generated" in answer_lower:
        # Agent saved a file instead of returning summary - verify file content
        if saved_file_path:
            file_path = Path(saved_file_path)
        else:
            # Extract path from answer message
            import re
            path_match = re.search(r'data/generated/[^\s]+', summarize_response["answer"])
            if path_match:
                file_path = Path(path_match.group())
            else:
                file_path = None
        
        if file_path:
            # Make path absolute if it's relative
            if not file_path.is_absolute():
                PROJECT_ROOT = Path(__file__).resolve().parents[2]
                file_path = PROJECT_ROOT / file_path
            if file_path.exists():
                file_content = file_path.read_text()
                assert len(file_content) > 100, f"Saved summary file should be substantial, got {len(file_content)} chars"
                
                # Verify summary mentions key topics
                content_lower = file_content.lower()
                relevant_keywords = [
                    "object detection", "r-cnn", "yolo", "fpn", "bifpn", "panet",
                    "deep learning", "cnn", "feature", "pyramid", "detection"
                ]
                has_relevant_content = any(keyword in content_lower for keyword in relevant_keywords)
                if not has_relevant_content:
                    import warnings
                    warnings.warn(f"Saved summary file may not reference document content. Preview: {file_content[:200]}")
                print(f"✅ Step 3 - Summarize: Saved to file ({len(file_content)} chars), route={summarize_response['route']}")
            else:
                import warnings
                warnings.warn(f"File path extracted but file does not exist: {file_path}")
                # Fall back to checking answer length
                assert len(summarize_response["answer"]) > 50, "Summary response should be substantial"
        else:
            import warnings
            warnings.warn(f"Could not extract file path from answer: {summarize_response['answer']}")
            # Fall back to checking answer length
            assert len(summarize_response["answer"]) > 50, "Summary response should be substantial"
    else:
        # Agent returned summary directly (expected behavior)
        assert len(summarize_response["answer"]) > 100, "Summary should be substantial"
        
        # Verify summary mentions key topics
        relevant_keywords = [
            "object detection", "r-cnn", "yolo", "fpn", "bifpn", "panet",
            "deep learning", "cnn", "feature", "pyramid", "detection"
        ]
        has_relevant_content = any(keyword in answer_lower for keyword in relevant_keywords)
        if not has_relevant_content:
            import warnings
            warnings.warn(f"Summary may not reference document content. Preview: {summarize_response['answer'][:200]}")
        print(f"✅ Step 3 - Summarize: {len(summarize_response['answer'])} chars, route={summarize_response['route']}")
    
    # Delay to avoid burst throttling (Gemini may throttle rapid requests even if under per-minute limit)
    time.sleep(5)
    
    # Step 4: QA about the document
    qa_response = post_event(
        client,
        session_id,
        {
            "type": "message",
            "content": "What is BiFPN and how does weighted feature fusion work?",
            "source_hints": [filename],
            "documents_only": True,
        },
    )
    assert qa_response["session_id"] == session_id
    assert qa_response["turn_id"] == 4
    assert qa_response["route"] in ["qa", "note"], \
        f"Expected route 'qa' or 'note' for QA, got: {qa_response['route']}"
    assert qa_response["answer"] is not None
    assert len(qa_response["answer"]) > 50, "QA answer should be substantial"
    
    # Verify answer contains relevant content
    qa_answer_lower = qa_response["answer"].lower()
    qa_keywords = ["bifpn", "bidirectional", "weighted", "fusion", "feature", "learnable"]
    has_qa_content = any(keyword in qa_answer_lower for keyword in qa_keywords)
    if not has_qa_content:
        import warnings
        warnings.warn(f"QA answer may not reference document content. Preview: {qa_response['answer'][:200]}")
    print(f"✅ Step 4 - QA: {len(qa_response['answer'])} chars, route={qa_response['route']}")
    
    # Delay to avoid burst throttling
    time.sleep(5)
    
    # Step 5: Create lesson note file
    note_file_response = post_event(
        client,
        session_id,
        {
            "type": "message",
            "content": "create a lesson note file about the uploaded document",
            "source_hints": [filename],
            "documents_only": True,
        },
    )
    assert note_file_response["session_id"] == session_id
    assert note_file_response["turn_id"] == 5
    assert note_file_response["route"] == "note", \
        f"Expected route 'note' for create lesson note file, got: {note_file_response['route']}"
    assert note_file_response["answer"] is not None
    
    # Verify file was created (check for saved_file_path in response)
    saved_file_path = note_file_response.get("saved_file_path")
    if saved_file_path:
        # Verify file exists
        file_path = Path(saved_file_path)
        if not file_path.is_absolute():
            file_path = PROJECT_ROOT / file_path
        assert file_path.exists(), f"Lesson note file should exist at: {saved_file_path}"
        assert file_path.stat().st_size > 0, "Lesson note file should not be empty"
        print(f"✅ Step 5 - Lesson Note File: Created at {saved_file_path} ({file_path.stat().st_size} bytes)")
    else:
        # Check if response mentions file path
        answer_lower = note_file_response["answer"].lower()
        if "saved to" in answer_lower or "data/generated" in answer_lower:
            import warnings
            warnings.warn(
                f"Response mentions file but saved_file_path not in response. "
                f"Answer: {note_file_response['answer'][:200]}"
            )
            print(f"⚠️  Step 5 - Lesson Note File: Response mentions file but saved_file_path not found")
        else:
            import warnings
            warnings.warn(
                f"Lesson note file may not have been created. "
                f"Response: {note_file_response['answer'][:200]}"
            )
            print(f"⚠️  Step 5 - Lesson Note File: May not have been created")
    
    # Delay before quiz creation to avoid burst throttling
    time.sleep(5)
    
    # Step 6: Create quizzes
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
    assert quiz_response["session_id"] == session_id
    assert quiz_response["turn_id"] == 6
    assert quiz_response["route"] == "quiz", \
        f"Expected route 'quiz' for quiz creation, got: {quiz_response['route']}"
    assert quiz_response["quiz"] is not None
    
    # Verify quiz structure
    quiz_data = quiz_response["quiz"]
    assert "topic" in quiz_data
    assert "questions" in quiz_data
    assert len(quiz_data["questions"]) == 5, f"Expected 5 questions, got {len(quiz_data['questions'])}"
    
    # Verify each question has required fields
    for question in quiz_data["questions"]:
        assert "question" in question
        assert "choices" in question
        assert len(question["choices"]) == 4, "Each question should have 4 choices"
        assert "correct_index" in question
        assert 0 <= question["correct_index"] < 4, "correct_index should be 0-3"
    
    # Verify quiz relates to document content
    quiz_text = quiz_response.get("quiz_markdown", "").lower()
    question_texts = " ".join([q.get("question", "").lower() for q in quiz_data["questions"]])
    combined_text = (quiz_text + " " + question_texts).lower()
    
    quiz_keywords = [
        "r-cnn", "rcnn", "yolo", "ssd", "fpn", "panet", "bifpn",
        "object detection", "bounding box", "region proposal",
        "feature pyramid", "detection", "cnn"
    ]
    has_quiz_content = any(keyword in combined_text for keyword in quiz_keywords)
    if not has_quiz_content:
        import warnings
        warnings.warn(
            f"Quiz may not reference document content. "
            f"Topic: {quiz_data.get('topic')}, "
            f"First question: {quiz_data['questions'][0].get('question', '')[:100] if quiz_data['questions'] else 'N/A'}"
        )
    print(f"✅ Step 6 - Quiz: {len(quiz_data['questions'])} questions generated")
    
    # Verify complete history
    history_resp = client.get(f"/sessions/{session_id}")
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history["events"]) == 6, f"Expected 6 events, got {len(history['events'])}"
    assert [e["type"] for e in history["events"]] == [
        "message",  # Greetings
        "upload",
        "message",  # Summarize
        "message",  # QA
        "message",  # Create lesson note file
        "quiz",
    ]
    print(f"✅ Complete flow verified: {len(history['events'])} events in session history")


def test_lecture8_combined_flow(api_client_with_real_service, lecture8_pdf):
    """Test combined flow: upload, QA, summarize, notes, quiz (legacy test)."""
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

