from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """Metadata describing a raw document that has been parsed into the system."""

    doc_id: str
    title: str
    source_path: Path
    domain: str = "general"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    extra: Dict[str, Any] = Field(default_factory=dict)


class Document(BaseModel):
    """Parsed document containing plain text and optional page mapping."""

    metadata: DocumentMetadata
    text: str
    page_map: Dict[int, str] = Field(
        default_factory=dict, description="Map of chunk index to page label."
    )


class ChunkMetadata(BaseModel):
    """Metadata for an individual chunk derived from a document."""

    chunk_id: str
    doc_id: str
    title: str
    page: Optional[str] = None
    section: Optional[str] = None
    domain: str = "general"
    source_path: Path


class Chunk(BaseModel):
    """Chunk of text ready for embedding and retrieval."""

    metadata: ChunkMetadata
    text: str
    embedding: Optional[list[float]] = None
    token_count: Optional[int] = None


class RetrievalHit(BaseModel):
    """Result returned by vector search, pairing a chunk with its similarity score."""

    chunk: Chunk
    score: float


class Query(BaseModel):
    """Learner question or statement to embed for retrieval."""

    text: str
    domain: Optional[str] = None
