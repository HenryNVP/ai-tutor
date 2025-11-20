from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Literal, Optional

from ai_tutor.learning.quiz_intent import (
    detect_quiz_request,
    extract_quiz_num_questions,
    extract_quiz_topic,
)

RouteTarget = Literal["qa", "note", "quiz", "web", "ingestion"]

GENERIC_SOURCE_TOKENS = {
    "uploaded documents",
    "uploaded document",
    "my documents",
    "the documents",
    "documents",
    "files",
    "these notes",
}


@dataclass
class RoutingDecision:
    target: RouteTarget
    reason: str
    source_filter: Optional[List[str]] = None
    quiz_topic: Optional[str] = None
    quiz_count: Optional[int] = None
    deterministic: bool = True
    confidence: float = 1.0
    documents_only: bool = False


def extract_source_mentions(message: str, extra_hints: Optional[List[str]] = None) -> List[str]:
    """Extract concrete document identifiers or titles for source filtering."""
    references: List[str] = []

    def _add_candidate(value: str) -> None:
        normalized = value.strip().strip("'\"").strip()
        if not normalized:
            return
        if normalized.lower() in GENERIC_SOURCE_TOKENS:
            return
        if normalized not in references:
            references.append(normalized)

    for quoted in re.findall(r"['\"]([^'\"]{3,120})['\"]", message):
        _add_candidate(quoted)

    for match in re.findall(r"([^\s]+?\.(?:pdf|pptx|ppt|docx|md|txt))", message, flags=re.IGNORECASE):
        _add_candidate(match)

    for match in re.findall(
        r"\b(?:lecture|chapter|module|lesson|unit)\s+\d+(?:[\w\s\-:]{0,40})",
        message,
        flags=re.IGNORECASE,
    ):
        _add_candidate(match)

    # Parse metadata-based hints injected by the UI (e.g., SOURCE_FILTER_HINTS or context headers)
    metadata_patterns = [
        r"SOURCE_FILTER_HINTS:\s*([^\n\r]+)",
        r"Source filter hints:\s*([^\n\r]+)",
        r"Content from uploaded documents:\s*([^\n\r]+)",
    ]
    combined_message = message
    if extra_hints:
        combined_message += "\n" + "\n".join(extra_hints)

    for pattern in metadata_patterns:
        for match in re.findall(pattern, combined_message, flags=re.IGNORECASE):
            for candidate in re.split(r"[,\|]", match):
                _add_candidate(candidate)

    return references


def should_use_source_filter(message: str) -> bool:
    return bool(extract_source_mentions(message))


def detect_note_request(message: str) -> bool:
    lowered = message.lower()
    keywords = [
        "summarize",
        "summary",
        "take notes",
        "write notes",
        "create notes",
        "note down",
        "save notes",
        "write a file",
        "create a file",
        "lesson notes",
        "study notes",
        "make notes",
    ]
    if any(keyword in lowered for keyword in keywords):
        return True
    return bool(re.search(r"\bnotes?\b", lowered) and "quiz" not in lowered)


def detect_ingestion_request(message: str) -> bool:
    lowered = message.lower()
    keywords = [
        "upload",
        "ingest",
        "add document",
        "add file",
        "index document",
        "process folder",
    ]
    return any(keyword in lowered for keyword in keywords)


def detect_news_request(message: str) -> bool:
    lowered = message.lower()
    keywords = [
        "news",
        "current events",
        "latest update",
        "today",
        "recent developments",
    ]
    return any(keyword in lowered for keyword in keywords)


def apply_deterministic_routing(
    question: str,
    extra_context: Optional[str] = None,
) -> Optional[RoutingDecision]:
    """Apply explicit routing rules before reaching for the LLM fallback."""
    if detect_quiz_request(question):
        return RoutingDecision(
            target="quiz",
            reason="Detected quiz intent keywords",
            quiz_topic=extract_quiz_topic(question),
            quiz_count=extract_quiz_num_questions(question),
            confidence=1.0,
        )

    if detect_note_request(question):
        return RoutingDecision(
            target="note",
            reason="Detected summarize/note intent",
            source_filter=extract_source_mentions(question),
            confidence=1.0,
        )

    if detect_ingestion_request(question):
        return RoutingDecision(
            target="ingestion",
            reason="Detected ingestion keywords",
            confidence=1.0,
        )

    if detect_news_request(question):
        return RoutingDecision(
            target="web",
            reason="Detected news/current events intent",
            confidence=1.0,
        )

    references = extract_source_mentions(question)
    if references:
        return RoutingDecision(
            target="qa",
            reason="Detected explicit document references",
            source_filter=references,
            confidence=1.0,
        )

    if extra_context:
        context_refs = extract_source_mentions(extra_context)
        if context_refs:
            return RoutingDecision(
                target="qa",
                reason="Detected contextual document references",
                source_filter=context_refs,
                confidence=1.0,
            )

    return None

