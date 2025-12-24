# Test Suite Quick Start

## Quick Commands

```bash
# Default: Run unit + integration tests (safe, fast)
pytest tests/ -v

# Run all tests including E2E
pytest tests/ -m "" -v

# Run by category
pytest tests/ -m unit -v          # Unit tests only
pytest tests/ -m integration -v   # Integration tests only
pytest tests/ -m e2e -v           # E2E tests only

# Run by directory
pytest tests/unit/ -v             # Unit tests
pytest tests/integration/ -v      # Integration tests
pytest tests/e2e/ -v              # E2E tests

# Run specific test file
pytest tests/unit/test_unit_simple.py -v

# Run specific test function
pytest tests/unit/test_unit_simple.py::test_basic_math -v
```

## What Gets Run?

- **Default** (`pytest tests/`): Unit + Integration (E2E skipped)
- **All** (`pytest tests/ -m ""`): Everything including E2E
- **Safe** (`pytest tests/ -m "not e2e"`): Unit + Integration only

## Requirements

- **Unit**: Just Python + pytest ✅
- **Integration**: Project dependencies ✅
- **E2E**: Full dependencies + API keys ⚠️

## Common Workflows

```bash
# Quick check during development
pytest tests/unit/ -v

# Before committing
pytest tests/unit/ tests/integration/ -v

# Full test suite
pytest tests/ -m "" -v
```

See [README.md](README.md) for test descriptions.

