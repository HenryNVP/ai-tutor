from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from tqdm import tqdm

from ai_tutor.config.schema import ChunkingConfig, Settings
from ai_tutor.data_models import Chunk, Document
from ai_tutor.ingestion.chunker import chunk_document
from ai_tutor.ingestion.embeddings import EmbeddingClient
from ai_tutor.ingestion.parsers import parse_path
from ai_tutor.retrieval.vector_store import VectorStore
from ai_tutor.storage import ChunkJsonlStore

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    documents: List[Document]
    chunks: List[Chunk]
    skipped: List[Path]


class IngestionPipeline:
    def __init__(
        self,
        settings: Settings,
        embedder: EmbeddingClient,
        vector_store: VectorStore,
        chunk_store: ChunkJsonlStore,
    ):
        self.settings = settings
        self.embedder = embedder
        self.vector_store = vector_store
        self.chunk_store = chunk_store

    def ingest_paths(self, paths: Iterable[Path]) -> IngestionResult:
        documents: List[Document] = []
        chunks: List[Chunk] = []
        skipped: List[Path] = []

        chunking_config: ChunkingConfig = self.settings.chunking

        for path in tqdm(list(paths), desc="Ingesting documents"):
            try:
                document = parse_path(path)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to parse %s: %s", path, exc)
                skipped.append(path)
                continue
            document.metadata.extra.setdefault("domain", self._infer_domain(path))
            documents.append(document)
            doc_chunks = chunk_document(document, chunking_config)
            chunks.extend(doc_chunks)

        if not chunks:
            return IngestionResult(documents=documents, chunks=[], skipped=skipped)

        embeddings = self.embedder.embed_documents(chunk.text for chunk in chunks)
        for chunk, embedding in zip(chunks, embeddings, strict=False):
            chunk.embedding = embedding

        self.chunk_store.upsert(chunks)
        self.vector_store.add(chunks)
        self.vector_store.persist()

        logger.info("Ingested %s documents into %s chunks.", len(documents), len(chunks))
        return IngestionResult(documents=documents, chunks=chunks, skipped=skipped)

    def _infer_domain(self, path: Path) -> str:
        lowercase = path.name.lower()
        default_domains = ["math", "physics", "cs"]
        configured_domains = getattr(
            getattr(self.settings, "course_defaults", None), "domains", None
        )
        candidates = configured_domains or default_domains
        for domain in candidates:
            if domain in lowercase:
                return domain
        return "general"
