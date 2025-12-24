# Test Suite Documentation

## Overview

The AI Tutor test suite is organized into three categories: **Unit**, **Integration**, and **End-to-End (E2E)** tests. Tests are organized in subfolders for clarity and easy execution.

## Test Organization

```
tests/
├── conftest.py          # Shared pytest configuration and fixtures
├── unit/                # Unit tests (no dependencies)
│   └── test_unit_simple.py
├── integration/         # Integration tests (mocked services)
│   ├── test_routing.py
│   ├── test_sessions.py
│   └── test_structure_verification.py
└── e2e/                 # End-to-end tests (full system)
    ├── test_e2e_use_cases.py
    └── test_simplified_api.py
```

## Test Categories

### Unit Tests (`tests/unit/`)

Fast, isolated tests with no external dependencies. Test pure functions and core logic.

**File: `test_unit_simple.py`** (16 tests)

Tests core AI Tutor functionality:

- **Quiz Intent Detection**:
  - `test_detect_quiz_request` - Detects quiz requests ("create quiz", "test me", "practice questions")
  - `test_extract_quiz_num_questions` - Extracts number of questions from requests (defaults to 4, caps at 40, min 3)
  - `test_extract_quiz_topic` - Extracts quiz topics from messages, handles document references

- **Routing Detection**:
  - `test_detect_note_request` - Detects note/summarize requests ("summarize", "create notes", "write a file")
  - `test_detect_visualization_request` - Detects visualization requests ("plot", "chart", "graph", "visualize")
  - `test_detect_ingestion_request` - Detects document ingestion requests ("upload", "ingest", "add document")
  - `test_detect_news_request` - Detects news/current events requests ("news", "current events", "latest update")

- **Source Filtering**:
  - `test_extract_source_mentions` - Extracts document references from messages (quoted filenames, file extensions, lecture references)
  - `test_should_use_source_filter` - Determines if source filter should be used based on message content
  - `test_detect_document_request` - Detects document-specific requests and extracts filenames

- **Routing Logic**:
  - `test_routing_decision_dataclass` - Tests RoutingDecision data structure
  - `test_apply_deterministic_routing_quiz` - Routes quiz requests correctly
  - `test_apply_deterministic_routing_note` - Routes note requests correctly
  - `test_apply_deterministic_routing_visualization` - Routes visualization requests correctly
  - `test_apply_deterministic_routing_default_qa` - Defaults to QA for generic questions

- **Utilities**:
  - `test_generate_filename_variations` - Tests filename path matching utilities for different storage locations

### Integration Tests (`tests/integration/`)

Tests components with mocked dependencies (no real API calls or external services).

**File: `test_routing.py`** (7 tests)

Tests routing logic with real functions:

- `test_quiz_routing_detects_topic_and_count` - Routing extracts quiz topic and question count from requests
- `test_note_routing_extracts_source_filter` - Note routing extracts source filter from quoted references
- `test_note_routing_detects_text_file_request` - Detects text file creation requests
- `test_routing_uses_extra_context_hints` - Routing uses extra context for better topic extraction
- `test_extract_source_mentions_handles_metadata_hints` - Source extraction handles metadata hints
- `test_extract_source_mentions_ignores_generic_tokens` - Filters out generic document references
- `test_extract_quiz_num_questions_handles_multiple_numbers` - Handles multiple number mentions correctly

**File: `test_sessions.py`** (3 tests)

Tests session management with mocked services:

- `test_full_session_flow` - Complete session flow: message events, quiz events, history retrieval
- `test_upload_event_metadata` - Upload events store metadata correctly
- `test_quiz_submission_event` - Quiz submission events are processed and stored

**File: `test_structure_verification.py`** (11 tests)

Structure verification tests (integrated from `scripts/` verification scripts):

- `test_cli_removed` - Verifies CLI file and entry point removed
- `test_routing_simplified` - Verifies LLM routing methods removed, keyword-based routing exists
- `test_session_simplified` - Verifies session management simplified (no turn counting, no rotation)
- `test_demo_mode_added` - Verifies demo_mode field exists in config schema and files
- `test_personalization_conditional` - Verifies personalization is conditional on demo_mode
- `test_config_files_exist` - Verifies required config files (default.yaml, demo.yaml) exist
- `test_api_endpoints_defined` - Verifies all API endpoints are defined
- `test_api_models_defined` - Verifies API request/response models exist
- `test_api_service_integration` - Verifies API uses TutorService correctly
- `test_demo_config_loading` - Verifies demo config loads correctly
- `test_demo_yaml_loading` - Verifies demo.yaml loads with demo_mode enabled

**Note**: Basic API endpoint tests (health, answer, quiz creation/evaluation) were removed as they're fully covered by E2E tests in `test_simplified_api.py`.

### End-to-End Tests (`tests/e2e/`)

Full system tests with real services (may require API keys and MCP servers).

**File: `test_e2e_use_cases.py`** (6 tests)

Complete use case flows with real TutorSystem:

- `test_settings` - Verifies test settings are loaded correctly
- `test_use_case_1_greetings` - User greets the system, receives appropriate response
- `test_use_case_2_upload_and_summarize` - User uploads document, system ingests it, user requests summary
- `test_use_case_3_make_note_of_section` - User requests notes from a specific section of uploaded document
- `test_use_case_4_create_quizzes_from_document` - User creates quizzes from uploaded document content
- `test_use_case_combined_flow` - Complete workflow: upload → summarize → create notes → generate quiz

**File: `test_simplified_api.py`** (13 tests)

Full API tests with real TutorSystem (or mocks when dependency override works):

- `test_health_endpoint` - Health check endpoint
- `test_answer_endpoint_routing` - Answer endpoint routes correctly (quiz, note, visualization, QA)
- `test_answer_demo_mode` - Demo mode disables personalization (no next_topic, no difficulty)
- `test_quiz_endpoint` - Quiz creation endpoint works
- `test_quiz_evaluation_endpoint` - Quiz evaluation endpoint processes answers
- `test_session_event_routing` - Session events route to correct agents
- `test_session_simplified_management` - Simplified session management (no rotation, persistent sessions)
- `test_session_reset` - Session reset clears conversation history
- `test_ingest_endpoint` - Document ingestion endpoint processes files
- `test_routing_keyword_based` - Keyword-based routing works for various patterns
- `test_demo_mode_vs_production` - Demo mode vs production mode differences
- `test_multiple_sessions_independent` - Multiple learners have independent sessions

## Running Tests

See [QUICK_START.md](QUICK_START.md) for quick reference commands.

**Default behavior**: Runs unit and integration tests only (E2E skipped by default).

```bash
# Default (safe, fast)
pytest tests/ -v

# All tests including E2E
pytest tests/ -m "" -v

# By category
pytest tests/ -m unit -v
pytest tests/ -m integration -v
pytest tests/ -m e2e -v
```

## Test Requirements

- **Unit tests**: No dependencies, just Python + pytest
- **Integration tests**: Project dependencies (fastapi, etc.)
- **E2E tests**: Full dependencies + `OPENAI_API_KEY` (optional: MCP servers)

## Configuration

- `pytest.ini` - Default configuration (E2E tests skipped by default)
- `conftest.py` - Shared fixtures and MCP server mocking

## Safety Features

- E2E tests skipped by default to prevent crashes
- Import guards for graceful skipping if dependencies missing
- Markers for easy filtering (`unit`, `integration`, `e2e`)

## Scripts Tests (`scripts/`)

The `scripts/` directory contains one remaining verification script:

**File: `test_qa_agent_mcp.py`**
- ⚠️ **Not integrated into pytest** (requires MCP servers running)
- Validates MCP server connectivity (ChromaDB, Filesystem)
- Tests agent MCP tool usage end-to-end
- **Purpose**: Manual MCP integration verification

**Note**: Other verification scripts (`test_api_structure.py`, `test_simplifications.py`, `test_simplified_system.py`) have been integrated into `tests/integration/test_structure_verification.py` and can be run via pytest.
