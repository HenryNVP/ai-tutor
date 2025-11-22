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


def extract_quiz_topic(
	message: str,
	extra_context: Optional[str] = None,
	source_filter: Optional[List[str]] = None,
) -> str:
	"""Extract quiz topic from message; handle document-based phrasing; fallback to cleaned text.
	
	Args:
		message: User's quiz request message
		extra_context: Optional context containing uploaded document content
		source_filter: Optional list of filenames from uploaded documents
		
	Returns:
		Extracted topic string, preferring actual document titles over generic "uploaded documents"
	"""
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

	# Try to extract document titles from extra_context
	# Format: "[1] Title\n{text}" or "SOURCE_FILTER_HINTS: filename1, filename2"
	if extra_context:
		# Extract from SOURCE_FILTER_HINTS if present
		hints_match = re.search(r"SOURCE_FILTER_HINTS:\s*([^\n\r]+)", extra_context, re.IGNORECASE)
		if hints_match:
			hints_str = hints_match.group(1).strip()
			# Extract first filename (remove extension for cleaner topic)
			filenames = [f.strip() for f in re.split(r"[,\|]", hints_str)]
			if filenames:
				first_file = filenames[0]
				# Remove extension for cleaner topic name
				topic = re.sub(r"\.(?:pdf|pptx|ppt|docx|md|txt)$", "", first_file, flags=re.IGNORECASE)
				if topic and topic.lower() not in ["uploaded documents", "documents", "files"]:
					return topic
		
		# Extract from formatted document content: "[1] Title\n{text}"
		# Look for patterns like "[1] Document Title\n" or "[1] Title (Doc: ...)\n"
		title_patterns = [
			r"\[\d+\]\s+([^\n]+?)(?:\s+\(Doc:|\n)",  # "[1] Title (Doc: ...)" or "[1] Title\n"
			r"\[\d+\]\s+([^\n]+?)(?:\n|$)",  # Fallback: "[1] Title\n"
		]
		for pattern in title_patterns:
			matches = re.findall(pattern, extra_context)
			if matches:
				# Use first non-generic title found
				for match in matches:
					title = match.strip()
					# Skip generic titles
					if title.lower() not in ["uploaded documents", "documents", "files", "unknown"]:
						# Clean up any trailing metadata
						title = re.sub(r"\s*\(Doc:.*?\)", "", title).strip()
						if title:
							return title
	
	# Use source_filter (filenames) if available
	if source_filter:
		for filename in source_filter:
			if filename:
				# Remove extension for cleaner topic name
				topic = re.sub(r"\.(?:pdf|pptx|ppt|docx|md|txt)$", "", filename, flags=re.IGNORECASE)
				if topic and topic.lower() not in ["uploaded documents", "documents", "files"]:
					return topic

	# document-based hints
	doc_patterns = [
		r"(?:from|using)\s+(?:the|my|these|uploaded)?\s*(?:document|documents|files|pdfs)",
		r"based\s+on\s+(?:the|my|these|uploaded)?\s*(?:document|documents|files|pdfs)",
		r"quiz\s+(?:from\s+)?(?:the|my|these)\s+(?:document|documents|files)",
		r"(?:the|my|these)\s+uploaded\s+(?:document|documents|files|pdfs)",
	]
	if any(re.search(p, message_lower) for p in doc_patterns):
		# Only return generic if we couldn't extract a specific title
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
