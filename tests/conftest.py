"""Pytest configuration and shared fixtures for AI Tutor tests."""

import os
import sys
from pathlib import Path
import pytest

# Add project root and src directory to path so we can import ai_tutor and apps modules
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Default: Disable MCP servers for all tests to prevent connection hangs
# Tests marked with @pytest.mark.mcp can enable real MCP servers
# This must be set before any modules that check these env vars are imported
os.environ.setdefault("MCP_USE_SERVER", "false")
os.environ.setdefault("FS_MCP_USE_SERVER", "false")
# Set a dummy API key to avoid errors during import
os.environ.setdefault("OPENAI_API_KEY", "test-key-do-not-use")

# Mock MCP server loading to prevent connection hangs (for non-MCP tests)
import unittest.mock

# Store patcher - will be started in pytest_configure after paths are set up
_mcp_patcher = None

def pytest_configure(config):
    """Configure pytest - mock MCP servers before any tests run."""
    global _mcp_patcher
    
    # Only mock MCP servers if not running MCP tests
    # MCP tests will use real servers (if available)
    try:
        _mcp_patcher = unittest.mock.patch('apps.mcp.load_mcp_servers', return_value={})
        _mcp_patcher.start()
    except (ImportError, AttributeError):
        # If apps.mcp doesn't exist yet, that's okay - the env vars will prevent connections
        pass

@pytest.fixture(autouse=True)
def configure_mcp_for_test(request):
    """
    Auto-use fixture that configures MCP servers based on test markers.
    
    For tests marked with @pytest.mark.mcp, enables real MCP servers.
    For other tests, keeps MCP servers disabled (mocked).
    """
    global _mcp_patcher
    
    # Check if this test is marked with 'mcp'
    if request.node.get_closest_marker("mcp"):
        # Stop the mock for MCP tests - they need real servers
        if _mcp_patcher is not None:
            _mcp_patcher.stop()
            _mcp_patcher = None
        
        # Enable MCP servers for MCP tests
        os.environ["MCP_USE_SERVER"] = "true"
        os.environ["FS_MCP_USE_SERVER"] = "true"
        
        yield
        
        # Restore mock after MCP test
        try:
            _mcp_patcher = unittest.mock.patch('apps.mcp.load_mcp_servers', return_value={})
            _mcp_patcher.start()
        except (ImportError, AttributeError):
            pass
        
        # Disable MCP servers again
        os.environ["MCP_USE_SERVER"] = "false"
        os.environ["FS_MCP_USE_SERVER"] = "false"
    else:
        # Non-MCP tests: keep mock enabled
        yield

def pytest_unconfigure(config):
    """Cleanup after all tests."""
    global _mcp_patcher
    if _mcp_patcher is not None:
        _mcp_patcher.stop()
    
    # Clean up MCP servers if they were used
    try:
        from apps.mcp import shutdown_mcp_servers
        shutdown_mcp_servers()
    except (ImportError, AttributeError):
        pass


# Fixtures for MCP tests
@pytest.fixture
def mcp_servers():
    """
    Fixture that provides real MCP servers if available.
    
    Skips test if MCP servers are not running.
    Use with @pytest.mark.mcp marker.
    """
    import pytest
    from apps.mcp import load_mcp_servers
    
    servers = load_mcp_servers()
    if not servers:
        pytest.skip("MCP servers not available. Start servers with:\n"
                   "  cd chroma_mcp_server && python server.py\n"
                   "  cd filesystem_mcp_server && python server.py")
    return servers


@pytest.fixture
def chroma_mcp_server(mcp_servers):
    """Fixture that provides ChromaDB MCP server if available."""
    return mcp_servers.get("chroma")


@pytest.fixture
def filesystem_mcp_server(mcp_servers):
    """Fixture that provides Filesystem MCP server if available."""
    return mcp_servers.get("filesystem")

