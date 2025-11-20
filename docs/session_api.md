## Session API Design

This document outlines the contract for the new session-based interface that replaces ad-hoc UI → service calls. It enables multiple clients (Streamlit, React, CLI, Slack bot) to share the same conversational API while keeping all orchestration in the backend.

### Concepts

- **Session**: Logical conversation identified by `{learner_id}`. We reuse `TutorAgent`'s existing session rotation to prevent token bloat.
- **Event**: A single client action: message, upload reference, quiz request, note request, etc.
- **Response**: Structured output for that turn (answer text, route used, citations, quiz payload).

### Routes

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/sessions/{learner_id}/events` | Submit a new `SessionEvent` and receive a `SessionResponse` describing how the system handled it. |
| `GET` | `/sessions/{learner_id}` | Retrieve the chronological list of `SessionEvent`s for display/debug/testing. Does **not** replay TutorResponses. |

### Pydantic models

```python
class SessionEvent(BaseModel):
    type: Literal["message", "upload", "quiz", "note"]
    content: Optional[str]
    quiz_topic: Optional[str]
    quiz_count: Optional[int]
    file_ids: Optional[List[str]]
    source_hints: Optional[List[str]]
    documents_only: bool = False

class SessionEventRequest(BaseModel):
    session_id: str  # Typically learner_id
    event: SessionEvent

class SessionResponse(BaseModel):
    session_id: str
    turn_id: int
    route: str
    answer: Optional[str]
    citations: List[str] = []
    source: Optional[str]
    quiz: Optional[Dict[str, Any]]
    metadata: Dict[str, Any] = {}

class SessionHistoryResponse(BaseModel):
    session_id: str
    events: List[SessionEvent]
```

### Flow

1. Client posts `/sessions/{learner_id}/events` with the next event.
2. API calls `TutorService.process_event`, which:
   - Persists the event (optional)
   - Routes to `TutorAgent` with inline context/source hints
   - Produces a `SessionResponse` (route taken, answer text, quiz data, etc.)
3. Client renders the response and optionally polls `/sessions/{learner_id}` to show chronological context.

### Testing

- Unit tests for model validation and route handlers.
- Integration test covering multi-step session (greeting → question → doc request → note → quiz) via the REST API with mocked agents.

### Future work

- WebSocket `/sessions/{learner_id}/stream` for real-time updates.
- Persisted event log for analytics/replay.
- Pluggable auth per session.

