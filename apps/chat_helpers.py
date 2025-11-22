from __future__ import annotations

import re
from typing import List


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
]


