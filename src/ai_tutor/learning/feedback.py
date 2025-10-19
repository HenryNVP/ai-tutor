from __future__ import annotations

from typing import Dict, List

from ai_tutor.learning.models import LearnerProfile


def generate_feedback(profile: LearnerProfile) -> Dict[str, List[str]]:
    """Summarize learner strengths, focus areas, and suggested actions from profile data."""
    strengths = sorted(
        profile.domain_strengths.items(), key=lambda item: item[1], reverse=True
    )
    struggles = sorted(
        profile.domain_struggles.items(), key=lambda item: item[1], reverse=True
    )
    mastered = sorted(
        profile.concepts_mastered.items(), key=lambda item: item[1], reverse=True
    )

    feedback = {
        "strengths": [
            f"You show consistent mastery in {domain} (score {score:.2f})."
            for domain, score in strengths[:3]
        ]
        or ["We're still collecting enough data to highlight strengths."],
        "focus_areas": [
            f"{domain} needs attention (struggle index {score:.2f}). Try revisiting key examples."
            for domain, score in struggles[:3]
        ]
        or ["No clear struggles yet—keep exploring challenging problems."],
        "next_steps": [],
        "suggested_practice": [],
    }

    if mastered:
        feedback["next_steps"].append(
            f"Extend your knowledge of {mastered[0][0]} with real-world applications."
        )
    if struggles:
        focus_domain = struggles[0][0]
        feedback["next_steps"].append(
            f"Schedule a focused review session on {focus_domain} using recent assessments."
        )
        feedback["suggested_practice"].extend(
            [
                f"Redo incorrect questions from {focus_domain} checkpoints.",
                f"Create a concept map summarizing {focus_domain} connections.",
            ]
        )
    else:
        feedback["suggested_practice"].append(
            "Attempt a mixed-topic practice set to challenge your breadth."
        )
    return feedback
