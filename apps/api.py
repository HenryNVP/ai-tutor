"""FastAPI application exposing the AI Tutor service as a REST API."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ai_tutor.services import TutorService
from ai_tutor.system import TutorSystem

logger = logging.getLogger(__name__)


def _require_api_key() -> str:
    """Ensure an OpenAI API key is available."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Provide an API key before starting the FastAPI app."
        )
    return api_key


@lru_cache(maxsize=1)
def _get_system() -> TutorSystem:
    """Create a singleton TutorSystem instance."""
    api_key = _require_api_key()
    logger.info("Initializing TutorSystem for FastAPI service")
    return TutorSystem.from_config(api_key=api_key)


@lru_cache(maxsize=1)
def _get_service_singleton() -> TutorService:
    """Return a cached TutorService instance."""
    system = _get_system()
    return TutorService(system)


async def get_service() -> TutorService:
    """FastAPI dependency that returns the shared TutorService."""
    return _get_service_singleton()


def _serialize_tutor_response(response) -> Dict[str, Any]:
    """Convert TutorResponse into a JSON-serializable dictionary."""
    quiz_payload = response.quiz.model_dump(mode="json") if response.quiz else None
    hits_payload = [hit.model_dump(mode="json") for hit in response.hits]
    return {
        "answer": response.answer,
        "citations": response.citations,
        "style": response.style,
        "source": response.source,
        "next_topic": response.next_topic,
        "difficulty": response.difficulty,
        "hits": hits_payload,
        "quiz": quiz_payload,
    }


def _summarize_ingestion(result) -> Dict[str, Any]:
    """Summarize an IngestionResult for API responses."""
    documents = [doc.metadata.title for doc in result.documents]
    skipped = [str(path) for path in result.skipped]
    return {
        "document_count": len(result.documents),
        "chunk_count": len(result.chunks),
        "documents": documents,
        "skipped_files": skipped,
    }


class AnswerRequest(BaseModel):
    learner_id: str = Field(..., description="Learner identifier")
    question: str = Field(..., description="Student's question or prompt")
    extra_context: Optional[str] = Field(
        default=None,
        description="Optional additional context to inject into the answer",
    )


class AnswerResponse(BaseModel):
    answer: str
    citations: List[str]
    style: str
    source: Optional[str]
    next_topic: Optional[str]
    difficulty: Optional[str]
    hits: List[Dict[str, Any]]
    quiz: Optional[Dict[str, Any]]


class QuizRequest(BaseModel):
    learner_id: str
    topic: str
    num_questions: int = Field(default=4, ge=1, le=20)
    difficulty: Optional[str] = None
    extra_context: Optional[str] = None


class QuizResponse(BaseModel):
    quiz: Dict[str, Any]


class IngestResponse(BaseModel):
    document_count: int
    chunk_count: int
    documents: List[str]
    skipped_files: List[str]


app = FastAPI(
    title="AI Tutor API",
    description="REST API for the AI Tutor system",
    version="0.1.0",
)

# Enable permissive CORS by default (can be overridden via environment variable)
allow_origins = os.getenv("API_ALLOW_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allow_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup_event() -> None:
    """Warm up the TutorService singleton on startup."""
    try:
        _get_service_singleton()
        logger.info("TutorService initialized successfully")
    except Exception as exc:  # pragma: no cover - startup failures should be logged
        logger.exception("Failed to initialize TutorService: %s", exc)
        raise


@app.get("/health", summary="Health check")
async def health() -> Dict[str, str]:
    """Return service health information."""
    return {"status": "ok"}


@app.post(
    "/answer",
    response_model=AnswerResponse,
    summary="Generate an answer to a learner question",
)
async def answer_question(
    payload: AnswerRequest,
    service: TutorService = Depends(get_service),
) -> AnswerResponse:
    """Generate a personalized answer using the tutor service."""
    try:
        tutor_response = await asyncio.to_thread(
            service.answer_question,
            learner_id=payload.learner_id,
            question=payload.question,
            extra_context=payload.extra_context,
        )
    except Exception as exc:  # pragma: no cover - surface underlying error
        logger.exception("Error during answer generation: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    response_payload = _serialize_tutor_response(tutor_response)
    return AnswerResponse(**response_payload)


@app.post(
    "/quiz",
    response_model=QuizResponse,
    summary="Create a quiz for a learner",
)
async def create_quiz(
    payload: QuizRequest,
    service: TutorService = Depends(get_service),
) -> QuizResponse:
    """Generate a quiz for the given topic and learner."""
    try:
        quiz = await asyncio.to_thread(
            service.create_quiz,
            learner_id=payload.learner_id,
            topic=payload.topic,
            num_questions=payload.num_questions,
            difficulty=payload.difficulty,
            extra_context=payload.extra_context,
        )
    except Exception as exc:
        logger.exception("Error during quiz generation: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return QuizResponse(quiz=quiz.model_dump(mode="json"))


@app.post(
    "/ingest",
    response_model=IngestResponse,
    summary="Ingest uploaded documents into the tutor knowledge base",
)
async def ingest_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    service: TutorService = Depends(get_service),
) -> IngestResponse:
    """Ingest one or more uploaded documents."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    temp_dir = Path(tempfile.mkdtemp(prefix="aitutor_ingest_"))
    try:
        for upload in files:
            if not upload.filename:
                continue
            destination = temp_dir / upload.filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            contents = await upload.read()
            destination.write_bytes(contents)

        ingestion_result = await asyncio.to_thread(
            service.ingest_directory,
            temp_dir,
        )
    except Exception as exc:
        logger.exception("Error during ingestion: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        background_tasks.add_task(shutil.rmtree, temp_dir, ignore_errors=True)

    summary = _summarize_ingestion(ingestion_result)
    return IngestResponse(**summary)


@app.post(
    "/sessions/{learner_id}/reset",
    summary="Clear conversation history for a learner",
)
async def reset_session(
    learner_id: str,
    service: TutorService = Depends(get_service),
) -> Dict[str, str]:
    """Clear the conversation history for a learner."""
    try:
        await asyncio.to_thread(service.system.clear_conversation_history, learner_id)
    except Exception as exc:
        logger.exception("Error clearing conversation history: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "cleared", "learner_id": learner_id}

