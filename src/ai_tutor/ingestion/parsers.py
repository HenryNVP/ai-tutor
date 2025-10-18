from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Type

from ai_tutor.data_models import Document, DocumentMetadata

logger = logging.getLogger(__name__)


class Parser(ABC):
    """Abstract base for parsing raw documents into normalized text."""

    extensions: List[str] = []

    @abstractmethod
    def parse(self, path: Path) -> Document:
        raise NotImplementedError


class TextParser(Parser):
    extensions = [".txt"]

    def parse(self, path: Path) -> Document:
        text = path.read_text(encoding="utf-8")
        metadata = DocumentMetadata(
            doc_id=path.stem, title=path.stem, source_path=path, extra={"format": "txt"}
        )
        return Document(metadata=metadata, text=text)


class MarkdownParser(Parser):
    extensions = [".md", ".markdown"]

    def parse(self, path: Path) -> Document:
        text = path.read_text(encoding="utf-8")
        metadata = DocumentMetadata(
            doc_id=path.stem,
            title=path.stem.replace("-", " ").title(),
            source_path=path,
            extra={"format": "markdown"},
        )
        return Document(metadata=metadata, text=text)


class PdfParser(Parser):
    extensions = [".pdf"]

    def parse(self, path: Path) -> Document:
        try:
            import fitz  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "pymupdf is required to parse PDF files. Install pymupdf."
            ) from exc

        doc = fitz.open(path)
        pages: List[str] = []
        page_map: Dict[int, str] = {}
        for page_idx, page in enumerate(doc):
            text = page.get_text()
            pages.append(text)
            page_map[page_idx] = f"p.{page_idx + 1}"

        combined_text = "\n\n".join(pages)
        metadata = DocumentMetadata(
            doc_id=path.stem,
            title=path.stem.replace("_", " ").title(),
            source_path=path,
            extra={"format": "pdf", "page_count": len(pages)},
        )
        return Document(metadata=metadata, text=combined_text, page_map=page_map)


def discover_parsers() -> Dict[str, Parser]:
    parser_classes: List[Type[Parser]] = [TextParser, MarkdownParser, PdfParser]
    parsers: Dict[str, Parser] = {}
    for parser_cls in parser_classes:
        parser = parser_cls()
        for ext in parser.extensions:
            parsers[ext.lower()] = parser
    return parsers


def parse_path(path: Path) -> Document:
    parsers = discover_parsers()
    parser = parsers.get(path.suffix.lower())
    if not parser:
        raise ValueError(f"No parser available for extension {path.suffix}")
    logger.info("Parsing %s with %s", path, parser.__class__.__name__)
    return parser.parse(path)
