# Test Suite

This directory contains tests for the AI Tutor system.

## Test Structure

- `test_sessions.py` - Unit tests for session API with mocked services
- `test_quiz_api.py` - Unit tests for quiz evaluation API
- `test_routing.py` - Unit tests for routing logic
- `test_e2e_use_cases.py` - **End-to-end integration tests** for complete user workflows

## Running Tests

### Run all tests
```bash
pytest
```

### Run only unit tests (skip integration tests)
```bash
pytest -m "not integration"
```

### Run only integration tests
```bash
pytest -m integration
```

### Run specific test file
```bash
pytest tests/test_e2e_use_cases.py -v
```

### Run specific test case
```bash
pytest tests/test_e2e_use_cases.py::test_use_case_1_greetings -v
```

## End-to-End Test Use Cases

The `test_e2e_use_cases.py` file contains comprehensive end-to-end tests for:

1. **Greetings** - Simple conversational interaction
2. **Upload and Summarize** - Upload document and request summary
3. **Make Notes** - Create study notes from a specific section
4. **Create Quizzes** - Generate quizzes from uploaded documents

### Requirements for E2E Tests

These tests use the real `TutorSystem` and may require:
- OpenAI API key (set `OPENAI_API_KEY` environment variable)
- Proper vector store configuration
- Test data setup

If these are not available, the tests will be skipped automatically.

### Test Data

The tests create sample documents (text files) with physics and computer science content for testing ingestion and retrieval.

## Test Fixtures

- `api_client` - FastAPI test client with mocked service
- `real_service` - Real TutorService instance (for integration tests)
- `sample_text_file` - Sample physics text document
- `sample_pdf_file` - Sample PDF document (simulated as text)

## Writing New Tests

When adding new tests:

1. **Unit tests** - Use mocked services (like `FakeTutorService`)
2. **Integration tests** - Mark with `@pytest.mark.integration`
3. **Use fixtures** - Leverage existing fixtures for common setup
4. **Clean up** - Tests should clean up after themselves

Example:
```python
@pytest.mark.integration
def test_my_feature(api_client_with_real_service):
    client, service = api_client_with_real_service
    # Test implementation
```





