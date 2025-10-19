from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class LearningObjective:
    """Goal describing a specific knowledge or skill target."""

    description: str
    mastery_level: float = 0.0  # 0-1 scale


@dataclass
class LessonPlan:
    """Structured lesson outline including objectives, resources, and practice."""

    title: str
    objectives: List[LearningObjective]
    resources: List[str]
    practice: List[str]
    worked_examples: List[str]


@dataclass
class CourseUnit:
    """Collection of lesson plans grouped under a thematic unit."""

    title: str
    focus_topics: List[str]
    lessons: List[LessonPlan]


@dataclass
class CoursePlan:
    """Full course blueprint covering multiple units over several weeks."""

    course_title: str
    duration_weeks: int
    units: List[CourseUnit]


@dataclass
class AssessmentItem:
    """Single assessment prompt with answer key and optional choices."""

    question: str
    answer: str
    rationale: str
    choices: Optional[List[str]] = None  # None => short answer


@dataclass
class Assessment:
    """Assessment comprised of multiple items for a particular unit."""

    title: str
    items: List[AssessmentItem]


@dataclass
class AttemptRecord:
    """Learner's recorded attempt at an assessment with score and responses."""

    assessment_title: str
    timestamp: datetime
    score: float
    responses: Dict[str, str]


@dataclass
class LearnerProfile:
    """Aggregated learner state capturing skills, history, and time on task."""

    learner_id: str
    name: str
    domain_strengths: Dict[str, float] = field(default_factory=dict)
    domain_struggles: Dict[str, float] = field(default_factory=dict)
    concepts_mastered: Dict[str, float] = field(default_factory=dict)
    attempts: List[AttemptRecord] = field(default_factory=list)
    total_time_minutes: float = 0.0
    session_history: List[Dict[str, str]] = field(default_factory=list)
    next_topics: Dict[str, str] = field(default_factory=dict)
    difficulty_preferences: Dict[str, str] = field(default_factory=dict)
