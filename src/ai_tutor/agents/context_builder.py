from __future__ import annotations

from typing import List

from ai_tutor.data_models import RetrievalHit

SYSTEM_PROMPT = (
    "You are a personal STEM instructor for high-school to pre-college students. "
    "You must answer using ONLY the provided context chunks. "
    "Cite each statement with [Title p.X] or [Title §Y]. "
    "If you lack evidence, say so and offer to search the web or suggest study steps."
)


def build_context(hits: List[RetrievalHit]) -> str:
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
) -> list[dict[str, str]]:
    context = build_context(hits)
    user_prompt = (
        f"Question: {question}\n\n"
        f"Mode: {mode}\n"
        f"Style: {style}\n\n"
        f"Context:\n{context}\n\n"
        "Respond with clear steps, cite references, and align with the given mode."
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
