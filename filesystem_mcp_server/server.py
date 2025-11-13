"""
Filesystem MCP Server
=====================

This MCP server exposes a safe, sandboxed view of the local workspace so agents
can list directories, read files, and write new content using standard MCP tools.

Configuration (environment variables)
-------------------------------------
FS_MCP_ROOT:
    Absolute path to the workspace root. Defaults to the project root (two levels
    above this file).
FS_MCP_PORT:
    TCP port to listen on (default: 8100).
FS_MCP_TRANSPORT:
    Transport mode for FastMCP (`streamable-http` or `sse`). Defaults to
    `streamable-http`.
FS_MCP_ALLOW_HIDDEN:
    If set to a truthy value, hidden files (names starting with ".") are returned
    by directory listings. Defaults to False.
FS_MCP_MAX_READ_BYTES:
    Maximum bytes to read from a file (default: 131072 bytes).

Running the server
------------------

    cd filesystem_mcp_server
    python server.py

"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Dict

from fastmcp import FastMCP


def _truthy(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.lower() in {"1", "true", "yes", "on"}


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROOT_DIR = Path(os.getenv("FS_MCP_ROOT", PROJECT_ROOT)).resolve()
ALLOW_HIDDEN = _truthy(os.getenv("FS_MCP_ALLOW_HIDDEN"))
MAX_READ_BYTES = int(os.getenv("FS_MCP_MAX_READ_BYTES", "131072"))

DEFAULT_WRITE_SUBDIR = os.getenv("FS_MCP_WRITE_ROOT", "data/generated")
WRITE_ROOT = Path(DEFAULT_WRITE_SUBDIR)
if not WRITE_ROOT.is_absolute():
    WRITE_ROOT = (ROOT_DIR / WRITE_ROOT).resolve()
if not str(WRITE_ROOT).startswith(str(ROOT_DIR)):
    raise ValueError("FS_MCP_WRITE_ROOT must reside within the workspace root.")
WRITE_ROOT.mkdir(parents=True, exist_ok=True)

# Helper to generate a non-conflicting path when overwrite is False.
def _generate_unique_path(path: Path) -> Path:
    parent = path.parent
    stem = path.stem
    suffix = path.suffix
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    candidate = parent / f"{stem}_{timestamp}{suffix}"
    counter = 1
    while candidate.exists():
        candidate = parent / f"{stem}_{timestamp}_{counter}{suffix}"
        counter += 1
    return candidate

WRITE_HISTORY: Dict[str, Path] = {}


def _canonical_request(path: str) -> str:
    return str(Path(path)).replace("\\", "/")


# Create FastMCP instance with name and instructions
mcp = FastMCP(
    name="Filesystem MCP Server",
    instructions="""
        This server provides safe filesystem operations for AI agents.
        Use list_directory to browse files, read_file to read content,
        write_text_file to create/update files, and delete_path to remove files.
        All operations are sandboxed to the configured workspace root.
    """,
)


def _resolve_path(path: str | None) -> Path:
    """Resolve path within the configured root directory."""
    if not path:
        candidate = ROOT_DIR
    else:
        candidate = (ROOT_DIR / path).resolve()

    try:
        candidate.relative_to(ROOT_DIR)
    except ValueError:
        raise ValueError(f"Path '{path}' is outside of allowed root: {ROOT_DIR}")

    return candidate


def _format_entry(path: Path) -> dict:
    """Create a serialisable dict describing a filesystem entry."""
    stat = path.stat()
    return {
        "path": str(path.relative_to(ROOT_DIR)),
        "name": path.name,
        "is_dir": path.is_dir(),
        "size": stat.st_size,
        "modified": stat.st_mtime,
    }


def _iter_directory(
    directory: Path,
    recursive: bool,
    max_entries: int,
) -> Iterable[dict]:
    """Yield directory entries respecting visibility, recursion, and limits."""
    count = 0
    stack: List[Path] = [directory]

    while stack and count < max_entries:
        current = stack.pop()
        if not current.exists():
            continue

        entries = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        for entry in entries:
            if count >= max_entries:
                break
            if not ALLOW_HIDDEN and entry.name.startswith("."):
                continue

            yield _format_entry(entry)
            count += 1

            if recursive and entry.is_dir():
                stack.append(entry)


@mcp.tool()
def list_directory(
    path: str | None = None,
    recursive: bool = False,
    max_entries: int = 200,
) -> str:
    """
    List files within the workspace.

    Parameters
    ----------
    path : str | None
        Directory relative to the workspace root. Defaults to the root itself.
    recursive : bool
        If true, recurse into subdirectories (breadth-first) until max_entries
        is reached.
    max_entries : int
        Maximum number of entries to return. Prevents overwhelming responses.
    """
    directory = _resolve_path(path)
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {directory}")

    entries = list(_iter_directory(directory, recursive=recursive, max_entries=max_entries))
    payload = {
        "root": str(ROOT_DIR),
        "directory": str(directory.relative_to(ROOT_DIR)),
        "count": len(entries),
        "has_more": recursive and len(entries) >= max_entries,
        "entries": entries,
    }
    return json.dumps(payload, indent=2)


@mcp.tool()
def read_text_file(
    path: str,
    start: int = 0,
    length: Optional[int] = None,
) -> str:
    """
    Read a UTF-8 text file within the workspace.

    Parameters
    ----------
    path : str
        File path relative to the workspace root.
    start : int
        Byte offset to start reading from (supports incremental reads).
    length : Optional[int]
        Maximum number of bytes to read. Defaults to FS_MCP_MAX_READ_BYTES.
    """
    canonical = _canonical_request(path)
    mapped_path = WRITE_HISTORY.get(canonical)
    if mapped_path and mapped_path.exists():
        file_path = mapped_path
    else:
        file_path = _resolve_path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not file_path.is_file():
        raise IsADirectoryError(f"Path is not a file: {file_path}")

    max_length = length if length is not None else MAX_READ_BYTES
    if max_length <= 0:
        raise ValueError("length must be > 0")

    with file_path.open("rb") as fh:
        fh.seek(start)
        content = fh.read(max_length)

    return content.decode("utf-8", errors="replace")


@mcp.tool()
def write_text_file(
    path: str,
    content: str,
    overwrite: bool = False,
) -> str:
    """
    Write (or create) a text file within the workspace.

    Parameters
    ----------
    path : str
        File path relative to the workspace root.
    content : str
        Text content to write.
    overwrite : bool
        If False, writing to an existing file raises an error.
    """
    canonical = _canonical_request(path)

    candidate = _resolve_path(path)
    try:
        candidate.relative_to(WRITE_ROOT)
        file_path = candidate
    except ValueError:
        file_path = (WRITE_ROOT / path).resolve()
        try:
            file_path.relative_to(WRITE_ROOT)
        except ValueError as exc:
            raise ValueError(
                f"Write path {file_path} escapes the allowed directory {WRITE_ROOT}"
            ) from exc

    mapped_path = WRITE_HISTORY.get(canonical)
    auto_renamed = False

    if mapped_path and mapped_path.exists() and not overwrite:
        file_path = mapped_path
    elif file_path.exists() and not overwrite:
        file_path = _generate_unique_path(file_path)
        auto_renamed = True

    WRITE_HISTORY[canonical] = file_path

    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as fh:
        fh.write(content)

    return json.dumps(
        {
            "path": str(file_path.relative_to(ROOT_DIR)),
            "bytes_written": len(content.encode("utf-8")),
            "overwrite": overwrite,
            "auto_renamed": auto_renamed,
        },
        indent=2,
    )


@mcp.tool()
def append_text_file(path: str, content: str) -> str:
    """Append text to a file within the workspace."""
    canonical = _canonical_request(path)
    mapped_path = WRITE_HISTORY.get(canonical)

    if mapped_path and mapped_path.exists():
        file_path = mapped_path
    else:
        candidate = _resolve_path(path)
        try:
            candidate.relative_to(WRITE_ROOT)
            file_path = candidate
        except ValueError:
            file_path = (WRITE_ROOT / path).resolve()
            try:
                file_path.relative_to(WRITE_ROOT)
            except ValueError as exc:
                raise ValueError(
                    f"Append path {file_path} escapes the allowed directory {WRITE_ROOT}"
                ) from exc
        WRITE_HISTORY[canonical] = file_path

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not file_path.is_file():
        raise IsADirectoryError(f"Cannot append to directory: {file_path}")

    with file_path.open("a", encoding="utf-8") as fh:
        fh.write(content)

    return json.dumps(
        {
            "path": str(file_path.relative_to(ROOT_DIR)),
            "bytes_appended": len(content.encode("utf-8")),
        },
        indent=2,
    )


def _delete_path(target: Path, recursive: bool) -> None:
    if target.is_dir():
        if not recursive and any(target.iterdir()):
            raise IsADirectoryError(
                f"Directory not empty: {target}. Pass recursive=True to delete contents."
            )
        for child in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name)):
            if child.is_dir():
                _delete_path(child, recursive=recursive)
            else:
                child.unlink()
        target.rmdir()
    else:
        target.unlink()


@mcp.tool()
def delete_path(path: str, recursive: bool = False) -> str:
    """Delete a file or directory (optionally recursive)."""
    target = _resolve_path(path)
    if not target.exists():
        raise FileNotFoundError(f"Path not found: {target}")

    _delete_path(target, recursive=recursive)

    return json.dumps(
        {
            "path": str(target.relative_to(ROOT_DIR)),
            "deleted": True,
        },
        indent=2,
    )


if __name__ == "__main__":
    transport = os.getenv("FS_MCP_TRANSPORT", os.getenv("MCP_TRANSPORT", "http"))
    # Get port (prioritize FS_MCP_PORT, default to 8100)
    port = int(os.getenv("FS_MCP_PORT", "8100"))
    
    print(f"Starting Filesystem MCP server on port {port} with {transport} transport...")
    print(f"Workspace root: {ROOT_DIR}")
    print(f"Hidden files {'allowed' if ALLOW_HIDDEN else 'hidden'}")
    print("Press Ctrl+C to stop the server.\n")

    # Use http transport with explicit host and port
    # streamable-http may not support host/port parameters
    if transport == "http":
        mcp.run(
            transport="http",
            host="127.0.0.1",
            port=port,
        )
    else:
        # For streamable-http or other transports, set PORT env var
        os.environ["PORT"] = str(port)
        mcp.run(transport=transport)

