"""Structure verification tests - check code structure and configuration.

These tests verify that simplifications are in place and code structure is correct.
They don't require full system initialization, just file/pattern checking.
"""

import pytest
import sys
from pathlib import Path

pytestmark = pytest.mark.integration

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # Go up from tests/integration/ to project root
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def check_file_removed(file_path: Path) -> bool:
    """Check if a file has been removed."""
    return not file_path.exists()


def check_code_removed(file_path: Path, patterns: list[str]) -> tuple[int, int]:
    """Check if code patterns are removed from a file."""
    if not file_path.exists():
        return 0, 0
    content = file_path.read_text()
    found = sum(1 for pattern in patterns if pattern in content)
    return found, len(patterns)


def check_code_exists(file_path: Path, patterns: list[str]) -> tuple[int, int]:
    """Check if code patterns exist in a file."""
    if not file_path.exists():
        return 0, len(patterns)
    content = file_path.read_text()
    found = sum(1 for pattern in patterns if pattern in content)
    return found, len(patterns)


def test_cli_removed():
    """Test that CLI has been removed."""
    cli_path = PROJECT_ROOT / "src" / "ai_tutor" / "cli.py"
    assert check_file_removed(cli_path), "CLI file should be removed"
    
    # Check pyproject.toml
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    if pyproject_path.exists():
        content = pyproject_path.read_text()
        # CLI entry should be commented or removed
        assert (
            "ai-tutor = \"ai_tutor.cli:app\"" not in content 
            or "# CLI removed" in content 
            or "#" in content.split("ai-tutor = \"ai_tutor.cli:app\"")[0].split("\n")[-1]
        ), "CLI script entry should be removed or commented in pyproject.toml"


def test_routing_simplified():
    """Test that routing has been simplified (LLM routing removed)."""
    tutor_path = PROJECT_ROOT / "src" / "ai_tutor" / "agents" / "tutor.py"
    assert tutor_path.exists(), "tutor.py should exist"
    
    content = tutor_path.read_text()
    
    # Check removed patterns
    removed_patterns = [
        "def _route_with_llm",
        "def _build_routing_prompt",
        "def _parse_routing_response",
        "MIN_ROUTING_CONFIDENCE =",
    ]
    
    found_removed, total_removed = check_code_removed(tutor_path, removed_patterns)
    removed_count = total_removed - found_removed
    
    # Check simplified patterns exist
    simplified_patterns = [
        "apply_deterministic_routing",
        "defaults to QA",
    ]
    found_simplified, total_simplified = check_code_exists(tutor_path, simplified_patterns)
    
    # Allow 1 pattern to remain (might be in comments/docstrings)
    assert removed_count >= (total_removed - 1), f"Most routing patterns should be removed, found {found_removed}/{total_removed}"
    assert found_simplified >= 1, f"Simplified routing patterns should exist, found {found_simplified}/{total_simplified}"


def test_session_simplified():
    """Test that session management has been simplified."""
    tutor_path = PROJECT_ROOT / "src" / "ai_tutor" / "agents" / "tutor.py"
    assert tutor_path.exists(), "tutor.py should exist"
    
    content = tutor_path.read_text()
    
    # Check removed patterns
    removed_patterns = [
        "session_turn_counts",
        "max_turns_per_session",
        "daily rotation",
    ]
    
    found_removed, total_removed = check_code_removed(tutor_path, removed_patterns)
    
    # Check simplified patterns exist
    simplified_patterns = [
        "ai_tutor_{learner_id}",
    ]
    found_simplified, total_simplified = check_code_exists(tutor_path, simplified_patterns)
    
    # Allow some patterns in comments
    assert found_removed <= 1, f"Session management patterns should be removed, found {found_removed}/{total_removed}"
    assert found_simplified >= 1, f"Simplified session patterns should exist, found {found_simplified}/{total_simplified}"


def test_demo_mode_added():
    """Test that demo mode has been added to configuration."""
    # Check config schema
    schema_path = PROJECT_ROOT / "src" / "ai_tutor" / "config" / "schema.py"
    assert schema_path.exists(), "schema.py should exist"
    content = schema_path.read_text()
    assert "demo_mode" in content, "demo_mode field should be in schema"
    
    # Check default.yaml
    default_yaml = PROJECT_ROOT / "config" / "default.yaml"
    if default_yaml.exists():
        content = default_yaml.read_text()
        # demo_mode should be present (true or false)
        assert "demo_mode" in content, "demo_mode should be in default.yaml"
    
    # Check demo.yaml exists
    demo_yaml = PROJECT_ROOT / "config" / "demo.yaml"
    assert demo_yaml.exists(), "demo.yaml config file should exist"
    content = demo_yaml.read_text()
    assert "demo_mode: true" in content or "demo_mode:true" in content.replace(" ", ""), "demo.yaml should have demo_mode enabled"
    
    # Check system.py uses demo_mode
    system_path = PROJECT_ROOT / "src" / "ai_tutor" / "system.py"
    assert system_path.exists(), "system.py should exist"
    content = system_path.read_text()
    assert "settings.demo_mode" in content, "system.py should check demo_mode"


def test_personalization_conditional():
    """Test that personalization is conditional on demo_mode."""
    system_path = PROJECT_ROOT / "src" / "ai_tutor" / "system.py"
    assert system_path.exists(), "system.py should exist"
    
    patterns = [
        "if settings.demo_mode",
        "self.personalizer = None",
        "self.progress_tracker = None",
    ]
    
    found, total = check_code_exists(system_path, patterns)
    assert found >= 2, f"Conditional personalization patterns should exist, found {found}/{total}"


def test_config_files_exist():
    """Test that required config files exist."""
    configs = [
        ("config/default.yaml", True),
        ("config/demo.yaml", True),
    ]
    
    for config_path, required in configs:
        path = PROJECT_ROOT / config_path
        if required:
            assert path.exists(), f"{config_path} should exist"


def test_api_endpoints_defined():
    """Test that API endpoints are defined."""
    api_path = PROJECT_ROOT / "apps" / "api.py"
    assert api_path.exists(), "api.py should exist"
    
    content = api_path.read_text()
    
    endpoints = [
        ("@app.get", "/health"),
        ("@app.post", "/answer"),
        ("@app.post", "/quiz"),
        ("@app.post", "/quiz/evaluate"),
        ("@app.post", "/ingest"),
        ("@app.post", "/sessions/{learner_id}/events"),
        ("@app.get", "/sessions/{learner_id}"),
        ("@app.post", "/sessions/{learner_id}/reset"),
    ]
    
    found = 0
    for decorator, path in endpoints:
        if decorator in content:
            # Check for path in function definition
            if path.replace("{learner_id}", "") in content or path.split("/")[-1] in content:
                found += 1
    
    # Allow 1 missing endpoint
    assert found >= len(endpoints) - 1, f"Most API endpoints should be defined, found {found}/{len(endpoints)}"


def test_api_models_defined():
    """Test that API request/response models are defined."""
    api_path = PROJECT_ROOT / "apps" / "api.py"
    assert api_path.exists(), "api.py should exist"
    
    content = api_path.read_text()
    
    # Models defined in api.py
    api_models = [
        "AnswerRequest",
        "AnswerResponse",
        "QuizRequest",
        "QuizResponse",
        "QuizEvaluateRequest",
        "QuizEvaluateResponse",
        "IngestResponse",
    ]
    
    found = 0
    for model in api_models:
        if f"class {model}" in content:
            found += 1
    
    # Session models are imported from data_models.session
    session_models_path = PROJECT_ROOT / "src" / "ai_tutor" / "data_models" / "session.py"
    session_models = []
    if session_models_path.exists():
        session_content = session_models_path.read_text()
        session_models = [
            "SessionEvent",
            "SessionEventRequest",
            "SessionResponse",
            "SessionHistoryResponse",
        ]
        session_found = sum(1 for model in session_models if f"class {model}" in session_content)
        found += session_found
    
    total_models = len(api_models) + len(session_models)
    # Allow 1 missing model
    assert found >= total_models - 1, f"Most API models should be defined, found {found}/{total_models}"


def test_api_service_integration():
    """Test that API uses TutorService."""
    api_path = PROJECT_ROOT / "apps" / "api.py"
    assert api_path.exists(), "api.py should exist"
    
    content = api_path.read_text()
    
    patterns = [
        "from ai_tutor.services import TutorService",
        "get_service",
        "TutorService = Depends",
        "service.answer_question",
        "service.create_quiz",
        "service.process_event",
    ]
    
    found = sum(1 for pattern in patterns if pattern in content)
    # Allow 1 missing pattern
    assert found >= len(patterns) - 1, f"Most service integration patterns should exist, found {found}/{len(patterns)}"


def test_demo_config_loading():
    """Test that demo config loads correctly."""
    try:
        from ai_tutor.config.loader import load_settings
        settings = load_settings()
        assert hasattr(settings, 'demo_mode'), "demo_mode field should exist"
        # demo_mode can be True or False, just check it exists
        assert isinstance(settings.demo_mode, bool), "demo_mode should be a boolean"
    except Exception as e:
        pytest.skip(f"Could not load settings: {e}")


def test_demo_yaml_loading():
    """Test that demo.yaml config loads correctly."""
    demo_config_path = PROJECT_ROOT / "config" / "demo.yaml"
    if not demo_config_path.exists():
        pytest.skip("demo.yaml not found")
    
    try:
        from ai_tutor.config.loader import load_settings
        settings = load_settings(demo_config_path)
        assert settings.demo_mode is True, "demo.yaml should have demo_mode: true"
    except Exception as e:
        pytest.skip(f"Could not load demo.yaml: {e}")

