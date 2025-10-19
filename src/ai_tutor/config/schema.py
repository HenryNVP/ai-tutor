from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class ModelConfig(BaseModel):
    name: str = Field(..., description="LLM identifier.")
    provider: str = Field("litellm", description="Provider backend to use.")
    temperature: float = Field(0.2, ge=0, le=2)
    max_output_tokens: int = Field(1024, ge=64)
    mode: str = Field("chat", description="chat or completion style.")


class EmbeddingConfig(BaseModel):
    model: str = Field(..., description="Embedding model identifier.")
    provider: str = Field("sentence-transformers", description="Embedding backend.")
    batch_size: int = Field(32, ge=1)
    normalize: bool = True
    dimension: int | None = Field(
        default=None,
        ge=1,
        description="Optional embedding dimensionality override (provider-specific).",
    )


class ChunkingConfig(BaseModel):
    chunk_size: int = Field(800, ge=100)
    chunk_overlap: int = Field(120, ge=0)
    tokenizer: str | None = Field(
        None, description="Optional tokenizer name (transformers-style)."
    )

    @validator("chunk_overlap")
    def overlap_less_than_chunk(cls, value: int, values: dict[str, int]) -> int:
        chunk_size = values.get("chunk_size", 800)
        if value >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return value


class RetrievalConfig(BaseModel):
    top_k: int = Field(8, ge=1)


class PathsConfig(BaseModel):
    raw_data_dir: Path = Field(Path("data/raw"))
    processed_data_dir: Path = Field(Path("data/processed"))
    vector_store_dir: Path = Field(Path("data/vector_store"))
    chunks_index: Path = Field(Path("data/processed/chunks.jsonl"))
    logs_dir: Path = Field(Path("logs"))


class LoggingConfig(BaseModel):
    level: str = Field("INFO")
    json: bool = False


class Settings(BaseModel):
    project_name: str = Field("Personal STEM Instructor")
    model: ModelConfig
    embeddings: EmbeddingConfig
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @validator("paths")
    def ensure_paths_are_dirs(cls, value: PathsConfig) -> PathsConfig:
        return value
