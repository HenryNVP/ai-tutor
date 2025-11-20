from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import sys

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.api import app, get_service
from ai_tutor.data_models.session import (
    SessionEvent,
    SessionResponse,
    SessionHistoryResponse,
)


class FakeTutorService:
    """Deterministic stub to exercise session routes without external dependencies."""

    def __init__(self) -> None:
        self.events: Dict[str, List[SessionEvent]] = {}
        self.responses: Dict[str, List[SessionResponse]] = {}

    def process_event(self, session_id: str, event: SessionEvent) -> SessionResponse:
        history = self.events.setdefault(session_id, [])
        history.append(event)
        turn_id = len(history)

        route = self._route_for_event(event)
        answer = f"{route.upper()} response for turn {turn_id}"
        metadata: Dict[str, Any] = {"event_type": event.type}
        if event.type == "upload" and event.file_ids:
            metadata["file_ids"] = event.file_ids
        response = SessionResponse(
            session_id=session_id,
            turn_id=turn_id,
            route=route,
            answer=answer,
            citations=[f"[{turn_id}]"],
            source="local" if route != "upload" else "upload",
            quiz={"topic": "physics", "questions": []} if route == "quiz" else None,
            metadata=metadata,
        )
        self.responses.setdefault(session_id, []).append(response)
        return response

    def get_session_history(self, session_id: str) -> SessionHistoryResponse:
        return SessionHistoryResponse(
            session_id=session_id,
            events=self.events.get(session_id, []),
            responses=self.responses.get(session_id, []),
        )

    @staticmethod
    def _route_for_event(event: SessionEvent) -> str:
        if event.type == "upload":
            return "upload"
        content = (event.content or "").lower()
        if event.type == "quiz" or "quiz" in content:
            return "quiz"
        note_keywords = ["summarize", "summary", "study notes", "make notes", "note topic"]
        if event.type == "note" or any(f" {kw}" in f" {content}" for kw in note_keywords):
            return "note"
        return "qa"


@pytest.fixture()
def api_client():
    fake_service = FakeTutorService()
    app.dependency_overrides[get_service] = lambda: fake_service
    with TestClient(app) as client:
        yield client, fake_service
    app.dependency_overrides.clear()


def post_event(client: TestClient, session_id: str, event_payload: Dict[str, Any]):
    response = client.post(
        f"/sessions/{session_id}/events",
        json={"session_id": session_id, "event": event_payload},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_full_session_flow(api_client):
    client, _ = api_client
    session_id = "learner-123"

    steps = [
        ({"type": "message", "content": "Hello tutor!"}, "qa"),
        ({"type": "message", "content": "Explain Newton's second law."}, "qa"),
        (
            {"type": "upload", "file_ids": ["physics_notes.pdf"]},
            "upload",
        ),
        (
            {
                "type": "message",
                "content": "From physics_notes.pdf, what is torque definition?",
                "source_hints": ["physics_notes.pdf"],
                "documents_only": True,
            },
            "qa",
        ),
        (
            {
                "type": "note",
                "content": "Summarize the uploaded physics notes.",
                "source_hints": ["physics_notes.pdf"],
            },
            "note",
        ),
        (
            {
                "type": "note",
                "content": "Make detailed study notes on torque from the document.",
                "source_hints": ["physics_notes.pdf"],
                "documents_only": True,
            },
            "note",
        ),
        (
            {
                "type": "quiz",
                "quiz_topic": "torque in physics",
                "quiz_count": 5,
                "source_hints": ["physics_notes.pdf"],
                "documents_only": True,
            },
            "quiz",
        ),
    ]

    routes_seen = []
    for event_payload, expected_route in steps:
        response = post_event(client, session_id, event_payload)
        routes_seen.append(response["route"])
        assert response["route"] == expected_route
        assert response["turn_id"] == len(routes_seen)

    history_resp = client.get(f"/sessions/{session_id}")
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history["events"]) == len(steps)
    assert len(history["responses"]) == len(steps)
    assert [evt["type"] for evt in history["events"]] == [step[0]["type"] for step in steps]
    assert [resp["route"] for resp in history["responses"]] == routes_seen


def test_upload_event_metadata(api_client):
    client, _ = api_client
    session_id = "learner-xyz"
    payload = {
        "session_id": session_id,
        "event": {"type": "upload", "file_ids": ["docA.pdf", "docB.pdf"]},
    }
    response = client.post(f"/sessions/{session_id}/events", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["route"] == "upload"
    assert data["metadata"]["file_ids"] == ["docA.pdf", "docB.pdf"]

