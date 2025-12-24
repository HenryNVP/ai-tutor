from __future__ import annotations

import re
from typing import List


def deduplicate_citations(citations: List[str]) -> List[str]:
	"""
	Remove duplicate citations from a list.
	
	Duplicates are identified by comparing the citation content (title and doc_id).
	Keeps the first occurrence of each unique citation.
	
	Args:
		citations: List of citation strings in format "[N] Title (Doc: doc_id)"
		
	Returns:
		List of unique citations, preserving order
	"""
	if not citations:
		return []
	
	seen = set()
	unique_citations = []
	
	for citation in citations:
		# Extract the core content (title and doc_id) for comparison
		# Format: "[N] Title (Doc: doc_id)" -> "Title (Doc: doc_id)"
		# Remove the index number to compare actual content
		match = re.match(r'\[\d+\]\s*(.+)', citation)
		if match:
			core_content = match.group(1).strip()
		else:
			# Fallback: use full citation if pattern doesn't match
			core_content = citation.strip()
		
		# Normalize for comparison (case-insensitive, whitespace normalized)
		normalized = re.sub(r'\s+', ' ', core_content.lower())
		
		if normalized not in seen:
			seen.add(normalized)
			unique_citations.append(citation)
	
	return unique_citations


def format_answer(text: str) -> str:
	normalized = re.sub(r"(?<=\S)\s+(?=(?:[-•*]|\d+\.)\s)", "\n", text)
	normalized = re.sub(r"\n{3,}", "\n\n", normalized)
	lines = normalized.splitlines()
	formatted: List[str] = []
	for line in lines:
		stripped = line.rstrip()
		is_bullet = stripped.startswith(("-", "*", "•"))
		is_enumeration = bool(re.match(r"^\d+\.\s", stripped))
		if (is_bullet or is_enumeration) and formatted and formatted[-1] != "":
			formatted.append("")
		formatted.append(stripped)
	return "\n".join(formatted)


def is_question_about_uploaded_docs(message: str) -> bool:
	upload_keywords = [
		"uploaded",
		"upload",
		"the documents i uploaded",
		"the files i uploaded",
		"these documents",
		"these files",
		"the 2 documents",
		"the 2 files",
		"the two documents",
		"the two files",
		"this document",
		"this file",
		"the document",  # Added: "summarize the document"
		"the file",  # Added: "summarize the file"
		"the pdf",  # Added: "summarize the pdf"
	]
	message_lower = message.lower()
	return any(keyword in message_lower for keyword in upload_keywords)


def extract_document_hints(message: str, filenames: List[str]) -> List[str]:
	"""Unified helper to detect when the user wants to operate on uploaded docs."""
	hints: List[str] = []
	if filenames and is_question_about_uploaded_docs(message):
		hints.extend(filenames)
	return hints


__all__ = [
	"format_answer",
	"is_question_about_uploaded_docs",
	"extract_document_hints",
	"deduplicate_citations",
]


