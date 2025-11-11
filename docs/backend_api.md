# FastAPI Backend

The AI Tutor exposes a lightweight REST API alongside the Streamlit UI for integrating the tutoring features into other applications.

## Quick Start

```bash
uvicorn apps.api:app --reload --port 8080
```

Environment requirements:
- `OPENAI_API_KEY` must be set before starting the server
- Optional CORS origins via `API_ALLOW_ORIGINS` (defaults to `*`)

## Shared Service Layer

The API reuses the same `TutorService` singleton as the Streamlit app, so vector stores, MCP connections, and cached tools stay in sync across interfaces.

## Endpoints

### `GET /health`
Simple health check to confirm the server is running.

### `POST /answer`
Generate a cited answer to a learner question.

**Request body**
```json
{
  "learner_id": "student123",
  "question": "Explain the Bernoulli equation",
  "extra_context": "Optional context string"
}
```

**Response body**
```json
{
  "answer": "...",
  "citations": ["[1] ..."],
  "style": "concise",
  "source": "local",
  "next_topic": null,
  "difficulty": null,
  "hits": [...],
  "quiz": null
}
```

### `POST /quiz`
Create a multiple-choice quiz.

**Request body**
```json
{
  "learner_id": "student123",
  "topic": "neural networks",
  "num_questions": 8,
  "difficulty": null,
  "extra_context": null
}
```

**Response body**
```json
{
  "quiz": {
    "topic": "neural networks",
    "questions": [...]
  }
}
```

### `POST /ingest`
Upload one or more documents for ingestion.

Multipart form request with `files` entries (PDF, TXT, MD). Documents are stored temporarily, processed, and summarized.

**Response body**
```json
{
  "document_count": 2,
  "chunk_count": 540,
  "documents": ["Lecture 1", "Lecture 2"],
  "skipped_files": []
}
```

### `POST /sessions/{learner_id}/reset`
Clear conversation history for a learner. Useful when starting a new tutoring session via the API.

**Response body**
```json
{
  "status": "cleared",
  "learner_id": "student123"
}
```

## Error Handling

All endpoints return standard HTTP error codes (4xx/5xx) with JSON payloads containing a `detail` field describing the issue.

## Notes

- Heavy operations (retrieval, ingestion) are offloaded to thread workers so the FastAPI event loop stays responsive.
- The same generated files manager used in Streamlit can be recreated externally by storing the response payloads (answers, quizzes, ingestion summaries) as needed.
