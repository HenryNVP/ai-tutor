#!/usr/bin/env python3
"""Demo script showing how quiz results update learner profiles."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_tutor.system import TutorSystem


def print_profile(profile, label: str) -> None:
    """Print a formatted profile summary."""
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    print(f"Learner ID: {profile.learner_id}")
    print(f"Name: {profile.name}")
    print(f"Total study time: {profile.total_time_minutes:.1f} minutes")
    
    if profile.domain_strengths:
        print("\nDomain Strengths:")
        for domain, score in sorted(profile.domain_strengths.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {domain}: {score:.2f}")
    
    if profile.domain_struggles:
        print("\nDomain Struggles:")
        for domain, score in sorted(profile.domain_struggles.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {domain}: {score:.2f}")
    
    if profile.difficulty_preferences:
        print("\nDifficulty Preferences:")
        for domain, pref in profile.difficulty_preferences.items():
            print(f"  • {domain}: {pref}")
    
    if profile.concepts_mastered:
        print(f"\nConcepts Mastered: {len(profile.concepts_mastered)}")
        for concept, score in sorted(profile.concepts_mastered.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  • {concept[:40]}...: {score:.2f}")
    print(f"{'=' * 60}\n")


def main():
    """Run the demo."""
    print("Quiz Profile Update Demo")
    print("=" * 60)
    
    # Initialize system
    print("\n1. Initializing AI Tutor System...")
    system = TutorSystem.from_config()
    
    # Use test learner
    learner_id = "demo_test_learner"
    print(f"2. Using learner ID: {learner_id}")
    
    # Load initial profile
    print("\n3. Loading initial profile...")
    profile_before = system.personalizer.load_profile(learner_id)
    print_profile(profile_before, "PROFILE BEFORE QUIZ")
    
    # Generate a quiz
    topic = "Newton's laws of motion"
    num_questions = 4
    print(f"\n4. Generating quiz on '{topic}' with {num_questions} questions...")
    quiz = system.generate_quiz(
        learner_id=learner_id,
        topic=topic,
        num_questions=num_questions,
    )
    print(f"✓ Generated {len(quiz.questions)} questions")
    
    # Display quiz questions
    print("\n5. Quiz Questions:")
    for idx, q in enumerate(quiz.questions, 1):
        print(f"\nQ{idx}. {q.question}")
        for choice_idx, choice in enumerate(q.choices):
            marker = "→" if choice_idx == q.correct_index else " "
            print(f"   {marker} {chr(65 + choice_idx)}. {choice}")
    
    # Simulate answers (mix of correct and incorrect)
    print("\n6. Simulating learner answers...")
    # Answer pattern: correct, incorrect, correct, correct (75% score)
    simulated_answers = [
        quiz.questions[0].correct_index,  # Correct
        (quiz.questions[1].correct_index + 1) % 4,  # Incorrect
        quiz.questions[2].correct_index,  # Correct
        quiz.questions[3].correct_index,  # Correct
    ]
    
    print("Simulated answers:")
    for idx, answer in enumerate(simulated_answers):
        is_correct = answer == quiz.questions[idx].correct_index
        status = "✓ Correct" if is_correct else "✗ Incorrect"
        print(f"  Q{idx + 1}: Answer {chr(65 + answer)} - {status}")
    
    # Evaluate quiz
    print("\n7. Evaluating quiz and updating profile...")
    evaluation = system.evaluate_quiz(
        learner_id=learner_id,
        quiz_payload=quiz,
        answers=simulated_answers,
    )
    
    print(f"\n✓ Evaluation complete!")
    print(f"  Score: {evaluation.correct_count}/{evaluation.total_questions} ({evaluation.score * 100:.0f}%)")
    
    # Load updated profile
    print("\n8. Loading updated profile...")
    profile_after = system.personalizer.load_profile(learner_id)
    print_profile(profile_after, "PROFILE AFTER QUIZ")
    
    # Show changes
    print("\n9. Profile Changes:")
    print(f"{'=' * 60}")
    
    # Study time change
    time_change = profile_after.total_time_minutes - profile_before.total_time_minutes
    print(f"Study time: {profile_before.total_time_minutes:.1f} → {profile_after.total_time_minutes:.1f} min (+{time_change:.1f})")
    
    # Domain strength changes
    domain = topic.lower()
    strength_before = profile_before.domain_strengths.get(domain, 0.0)
    strength_after = profile_after.domain_strengths.get(domain, 0.0)
    print(f"Domain strength ({domain}): {strength_before:.2f} → {strength_after:.2f} (+{strength_after - strength_before:.2f})")
    
    # Domain struggle changes
    struggle_before = profile_before.domain_struggles.get(domain, 0.0)
    struggle_after = profile_after.domain_struggles.get(domain, 0.0)
    print(f"Domain struggle ({domain}): {struggle_before:.2f} → {struggle_after:.2f} ({struggle_after - struggle_before:+.2f})")
    
    # Difficulty preference
    pref_before = profile_before.difficulty_preferences.get(domain, "N/A")
    pref_after = profile_after.difficulty_preferences.get(domain, "N/A")
    print(f"Difficulty preference: {pref_before} → {pref_after}")
    
    # Concepts mastered
    concepts_before = len(profile_before.concepts_mastered)
    concepts_after = len(profile_after.concepts_mastered)
    print(f"Concepts mastered: {concepts_before} → {concepts_after} (+{concepts_after - concepts_before})")
    
    print(f"{'=' * 60}\n")
    
    print("✓ Demo complete! The learner profile was successfully updated based on quiz performance.")
    print(f"  Profile saved to: {system.progress_tracker.profile_path(learner_id)}")


if __name__ == "__main__":
    main()

