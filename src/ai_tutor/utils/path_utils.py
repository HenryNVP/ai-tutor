"""Utility functions for path and filename handling."""

from pathlib import Path
from typing import List


def normalize_source_path(source_path: Path) -> Path:
    """
    Normalize a source path to a consistent format for storage in chunk metadata.
    
    This function standardizes file paths to ensure consistent storage and retrieval.
    It handles various input path formats and converts them to a standard format.
    
    Normalization Rules
    -------------------
    1. **Temp paths** (`/tmp/`, `aitutor_ingest`): Convert to filename only
       - Input: `/tmp/aitutor_ingest_abc123/file.pdf`
       - Output: `file.pdf`
    
    2. **data/uploads/**: Preserve `data/uploads/` prefix with filename
       - Input: `data/uploads/file.pdf`
       - Output: `data/uploads/file.pdf`
    
    3. **data/raw/**: Preserve relative path from `data/raw/`
       - Input: `data/raw/physics/textbook.pdf`
       - Output: `data/raw/physics/textbook.pdf`
       - Input: `data/raw/file.pdf`
       - Output: `data/raw/file.pdf`
    
    4. **Other paths**: Convert to filename only (avoid storing absolute paths)
       - Input: `/home/user/documents/file.pdf`
       - Output: `file.pdf`
       - Input: `./relative/path/file.pdf`
       - Output: `file.pdf`
    
    5. **Empty/None**: Return `unknown`
       - Input: `None` or empty
       - Output: `unknown`
    
    Parameters
    ----------
    source_path : Path
        Original source path to normalize
        
    Returns
    -------
    Path
        Normalized path following the rules above
        
    Examples
    --------
    >>> from pathlib import Path
    >>> normalize_source_path(Path("/tmp/aitutor_ingest_abc/file.pdf"))
    Path('file.pdf')
    
    >>> normalize_source_path(Path("data/uploads/lecture.pdf"))
    Path('data/uploads/lecture.pdf')
    
    >>> normalize_source_path(Path("data/raw/physics/chapter1.pdf"))
    Path('data/raw/physics/chapter1.pdf')
    
    >>> normalize_source_path(Path("/absolute/path/file.pdf"))
    Path('file.pdf')
    """
    if not source_path:
        return Path("unknown")
    
    source_str = str(source_path)
    
    # Rule 1: Temp paths → filename only
    if "/tmp/" in source_str or "aitutor_ingest" in source_str:
        return Path(source_path.name)
    
    # Rule 2: data/uploads/ → preserve prefix
    if source_str.startswith("data/uploads/"):
        return Path("data/uploads") / source_path.name
    
    # Rule 3: data/raw/ → preserve relative path from data/raw
    if source_str.startswith("data/raw/"):
        try:
            relative_path = source_path.relative_to(Path("data/raw"))
            return Path("data/raw") / relative_path
        except ValueError:
            # If not relative to data/raw (shouldn't happen, but handle gracefully)
            return Path(source_path.name)
    
    # Rule 4: Other paths → filename only (avoid storing absolute paths)
    return Path(source_path.name)


def generate_filename_variations(filename: str) -> List[str]:
    """
    Generate common filename variations for path matching.
    
    This function creates variations of a filename to handle different storage
    locations and path formats (e.g., temp paths, data/uploads, data/raw).
    
    Parameters
    ----------
    filename : str
        Original filename or path
        
    Returns
    -------
    List[str]
        List of filename variations to try, in order of preference
        
    Examples
    --------
    >>> variations = generate_filename_variations("lecture7.pdf")
    >>> # Returns: ["lecture7.pdf", "data/uploads/lecture7.pdf", "data/raw/lecture7.pdf"]
    
    >>> variations = generate_filename_variations("data/uploads/file.pdf")
    >>> # Returns: ["data/uploads/file.pdf", "file.pdf", "data/raw/file.pdf"]
    """
    variations = []
    
    # Add original
    variations.append(filename)
    
    # Extract filename only (no path)
    filename_only = Path(filename).name
    if filename_only != filename:
        variations.append(filename_only)
    
    # Add with data/uploads prefix (common for uploaded files)
    if not filename.startswith("data/uploads"):
        variations.append(f"data/uploads/{filename}")
        if filename_only != filename:
            variations.append(f"data/uploads/{filename_only}")
    
    # Add with data/raw prefix (common for ingested documents)
    if not filename.startswith("data/raw"):
        variations.append(f"data/raw/{filename}")
        if filename_only != filename:
            variations.append(f"data/raw/{filename_only}")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_variations = []
    for var in variations:
        if var not in seen:
            seen.add(var)
            unique_variations.append(var)
    
    return unique_variations

