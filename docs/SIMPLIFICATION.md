# Simplification Guide

## Completed Simplifications

### ✅ CLI Removal
- Deleted `src/ai_tutor/cli.py`
- Removed CLI script from `pyproject.toml`

### ✅ Session Management Simplification
- Removed daily rotation logic
- Removed turn-based pruning
- Simplified to one session per learner
- **Impact**: ~100 lines removed

### ✅ Demo Mode Flag
- Added `demo_mode: bool` to config schema
- Enabled by default in `config/default.yaml`
- Disables personalization when enabled
- **Impact**: Faster startup, simpler code path

### ✅ Routing Simplification
- Removed LLM-based routing fallback
- Uses keyword-based routing only
- Defaults to QA for generic questions
- **Impact**: ~150 lines removed, faster responses

## Current State

- **Code Reduction**: ~250 lines removed/simplified
- **Performance**: Faster responses, faster startup
- **Complexity**: Simpler debugging, more predictable behavior
- **Maintainability**: Clear separation between demo and production modes

## Demo Mode

When `demo_mode: true`:
- ❌ Personalization disabled
- ❌ Adaptive difficulty disabled
- ❌ Progress tracking disabled
- ✅ Static "stepwise" style
- ✅ All core RAG features enabled

## Configuration

- `config/default.yaml` - Full config (demo mode enabled by default)
- `config/demo.yaml` - Minimal config for quick demos

## See Also

- [GETTING_STARTED.md](GETTING_STARTED.md) - Quick start guide
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture

