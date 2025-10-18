from __future__ import annotations

from typing import Dict, List, Sequence

from ai_tutor.config.schema import CourseDefaults
from ai_tutor.learning.models import CoursePlan, CourseUnit, LearnerProfile, LessonPlan, LearningObjective


UNIT_LIBRARY: Dict[str, List[Dict[str, Sequence[str]]]] = {
    "math": [
        {"title": "Functions & Graphs", "topics": ["Function notation", "Transformations", "Piecewise behavior"]},
        {"title": "Trigonometry Essentials", "topics": ["Unit circle", "Identities", "Real-world models"]},
        {"title": "Calculus Preview", "topics": ["Limits", "Derivatives", "Optimization"]},
        {"title": "Data & Probability", "topics": ["Descriptive stats", "Probability rules", "Distributions"]},
    ],
    "physics": [
        {"title": "Kinematics Foundations", "topics": ["Motion graphs", "Vector decomposition", "Relative frames"]},
        {"title": "Forces & Dynamics", "topics": ["Newton's laws", "Free-body diagrams", "Systems analysis"]},
        {"title": "Energy Methods", "topics": ["Work-energy theorem", "Power", "Conservation"]},
        {"title": "Electricity Basics", "topics": ["Circuits", "Ohm's law", "Fields & potentials"]},
    ],
    "cs": [
        {"title": "Programming Basics", "topics": ["Control flow", "Data types", "Problem decomposition"]},
        {"title": "Data Structures", "topics": ["Arrays", "Stacks & queues", "Linked lists"]},
        {"title": "Algorithms", "topics": ["Sorting", "Searching", "Complexity"]},
        {"title": "Software Design", "topics": ["Modularization", "Testing", "Debugging"]},
    ],
}


def _derive_strengths(profile: LearnerProfile | None, domain: str) -> List[str]:
    if not profile:
        return []
    strengths = sorted(
        ((topic, score) for topic, score in profile.concepts_mastered.items() if domain in topic),
        key=lambda item: item[1],
        reverse=True,
    )
    return [topic for topic, _ in strengths[:3]]


def _derive_struggles(profile: LearnerProfile | None, domain: str) -> List[str]:
    if not profile:
        return []
    struggles = sorted(
        ((topic, score) for topic, score in profile.domain_struggles.items() if domain in topic),
        key=lambda item: item[1],
        reverse=True,
    )
    return [topic for topic, _ in struggles[:3]]


class CoursePlanner:
    def __init__(self, defaults: CourseDefaults):
        self.defaults = defaults

    def plan_course(
        self,
        domain: str,
        learner: LearnerProfile | None = None,
        weeks: int | None = None,
        lessons_per_week: int | None = None,
    ) -> CoursePlan:
        weeks = weeks or self.defaults.weeks
        lessons_per_week = lessons_per_week or self.defaults.lessons_per_week
        library = UNIT_LIBRARY.get(domain, UNIT_LIBRARY["math"])

        num_units = min(len(library), weeks)
        selected_units = library[:num_units]

        strengths = _derive_strengths(learner, domain)
        struggles = _derive_struggles(learner, domain)

        units: List[CourseUnit] = []
        for unit_def in selected_units:
            lesson_plans: List[LessonPlan] = []
            lesson_topics = list(unit_def["topics"])
            for lesson_index in range(lessons_per_week):
                topic = lesson_topics[lesson_index % len(lesson_topics)]
                objectives = [
                    LearningObjective(description=f"Define key ideas of {topic}"),
                    LearningObjective(description=f"Apply {topic} to solve problems"),
                    LearningObjective(description=f"Explain misconceptions around {topic}"),
                ]
                if struggles:
                    objectives.append(
                        LearningObjective(
                            description=f"Reinforce fundamentals of {struggles[0]} through {topic}"
                        )
                    )
                lesson_plans.append(
                    LessonPlan(
                        title=f"{unit_def['title']} - Lesson {lesson_index + 1}",
                        objectives=objectives,
                        resources=[
                            f"{unit_def['title']} reference notes",
                            f"Practice problems on {topic}",
                        ],
                        practice=[
                            f"10 minute warm-up on {topic}",
                            f"Guided example applying {topic}",
                            "Reflection: What step was hardest?",
                        ],
                        worked_examples=[
                            f"Example 1: Core application of {topic}",
                            f"Example 2: Real-world scenario for {topic}",
                        ],
                    )
                )
            units.append(
                CourseUnit(
                    title=unit_def["title"],
                    focus_topics=list(unit_def["topics"]),
                    lessons=lesson_plans,
                )
            )

        course_title = f"{domain.capitalize()} Mastery Plan"
        return CoursePlan(course_title=course_title, duration_weeks=weeks, units=units)
