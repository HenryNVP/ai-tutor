from __future__ import annotations

import hashlib
import math
from typing import Iterable, List, Tuple

from ai_tutor.config.schema import ChunkingConfig
from ai_tutor.data_models import Chunk, ChunkMetadata, Document


def _hash_chunk(text: str, doc_id: str, index: int) -> str:
    """Create a deterministic identifier for a chunk based on its text and source."""
    digest = hashlib.sha1(f"{doc_id}:{index}:{text[:100]}".encode("utf-8")).hexdigest()
    return f"{doc_id}-{index}-{digest[:8]}"


def _word_chunks(words: List[str], chunk_size: int, overlap: int) -> Iterable[Tuple[int, List[str]]]:
    """Yield windowed word slices along with their sequential chunk indices."""
    step = chunk_size - overlap
    if step <= 0:
        step = chunk_size
    for idx in range(0, len(words), step):
        yield idx // step, words[idx : idx + chunk_size]


def chunk_document(document: Document, config: ChunkingConfig) -> List[Chunk]:
    """
    Split a parsed document into overlapping text chunks ready for embedding.

    Slides a fixed-size word window across the document, assigns hashed chunk IDs, infers
    approximate page labels when available, and returns a list of `Chunk` objects with metadata.
    """
    words = document.text.split()
    chunks: List[Chunk] = []
    for chunk_index, chunk_words in _word_chunks(
        words, config.chunk_size, config.chunk_overlap
    ):
        chunk_text = " ".join(chunk_words).strip()
        if not chunk_text:
            continue
        chunk_id = _hash_chunk(chunk_text, document.metadata.doc_id, chunk_index)
        page_label = None
        if document.page_map:
            approx_word_start = chunk_index * (config.chunk_size - config.chunk_overlap)
            total_pages = len(document.page_map)
            approx_page = (
                math.floor(approx_word_start / max(len(words), 1) * total_pages) + 1
            )
            page_label = document.page_map.get(approx_page - 1)

        chunk_metadata = ChunkMetadata(
            chunk_id=chunk_id,
            doc_id=document.metadata.doc_id,
            title=document.metadata.title,
            page=page_label,
            domain=document.metadata.extra.get("domain", "general"),
            source_path=document.metadata.source_path,
        )
        chunk = Chunk(metadata=chunk_metadata, text=chunk_text, token_count=len(chunk_words))
        chunks.append(chunk)
    return chunks
