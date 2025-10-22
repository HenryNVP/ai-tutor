"""Quick CLI to inspect stored agent sessions."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

DEFAULT_DB = Path("data/processed/sessions.sqlite")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect persisted tutor sessions.")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"Path to sessions database (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of most recent messages per session to display.",
    )
    args = parser.parse_args()

    if not args.db.exists():
        raise SystemExit(f"Database not found at {args.db}")

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    sessions = conn.execute(
        "SELECT session_id, created_at, updated_at FROM agent_sessions ORDER BY updated_at DESC"
    ).fetchall()

    if not sessions:
        print("No sessions stored yet.")
        conn.close()
        return

    for session in sessions:
        session_id = session["session_id"]
        print(f"Session: {session_id} (created {session['created_at']}, updated {session['updated_at']})")
        rows = conn.execute(
            "SELECT message_data FROM agent_messages WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
            (session_id, args.limit),
        ).fetchall()
        if not rows:
            print("  (no messages)")
            print()
            continue
        for row in reversed(rows):
            payload = json.loads(row["message_data"])
            role = payload.get("role", "unknown")
            content = payload.get("content")
            if isinstance(content, list):
                text = " ".join(part.get("text", "") for part in content if isinstance(part, dict))
            else:
                text = str(content)
            print(f"  {role}: {text[:200]}")
        print()

    conn.close()


if __name__ == "__main__":
    main()
