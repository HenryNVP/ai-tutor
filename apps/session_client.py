from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence
from pathlib import Path
import os

import requests

from ai_tutor.data_models.session import SessionResponse, SessionHistoryResponse


DEFAULT_SESSION_TIMEOUT = float(os.getenv("SESSION_HTTP_TIMEOUT", "90"))


class SessionClient:
    """HTTP client for interacting with the FastAPI session endpoints."""

    def __init__(
        self,
        *,
        api_base_url: str,
        session_id: str,
        timeout: Optional[float] = None,
    ):
        self.base_url = api_base_url.rstrip("/")
        self.session_id = session_id
        self._timeout = timeout or DEFAULT_SESSION_TIMEOUT
        self._http = requests.Session()

    def post_event(
        self,
        *,
        event_type: str,
        content: Optional[str] = None,
        quiz_topic: Optional[str] = None,
        quiz_count: Optional[int] = None,
        file_ids: Optional[List[str]] = None,
        source_hints: Optional[List[str]] = None,
        documents_only: bool = False,
        csv_filename: Optional[str] = None,
    ) -> SessionResponse:
        url = f"{self.base_url}/sessions/{self.session_id}/events"
        payload = {
            "session_id": self.session_id,
            "event": {
                "type": event_type,
                "content": content,
                "quiz_topic": quiz_topic,
                "quiz_count": quiz_count,
                "file_ids": file_ids,
                "source_hints": source_hints,
                "documents_only": documents_only,
                "csv_filename": csv_filename,
            },
        }
        response = self._http.post(url, json=payload, timeout=self._timeout)
        response.raise_for_status()
        return SessionResponse.model_validate(response.json())

    def get_history(self) -> SessionHistoryResponse:
        url = f"{self.base_url}/sessions/{self.session_id}"
        response = self._http.get(url, timeout=self._timeout)
        response.raise_for_status()
        return SessionHistoryResponse.model_validate(response.json())

    def ingest_files(self, paths: Sequence[Path]) -> Dict[str, Any]:
        """Upload documents to the backend for ingestion."""
        if not paths:
            return {}
        files: List[tuple[str, tuple[str, bytes, str]]] = []
        for path in paths:
            data = path.read_bytes()
            files.append(
                (
                    "files",
                    (
                        path.name,
                        data,
                        "application/octet-stream",
                    ),
                )
            )
        url = f"{self.base_url}/ingest"
        response = self._http.post(url, files=files, timeout=self._timeout)
        response.raise_for_status()
        return response.json()

    def submit_quiz(self, quiz_payload, answers: List[int]) -> SessionResponse:
        """Send quiz submission through the session API."""
        url = f"{self.base_url}/sessions/{self.session_id}/events"
        event = {
            "type": "quiz_submission",
            "quiz": quiz_payload,
            "answers": answers,
        }
        payload = {
            "session_id": self.session_id,
            "event": event,
        }
        response = self._http.post(url, json=payload, timeout=self._timeout)
        response.raise_for_status()
        return SessionResponse.model_validate(response.json())

