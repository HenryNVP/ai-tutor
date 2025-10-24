from __future__ import annotations

import json
from pathlib import Path

from ai_tutor.learning.models import LearnerProfile


class ProgressTracker:
    """
    Handle persistence and incremental updates for learner progress data.
    
    This class manages the storage and retrieval of learner profiles, which
    track domain-specific strengths, struggles, time-on-task, and concept mastery.
    Each learner's profile is stored as a separate JSON file for simplicity and
    portability.
    
    The tracker provides atomic update operations for strength/struggle scores,
    ensuring all changes are properly bounded (0.0 to 1.0) and immediately
    reflected in the in-memory profile object. Calling code is responsible for
    saving profiles back to disk after modifications.
    
    Profile Storage Format
    ----------------------
    Profiles are stored as JSON files in the format: `{learner_id}.json`
    
    Example: `data/processed/profiles/student123.json`
    ```json
    {
      "learner_id": "student123",
      "name": "Alice Johnson",
      "domain_strengths": {"physics": 0.72, "math": 0.58},
      "domain_struggles": {"cs": 0.35},
      "concepts_mastered": {"derivatives": 0.85, "integrals": 0.62},
      "total_time_minutes": 247.5,
      "next_topics": {"math": "integration by parts"},
      "difficulty_preferences": {"math": "guided practice"}
    }
    ```
    
    Attributes
    ----------
    base_dir : Path
        Directory where learner profile JSON files are stored. Created if
        it doesn't exist during initialization.
    
    Examples
    --------
    >>> from pathlib import Path
    >>> tracker = ProgressTracker(Path("data/processed/profiles"))
    >>> 
    >>> # Load or create a profile
    >>> profile = tracker.load_profile("student123", name="Alice")
    >>> print(profile.domain_strengths)
    {}  # Empty for new learners
    >>> 
    >>> # Update strength and struggle scores
    >>> profile = tracker.mark_strength(profile, "physics", 0.1)
    >>> profile = tracker.mark_struggle(profile, "physics", 0.05)
    >>> profile = tracker.update_time_on_task(profile, 15.0)
    >>> 
    >>> # Save to disk
    >>> tracker.save_profile(profile)
    >>> 
    >>> # Reload to verify persistence
    >>> reloaded = tracker.load_profile("student123")
    >>> print(reloaded.domain_strengths["physics"])
    0.1
    """

    def __init__(self, base_dir: Path):
        """
        Initialize the progress tracker with a storage directory.
        
        Parameters
        ----------
        base_dir : Path
            Directory where learner profile JSON files will be stored.
            Created automatically if it doesn't exist.
        
        Examples
        --------
        >>> tracker = ProgressTracker(Path("data/processed/profiles"))
        >>> print(tracker.base_dir)
        PosixPath('data/processed/profiles')
        """
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def profile_path(self, learner_id: str) -> Path:
        """Return the JSON file path for a given learner ID."""
        return self.base_dir / f"{learner_id}.json"

    def load_profile(self, learner_id: str, name: str | None = None) -> LearnerProfile:
        """
        Load a learner profile from disk or create a default one if missing.
        
        This method checks if a profile file exists for the given learner ID.
        If found, it deserializes the JSON and constructs a LearnerProfile object.
        If not found, it creates a new profile with default values (all scores at 0.0).
        
        Parameters
        ----------
        learner_id : str
            Unique identifier for the learner. Used to construct the profile filename.
        name : str | None, default=None
            Human-readable name for the learner. Only used when creating a new
            profile. If None, defaults to the learner_id.
        
        Returns
        -------
        LearnerProfile
            Learner profile object with all tracked metrics (strengths, struggles,
            time, concepts, etc.). For new learners, all dictionaries are empty and
            total_time_minutes is 0.0.
        
        Raises
        ------
        json.JSONDecodeError
            If the profile file exists but contains invalid JSON.
        PermissionError
            If the profile file exists but cannot be read due to permissions.
        
        Examples
        --------
        >>> tracker = ProgressTracker(Path("data/processed/profiles"))
        >>> 
        >>> # Load existing profile
        >>> profile = tracker.load_profile("student123")
        >>> print(profile.name)
        "Alice Johnson"
        >>> 
        >>> # Create new profile
        >>> new_profile = tracker.load_profile("new_student", name="Bob Smith")
        >>> print(new_profile.domain_strengths)
        {}  # Empty for new learners
        >>> print(new_profile.total_time_minutes)
        0.0
        """
        path = self.profile_path(learner_id)
        
        # Create new profile if file doesn't exist
        if not path.exists():
            return LearnerProfile(learner_id=learner_id, name=name or learner_id)
        
        # Load and deserialize existing profile
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        
        profile = LearnerProfile(
            learner_id=data["learner_id"],
            name=data["name"],
            domain_strengths=data.get("domain_strengths", {}),
            domain_struggles=data.get("domain_struggles", {}),
            concepts_mastered=data.get("concepts_mastered", {}),
            total_time_minutes=data.get("total_time_minutes", 0.0),
            next_topics=data.get("next_topics", {}),
            difficulty_preferences=data.get("difficulty_preferences", {}),
        )
        return profile

    def save_profile(self, profile: LearnerProfile) -> None:
        """Serialize the learner profile back to disk."""
        path = self.profile_path(profile.learner_id)
        serialized = {
            "learner_id": profile.learner_id,
            "name": profile.name,
            "domain_strengths": profile.domain_strengths,
            "domain_struggles": profile.domain_struggles,
            "concepts_mastered": profile.concepts_mastered,
            "total_time_minutes": profile.total_time_minutes,
            "next_topics": profile.next_topics,
            "difficulty_preferences": profile.difficulty_preferences,
        }
        with path.open("w", encoding="utf-8") as handle:
            json.dump(serialized, handle, indent=2)

    def update_time_on_task(self, profile: LearnerProfile, minutes: float) -> LearnerProfile:
        """Accumulate minutes spent learning onto the profile's time counter."""
        profile.total_time_minutes += minutes
        return profile

    def mark_strength(self, profile: LearnerProfile, domain: str, delta: float) -> LearnerProfile:
        """
        Adjust the learner's strength score for a domain within bounds.
        
        This method performs an atomic update to a domain-specific strength score,
        clamping the result to the valid range [0.0, 1.0]. The delta can be positive
        (increasing mastery) or negative (decreasing mastery, rarely used).
        
        Parameters
        ----------
        profile : LearnerProfile
            Learner profile to update (modified in-place).
        domain : str
            Subject domain (e.g., "physics", "math", "cs"). Created if not exists.
        delta : float
            Amount to add to current strength score. Positive values increase mastery.
            Common values: +0.08 (Q&A interaction), +0.12 (quiz score ≥70%).
        
        Returns
        -------
        LearnerProfile
            The same profile object (modified in-place) for method chaining.
        
        Notes
        -----
        - If domain doesn't exist in profile, initializes at 0.0 before applying delta
        - Result is always clamped to [0.0, 1.0] regardless of delta magnitude
        - Profile is NOT saved to disk; caller must call save_profile()
        
        Examples
        --------
        >>> profile = tracker.load_profile("student123")
        >>> profile.domain_strengths["physics"] = 0.5
        >>> 
        >>> # Boost strength after successful interaction
        >>> profile = tracker.mark_strength(profile, "physics", 0.1)
        >>> print(profile.domain_strengths["physics"])
        0.6
        >>> 
        >>> # Large delta is clamped to 1.0
        >>> profile = tracker.mark_strength(profile, "physics", 0.8)
        >>> print(profile.domain_strengths["physics"])
        1.0
        >>> 
        >>> # Initialize new domain
        >>> profile = tracker.mark_strength(profile, "chemistry", 0.05)
        >>> print(profile.domain_strengths["chemistry"])
        0.05
        """
        current = profile.domain_strengths.get(domain, 0.0)
        profile.domain_strengths[domain] = max(0.0, min(1.0, current + delta))
        return profile

    def mark_struggle(self, profile: LearnerProfile, domain: str, delta: float) -> LearnerProfile:
        """
        Adjust the learner's struggle score for a domain within bounds.
        
        This method performs an atomic update to a domain-specific struggle score,
        clamping the result to [0.0, 1.0]. Higher struggle scores indicate the
        learner needs more support in that domain.
        
        Parameters
        ----------
        profile : LearnerProfile
            Learner profile to update (modified in-place).
        domain : str
            Subject domain (e.g., "physics", "math", "cs"). Created if not exists.
        delta : float
            Amount to add to current struggle score. Positive values indicate
            increased difficulty, negative values indicate improvement.
            Common values: +0.10 (quiz score <40%), -0.08 (quiz score ≥70%).
        
        Returns
        -------
        LearnerProfile
            The same profile object (modified in-place) for method chaining.
        
        Notes
        -----
        - Struggle score semantics: 0.0 = no struggles, 1.0 = significant struggles
        - Result is always clamped to [0.0, 1.0]
        - Often inversely correlated with strength (high strength → low struggle)
        - Profile is NOT saved to disk; caller must call save_profile()
        
        Examples
        --------
        >>> profile = tracker.load_profile("student123")
        >>> profile.domain_struggles["physics"] = 0.3
        >>> 
        >>> # Increase struggle after poor quiz performance
        >>> profile = tracker.mark_struggle(profile, "physics", 0.15)
        >>> print(profile.domain_struggles["physics"])
        0.45
        >>> 
        >>> # Decrease struggle after successful learning
        >>> profile = tracker.mark_struggle(profile, "physics", -0.2)
        >>> print(profile.domain_struggles["physics"])
        0.25
        """
        current = profile.domain_struggles.get(domain, 0.0)
        profile.domain_struggles[domain] = max(0.0, min(1.0, current + delta))
        return profile
