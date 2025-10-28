"""
Visualization Agent - Handles data visualization requests with dynamic code generation.

This agent:
1. Inspects uploaded datasets (CSV files)
2. Interprets user's visualization intent
3. Generates Python plotting code (matplotlib/seaborn)
4. Executes code safely and returns base64-encoded images

Example usage:
    User uploads "sales_data.csv"
    User: "plot sales by month"
    Agent: Generates code, executes, returns plot in chat
"""

import base64
import io
import logging
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DatasetInfo:
    """Metadata about an uploaded dataset."""
    filename: str
    shape: tuple  # (rows, cols)
    columns: List[str]
    dtypes: Dict[str, str]
    sample_rows: str  # First 5 rows as string
    numeric_cols: List[str]
    categorical_cols: List[str]


class VisualizationAgent:
    """
    Agent for data visualization with dynamic code generation.
    
    Follows the agent-first architecture pattern:
    - Orchestrator routes "plot X" requests here
    - Agent inspects dataset and generates Python code
    - Code executes in controlled environment
    - Returns base64-encoded image to chat
    """
    
    def __init__(self, llm_client, upload_dir: Path = Path("data/uploads")):
        """
        Initialize visualization agent.
        
        Args:
            llm_client: LLM client for code generation
            upload_dir: Directory where CSV files are uploaded
        """
        self.llm_client = llm_client
        self.upload_dir = upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Seaborn styling for better-looking plots
        sns.set_theme(style="whitegrid")
        
        logger.info("VisualizationAgent initialized")
    
    def inspect_dataset(self, csv_path: Path) -> DatasetInfo:
        """
        Inspect a CSV file and extract metadata.
        
        Args:
            csv_path: Path to CSV file
            
        Returns:
            DatasetInfo with columns, types, sample data
        """
        logger.info(f"Inspecting dataset: {csv_path.name}")
        
        # Read CSV
        df = pd.read_csv(csv_path)
        
        # Extract metadata
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        
        # Sample rows for LLM context
        sample_str = df.head(5).to_string()
        
        info = DatasetInfo(
            filename=csv_path.name,
            shape=df.shape,
            columns=df.columns.tolist(),
            dtypes={col: str(dtype) for col, dtype in df.dtypes.items()},
            sample_rows=sample_str,
            numeric_cols=numeric_cols,
            categorical_cols=categorical_cols
        )
        
        logger.info(f"Dataset: {info.shape[0]} rows, {info.shape[1]} cols")
        logger.info(f"Numeric: {numeric_cols}")
        logger.info(f"Categorical: {categorical_cols}")
        
        return info
    
    def generate_plot_code(
        self, 
        dataset_info: DatasetInfo, 
        user_request: str
    ) -> str:
        """
        Generate Python plotting code based on user request.
        
        Args:
            dataset_info: Metadata about the dataset
            user_request: User's visualization request (e.g., "plot sales by month")
            
        Returns:
            Python code string that creates the plot
        """
        logger.info(f"Generating plot code for: '{user_request}'")
        
        prompt = f"""You are a data visualization expert. Generate Python code to create a plot.

DATASET INFO:
Filename: {dataset_info.filename}
Shape: {dataset_info.shape[0]} rows × {dataset_info.shape[1]} columns
Columns: {', '.join(dataset_info.columns)}
Numeric columns: {', '.join(dataset_info.numeric_cols)}
Categorical columns: {', '.join(dataset_info.categorical_cols)}

Sample data:
{dataset_info.sample_rows}

USER REQUEST: "{user_request}"

REQUIREMENTS:
1. Import necessary libraries (pandas, matplotlib.pyplot, seaborn)
2. Read the CSV file: df = pd.read_csv('{self.upload_dir / dataset_info.filename}')
3. Generate the appropriate plot (bar, line, scatter, histogram, etc.)
4. Use seaborn for styling when appropriate
5. Add title, labels, and legend if needed
6. Use plt.tight_layout() for clean spacing
7. DO NOT call plt.show() - the code will handle saving
8. Handle any data preprocessing needed (grouping, aggregation, etc.)

Return ONLY the Python code, no explanations.

Example output format:
```python
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

df = pd.read_csv('{self.upload_dir / dataset_info.filename}')

# Your plotting code here
plt.figure(figsize=(10, 6))
sns.barplot(data=df, x='month', y='sales')
plt.title('Sales by Month')
plt.xlabel('Month')
plt.ylabel('Sales ($)')
plt.tight_layout()
```
"""
        
        messages = [
            {"role": "system", "content": "You are a data visualization expert that generates Python plotting code."},
            {"role": "user", "content": prompt}
        ]
        
        response = self.llm_client.generate(
            messages=messages,
            temperature=0.2,  # Low temperature for consistent code
            max_tokens=1024
        )
        
        # Extract code from markdown if present
        code = response.strip()
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0].strip()
        elif "```" in code:
            code = code.split("```")[1].split("```")[0].strip()
        
        logger.info(f"Generated {len(code)} characters of plotting code")
        logger.debug(f"Code:\n{code}")
        
        return code
    
    def execute_plot_code(self, code: str) -> str:
        """
        Execute plotting code and return base64-encoded image.
        
        Args:
            code: Python code that generates a matplotlib plot
            
        Returns:
            Base64-encoded PNG image string
            
        Raises:
            Exception: If code execution fails
        """
        logger.info("Executing plotting code")
        
        # Create execution environment with safe imports
        safe_globals = {
            'pd': pd,
            'plt': plt,
            'sns': sns,
            'Path': Path,
            '__builtins__': __builtins__
        }
        
        try:
            # Execute code
            exec(code, safe_globals)
            
            # Save plot to bytes buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            
            # Encode as base64
            img_base64 = base64.b64encode(buf.read()).decode('utf-8')
            
            # Cleanup
            plt.close('all')
            buf.close()
            
            logger.info(f"Successfully generated plot ({len(img_base64)} bytes encoded)")
            
            return img_base64
            
        except Exception as e:
            logger.error(f"Plot execution failed: {str(e)}")
            plt.close('all')  # Cleanup on error
            raise Exception(f"Plotting failed: {str(e)}")
    
    def create_visualization(
        self, 
        csv_filename: str, 
        user_request: str
    ) -> Dict[str, Any]:
        """
        Main method: inspect dataset, generate code, execute, return image.
        
        Args:
            csv_filename: Name of uploaded CSV file
            user_request: User's visualization request
            
        Returns:
            Dict with keys:
                - success: bool
                - image_base64: str (if success)
                - code: str (generated code)
                - error: str (if failure)
                - dataset_info: DatasetInfo
        """
        csv_path = self.upload_dir / csv_filename
        
        if not csv_path.exists():
            logger.error(f"CSV file not found: {csv_path}")
            return {
                "success": False,
                "error": f"File not found: {csv_filename}",
                "code": None,
                "image_base64": None,
                "dataset_info": None
            }
        
        try:
            # Step 1: Inspect dataset
            dataset_info = self.inspect_dataset(csv_path)
            
            # Step 2: Generate plotting code
            code = self.generate_plot_code(dataset_info, user_request)
            
            # Step 3: Execute code and get image
            image_base64 = self.execute_plot_code(code)
            
            return {
                "success": True,
                "image_base64": image_base64,
                "code": code,
                "error": None,
                "dataset_info": dataset_info
            }
            
        except Exception as e:
            logger.error(f"Visualization failed: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "code": code if 'code' in locals() else None,
                "image_base64": None,
                "dataset_info": dataset_info if 'dataset_info' in locals() else None
            }


# Agent function tool for orchestrator
def create_visualization_tool(agent: VisualizationAgent):
    """
    Create a function tool for the orchestrator agent.
    
    Usage:
        tool = create_visualization_tool(viz_agent)
        orchestrator.add_tool(tool)
    """
    def create_visualization(csv_filename: str, visualization_request: str) -> str:
        """
        Create a data visualization from an uploaded CSV file.
        
        Args:
            csv_filename: Name of the uploaded CSV file (e.g., "sales_data.csv")
            visualization_request: Description of what to plot (e.g., "bar chart of sales by month")
            
        Returns:
            JSON string with visualization result
            
        Examples:
            create_visualization("sales.csv", "plot monthly revenue as a line chart")
            create_visualization("grades.csv", "histogram of student scores")
            create_visualization("inventory.csv", "bar chart showing top 10 products by quantity")
        """
        import json
        
        logger.info(f"Tool called: create_visualization('{csv_filename}', '{visualization_request}')")
        
        result = agent.create_visualization(csv_filename, visualization_request)
        
        # Return result as JSON (orchestrator will handle image display)
        return json.dumps({
            "success": result["success"],
            "error": result["error"],
            "has_image": result["image_base64"] is not None,
            "dataset_shape": result["dataset_info"].shape if result["dataset_info"] else None,
            "code_preview": result["code"][:200] + "..." if result["code"] and len(result["code"]) > 200 else result["code"]
        })
    
    create_visualization.__name__ = "create_visualization"
    return create_visualization


# Convenience function for standalone usage
def visualize_csv(
    csv_path: str,
    request: str,
    llm_client,
    upload_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Standalone function for quick visualization.
    
    Args:
        csv_path: Path to CSV file
        request: Visualization request
        llm_client: LLM client
        upload_dir: Optional upload directory
        
    Returns:
        Visualization result dict
    """
    if upload_dir is None:
        upload_dir = Path(csv_path).parent
    
    agent = VisualizationAgent(llm_client, upload_dir)
    return agent.create_visualization(Path(csv_path).name, request)

