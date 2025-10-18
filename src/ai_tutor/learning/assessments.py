from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ai_tutor.learning.models import Assessment, AssessmentItem, CoursePlan


@dataclass
class AssessmentConfig:
    questions_per_unit: int = 4
    include_short_answer: bool = True


class AssessmentGenerator:
    def __init__(self, config: AssessmentConfig | None = None):
        self.config = config or AssessmentConfig()

    def generate_unit_assessment(
        self,
        course_plan: CoursePlan,
        unit_index: int,
    ) -> Assessment:
        unit = course_plan.units[unit_index]
        items: List[AssessmentItem] = []
        topics = unit.focus_topics
        for idx, topic in enumerate(topics):
            stem = f"A student is working on {topic}. What is the first step they should consider?"
            choices = [
                "Review the known quantities and draw a diagram.",
                "Guess the answer based on intuition.",
                "Skip directly to using a formula without context.",
                "Look up the answer online without attempting the problem.",
            ]
            items.append(
                AssessmentItem(
                    question=stem,
                    choices=choices,
                    answer=choices[0],
                    rationale=f"Successful solutions to {topic} begin with understanding the givens.",
                )
            )

        if self.config.include_short_answer:
            synthesis_prompt = (
                f"Explain how the topics in {unit.title} fit together. "
                "Provide a short answer highlighting real-world relevance."
            )
            items.append(
                AssessmentItem(
                    question=synthesis_prompt,
                    choices=None,
                    answer=f"The ideas in {unit.title} connect because they each build on foundational principles.",
                    rationale="The response should synthesize key relationships and applications.",
                )
            )

        return Assessment(
            title=f"{unit.title} Check-in",
            items=items[: self.config.questions_per_unit + (1 if self.config.include_short_answer else 0)],
        )
