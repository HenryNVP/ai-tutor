#!/usr/bin/env python3
"""Clear conversation session history to prevent token overflow."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_tutor.system import TutorSystem


def main():
    """Clear all or specific learner sessions."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Clear conversation session history")
    parser.add_argument(
        "learner_id",
        nargs="?",
        help="Learner ID to clear (or 'all' to clear all sessions)"
    )
    args = parser.parse_args()
    
    system = TutorSystem.from_config()
    
    if not args.learner_id:
        print("Current sessions in memory:")
        if system.tutor_agent.sessions:
            for learner_id in system.tutor_agent.sessions.keys():
                print(f"  - {learner_id}")
        else:
            print("  (none)")
        print("\nUsage:")
        print("  python scripts/clear_sessions.py <learner_id>  # Clear specific learner")
        print("  python scripts/clear_sessions.py all           # Clear all sessions")
        return
    
    if args.learner_id == "all":
        count = len(system.tutor_agent.sessions)
        system.tutor_agent.sessions.clear()
        print(f"✓ Cleared {count} session(s) from memory")
        print("\nNote: SQLite sessions are date-based and will auto-rotate daily.")
        print("Old sessions remain in the database but won't be loaded.")
    else:
        learner_id = args.learner_id
        system.clear_conversation_history(learner_id)
        print(f"✓ Cleared session for learner: {learner_id}")
        print("\nThe session will start fresh on the next question.")
    
    print("\nSession database location:")
    print(f"  {system.tutor_agent.session_db_path}")


if __name__ == "__main__":
    main()

