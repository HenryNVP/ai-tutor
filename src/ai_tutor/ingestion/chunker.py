from __future__ import annotations

import hashlib
import math
from pathlib import Path
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

        # Copy domain metadata from document to chunk
        primary_domain = getattr(document.metadata, "primary_domain", None) or document.metadata.extra.get("domain", "general")
        secondary_domains = getattr(document.metadata, "secondary_domains", []) or []
        domain_tags = getattr(document.metadata, "domain_tags", []) or []
        domain_confidence = getattr(document.metadata, "domain_confidence", 0.5)
        
        # CRITICAL FIX: Normalize source_path to just the filename
        # This prevents temp paths like /tmp/aitutor_ingest_*/filename.pdf from being stored permanently
        # We store just the filename, which is what we use for matching anyway
        original_source_path = document.metadata.source_path
        if original_source_path:
            # Normalize to just the filename (handles temp paths, data/uploads, data/raw, etc.)
            normalized_source_path = Path(original_source_path.name)
            # If the file was from data/uploads, preserve that for clarity
            if str(original_source_path).startswith("data/uploads/"):
                normalized_source_path = Path("data/uploads") / original_source_path.name
            # If the file was from data/raw, preserve the relative path structure
            elif str(original_source_path).startswith("data/raw/"):
                # Keep the relative path from data/raw (e.g., data/raw/physics/file.pdf)
                try:
                    relative_path = original_source_path.relative_to(Path("data/raw"))
                    normalized_source_path = Path("data/raw") / relative_path
                except ValueError:
                    # If not relative to data/raw, just use filename
                    normalized_source_path = Path(original_source_path.name)
            # For temp paths (/tmp/aitutor_ingest_*/), just use filename
            elif "/tmp/" in str(original_source_path) or "aitutor_ingest" in str(original_source_path):
                normalized_source_path = Path(original_source_path.name)
            else:
                # For other paths, try to preserve relative structure if it's within project
                normalized_source_path = Path(original_source_path.name)
        else:
            normalized_source_path = Path("unknown")
        
        chunk_metadata = ChunkMetadata(
            chunk_id=chunk_id,
            doc_id=document.metadata.doc_id,
            title=document.metadata.title,
            page=page_label,
            chunk_index=chunk_index,  # REFACTOR: Store chunk index for sequential retrieval
            domain=document.metadata.extra.get("domain", primary_domain),  # Legacy field
            primary_domain=primary_domain,
            secondary_domains=secondary_domains,
            domain_tags=domain_tags,
            domain_confidence=domain_confidence,
            source_path=normalized_source_path,  # CRITICAL FIX: Use normalized path (filename only for temp paths)
        )
        chunk = Chunk(metadata=chunk_metadata, text=chunk_text, token_count=len(chunk_words))
        chunks.append(chunk)
    return chunks
