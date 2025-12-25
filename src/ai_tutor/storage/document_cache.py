"""Document cache for storing parsed documents (before chunking).

This cache allows Note Agent to access full document text directly when using
Gemini (large context window), bypassing the need to retrieve and concatenate chunks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from ai_tutor.data_models import Document


class DocumentCache:
    """Simple JSONL persistence for parsed documents (before chunking)."""

    def __init__(self, path: Path):
        """Initialize document cache with JSONL storage."""
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Document] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load all documents from disk into memory cache."""
        if not self.path.exists():
            return
        
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    doc = Document.model_validate(data)
                    # Use doc_id as key for fast lookup
                    self._cache[doc.metadata.doc_id] = doc
        except Exception as e:
            # If cache is corrupted, start fresh
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to load document cache: {e}. Starting with empty cache.")
            self._cache = {}

    def store(self, document: Document) -> None:
        """Store a parsed document in the cache."""
        self._cache[document.metadata.doc_id] = document
        self._persist()

    def store_many(self, documents: list[Document]) -> None:
        """Store multiple documents in the cache."""
        for doc in documents:
            self._cache[doc.metadata.doc_id] = doc
        self._persist()

    def get(self, doc_id: str) -> Optional[Document]:
        """Retrieve a document by doc_id."""
        return self._cache.get(doc_id)

    def get_by_filename(self, filename: str) -> Optional[Document]:
        """Retrieve a document by filename (matches source_path)."""
        # Try exact match first
        for doc in self._cache.values():
            if doc.metadata.source_path.name == filename:
                return doc
            # Also check if filename is in the source_path string
            if filename in str(doc.metadata.source_path):
                return doc
        return None

    def list_all(self) -> list[Document]:
        """List all documents in the cache."""
        return list(self._cache.values())

    def _persist(self) -> None:
        """Persist cache to disk."""
        with self.path.open("w", encoding="utf-8") as handle:
            for doc in self._cache.values():
                handle.write(doc.model_dump_json())
                handle.write("\n")

    def clear(self) -> None:
        """Clear the cache (both memory and disk)."""
        self._cache = {}
        if self.path.exists():
            self.path.unlink()

