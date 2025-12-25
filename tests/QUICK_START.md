# Test Suite Quick Start

## Quick Commands

### Using `uv` (Recommended)

```bash
# First time setup: Install all dependencies including dev dependencies
uv sync --dev

# Default: Run unit + integration tests (safe, fast)
# Note: Use --all-extras to include dev dependencies (pytest, etc.)
uv run --all-extras pytest tests/ -v

# Run all tests including E2E
uv run --all-extras pytest tests/ -m "" -v

# Run by category
uv run --all-extras pytest tests/ -m unit -v          # Unit tests only
uv run --all-extras pytest tests/ -m integration -v   # Integration tests only
uv run --all-extras pytest tests/ -m e2e -v           # E2E tests only

# Run by directory
uv run --all-extras pytest tests/unit/ -v             # Unit tests
uv run --all-extras pytest tests/integration/ -v      # Integration tests
uv run --all-extras pytest tests/e2e/ -v              # E2E tests

# Run specific test file
uv run --all-extras pytest tests/unit/test_unit_simple.py -v

# Run specific test function
uv run --all-extras pytest tests/unit/test_unit_simple.py::test_detect_quiz_request -v
```

**Note**: After running `uv sync --dev`, you can also use `uv run pytest` without `--all-extras` if the virtual environment is properly set up. The `--all-extras` flag ensures dev dependencies (like pytest) are available.

### Using `pytest` directly (if virtual environment is activated)

```bash
# Default: Run unit + integration tests (safe, fast)
pytest tests/ -v

# Run all tests including E2E
pytest tests/ -m "" -v

# Run by category
pytest tests/ -m unit -v          # Unit tests only
pytest tests/ -m integration -v   # Integration tests only
pytest tests/ -m e2e -v           # E2E tests only
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

### Using `uv`

```bash
# Quick check during development
uv run --all-extras pytest tests/unit/ -v

# Before committing
uv run --all-extras pytest tests/unit/ tests/integration/ -v

# Full test suite
uv run --all-extras pytest tests/ -m "" -v
```

### Using `pytest` directly (if virtual environment is activated)

```bash
# Quick check during development
pytest tests/unit/ -v

# Before committing
pytest tests/unit/ tests/integration/ -v

# Full test suite
pytest tests/ -m "" -v
```

See [README.md](README.md) for test descriptions.

