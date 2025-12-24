# Testing Documentation

## Quick Reference

See [tests/README.md](../tests/README.md) for complete test documentation.

## Test Organization

```
tests/
├── unit/              # Pure function tests (16 tests)
├── integration/      # Component tests (21 tests)
└── e2e/              # Full system tests (19 tests)
```

## Running Tests

```bash
# Default: Unit + Integration (E2E skipped)
pytest tests/ -v

# All tests including E2E
pytest tests/ -m "" -v

# By category
pytest tests/ -m unit -v
pytest tests/ -m integration -v
pytest tests/ -m e2e -v
```

## Test Coverage

### Unit Tests
- Routing detection functions
- Quiz intent parsing
- Source extraction
- Filename utilities

### Integration Tests
- Routing logic
- Session management
- Structure verification

### E2E Tests
- Full API endpoints
- Complete use case flows
- Demo mode behavior

## Test Results

All tests passing:
- ✅ 16 unit tests
- ✅ 21 integration tests
- ✅ 19 E2E tests
- **Total**: 56 tests

## See Also

- [tests/README.md](../tests/README.md) - Detailed test documentation
- [tests/QUICK_START.md](../tests/QUICK_START.md) - Quick reference commands

