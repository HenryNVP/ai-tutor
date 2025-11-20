from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class SessionEvent(BaseModel):
    type: Literal["message", "upload", "quiz", "note", "quiz_submission"]
    content: Optional[str] = Field(default=None, description="User text payload")
    quiz_topic: Optional[str] = Field(default=None, description="Topic for quiz events")
    quiz_count: Optional[int] = Field(default=None, description="Requested number of questions")
    file_ids: Optional[List[str]] = Field(default=None, description="Uploaded file identifiers")
    source_hints: Optional[List[str]] = Field(default=None, description="Document names to prioritize")
    documents_only: bool = Field(default=False, description="Restrict processing to uploaded docs only")
    quiz: Optional[Dict[str, Any]] = Field(default=None, description="Serialized quiz payload")
    answers: Optional[List[int]] = Field(default=None, description="Selected quiz answers (0-indexed)")


class SessionEventRequest(BaseModel):
    session_id: str = Field(..., description="Learner/session identifier")
    event: SessionEvent


class SessionResponse(BaseModel):
    session_id: str
    turn_id: int
    route: str
    answer: Optional[str]
    citations: List[str] = Field(default_factory=list)
    source: Optional[str]
    quiz: Optional[Dict[str, Any]]
    quiz_markdown: Optional[str] = Field(default=None, description="Rendered quiz markdown")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionHistoryResponse(BaseModel):
    session_id: str
    events: List[SessionEvent]
    responses: List[SessionResponse] = Field(default_factory=list)

