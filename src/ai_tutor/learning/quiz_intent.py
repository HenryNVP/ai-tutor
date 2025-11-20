from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Protocol


def detect_quiz_request(message: str) -> bool:
	"""Detect if user is requesting a quiz from their message."""
	message_lower = message.lower()
	patterns = [
		r"\b(create|generate|make)\s+.*?\bquiz",
		r"\bquiz\s+me\b",
		r"\btest\s+me\b",
		r"\bpractice\s+questions?\b",
		r"\b(create|generate)\s+.*?\bquestions?\b",
		r"\bdownloadable\s+quiz",
	]
	return any(re.search(p, message_lower) for p in patterns)


def extract_quiz_num_questions(message: str) -> int:
	"""Extract requested number of questions; cap at 40; default 4.

	If multiple quantities are mentioned (e.g., "5 easy and 10 hard"),
	use the largest explicit count to avoid underestimating the total quiz size.
	"""
	message_lower = message.lower()
	patterns = [
		r"(\d+)\s+(?:question|questions)",
		r"create\s+(\d+)\s+(?:\w+\s+)?(?:quiz|quizzes)",
		r"generate\s+(\d+)\s+(?:\w+\s+)?(?:quiz|quizzes)",
		r"make\s+(\d+)\s+(?:\w+\s+)?(?:quiz|quizzes)",
		r"quiz\s+with\s+(\d+)",
	]
	found_counts: list[int] = []
	for p in patterns:
		for m in re.finditer(p, message_lower):
			try:
				found_counts.append(int(m.group(1)))
			except ValueError:
				continue
	if found_counts:
		max_value = max(found_counts)
		return max(3, min(max_value, 40))
	return 4


def extract_quiz_topic(message: str) -> str:
	"""Extract quiz topic from message; handle document-based phrasing; fallback to cleaned text."""
	message_lower = message.lower()
	# If the user references explicit filenames (e.g., lecture_notes.pdf, "Module 3 Summary"),
	# prefer those signals over generic "uploaded documents".
	filename_matches = re.findall(r"([\w\-\s]+\.(?:pdf|pptx|ppt|docx|md|txt))", message, flags=re.IGNORECASE)
	if filename_matches:
		return filename_matches[0].strip()

	title_matches = re.findall(
		r"(?:\"|“)([^\"”]{3,120})(?:\"|”)",
		message,
	)
	if title_matches:
		return title_matches[0].strip()

	# document-based hints
	doc_patterns = [
		r"(?:from|using)\s+(?:the|my|these|uploaded)?\s*(?:document|documents|files|pdfs)",
		r"based\s+on\s+(?:the|my|these|uploaded)?\s*(?:document|documents|files|pdfs)",
		r"quiz\s+(?:from\s+)?(?:the|my|these)\s+(?:document|documents|files)",
		r"(?:the|my|these)\s+uploaded\s+(?:document|documents|files|pdfs)",
	]
	if any(re.search(p, message_lower) for p in doc_patterns):
		return "uploaded documents"

	patterns = [
		r"(?:create|generate|make)\s+(?:\d+\s+)?(?:\w+\s+)?quiz(?:zes)?\s+(?:about|on|regarding|for)\s+(.+)",
		r"quiz(?:zes)?\s+(?:about|on|regarding|for)\s+(.+)",
		r"test me on\s+(.+)",
	]
	for p in patterns:
		m = re.search(p, message_lower)
		if m:
			topic = m.group(1).strip()
			topic = re.sub(r"\bwith\s+\d+\s+(?:question|questions?)\b", "", topic).strip()
			return topic

	cleaned = message_lower
	for keyword in ["create", "generate", "make", "quiz", "quizzes", "test", "questions", "downloadable"]:
		cleaned = cleaned.replace(keyword, "")
	cleaned = re.sub(r"^\s*\d+\s+", "", cleaned).strip()
	return cleaned or "general"


@dataclass
class DocumentRequest:
	source_filter: List[str]
	use_documents_only: bool = False


def detect_document_request(message: str, filenames: Optional[List[str]] = None) -> DocumentRequest:
	source_filter = [name for name in (filenames or []) if name]
	if not source_filter:
		file_matches = re.findall(r"([\w\-\s]+\.(?:pdf|pptx|ppt|docx|md|txt))", message, flags=re.IGNORECASE)
		if file_matches:
			source_filter = [match.strip() for match in file_matches]
	lowered = message.lower()
	use_docs = any(
		phrase in lowered
		for phrase in [
			"uploaded document",
			"uploaded file",
			"these documents",
			"these files",
			"this document",
			"this file",
		]
	)
	return DocumentRequest(source_filter=source_filter, use_documents_only=use_docs)


class QuizCountLLM(Protocol):
	def generate(self, messages, **kwargs) -> str: ...


def refine_quiz_count_with_llm(
	message: str,
	initial_count: int,
	llm: QuizCountLLM,
) -> int:
	"""
	Ask the LLM to interpret ambiguous quiz count instructions.
	Returns the refined count, clamped to [3, 40].
	"""
	system_prompt = (
		"You interpret quiz instructions and return ONLY a JSON object "
		"with a `num_questions` integer (3-40). "
		"If multiple counts are mentioned (e.g. '5 easy and 10 hard'), "
		"set num_questions to the total."
	)
	user_prompt = (
		f"Instruction: {message}\n"
		f"Initial heuristic count: {initial_count}\n\n"
		"Respond with: {\"num_questions\": <int>}"
	)
	raw = llm.generate(
		[
			{"role": "system", "content": system_prompt},
			{"role": "user", "content": user_prompt},
		],
		max_tokens=150,
	)
	match = re.search(r'"num_questions"\s*:\s*(\d+)', raw)
	if not match:
		return initial_count
	refined = int(match.group(1))
	return max(3, min(refined, 40))
