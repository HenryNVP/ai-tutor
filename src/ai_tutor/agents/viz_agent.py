"""Visualization agent builder for orchestrator integration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from agents import Agent, function_tool

from ai_tutor.agents.visualization import VisualizationAgent, create_visualization_tool
from ai_tutor.agents.llm_client import LLMClient
from ai_tutor.config.loader import load_settings

logger = logging.getLogger(__name__)


def build_visualization_agent(
    state: Any,
    upload_dir: Optional[Path] = None,
) -> Agent:
    """
    Create an agent that handles data visualization requests.
    
    Args:
        state: AgentState for storing visualization results
        upload_dir: Directory where CSV files are uploaded (defaults to data/uploads)
        
    Returns:
        Agent configured for visualization tasks
    """
    if upload_dir is None:
        upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize visualization agent with LLM client
    settings = load_settings()
    llm_client = LLMClient(config=settings.model)
    viz_agent = VisualizationAgent(llm_client, upload_dir)
    
    # Create the tool function
    create_viz_tool = create_visualization_tool(viz_agent)
    
    @function_tool
    def create_visualization(csv_filename: str, visualization_request: str) -> str:
        """
        Create a data visualization from an uploaded CSV file.
        
        Args:
            csv_filename: Name of the uploaded CSV file (e.g., "sales_data.csv")
            visualization_request: Description of what to plot (e.g., "bar chart of sales by month")
            
        Returns:
            JSON string with visualization result
        """
        logger.info(f"[Visualization Agent] Creating visualization: {csv_filename} - {visualization_request}")
        
        result = viz_agent.create_visualization(csv_filename, visualization_request)
        
        # Store result in state for later retrieval
        state.last_visualization = result  # type: ignore
        state.last_source = "visualization"  # type: ignore
        
        # Return JSON summary
        import json
        dataset_info = result.get("dataset_info")
        dataset_shape = dataset_info.shape if dataset_info else None
        
        code = result.get("code", "")
        code_preview = code[:200] + "..." if code and len(code) > 200 else code
        
        return json.dumps({
            "success": result["success"],
            "error": result.get("error"),
            "has_image": result.get("image_base64") is not None,
            "dataset_shape": dataset_shape,
            "code_preview": code_preview,
        })
    
    instructions = (
        "You specialize in data visualization using the create_visualization tool.\n\n"
        "MANDATORY WORKFLOW:\n"
        "1. Look for 'CSV_FILENAME: filename.csv' in the user's message or context to find the uploaded CSV file name.\n"
        "2. Extract the visualization request (what to plot) from the user's message.\n"
        "3. Call create_visualization EXACTLY ONCE with the CSV filename and visualization request.\n"
        "4. After the tool call succeeds, respond with a brief confirmation message.\n"
        "   - DO NOT describe the plot in detail - the tool handles visualization.\n"
        "   - Simply confirm that the visualization was created successfully.\n\n"
        "CRITICAL RULES:\n"
        "- The CSV file must already be uploaded to the system.\n"
        "- Look for 'CSV_FILENAME: filename.csv' in the context to find the exact filename.\n"
        "- If CSV_FILENAME is not found, try to extract the filename from the user's message.\n"
        "- Your response should be brief and confirm the visualization was created.\n"
    )
    
    return Agent(
        name="visualization_agent",
        model="gpt-4o-mini",
        instructions=instructions,
        tools=[create_visualization],
    )

