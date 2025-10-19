from __future__ import annotations

from typing import Dict, List, Optional

from ai_tutor.data_models import RetrievalHit

SYSTEM_PROMPT = (
    "You are a personal STEM instructor for high-school to pre-college students. "
    "Answer using ONLY the provided context chunks. Do not use external knowledge. "
    "Citations:\n"
    "  • When a statement is supported by a specific context chunk, append a bracketed index like [1] that refers to that chunk in the Context section.\n"
    "  • Only cite indices that you actually used. Do not invent or copy indices you did not rely on.\n"
    "  • If you cannot find sufficient evidence in the provided context to answer, say so briefly and suggest next steps. In that case, include NO citations.\n"
    "Style:\n"
    "  • Be clear, concise, and pedagogically helpful. If a style is given (scaffolded, stepwise, concise), follow it.\n"
    "Constraints:\n"
    "  • Do not fabricate facts or citations. Do not reference materials outside the provided Context."
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
    extra_context: Optional[str] = None,
) -> list[dict[str, str]]:
    """
    Compose the system and user messages that constrain the tutor's response style.

    Includes a short summary of recent learner interactions when available so the tutor can
    pick up where the session left off.
    """
    context_sections = []
    if hits:
        context_sections.append("Retrieved passages:\n" + build_context(hits))
    if extra_context:
        context_sections.append(extra_context)
    if context_sections:
        context_block = "\n\n".join(context_sections)
    else:
        context_block = "No supporting passages were found."
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
        f"Context:\n{context_block}\n\n"
        "Respond clearly. If you use a context chunk, cite it with [index]. "
        "If you cannot answer from the provided context, say so and suggest next steps; include no citations in that case."


    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
