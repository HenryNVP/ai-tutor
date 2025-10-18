from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict

from ai_tutor.learning.models import AttemptRecord, LearnerProfile


class ProgressTracker:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def profile_path(self, learner_id: str) -> Path:
        return self.base_dir / f"{learner_id}.json"

    def load_profile(self, learner_id: str, name: str | None = None) -> LearnerProfile:
        path = self.profile_path(learner_id)
        if not path.exists():
            return LearnerProfile(learner_id=learner_id, name=name or learner_id)
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        attempts = [
            AttemptRecord(
                assessment_title=record["assessment_title"],
                timestamp=datetime.fromisoformat(record["timestamp"]),
                score=record["score"],
                responses=record.get("responses", {}),
            )
            for record in data.get("attempts", [])
        ]
        profile = LearnerProfile(
            learner_id=data["learner_id"],
            name=data["name"],
            domain_strengths=data.get("domain_strengths", {}),
            domain_struggles=data.get("domain_struggles", {}),
            concepts_mastered=data.get("concepts_mastered", {}),
            attempts=attempts,
            total_time_minutes=data.get("total_time_minutes", 0.0),
        )
        return profile

    def save_profile(self, profile: LearnerProfile) -> None:
        path = self.profile_path(profile.learner_id)
        serialized = {
            "learner_id": profile.learner_id,
            "name": profile.name,
            "domain_strengths": profile.domain_strengths,
            "domain_struggles": profile.domain_struggles,
            "concepts_mastered": profile.concepts_mastered,
            "total_time_minutes": profile.total_time_minutes,
            "attempts": [
                {
                    "assessment_title": attempt.assessment_title,
                    "timestamp": attempt.timestamp.isoformat(),
                    "score": attempt.score,
                    "responses": attempt.responses,
                }
                for attempt in profile.attempts
            ],
        }
        with path.open("w", encoding="utf-8") as handle:
            json.dump(serialized, handle, indent=2)

    def record_attempt(
        self,
        profile: LearnerProfile,
        assessment_title: str,
        score: float,
        responses: Dict[str, str] | None = None,
        concepts: Dict[str, float] | None = None,
    ) -> LearnerProfile:
        record = AttemptRecord(
            assessment_title=assessment_title,
            timestamp=datetime.utcnow(),
            score=score,
            responses=responses or {},
        )
        profile.attempts.append(record)
        if concepts:
            for concept, delta in concepts.items():
                current = profile.concepts_mastered.get(concept, 0.0)
                profile.concepts_mastered[concept] = max(0.0, min(1.0, current + delta))
        return profile

    def update_time_on_task(self, profile: LearnerProfile, minutes: float) -> LearnerProfile:
        profile.total_time_minutes += minutes
        return profile

    def mark_strength(self, profile: LearnerProfile, domain: str, delta: float) -> LearnerProfile:
        current = profile.domain_strengths.get(domain, 0.0)
        profile.domain_strengths[domain] = max(0.0, min(1.0, current + delta))
        return profile

    def mark_struggle(self, profile: LearnerProfile, domain: str, delta: float) -> LearnerProfile:
        current = profile.domain_struggles.get(domain, 0.0)
        profile.domain_struggles[domain] = max(0.0, min(1.0, current + delta))
        return profile
