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
uv run --all-extras pytest tests/ -m mcp -v           # MCP server tests (requires servers running)

# Run by directory
uv run --all-extras pytest tests/unit/ -v             # Unit tests
uv run --all-extras pytest tests/integration/ -v      # Integration tests
uv run --all-extras pytest tests/e2e/ -v              # E2E tests

# Run specific test file
uv run --all-extras pytest tests/unit/test_unit_simple.py -v

# Run specific test function
uv run --all-extras pytest tests/unit/test_unit_simple.py::test_detect_quiz_request -v

# Run E2E tests with real PDF document (requires API keys)
uv run --all-extras pytest tests/e2e/test_lecture8_document.py -m e2e -v
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
pytest tests/ -m mcp -v           # MCP server tests (requires servers running)

# Run MCP tests (requires MCP servers to be started first)
# Terminal 1: cd chroma_mcp_server && python server.py
# Terminal 2: cd filesystem_mcp_server && python server.py
# Terminal 3: pytest tests/integration/test_mcp_servers.py -m mcp -v
#            pytest tests/integration/test_gemini_mcp_compat.py -m mcp -v
```

## What Gets Run?

- **Default** (`pytest tests/`): Unit + Integration (E2E and MCP skipped)
- **All** (`pytest tests/ -m ""`): Everything including E2E and MCP
- **Safe** (`pytest tests/ -m "not e2e and not mcp"`): Unit + Integration only

## Requirements

- **Unit**: Just Python + pytest ✅
- **Integration**: Project dependencies ✅
- **E2E**: Full dependencies + API keys ⚠️
- **MCP**: MCP servers running (ChromaDB on port 8200, Filesystem on port 8100) ⚠️

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

