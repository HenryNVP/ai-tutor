#!/usr/bin/env python3
"""Validate that our agents can actually use MCP tools end-to-end."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.mcp import load_mcp_servers, shutdown_mcp_servers
from ai_tutor.system import TutorSystem


async def _verify_filesystem_tools(fs_server) -> None:
    """Directly call filesystem MCP tools to confirm connectivity."""
    print("\n[MCP] Listing data/generated/ via filesystem MCP tool...")
    result = await fs_server.call_tool(
        "list_directory",
        {"path": "data/generated", "recursive": False, "max_entries": 20},
    )
    payload = result.structuredContent.get("result") if result.structuredContent else None
    if not payload and result.content:
        payload = result.content[0].text
    print(payload or "<no content returned>")


async def _verify_chroma_tools(chroma_server) -> None:
    """Directly call Chroma MCP tool to confirm connectivity."""
    print("\n[MCP] Listing Chroma collections via MCP tool...")
    result = await chroma_server.call_tool("list_collections", {})
    payload = result.structuredContent.get("result") if result.structuredContent else None
    if not payload and result.content:
        payload = result.content[0].text
    print(payload or "<no content returned>")


def _run_note_request(system: TutorSystem) -> None:
    """Invoke the full tutor pipeline to create a text file."""
    learner_id = "mcp_test"
    prompt = "Please create a text file introducing BERT for beginners. Keep it short."
    print("\n[NOTE] Requesting tutor to create a text file...")
    response = system.answer_question(learner_id=learner_id, question=prompt, mode="learning", style_hint="stepwise")
    print("Tutor response:")
    print(response.answer)
    expected_path = Path("data/generated/text/bert-for-beginners.txt")
    if expected_path.exists():
        snippet = expected_path.read_text(encoding="utf-8")[:200]
        print(f"\n✅ note file created at {expected_path}")
        print("Preview:")
        print(snippet)
        expected_path.unlink()
        print("Cleanup: removed generated file.")
    else:
        print(f"\n⚠️ Expected note file {expected_path} was not created.")


def main() -> None:
    config_path = ROOT / "config" / "default.yaml"
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY is required to run this test.")
        return

    print("Loading MCP servers...")
    mcp_servers = load_mcp_servers()
    if not mcp_servers:
        print("❌ No MCP servers detected. Start filesystem/chroma MCP servers and re-run.")
        return

    try:
        print(f"Building TutorSystem from {config_path}...")
        system = TutorSystem.from_config(config_path=config_path, api_key=api_key, mcp_servers=mcp_servers)
        fs_server = mcp_servers.get("filesystem")
        chroma_server = mcp_servers.get("chroma")
        if fs_server:
            asyncio.run(_verify_filesystem_tools(fs_server))
        else:
            print("⚠️ Filesystem MCP server missing; skipping direct tool check.")
        if chroma_server:
            asyncio.run(_verify_chroma_tools(chroma_server))
        else:
            print("⚠️ Chroma MCP server missing; skipping direct tool check.")
        try:
            _run_note_request(system)
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"⚠️ Note MCP test failed: {exc}")
    finally:
        print("\nShutting down MCP connections...")
        shutdown_mcp_servers()


if __name__ == "__main__":
    main()

