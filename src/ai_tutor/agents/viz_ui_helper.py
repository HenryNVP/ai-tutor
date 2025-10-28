"""
UI Helper for Visualization Agent in Streamlit

Provides utilities for displaying plots in the Streamlit chat interface.
"""

import base64
import streamlit as st
from typing import Dict, Any, Optional
from pathlib import Path


def display_visualization_in_chat(result: Dict[str, Any], message_placeholder=None):
    """
    Display visualization result in Streamlit chat.
    
    Args:
        result: Result dict from VisualizationAgent.create_visualization()
        message_placeholder: Optional Streamlit placeholder for updating
        
    Usage in UI:
        if "plot" in user_message:
            result = viz_agent.create_visualization(...)
            display_visualization_in_chat(result)
    """
    if result["success"]:
        # Display success message
        st.success("✅ Visualization created!")
        
        # Display the plot
        if result["image_base64"]:
            # Decode base64 and display
            img_bytes = base64.b64decode(result["image_base64"])
            st.image(img_bytes, use_container_width=True)
        
        # Show dataset info
        if result["dataset_info"]:
            info = result["dataset_info"]
            with st.expander("📊 Dataset Info"):
                st.write(f"**File:** {info.filename}")
                st.write(f"**Shape:** {info.shape[0]} rows × {info.shape[1]} columns")
                st.write(f"**Columns:** {', '.join(info.columns)}")
        
        # Show generated code
        if result["code"]:
            with st.expander("🐍 Generated Code"):
                st.code(result["code"], language="python")
    
    else:
        # Display error
        st.error(f"❌ Visualization failed: {result['error']}")
        
        # Show attempted code if available
        if result["code"]:
            with st.expander("🐍 Attempted Code (for debugging)"):
                st.code(result["code"], language="python")


def add_csv_uploader_to_sidebar() -> Optional[Path]:
    """
    Add CSV file uploader to sidebar for visualization.
    
    Returns:
        Path to uploaded CSV file if uploaded, None otherwise
        
    Usage:
        with st.sidebar:
            csv_path = add_csv_uploader_to_sidebar()
            if csv_path:
                st.success(f"Uploaded: {csv_path.name}")
    """
    st.sidebar.markdown("### 📊 Data Visualization")
    
    uploaded_file = st.sidebar.file_uploader(
        "Upload CSV for visualization",
        type=["csv"],
        help="Upload a CSV file to create plots"
    )
    
    if uploaded_file:
        # Save to uploads directory
        upload_dir = Path("data/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        csv_path = upload_dir / uploaded_file.name
        csv_path.write_bytes(uploaded_file.getvalue())
        
        return csv_path
    
    return None


def render_visualization_examples():
    """
    Display example visualization commands in the UI.
    
    Usage:
        with st.expander("📊 Visualization Examples"):
            render_visualization_examples()
    """
    st.markdown("""
    **Example requests:**
    
    After uploading a CSV file, try:
    - "plot sales by month"
    - "create a bar chart of revenue by category"
    - "show me a histogram of test scores"
    - "line chart of temperature over time"
    - "scatter plot of height vs weight"
    - "visualize the top 10 products by sales"
    
    **Supported plot types:**
    - Bar charts, line plots, scatter plots
    - Histograms, box plots
    - Heatmaps, pie charts
    - Time series plots
    """)


# Integration with chat messages
def format_viz_message_for_chat(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format visualization result for storage in chat history.
    
    Args:
        result: Result from VisualizationAgent
        
    Returns:
        Dict suitable for st.session_state.messages
        
    Usage:
        result = viz_agent.create_visualization(...)
        message = format_viz_message_for_chat(result)
        st.session_state.messages.append(message)
    """
    if result["success"]:
        return {
            "role": "assistant",
            "content": "Here's your visualization:",
            "image_base64": result["image_base64"],
            "dataset_info": result["dataset_info"],
            "code": result["code"],
            "type": "visualization"
        }
    else:
        return {
            "role": "assistant",
            "content": f"I couldn't create the visualization: {result['error']}",
            "type": "error"
        }


def display_message_with_viz(message: Dict[str, Any]):
    """
    Display a chat message that may contain a visualization.
    
    Args:
        message: Message dict from session state
        
    Usage:
        for msg in st.session_state.messages:
            display_message_with_viz(msg)
    """
    with st.chat_message(message["role"]):
        st.write(message["content"])
        
        # Display visualization if present
        if message.get("type") == "visualization" and message.get("image_base64"):
            img_bytes = base64.b64decode(message["image_base64"])
            st.image(img_bytes, use_container_width=True)
            
            # Optional: Show code in expander
            if message.get("code"):
                with st.expander("View generated code"):
                    st.code(message["code"], language="python")


# Example UI integration snippet
STREAMLIT_INTEGRATION_EXAMPLE = """
# In apps/ui.py, integrate visualization agent:

from ai_tutor.agents.visualization import VisualizationAgent, create_visualization_tool
from ai_tutor.agents.viz_ui_helper import (
    display_visualization_in_chat, 
    add_csv_uploader_to_sidebar,
    render_visualization_examples
)

# 1. Initialize visualization agent
viz_agent = VisualizationAgent(
    llm_client=system.tutor_agent.llm,
    upload_dir=Path("data/uploads")
)

# 2. Add CSV uploader to sidebar
with st.sidebar:
    csv_path = add_csv_uploader_to_sidebar()
    if csv_path:
        st.session_state.uploaded_csv = csv_path.name

# 3. Show examples
with st.expander("📊 Visualization Examples"):
    render_visualization_examples()

# 4. In chat handling:
if user_message:
    # Check if it's a visualization request
    viz_keywords = ["plot", "chart", "graph", "visualize", "histogram", "scatter"]
    if any(kw in user_message.lower() for kw in viz_keywords) and st.session_state.get("uploaded_csv"):
        # Create visualization
        result = viz_agent.create_visualization(
            st.session_state.uploaded_csv,
            user_message
        )
        
        # Display result
        display_visualization_in_chat(result)
    else:
        # Normal chat processing
        response = system.answer(learner_id, user_message, mode="chat")
        st.write(response.answer)
"""


if __name__ == "__main__":
    print("📊 Visualization UI Helper")
    print("=" * 70)
    print("\nThis module provides utilities for integrating visualizations")
    print("into the Streamlit chat interface.")
    print("\nKey functions:")
    print("  - display_visualization_in_chat(): Show plots in chat")
    print("  - add_csv_uploader_to_sidebar(): CSV upload widget")
    print("  - render_visualization_examples(): Show example commands")
    print("\nSee STREAMLIT_INTEGRATION_EXAMPLE for integration code.")

