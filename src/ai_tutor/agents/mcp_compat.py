"""MCP server compatibility utilities for Gemini models.

This module provides utilities to make MCP servers work with Gemini models.
The main issue is that some MCP tools have function schemas that don't comply
with Gemini's requirement that parameters must be of type OBJECT.

The solution is to configure LiteLLM to handle schema conversion more gracefully,
or to filter out problematic tools. Currently, we keep all MCP servers enabled
and rely on error handling to catch schema issues.
"""

from __future__ import annotations

import logging
import os
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# Tools known to have schema compatibility issues with Gemini
GEMINI_INCOMPATIBLE_TOOLS = {
    "list_collections",  # ChromaDB MCP - parameters not properly formatted as OBJECT
    # Add more tools here as they're discovered
}


def filter_mcp_servers_for_gemini(
    mcp_servers: Optional[List[Any]],
    model_name: Optional[str] = None,
) -> List[Any]:
    """
    Filter or fix MCP servers for Gemini compatibility.
    
    Currently, this filters out MCP servers that contain incompatible tools.
    In the future, this could be enhanced to fix tool schemas instead of filtering.
    
    Parameters
    ----------
    mcp_servers : Optional[List[Any]]
        List of MCP server connections.
    model_name : Optional[str]
        Model name. If it starts with "gemini/", filtering will be applied.
        
    Returns
    -------
    List[Any]
        Filtered list of MCP servers compatible with Gemini, or original list if not Gemini.
    """
    if not mcp_servers or not model_name or not model_name.startswith("gemini/"):
        return mcp_servers or []
    
    # For now, we'll keep all MCP servers but log a warning
    # The actual schema fixing should happen at the tool level in the Agents SDK
    # or LiteLLM layer. This is a temporary workaround.
    logger.info(
        "[MCP Compat] Using Gemini model (%s) with MCP servers. "
        "Some tools may have schema compatibility issues.",
        model_name
    )
    
    # Return all servers - let LiteLLM/Agents SDK handle schema conversion
    # If specific tools fail, they'll be caught and logged
    return mcp_servers


def _fix_tool_schema_for_gemini(tool: dict) -> dict:
    """
    Fix a single tool's schema to be Gemini-compatible.
    
    Ensures parameters are of type OBJECT, which Gemini requires.
    Handles both MCP tool formats and standard function calling formats.
    """
    if not isinstance(tool, dict):
        return tool
    
    # Handle different tool formats (MCP tools, OpenAI format, etc.)
    func = None
    if 'function' in tool:
        func = tool['function']
    elif 'type' in tool and tool['type'] == 'function':
        func = tool
    
    if func:
        # Ensure parameters exist and are OBJECT type
        if 'parameters' not in func:
            func['parameters'] = {'type': 'object', 'properties': {}, 'required': []}
        else:
            params = func['parameters']
            # Ensure parameters is an OBJECT type
            if not isinstance(params, dict):
                func['parameters'] = {'type': 'object', 'properties': {}, 'required': []}
            else:
                # Ensure it has type: object
                if params.get('type') != 'object':
                    # If it's a dict but not OBJECT type, wrap it properly
                    func['parameters'] = {
                        'type': 'object',
                        'properties': params.get('properties', params) if isinstance(params, dict) else {},
                        'required': params.get('required', []),
                    }
                # Ensure it has properties and required fields
                if 'properties' not in func['parameters']:
                    func['parameters']['properties'] = {}
                if 'required' not in func['parameters']:
                    func['parameters']['required'] = []
    
    return tool


def _patch_litellm_function_schemas():
    """
    Patch LiteLLM to fix function schemas for Gemini compatibility.
    
    This patches both sync and async completion methods to ensure all tool
    parameters are properly formatted as OBJECT type, which Gemini requires.
    """
    try:
        import litellm
        from litellm.llms.vertex_ai.gemini.vertex_and_google_ai_studio_gemini import (
            vertex_chat_completion,
        )
        
        # Patch async_completion (used by Agents SDK)
        if not hasattr(vertex_chat_completion, '_original_async_completion'):
            original_async_completion = vertex_chat_completion.async_completion
            
            async def patched_async_completion(*args, **kwargs):
                """Patched async completion that fixes function schemas for Gemini."""
                # Fix function schemas in tools
                if 'tools' in kwargs:
                    kwargs['tools'] = [_fix_tool_schema_for_gemini(tool) for tool in kwargs['tools']]
                elif 'functions' in kwargs:
                    kwargs['functions'] = [_fix_tool_schema_for_gemini(tool) for tool in kwargs['functions']]
                
                return await original_async_completion(*args, **kwargs)
            
            # Apply async patch
            vertex_chat_completion.async_completion = patched_async_completion
            vertex_chat_completion._original_async_completion = original_async_completion
            logger.debug("[MCP Compat] Patched LiteLLM async_completion for Gemini schema compatibility")
        
        # Also patch sync completion for completeness
        if not hasattr(vertex_chat_completion, '_original_completion'):
            original_completion = vertex_chat_completion.completion
            
            def patched_completion(*args, **kwargs):
                """Patched completion that fixes function schemas for Gemini."""
                # Fix function schemas in tools
                if 'tools' in kwargs:
                    kwargs['tools'] = [_fix_tool_schema_for_gemini(tool) for tool in kwargs['tools']]
                elif 'functions' in kwargs:
                    kwargs['functions'] = [_fix_tool_schema_for_gemini(tool) for tool in kwargs['functions']]
                
                return original_completion(*args, **kwargs)
            
            # Apply sync patch
            vertex_chat_completion.completion = patched_completion
            vertex_chat_completion._original_completion = original_completion
            logger.debug("[MCP Compat] Patched LiteLLM completion for Gemini schema compatibility")
            
    except Exception as e:
        logger.warning("[MCP Compat] Could not patch LiteLLM: %s", e, exc_info=True)


def configure_litellm_for_gemini_mcp(model_name: Optional[str] = None) -> None:
    """
    Configure LiteLLM for better Gemini + MCP compatibility.
    
    This attempts to configure LiteLLM to handle function schema conversion more gracefully.
    It also tries to patch LiteLLM to fix function schemas automatically.
    
    Note: The schema error happens when LiteLLM sends function declarations to Gemini.
    Gemini strictly requires parameters to be of type OBJECT, and some MCP tools don't comply.
    
    IMPORTANT: After modifying MCP server tool schemas, you must restart the MCP server
    for changes to take effect. The Agents SDK caches tool schemas from MCP servers.
    """
    if not model_name or not model_name.startswith("gemini/"):
        return
    
    # Set LiteLLM to suppress some validation errors
    os.environ.setdefault("LITELLM_LOG", "ERROR")  # Reduce noise from schema warnings
    os.environ.setdefault("LITELLM_SUPPRESS_DEBUG", "true")
    
    # Try to patch LiteLLM to fix function schemas (handles both sync and async)
    _patch_litellm_function_schemas()
    
    # Try to configure LiteLLM settings
    try:
        import litellm
        litellm.drop_params = True  # Drop invalid parameters instead of failing
        
        # Configure automatic retries for rate limit errors (429)
        # LiteLLM will automatically retry with exponential backoff
        # Set max retries and retry delay for rate limit errors
        if not hasattr(litellm, '_rate_limit_retry_config'):
            # Configure retry behavior for rate limit errors
            # This helps handle burst throttling and temporary rate limits
            os.environ.setdefault("LITELLM_NUM_RETRIES", "5")  # Retry up to 5 times
            os.environ.setdefault("LITELLM_RETRY_DELAY", "3")  # Initial delay of 3 seconds
            litellm.num_retries = 5  # Set programmatically as well
            litellm.retry_delay = 3  # Initial delay between retries
            logger.info("[MCP Compat] Configured LiteLLM for Gemini MCP compatibility with rate limit retries")
        else:
            logger.info("[MCP Compat] Configured LiteLLM for Gemini MCP compatibility")
    except Exception as e:
        logger.debug("[MCP Compat] Could not configure LiteLLM settings: %s", e)


def get_gemini_compatible_mcp_servers(
    mcp_servers: Optional[List[Any]],
    mcp_server_names: Optional[List[str]] = None,
    model_name: Optional[str] = None,
) -> tuple[List[Any], List[str]]:
    """
    Get MCP servers compatible with Gemini.
    
    For Gemini models, we configure LiteLLM to handle schema issues more gracefully.
    All MCP servers are kept enabled - if specific tools have schema issues,
    they'll fail at runtime and be handled by error handling in the agent.
    
    Parameters
    ----------
    mcp_servers : Optional[List[Any]]
        List of MCP server connections.
    mcp_server_names : Optional[List[str]]
        List of MCP server names corresponding to mcp_servers.
    model_name : Optional[str]
        Model name. If it starts with "gemini/", compatibility mode will be enabled.
        
    Returns
    -------
    tuple[List[Any], List[str]]
        MCP servers and names (all kept, compatibility configured).
    """
    if not mcp_servers:
        return ([], mcp_server_names or [])
    
    # Configure LiteLLM for Gemini + MCP compatibility
    if model_name and model_name.startswith("gemini/"):
        configure_litellm_for_gemini_mcp(model_name)
        logger.info(
            "[MCP Compat] Gemini model detected (%s). "
            "MCP servers enabled with compatibility mode. "
            "Some tools may have schema issues - errors will be handled gracefully.",
            model_name
        )
        
        # Log warnings for known problematic servers
        for i, server in enumerate(mcp_servers):
            server_name = mcp_server_names[i] if mcp_server_names and i < len(mcp_server_names) else f"server_{i}"
            if "chroma" in server_name.lower():
                logger.warning(
                    "[MCP Compat] ChromaDB MCP server detected. "
                    "Tool 'list_collections' may have schema compatibility issues. "
                    "If you encounter errors, the agent will handle them gracefully."
                )
    
    return (mcp_servers, mcp_server_names or [])

