from __future__ import annotations

from typing import List, Optional

from ai_tutor.data_models.session import (
    SessionEvent,
    SessionEventRequest,
    SessionResponse,
    SessionHistoryResponse,
)
from ai_tutor.services.tutor_service import TutorService


class SessionClient:
    """Lightweight client for posting session events to the tutor service."""

    def __init__(self, service: TutorService, session_id: str):
        self.service = service
        self.session_id = session_id

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
    ) -> SessionResponse:
        event = SessionEvent(
            type=event_type,  # type: ignore[arg-type]
            content=content,
            quiz_topic=quiz_topic,
            quiz_count=quiz_count,
            file_ids=file_ids,
            source_hints=source_hints,
            documents_only=documents_only,
        )
        return self.service.process_event(self.session_id, event)

    def get_history(self) -> SessionHistoryResponse:
        return self.service.get_session_history(self.session_id)

