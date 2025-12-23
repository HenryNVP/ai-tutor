# Demo Mode Configuration

## Overview

Demo mode is a configuration flag that simplifies the AI Tutor system for demonstration purposes by disabling personalization features and using static defaults.

## Configuration

### Enable Demo Mode

Add to `config/default.yaml`:
```yaml
demo_mode: true  # Enable demo mode: disables personalization, simplifies features
```

Or set via environment variable:
```bash
export DEMO_MODE=true
```

### Default Value

Demo mode defaults to `false` (production mode with full personalization).

## What Demo Mode Does

### ✅ Disabled Features

1. **Personalization System**
   - No learner profile loading/saving
   - No adaptive difficulty adjustment
   - No style selection based on mastery
   - No progress tracking

2. **Profile Updates**
   - Quiz evaluations don't update profiles
   - Q&A interactions don't update profiles
   - No domain strength/struggle tracking

### ✅ Static Defaults Used

1. **Explanation Style**: Always `"stepwise"` (balanced, moderate guidance)
2. **Difficulty**: Uses provided difficulty or defaults to balanced
3. **No Recommendations**: `next_topic` and `difficulty` hints are not generated

### ✅ What Still Works

- ✅ Document ingestion
- ✅ Q&A with citations (RAG)
- ✅ Quiz generation
- ✅ Note generation
- ✅ Data visualization
- ✅ Source-filtered retrieval
- ✅ Session management (simplified)
- ✅ All core RAG features

## Code Changes

### Configuration Schema

Added `demo_mode: bool` field to `Settings` class in `src/ai_tutor/config/schema.py`.

### TutorSystem Changes

- Conditionally initializes `PersonalizationManager` and `ProgressTracker`
- `answer_question()` uses static style when demo_mode is enabled
- `create_quiz()` and `evaluate_quiz()` skip profile operations in demo mode

### QuizService Changes

- Accepts `None` for `progress_tracker` parameter
- Skips profile updates when `progress_tracker` is `None`

## Usage Examples

### Production Mode (demo_mode: false)

```python
# Full personalization enabled
system = TutorSystem.from_config()
response = system.answer_question("student123", "What is momentum?")
# Response includes:
# - Adaptive style based on learner mastery
# - next_topic recommendation
# - difficulty level
# - Profile updates saved to disk
```

### Demo Mode (demo_mode: true)

```python
# Personalization disabled, static defaults
system = TutorSystem.from_config()
response = system.answer_question("student123", "What is momentum?")
# Response includes:
# - Static "stepwise" style
# - No next_topic or difficulty hints
# - No profile updates
```

## Benefits

1. **Simpler Setup**: No profile directory needed
2. **Faster Startup**: No personalization initialization
3. **Consistent Behavior**: Same experience for all users
4. **Easier Debugging**: No profile state to track
5. **Focus on RAG**: Highlights core RAG capabilities

## Migration

To switch between modes:

1. **Enable Demo Mode**: Set `demo_mode: true` in config
2. **Disable Demo Mode**: Set `demo_mode: false` in config
3. **Restart**: Restart the application to apply changes

No data migration needed - profiles are simply not used in demo mode.

## Future Enhancements

Demo mode can be extended to:
- Simplify routing (keyword-based only)
- Disable MCP servers
- Use simplified error messages
- Reduce logging verbosity

