"""Pytest configuration and shared fixtures for AI Tutor tests."""

import os
import sys
from pathlib import Path

# Add project root to path so we can import apps module
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Disable MCP servers for all tests to prevent connection hangs
# This must be set before any modules that check these env vars are imported
os.environ["MCP_USE_SERVER"] = "false"
os.environ["FS_MCP_USE_SERVER"] = "false"
# Set a dummy API key to avoid errors during import
os.environ.setdefault("OPENAI_API_KEY", "test-key-do-not-use")

# Mock MCP server loading to prevent connection hangs
import unittest.mock

# Store patcher - will be started in pytest_configure after paths are set up
_mcp_patcher = None

def pytest_configure(config):
    """Configure pytest - mock MCP servers before any tests run."""
    global _mcp_patcher
    
    # Now that paths are set up, we can patch apps.mcp
    try:
        _mcp_patcher = unittest.mock.patch('apps.mcp.load_mcp_servers', return_value={})
        _mcp_patcher.start()
    except (ImportError, AttributeError):
        # If apps.mcp doesn't exist yet, that's okay - the env vars will prevent connections
        pass

def pytest_unconfigure(config):
    """Cleanup after all tests."""
    global _mcp_patcher
    if _mcp_patcher is not None:
        _mcp_patcher.stop()

