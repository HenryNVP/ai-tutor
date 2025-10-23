"""Tests for quiz profile update functionality."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ai_tutor.agents.llm_client import LLMClient
from ai_tutor.config.schema import ModelConfig, RetrievalConfig
from ai_tutor.ingestion.embeddings import EmbeddingClient
from ai_tutor.learning.models import LearnerProfile
from ai_tutor.learning.progress import ProgressTracker
from ai_tutor.learning.quiz import Quiz, QuizQuestion, QuizService
from ai_tutor.retrieval.simple_store import SimpleVectorStore
from ai_tutor.retrieval.retriever import Retriever


@pytest.fixture
def temp_profile_dir():
    """Create a temporary directory for profile storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def progress_tracker(temp_profile_dir):
    """Create a progress tracker with temporary storage."""
    return ProgressTracker(temp_profile_dir)


@pytest.fixture
def learner_profile(progress_tracker):
    """Create a test learner profile."""
    profile = LearnerProfile(
        learner_id="test_learner",
        name="Test Learner",
        domain_strengths={},
        domain_struggles={},
        concepts_mastered={},
        total_time_minutes=0.0,
        next_topics={},
        difficulty_preferences={},
    )
    progress_tracker.save_profile(profile)
    return profile


@pytest.fixture
def sample_quiz():
    """Create a sample quiz for testing."""
    return Quiz(
        topic="Physics Basics",
        difficulty="balanced",
        questions=[
            QuizQuestion(
                question="What is Newton's first law?",
                choices=[
                    "An object in motion stays in motion",
                    "F = ma",
                    "Every action has a reaction",
                    "E = mc²",
                ],
                correct_index=0,
                explanation="Newton's first law is the law of inertia.",
                references=["Physics textbook p. 42"],
            ),
            QuizQuestion(
                question="What is the unit of force?",
                choices=["Joule", "Newton", "Watt", "Pascal"],
                correct_index=1,
                explanation="Force is measured in Newtons (N).",
                references=["Physics textbook p. 45"],
            ),
            QuizQuestion(
                question="What is acceleration?",
                choices=[
                    "Rate of change of position",
                    "Rate of change of velocity",
                    "Rate of change of force",
                    "Rate of change of energy",
                ],
                correct_index=1,
                explanation="Acceleration is the rate of change of velocity.",
                references=["Physics textbook p. 50"],
            ),
            QuizQuestion(
                question="What is the formula for kinetic energy?",
                choices=["mgh", "1/2 mv²", "mv", "F/m"],
                correct_index=1,
                explanation="Kinetic energy = 1/2 * mass * velocity².",
                references=["Physics textbook p. 60"],
            ),
        ],
        references=["Physics textbook"],
    )


def test_excellent_performance_updates_profile(
    progress_tracker, learner_profile, sample_quiz
):
    """Test that excellent quiz performance (100%) increases strengths significantly."""
    # Mock dependencies
    with tempfile.TemporaryDirectory() as tmpdir:
        vector_store = SimpleVectorStore(Path(tmpdir) / "vectors")
        retriever = Retriever(
            RetrievalConfig(top_k=5),
            embedder=None,  # Not needed for this test
            vector_store=vector_store,
        )
        llm_client = None  # Not needed for evaluation
        
        quiz_service = QuizService(
            retriever=retriever,
            llm_client=llm_client,
            progress_tracker=progress_tracker,
        )
        
        # All answers correct (100% score)
        answers = [0, 1, 1, 1]
        
        initial_strength = learner_profile.domain_strengths.get(
            "physics basics", 0.0
        )
        initial_time = learner_profile.total_time_minutes
        
        # Evaluate quiz
        evaluation = quiz_service.evaluate_quiz(
            quiz=sample_quiz,
            answers=answers,
            profile=learner_profile,
        )
        
        # Assertions
        assert evaluation.score == 1.0
        assert evaluation.correct_count == 4
        
        # Check profile updates
        final_strength = learner_profile.domain_strengths.get("physics basics", 0.0)
        assert final_strength > initial_strength, "Strength should increase"
        assert final_strength >= 0.15, "Excellent performance should give +0.15 strength"
        
        # Check struggle decreased
        final_struggle = learner_profile.domain_struggles.get("physics basics", 0.0)
        assert final_struggle == 0.0, "Struggle should be minimal or negative"
        
        # Check time updated
        assert learner_profile.total_time_minutes > initial_time
        assert learner_profile.total_time_minutes == initial_time + (4 * 1.5)
        
        # Check difficulty preference
        assert learner_profile.difficulty_preferences.get("physics basics") == "independent challenge"
        
        # Check concepts mastered
        assert len(learner_profile.concepts_mastered) > 0


def test_poor_performance_updates_profile(
    progress_tracker, learner_profile, sample_quiz
):
    """Test that poor quiz performance (25%) increases struggles."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vector_store = SimpleVectorStore(Path(tmpdir) / "vectors")
        retriever = Retriever(
            RetrievalConfig(top_k=5),
            embedder=None,
            vector_store=vector_store,
        )
        
        quiz_service = QuizService(
            retriever=retriever,
            llm_client=None,
            progress_tracker=progress_tracker,
        )
        
        # Only 1 correct answer (25% score)
        answers = [0, 0, 0, 0]  # First is correct, others are wrong
        
        initial_strength = learner_profile.domain_strengths.get(
            "physics basics", 0.0
        )
        initial_struggle = learner_profile.domain_struggles.get(
            "physics basics", 0.0
        )
        
        # Evaluate quiz
        evaluation = quiz_service.evaluate_quiz(
            quiz=sample_quiz,
            answers=answers,
            profile=learner_profile,
        )
        
        # Assertions
        assert evaluation.score == 0.25
        assert evaluation.correct_count == 1
        
        # Check profile updates
        final_strength = learner_profile.domain_strengths.get("physics basics", 0.0)
        assert final_strength > initial_strength, "Strength should increase slightly"
        assert final_strength <= 0.05, "Poor performance should give small strength increase"
        
        # Check struggle increased
        final_struggle = learner_profile.domain_struggles.get("physics basics", 0.0)
        assert final_struggle > initial_struggle, "Struggle should increase"
        assert final_struggle >= 0.12, "Poor performance should give +0.12 struggle"
        
        # Check difficulty preference
        assert learner_profile.difficulty_preferences.get("physics basics") == "foundational guidance"
        
        # Check review topics
        assert len(evaluation.review_topics) == 3, "Should have 3 incorrect answers to review"


def test_moderate_performance_balanced_updates(
    progress_tracker, learner_profile, sample_quiz
):
    """Test that moderate quiz performance (50%) gives balanced updates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vector_store = SimpleVectorStore(Path(tmpdir) / "vectors")
        retriever = Retriever(
            RetrievalConfig(top_k=5),
            embedder=None,
            vector_store=vector_store,
        )
        
        quiz_service = QuizService(
            retriever=retriever,
            llm_client=None,
            progress_tracker=progress_tracker,
        )
        
        # 2 correct answers (50% score)
        answers = [0, 1, 0, 0]  # First two correct
        
        # Evaluate quiz
        evaluation = quiz_service.evaluate_quiz(
            quiz=sample_quiz,
            answers=answers,
            profile=learner_profile,
        )
        
        # Assertions
        assert evaluation.score == 0.5
        assert evaluation.correct_count == 2
        
        # Check profile updates
        final_strength = learner_profile.domain_strengths.get("physics basics", 0.0)
        assert final_strength == 0.05, "Moderate performance should give +0.05 strength"
        
        # Check struggle
        final_struggle = learner_profile.domain_struggles.get("physics basics", 0.0)
        assert final_struggle == 0.05, "Moderate performance should give +0.05 struggle"
        
        # Check difficulty preference
        assert learner_profile.difficulty_preferences.get("physics basics") == "guided practice"


def test_concepts_mastered_only_for_correct_answers(
    progress_tracker, learner_profile, sample_quiz
):
    """Test that only correctly answered questions update concepts_mastered."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vector_store = SimpleVectorStore(Path(tmpdir) / "vectors")
        retriever = Retriever(
            RetrievalConfig(top_k=5),
            embedder=None,
            vector_store=vector_store,
        )
        
        quiz_service = QuizService(
            retriever=retriever,
            llm_client=None,
            progress_tracker=progress_tracker,
        )
        
        # 2 correct answers
        answers = [0, 1, 0, 0]
        
        # Evaluate quiz
        quiz_service.evaluate_quiz(
            quiz=sample_quiz,
            answers=answers,
            profile=learner_profile,
        )
        
        # Only 2 concepts should be mastered (questions 0 and 1)
        assert len(learner_profile.concepts_mastered) == 2
        
        # Check that the first two questions are tracked
        for idx in [0, 1]:
            concept_key = sample_quiz.questions[idx].question[:50].lower().strip()
            assert concept_key in learner_profile.concepts_mastered
            assert learner_profile.concepts_mastered[concept_key] == 0.15


def test_profile_persistence(
    progress_tracker, learner_profile, sample_quiz
):
    """Test that profile updates are persisted correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vector_store = SimpleVectorStore(Path(tmpdir) / "vectors")
        retriever = Retriever(
            RetrievalConfig(top_k=5),
            embedder=None,
            vector_store=vector_store,
        )
        
        quiz_service = QuizService(
            retriever=retriever,
            llm_client=None,
            progress_tracker=progress_tracker,
        )
        
        # All answers correct
        answers = [0, 1, 1, 1]
        
        # Evaluate quiz
        quiz_service.evaluate_quiz(
            quiz=sample_quiz,
            answers=answers,
            profile=learner_profile,
        )
        
        # Save profile
        progress_tracker.save_profile(learner_profile)
        
        # Load profile again
        loaded_profile = progress_tracker.load_profile("test_learner")
        
        # Verify all updates are persisted
        assert loaded_profile.domain_strengths.get("physics basics") == 0.15
        assert loaded_profile.total_time_minutes == 6.0
        assert loaded_profile.difficulty_preferences.get("physics basics") == "independent challenge"
        assert len(loaded_profile.concepts_mastered) == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

