from __future__ import annotations

from typing import Dict, List, Optional

from ai_tutor.data_models import RetrievalHit

SYSTEM_PROMPT = (
    "You are a personal STEM instructor for high-school to pre-college students. "
    "You must answer using ONLY the provided context chunks. "
    "Cite each statement with [X] like IEEE. "
    "If you lack evidence, say so and offer to search the web or suggest study steps."
)


def build_context(hits: List[RetrievalHit]) -> str:
    """Render retrieval hits into numbered chunks with metadata for the LLM prompt."""
    formatted = []
    for idx, hit in enumerate(hits, start=1):
        metadata = hit.chunk.metadata
        page = metadata.page or "N/A"
        formatted.append(
            f"[{idx}] Title: {metadata.title} "
            f"(Doc: {metadata.doc_id}, Page: {page}, Score: {hit.score:.2f})\n"
            f"{hit.chunk.text}"
        )
    return "\n\n".join(formatted)


def build_messages(
    question: str,
    hits: List[RetrievalHit],
    mode: str = "learning",
    style: str = "stepwise",
    history: Optional[List[Dict[str, str]]] = None,
) -> list[dict[str, str]]:
    """
    Compose the system and user messages that constrain the tutor's response style.

    Includes a short summary of recent learner interactions when available so the tutor can
    pick up where the session left off.
    """
    context = build_context(hits)
    history_section = ""
    if history:
        trimmed = history[-3:]
        history_lines = []
        for idx, item in enumerate(trimmed, start=1):
            past_question = item.get("question", "").strip()
            past_answer = item.get("answer", "").strip()
            summary = past_answer[:400] + ("..." if len(past_answer) > 400 else "")
            history_lines.append(
                f"{idx}. Question: {past_question}\n   Answer summary: {summary}"
            )
        history_section = "Recent session history:\n" + "\n".join(history_lines) + "\n\n"
    else:
        history_section = "Recent session history: None recorded yet.\n\n"
    user_prompt = (
        f"Question: {question}\n\n"
        f"Mode: {mode}\n"
        f"Style: {style}\n\n"
        f"{history_section}"
        f"Context:\n{context}\n\n"
        "Respond with clear steps, cite references, and align with the given mode."
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
