from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from ai_tutor.learning.models import AttemptRecord, LearnerProfile


class ProgressTracker:
    """Handle persistence and incremental updates for learner progress data."""

    def __init__(self, base_dir: Path):
        """Create the storage directory that will hold learner progress files."""
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def profile_path(self, learner_id: str) -> Path:
        """Return the JSON file path for a given learner ID."""
        return self.base_dir / f"{learner_id}.json"

    def load_profile(self, learner_id: str, name: str | None = None) -> LearnerProfile:
        """Load a learner profile from disk or create a default one if missing."""
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
        history_payload: List[Dict[str, str]] = data.get("session_history", [])
        profile = LearnerProfile(
            learner_id=data["learner_id"],
            name=data["name"],
            domain_strengths=data.get("domain_strengths", {}),
            domain_struggles=data.get("domain_struggles", {}),
            concepts_mastered=data.get("concepts_mastered", {}),
            attempts=attempts,
            total_time_minutes=data.get("total_time_minutes", 0.0),
            session_history=history_payload,
            next_topics=data.get("next_topics", {}),
            difficulty_preferences=data.get("difficulty_preferences", {}),
        )
        return profile

    def save_profile(self, profile: LearnerProfile) -> None:
        """Serialize the learner profile (including attempts) back to disk."""
        path = self.profile_path(profile.learner_id)
        serialized = {
            "learner_id": profile.learner_id,
            "name": profile.name,
            "domain_strengths": profile.domain_strengths,
            "domain_struggles": profile.domain_struggles,
            "concepts_mastered": profile.concepts_mastered,
            "total_time_minutes": profile.total_time_minutes,
            "session_history": profile.session_history,
            "next_topics": profile.next_topics,
            "difficulty_preferences": profile.difficulty_preferences,
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
        """
        Append an assessment attempt and adjust mastery deltas on the profile.

        Creates a timestamped `AttemptRecord`, extends the profile's attempt list, and
        optionally updates concept mastery scores with bounded deltas.
        """
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
        """Accumulate minutes spent learning onto the profile's time counter."""
        profile.total_time_minutes += minutes
        return profile

    def mark_strength(self, profile: LearnerProfile, domain: str, delta: float) -> LearnerProfile:
        """Adjust the learner's strength score for a domain within bounds."""
        current = profile.domain_strengths.get(domain, 0.0)
        profile.domain_strengths[domain] = max(0.0, min(1.0, current + delta))
        return profile

    def mark_struggle(self, profile: LearnerProfile, domain: str, delta: float) -> LearnerProfile:
        """Adjust the learner's struggle score for a domain within bounds."""
        current = profile.domain_struggles.get(domain, 0.0)
        profile.domain_struggles[domain] = max(0.0, min(1.0, current + delta))
        return profile
