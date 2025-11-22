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
        """Convert a filesystem path into a normalized `Document` instance."""
        raise NotImplementedError


class TextParser(Parser):
    extensions = [".txt"]

    def parse(self, path: Path) -> Document:
        """Read plain-text files verbatim and attach minimal metadata."""
        text = path.read_text(encoding="utf-8")
        metadata = DocumentMetadata(
            doc_id=path.stem, title=path.stem, source_path=path, extra={"format": "txt"}
        )
        return Document(metadata=metadata, text=text)


class MarkdownParser(Parser):
    extensions = [".md", ".markdown"]

    def parse(self, path: Path) -> Document:
        """Load Markdown documents as raw text and prettify the inferred title."""
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
        """Extract text and page metadata from PDFs using PyMuPDF."""
        try:
            import fitz  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "pymupdf is required to parse PDF files. Install pymupdf."
            ) from exc

        doc = fitz.open(path)
        pages: List[str] = []
        page_map: Dict[int, str] = {}
        pages_with_text = 0
        total_chars = 0
        
        for page_idx, page in enumerate(doc):
            text = page.get_text()
            text_len = len(text.strip())
            pages.append(text)
            page_map[page_idx] = f"p.{page_idx + 1}"
            
            if text_len > 0:
                pages_with_text += 1
                total_chars += text_len

        combined_text = "\n\n".join(pages)
        
        # Warn if PDF appears to have sparse or no text content
        if len(pages) > 0:
            text_ratio = pages_with_text / len(pages)
            chars_per_page = total_chars / len(pages) if len(pages) > 0 else 0
            
            if text_ratio < 0.1:  # Less than 10% of pages have text
                logger.warning(
                    f"PDF {path.name} appears to be image-based or have parsing issues: "
                    f"only {pages_with_text}/{len(pages)} pages contain text. "
                    f"Average {chars_per_page:.0f} chars per page. "
                    f"This may result in very few chunks."
                )
            elif chars_per_page < 100:  # Very sparse content
                logger.warning(
                    f"PDF {path.name} has sparse text content: "
                    f"average {chars_per_page:.0f} chars per page. "
                    f"This may result in very few chunks."
                )
        
        metadata = DocumentMetadata(
            doc_id=path.stem,
            title=path.stem.replace("_", " ").title(),
            source_path=path,
            extra={
                "format": "pdf",
                "page_count": len(pages),
                "pages_with_text": pages_with_text,
                "total_chars": total_chars,
                "chars_per_page": total_chars / len(pages) if len(pages) > 0 else 0,
            },
        )
        return Document(metadata=metadata, text=combined_text, page_map=page_map)


def discover_parsers() -> Dict[str, Parser]:
    """Map supported file extensions to their parser instances."""
    parser_classes: List[Type[Parser]] = [TextParser, MarkdownParser, PdfParser]
    parsers: Dict[str, Parser] = {}
    for parser_cls in parser_classes:
        parser = parser_cls()
        for ext in parser.extensions:
            parsers[ext.lower()] = parser
    return parsers


def parse_path(path: Path) -> Document:
    """Select the appropriate parser for the file extension and return a `Document`."""
    parsers = discover_parsers()
    parser = parsers.get(path.suffix.lower())
    if not parser:
        raise ValueError(f"No parser available for extension {path.suffix}")
    logger.info("Parsing %s with %s", path, parser.__class__.__name__)
    return parser.parse(path)
