from __future__ import annotations
from typing import Dict, List, Optional, Sequence

from ai_tutor.learning.models import LearnerProfile
from ai_tutor.learning.planner import UNIT_LIBRARY
from ai_tutor.learning.progress import ProgressTracker


class PersonalizationManager:
    """
    Coordinate learner memory, mastery tracking, and adaptive preferences.
    
    This manager implements the adaptive learning logic that personalizes the
    tutoring experience based on student performance. It tracks domain-specific
    strengths and struggles, selects appropriate explanation styles, and
    recommends next topics to address knowledge gaps.
    
    The personalization system operates on a continuous scale from 0.0 (no mastery)
    to 1.0 (full mastery) for each domain. These scores are updated incrementally
    based on interactions and quiz performance, creating a nuanced learner model.
    
    Adaptation Mechanisms
    ---------------------
    1. **Style Selection**: Choose explanation approach based on mastery
       - Low mastery (≤0.3): "scaffolded" - step-by-step with high support
       - Medium (0.3-0.7): "stepwise" - moderate guidance with examples
       - High mastery (≥0.7): "concise" - challenge-oriented, minimal scaffolding
    
    2. **Difficulty Adjustment**: Set assessment difficulty dynamically
       - Low mastery: "foundational guidance" - basic concepts, explicit hints
       - Medium: "guided practice" - standard difficulty with explanations
       - High mastery: "independent challenge" - advanced problems, minimal help
    
    3. **Topic Sequencing**: Recommend next topics based on knowledge gaps
       - Scans course unit library for each domain
       - Identifies topics with lowest mastery scores
       - Prioritizes prerequisite concepts before advanced ones
    
    Attributes
    ----------
    tracker : ProgressTracker
        Handles persistence and atomic updates to learner profiles stored as JSON.
    
    Examples
    --------
    >>> from pathlib import Path
    >>> tracker = ProgressTracker(Path("data/processed/profiles"))
    >>> manager = PersonalizationManager(tracker)
    >>> 
    >>> # Load and personalize for a learner
    >>> profile = manager.load_profile("student123")
    >>> style = manager.select_style(profile, "physics")
    >>> print(style)  # "scaffolded", "stepwise", or "concise"
    >>> 
    >>> # Record a Q&A interaction
    >>> hits = [...]  # Retrieval results from vector store
    >>> domain = manager.infer_domain(hits)
    >>> personalization = manager.record_interaction(
    ...     profile=profile,
    ...     question="What is momentum?",
    ...     answer="Momentum is mass times velocity...",
    ...     domain=domain,
    ...     citations=["[1] Physics Vol 1 (Page 42)"]
    ... )
    >>> print(personalization["difficulty"])  # "guided practice"
    >>> print(personalization["next_topic"])  # "conservation of momentum"
    >>> 
    >>> manager.save_profile(profile)
    """

    def __init__(self, tracker: ProgressTracker):
        """
        Initialize the personalization manager with a progress tracker.
        
        Parameters
        ----------
        tracker : ProgressTracker
            Progress tracker instance for loading/saving learner profiles.
            Must be initialized with a valid profiles directory path.
        """
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
        Choose an explanation style based on learner's domain mastery.
        
        This is a core personalization function that adapts the teaching approach
        to the student's current skill level. Styles influence prompt engineering
        in the LLM generation phase, affecting verbosity, scaffolding, and examples.
        
        Style Definitions
        -----------------
        - **scaffolded** (mastery ≤0.3): Maximum support
          * Detailed step-by-step breakdowns
          * Explicit prerequisite review
          * Multiple examples with worked solutions
          * Frequent comprehension checks
          
        - **stepwise** (0.3 < mastery < 0.7): Moderate guidance
          * Clear explanations with some detail
          * Examples with partial solutions
          * Hints rather than full scaffolding
          * Balance of guidance and independence
          
        - **concise** (mastery ≥0.7): Minimal scaffolding
          * Brief, technical explanations
          * Challenging problems without hints
          * Assumes prerequisite knowledge
          * Encourages independent problem-solving
        
        Parameters
        ----------
        profile : LearnerProfile
            The learner's profile containing domain_strengths dictionary.
        domain : Optional[str]
            Subject domain (e.g., "physics", "math", "cs"). If None or not
            in profile, defaults to "stepwise" (medium guidance).
        
        Returns
        -------
        str
            One of "scaffolded", "stepwise", or "concise" based on mastery level.
        
        Examples
        --------
        >>> profile = LearnerProfile(
        ...     learner_id="student123",
        ...     domain_strengths={"physics": 0.25, "math": 0.65, "cs": 0.85}
        ... )
        >>> manager.select_style(profile, "physics")
        'scaffolded'  # Low mastery → high support
        >>> manager.select_style(profile, "math")
        'stepwise'    # Medium mastery → balanced approach
        >>> manager.select_style(profile, "cs")
        'concise'     # High mastery → minimal scaffolding
        >>> manager.select_style(profile, None)
        'stepwise'    # Unknown domain → safe default
        """
        # Default to balanced style if domain not specified
        if not domain:
            return "stepwise"
        
        # Look up learner's mastery score for this domain (0.0 if never seen)
        mastery = profile.domain_strengths.get(domain, 0.0)
        
        # Map mastery to appropriate style
        if mastery <= 0.3:
            return "scaffolded"  # Beginner: needs high support
        if mastery >= 0.7:
            return "concise"     # Advanced: ready for challenges
        return "stepwise"        # Intermediate: balanced guidance

    def record_interaction(
        self,
        profile: LearnerProfile,
        question: str,
        answer: str,
        domain: Optional[str],
        citations: Sequence[str],
    ) -> Dict[str, Optional[str]]:
        """
        Update learner profile based on a Q&A interaction.
        
        This method implements incremental learning by adjusting domain mastery
        scores after each question. The assumption is that asking a question
        demonstrates engagement and leads to knowledge gain, so we increase
        strength scores. Struggle scores are adjusted based on current mastery
        to reflect confidence level.
        
        Update Logic
        ------------
        1. **Strength Boost**: +0.08 to domain strength (bounded at 1.0)
           - Reflects knowledge gain from the interaction
           - Accumulates over multiple questions to build mastery
        
        2. **Struggle Adjustment**: Dynamic based on current level
           - If mastery > 0.5: -0.04 (student is overcoming challenges)
           - If mastery ≤ 0.5: +0.04 (student still needs support)
        
        3. **Topic Recommendation**: Identify next concept to study
           - Scans course unit library for domain
           - Selects topic with lowest mastery score
           - Updates concepts_mastered with +0.05 increment
        
        4. **Difficulty Update**: Set difficulty label for future interactions
           - Based on updated mastery score
           - Stored in profile for quiz generation and style selection
        
        Parameters
        ----------
        profile : LearnerProfile
            Learner's profile to be updated (modified in-place).
        question : str
            The question asked by the student. Currently for logging/future use.
        answer : str
            The generated answer. Currently for logging/future use.
        domain : Optional[str]
            Subject domain inferred from retrieval hits. If None, no updates occur.
        citations : Sequence[str]
            List of citations used in the answer. Currently for logging/future use.
        
        Returns
        -------
        Dict[str, Optional[str]]
            Personalization recommendations with keys:
            - "next_topic": Suggested next concept to study (or None if domain unknown)
            - "difficulty": Current difficulty level label (or None if domain unknown)
        
        Notes
        -----
        - Profile is modified in-place but NOT saved to disk. Caller must call
          personalizer.save_profile(profile) to persist changes.
        - If domain is None, returns empty recommendations and makes no updates.
        - Updates are incremental; mastery changes slowly over many interactions.
        
        Examples
        --------
        >>> profile = manager.load_profile("student123")
        >>> initial_strength = profile.domain_strengths.get("physics", 0.0)
        >>> 
        >>> # Record a physics Q&A interaction
        >>> personalization = manager.record_interaction(
        ...     profile=profile,
        ...     question="What is Newton's third law?",
        ...     answer="For every action, there is an equal and opposite reaction...",
        ...     domain="physics",
        ...     citations=["[1] Physics Vol 1 (Page 92)"]
        ... )
        >>> 
        >>> updated_strength = profile.domain_strengths["physics"]
        >>> print(f"Strength increased from {initial_strength:.2f} to {updated_strength:.2f}")
        >>> print(f"Next topic: {personalization['next_topic']}")
        >>> print(f"Difficulty: {personalization['difficulty']}")
        >>> 
        >>> manager.save_profile(profile)  # Persist to disk
        """
        # Skip updates if domain not identified
        if not domain:
            return {"next_topic": None, "difficulty": None}

        # Boost domain strength by fixed increment
        profile = self.tracker.mark_strength(profile, domain, 0.08)
        
        # Get updated mastery score
        mastery = profile.domain_strengths.get(domain, 0.0)
        
        # Adjust struggle score based on mastery level
        # Higher mastery → less struggle; lower mastery → continued struggle
        struggle_delta = -0.04 if mastery > 0.5 else 0.04
        profile = self.tracker.mark_struggle(profile, domain, struggle_delta)

        # Identify next topic to address knowledge gaps
        next_topic = self._choose_next_topic(profile, domain)
        
        # Map mastery to difficulty label
        difficulty = self._difficulty_label(mastery)
        
        # Update profile metadata for future interactions
        profile.difficulty_preferences[domain] = difficulty
        if next_topic:
            profile.next_topics[domain] = next_topic
            # Partially credit mastery for the recommended topic
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
