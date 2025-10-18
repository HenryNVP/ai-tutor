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
    initial_k: int = Field(20, ge=1)
    top_k: int = Field(8, ge=1)
    min_score: float = Field(0.25, ge=0.0, le=1.0)
    rerank_top_k: int = Field(0, ge=0)


class GuardrailConfig(BaseModel):
    min_hits: int = Field(2, ge=0)
    min_score: float = Field(0.35, ge=0.0, le=1.0)
    academic_integrity_mode: str = Field("learning")
    blocked_topics: List[str] = Field(
        default_factory=lambda: ["violence", "adult content", "illicit behavior"]
    )


class SearchToolConfig(BaseModel):
    enabled: bool = True
    min_hits_before_search: int = Field(1, ge=0)
    provider: str = Field("tavily", description="Search tool provider identifier.")
    max_results: int = Field(5, ge=1)


class CourseDefaults(BaseModel):
    weeks: int = Field(12, ge=1)
    lessons_per_week: int = Field(3, ge=1)
    assessment_frequency: int = Field(2, ge=1)
    domains: List[str] = Field(default_factory=lambda: ["math", "physics", "cs"])


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
    guardrails: GuardrailConfig = Field(default_factory=GuardrailConfig)
    search_tool: SearchToolConfig = Field(default_factory=SearchToolConfig)
    course_defaults: CourseDefaults = Field(default_factory=CourseDefaults)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @validator("paths")
    def ensure_paths_are_dirs(cls, value: PathsConfig) -> PathsConfig:
        return value
