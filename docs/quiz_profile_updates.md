# Quiz Profile Update Feature

## Overview

The quiz app now automatically updates learner profiles based on quiz performance. After a learner completes a quiz, their profile is updated with:

- **Domain Strengths**: Increased based on quiz performance
- **Domain Struggles**: Adjusted to reflect areas needing support
- **Concepts Mastered**: Tracks correctly answered questions
- **Difficulty Preferences**: Updated based on performance level
- **Study Time**: Accumulated based on quiz length
- **Next Topics**: Suggested based on review topics

## How It Works

### 1. Quiz Evaluation Flow

```
User completes quiz
    ↓
TutorSystem.evaluate_quiz() called
    ↓
QuizService.evaluate_quiz() scores the quiz
    ↓
QuizService._update_profile_from_quiz() updates the profile
    ↓
Profile saved to disk
```

### 2. Profile Updates Based on Performance

#### Excellent Performance (≥80%)
- **Strength Delta**: +0.15
- **Struggle Delta**: -0.10
- **Difficulty Preference**: "independent challenge"

#### Good Performance (60-79%)
- **Strength Delta**: +0.10
- **Struggle Delta**: -0.05
- **Difficulty Preference**: "guided practice"

#### Moderate Performance (40-59%)
- **Strength Delta**: +0.05
- **Struggle Delta**: +0.05
- **Difficulty Preference**: "guided practice"

#### Poor Performance (<40%)
- **Strength Delta**: +0.02
- **Struggle Delta**: +0.12
- **Difficulty Preference**: "foundational guidance"

### 3. Profile Fields Updated

#### Domain Strengths & Struggles
The quiz topic is used as the domain identifier. Strength and struggle scores are bounded between 0.0 and 1.0.

#### Concepts Mastered
For each correct answer, the first 50 characters of the question are used as a concept identifier, and mastery is increased by 0.15 (capped at 1.0).

#### Study Time
Estimated as 1.5 minutes per question and added to the learner's total study time.

#### Difficulty Preferences
Updated per domain based on quiz performance to guide future content difficulty.

#### Next Topics
Set to the first review topic (if any) to guide future learning sessions.

## Usage

### In the Quiz App

1. **Generate a quiz** by entering a topic and clicking "Generate quiz"
2. **Answer the questions** by selecting options
3. **Submit answers** to see results
4. **Profile is automatically updated** based on performance
5. **View updated profile** in the sidebar "Profile Summary" section

### Programmatically

```python
from ai_tutor.system import TutorSystem

# Initialize system
system = TutorSystem.from_config()

# Generate quiz
quiz = system.generate_quiz(
    learner_id="student123",
    topic="Newton's laws of motion",
    num_questions=4,
)

# Evaluate quiz (profile is automatically updated)
evaluation = system.evaluate_quiz(
    learner_id="student123",
    quiz_payload=quiz,
    answers=[0, 2, 1, 3],  # Answer indices
)

# Profile is now updated and saved
profile = system.personalizer.load_profile("student123")
print(f"Updated strength: {profile.domain_strengths}")
```

## Demo Script

Run the demonstration script to see profile updates in action:

```bash
python scripts/demo_profile_update.py
```

This script will:
1. Create a test learner profile
2. Generate a quiz on "Newton's laws of motion"
3. Simulate quiz answers (75% score)
4. Show profile before and after updates
5. Display all changes made to the profile

## Files Modified

### Core Implementation
- **`src/ai_tutor/learning/quiz.py`**
  - Added `_update_profile_from_quiz()` method
  - Modified `evaluate_quiz()` to call profile update

### UI Enhancements
- **`apps/quiz.py`**
  - Added profile update notification after quiz submission
  - Added "Profile Summary" section in sidebar showing real-time profile data

### Documentation & Demo
- **`docs/quiz_profile_updates.md`** (this file)
  - Documentation of the feature
- **`scripts/demo_profile_update.py`**
  - Demo script showing profile updates

## Benefits

1. **Adaptive Learning**: The system learns from quiz performance and adjusts difficulty
2. **Progress Tracking**: Learners can see their strengths and weaknesses evolve
3. **Personalized Content**: Future quizzes and content are tailored based on profile
4. **Motivation**: Visual feedback on progress encourages continued learning
5. **Data-Driven**: Profile updates are based on objective quiz performance

## Future Enhancements

Potential improvements for the profile update system:

1. **More Sophisticated Concept Extraction**: Use NLP to better identify concepts from questions
2. **Weighted Updates**: Weight profile updates by question difficulty
3. **Domain Detection**: Automatically detect domain from quiz content using metadata or embeddings
4. **Historical Tracking**: Store quiz history and show progress over time
5. **Concept Graph**: Build relationships between mastered concepts
6. **Adaptive Difficulty**: Automatically adjust quiz difficulty based on recent performance
7. **Spaced Repetition**: Suggest review of topics based on time since last quiz

## Testing

To test the feature:

1. **Unit Tests**: Test profile update logic
   ```bash
   pytest tests/test_quiz_profile_updates.py
   ```

2. **Integration Test**: Run the demo script
   ```bash
   python scripts/demo_profile_update.py
   ```

3. **Manual Testing**: Use the quiz app
   ```bash
   streamlit run scripts/quiz_app.py
   ```

## Troubleshooting

### Profile Not Updating
- Ensure learner_id is consistent between quiz generation and evaluation
- Check that the profile directory exists and is writable
- Verify API key is set for quiz generation

### Incorrect Scores
- Ensure answer indices match question order
- Verify correct_index is properly set in quiz questions
- Check that answers are zero-indexed integers

### Missing Profile Data
- Profile is created on first use with default values
- Run demo script to populate sample profile data
- Check file permissions on `data/processed/profiles/` directory

