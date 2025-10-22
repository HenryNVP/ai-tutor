from __future__ import annotations
from typing import Dict, Optional, Sequence

from ai_tutor.learning.models import LearnerProfile
from ai_tutor.learning.planner import UNIT_LIBRARY
from ai_tutor.learning.progress import ProgressTracker


class PersonalizationManager:
    """Coordinate learner memory, mastery tracking, and adaptive preferences."""

    def __init__(self, tracker: ProgressTracker):
        """Store the shared progress tracker used for learner profiles."""
        self.tracker = tracker

    def load_profile(self, learner_id: str, name: Optional[str] = None) -> LearnerProfile:
        """Fetch an existing profile or initialize a new one for the learner."""
        return self.tracker.load_profile(learner_id, name=name)

    def save_profile(self, profile: LearnerProfile) -> None:
        """Persist the learner profile to disk."""
        self.tracker.save_profile(profile)

    def infer_domain(self, hits: Sequence, fallback: Optional[str] = None) -> Optional[str]:
        """Derive a domain label from retrieval hits or fall back to a provided default."""
        for hit in hits:
            metadata = getattr(hit.chunk, "metadata", None)
            if metadata and getattr(metadata, "domain", None):
                return metadata.domain
        return fallback

    def select_style(self, profile: LearnerProfile, domain: Optional[str]) -> str:
        """
        Choose a response style based on the learner's mastery for the domain.

        Returns
        -------
        "scaffolded" for low mastery, "concise" for high mastery, otherwise "stepwise".
        """
        if not domain:
            return "stepwise"
        mastery = profile.domain_strengths.get(domain, 0.0)
        if mastery <= 0.3:
            return "scaffolded"
        if mastery >= 0.7:
            return "concise"
        return "stepwise"

    def record_interaction(
        self,
        profile: LearnerProfile,
        question: str,
        answer: str,
        domain: Optional[str],
        citations: Sequence[str],
    ) -> Dict[str, Optional[str]]:
        """
        Append the latest exchange to memory and update adaptive preferences.

        Returns a small payload describing the suggested next topic and difficulty label.
        """
        if not domain:
            return {"next_topic": None, "difficulty": None}

        profile = self.tracker.mark_strength(profile, domain, 0.08)
        mastery = profile.domain_strengths.get(domain, 0.0)
        struggle_delta = -0.04 if mastery > 0.5 else 0.04
        profile = self.tracker.mark_struggle(profile, domain, struggle_delta)

        next_topic = self._choose_next_topic(profile, domain)
        difficulty = self._difficulty_label(mastery)
        profile.difficulty_preferences[domain] = difficulty
        if next_topic:
            profile.next_topics[domain] = next_topic
            profile.concepts_mastered[next_topic] = min(
                1.0, profile.concepts_mastered.get(next_topic, 0.0) + 0.05
            )

        return {"next_topic": next_topic, "difficulty": difficulty}

    def _choose_next_topic(self, profile: LearnerProfile, domain: str) -> Optional[str]:
        """Suggest the next topic within the domain based on the learner's mastery gaps."""
        units = UNIT_LIBRARY.get(domain, [])
        topics: List[str] = []
        for unit in units:
            topics.extend(unit.get("topics", []))
        if not topics:
            return None
        mastery = profile.concepts_mastered
        return min(topics, key=lambda topic: mastery.get(topic, 0.0))

    @staticmethod
    def _difficulty_label(mastery: float) -> str:
        """Map a mastery score to a friendly difficulty descriptor."""
        if mastery <= 0.3:
            return "foundational guidance"
        if mastery >= 0.7:
            return "independent challenge"
        return "guided practice"
