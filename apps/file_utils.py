from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict, Iterable, List


def extract_text(upload: Any) -> str:
	"""Read Streamlit UploadedFile and return raw text for preview/processing."""
	suffix = Path(upload.name).suffix.lower()
	try:
		upload.seek(0)
	except AttributeError:
		pass
	data = upload.read()
	if not data:
		return ""
	if suffix == ".pdf":
		try:
			from pypdf import PdfReader  # optional dependency
		except Exception:
			raise RuntimeError("pypdf is required to read PDF files. Install it or upload text instead.")
		reader = PdfReader(io.BytesIO(data))
		pages: List[str] = []
		for page in reader.pages:
			try:
				pages.append(page.extract_text() or "")
			except Exception:
				pages.append("")
		return "\n\n".join(pages)
	try:
		return data.decode("utf-8")
	except UnicodeDecodeError:
		return data.decode("latin-1", errors="ignore")


def summarize_documents(docs: Iterable[Dict[str, str]], max_chars: int = 6000) -> str:
	"""Concatenate document snippets for UI context within a character budget."""
	parts: List[str] = []
	remaining = max_chars
	for doc in docs:
		text = doc.get("text", "").strip()
		if not text:
			continue
		header = f"[{doc.get('name', 'Document')}]\n"
		available = max(0, remaining - len(header))
		body = text[:available] if available else ""
		parts.append(header + body)
		remaining -= len(header) + len(body) + 2
		if remaining <= 0:
			break
	return "\n\n".join(parts)


__all__ = [
	"extract_text",
	"summarize_documents",
]


