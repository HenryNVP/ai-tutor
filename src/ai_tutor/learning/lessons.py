from __future__ import annotations

from typing import Dict, List

from ai_tutor.learning.models import CoursePlan, LessonPlan


def create_weekly_schedule(course_plan: CoursePlan, lessons_per_week: int | None = None) -> Dict[int, List[LessonPlan]]:
    """Group lesson plans into a week-by-week schedule for the course plan."""
    if lessons_per_week is None:
        lessons_per_week = max(len(unit.lessons) for unit in course_plan.units) if course_plan.units else 0
    schedule: Dict[int, List[LessonPlan]] = {}
    ordered_lessons: List[LessonPlan] = []
    for unit in course_plan.units:
        ordered_lessons.extend(unit.lessons)
    for week in range(1, course_plan.duration_weeks + 1):
        start_index = (week - 1) * lessons_per_week
        end_index = start_index + lessons_per_week
        schedule[week] = ordered_lessons[start_index:end_index]
    return schedule


def create_daily_plan(lesson: LessonPlan) -> Dict[str, List[str]]:
    """Translate a lesson plan into daily teaching components."""
    return {
        "objectives": [obj.description for obj in lesson.objectives],
        "worked_examples": lesson.worked_examples,
        "practice": lesson.practice,
        "resources": lesson.resources,
    }
