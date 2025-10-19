from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel, Field, validator


class ModelConfig(BaseModel):
    """Model-level settings for the chat LLM used during tutoring."""

    name: str = Field(..., description="LLM identifier.")
    provider: str = Field("litellm", description="Provider backend to use.")
    temperature: float = Field(0.2, ge=0, le=2)
    max_output_tokens: int = Field(1024, ge=64)
    mode: str = Field("chat", description="chat or completion style.")


class EmbeddingConfig(BaseModel):
    """Configuration describing which embedding provider and parameters to use."""

    model: str = Field(..., description="Embedding model identifier.")
    provider: str = Field("sentence-transformers", description="Embedding backend (sentence-transformers only).")
    batch_size: int = Field(32, ge=1)
    normalize: bool = True
    dimension: int | None = Field(
        default=None,
        ge=1,
        description="Optional embedding dimensionality override (provider-specific).",
    )


class ChunkingConfig(BaseModel):
    """Chunking strategy for turning parsed documents into retrieval-friendly segments."""

    chunk_size: int = Field(800, ge=100)
    chunk_overlap: int = Field(120, ge=0)
    tokenizer: str | None = Field(
        None, description="Optional tokenizer name (transformers-style)."
    )

    @validator("chunk_overlap")
    def overlap_less_than_chunk(cls, value: int, values: dict[str, int]) -> int:
        """Ensure chunk overlap never equals or exceeds the chunk size."""
        chunk_size = values.get("chunk_size", 800)
        if value >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return value


class RetrievalConfig(BaseModel):
    """Retrieve-time controls such as top-k depth."""

    top_k: int = Field(8, ge=1)


class PathsConfig(BaseModel):
    """Filesystem layout for raw data, processed artifacts, and logs."""

    raw_data_dir: Path = Field(Path("data/raw"))
    processed_data_dir: Path = Field(Path("data/processed"))
    vector_store_dir: Path = Field(Path("data/vector_store"))
    chunks_index: Path = Field(Path("data/processed/chunks.jsonl"))
    logs_dir: Path = Field(Path("logs"))


class LoggingConfig(BaseModel):
    """Controls for tutor logging output and format."""

    level: str = Field("INFO")
    json: bool = False


class Settings(BaseModel):
    """Top-level project configuration aggregating all sub-settings."""

    project_name: str = Field("Personal STEM Instructor")
    model: ModelConfig
    embeddings: EmbeddingConfig
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @validator("paths")
    def ensure_paths_are_dirs(cls, value: PathsConfig) -> PathsConfig:
        """Return the paths config unchanged; kept for symmetry and future validation."""
        return value
