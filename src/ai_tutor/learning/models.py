from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class LearningObjective:
    description: str
    mastery_level: float = 0.0  # 0-1 scale


@dataclass
class LessonPlan:
    title: str
    objectives: List[LearningObjective]
    resources: List[str]
    practice: List[str]
    worked_examples: List[str]


@dataclass
class CourseUnit:
    title: str
    focus_topics: List[str]
    lessons: List[LessonPlan]


@dataclass
class CoursePlan:
    course_title: str
    duration_weeks: int
    units: List[CourseUnit]


@dataclass
class AssessmentItem:
    question: str
    answer: str
    rationale: str
    choices: Optional[List[str]] = None  # None => short answer


@dataclass
class Assessment:
    title: str
    items: List[AssessmentItem]


@dataclass
class AttemptRecord:
    assessment_title: str
    timestamp: datetime
    score: float
    responses: Dict[str, str]


@dataclass
class LearnerProfile:
    learner_id: str
    name: str
    domain_strengths: Dict[str, float] = field(default_factory=dict)
    domain_struggles: Dict[str, float] = field(default_factory=dict)
    concepts_mastered: Dict[str, float] = field(default_factory=dict)
    attempts: List[AttemptRecord] = field(default_factory=list)
    total_time_minutes: float = 0.0
