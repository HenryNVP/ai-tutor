from __future__ import annotations

import re


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
	"""Extract requested number of questions; cap at 20; default 4."""
	message_lower = message.lower()
	patterns = [
		r"(\d+)\s+(?:question|questions)",
		r"create\s+(\d+)\s+(?:\w+\s+)?(?:quiz|quizzes)",
		r"generate\s+(\d+)\s+(?:\w+\s+)?(?:quiz|quizzes)",
		r"make\s+(\d+)\s+(?:\w+\s+)?(?:quiz|quizzes)",
		r"quiz\s+with\s+(\d+)",
	]
	for p in patterns:
		m = re.search(p, message_lower)
		if m:
			n = int(m.group(1))
			return min(n, 20)
	return 4


def extract_quiz_topic(message: str) -> str:
	"""Extract quiz topic from message; handle document-based phrasing; fallback to cleaned text."""
	message_lower = message.lower()
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
