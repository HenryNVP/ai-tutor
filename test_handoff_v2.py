#!/usr/bin/env python3
"""Test script to verify orchestrator handoff behavior."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_tutor.system import TutorSystem


def test_stem_question():
    """Test that STEM questions get handed off properly."""
    print("=" * 70)
    print("TEST: STEM Question Handoff")
    print("=" * 70)
    
    system = TutorSystem.from_config()
    
    question = "What is the Bernoulli equation?"
    learner_id = "test_handoff"
    
    print(f"\n📝 Question: {question}")
    print(f"👤 Learner: {learner_id}")
    print("\n⏳ Processing...\n")
    
    response = system.answer_question(
        learner_id=learner_id,
        question=question,
        mode="learning",
    )
    
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"\n✨ Answer:\n{response.answer}\n")
    print(f"📊 Source: {response.source}")
    print(f"📚 Citations: {len(response.citations)}")
    
    if response.citations:
        print("\n📖 Citation Details:")
        for i, citation in enumerate(response.citations, 1):
            print(f"  [{i}] {citation}")
    
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    
    # Check if proper handoff occurred
    if response.source in ['local', 'web']:
        print("✅ PASS: Response has source attribution")
    else:
        print("❌ FAIL: No source attribution (orchestrator answered directly?)")
    
    if response.citations:
        print("✅ PASS: Response has citations")
    else:
        print("❌ FAIL: No citations found")
    
    if response.source == 'local':
        print("✅ PASS: Used local course materials (qa_agent)")
    elif response.source == 'web':
        print("✅ PASS: Used web search (web_agent)")
    else:
        print("❌ FAIL: Orchestrator answered directly without handoff")
    
    print("\n💡 TIP: Check OpenAI traces to see handoff events and tool calls")
    print("   - Look for 'handoff to qa_agent' or 'handoff to web_agent'")
    print("   - Look for 'retrieve_local_context' or 'web_search' tool calls")


def test_system_question():
    """Test that system questions are answered directly."""
    print("\n\n" + "=" * 70)
    print("TEST: System Question (Direct Answer)")
    print("=" * 70)
    
    system = TutorSystem.from_config()
    
    question = "What can you help me with?"
    learner_id = "test_handoff"
    
    print(f"\n📝 Question: {question}")
    print(f"👤 Learner: {learner_id}")
    print("\n⏳ Processing...\n")
    
    response = system.answer_question(
        learner_id=learner_id,
        question=question,
        mode="learning",
    )
    
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"\n✨ Answer:\n{response.answer}\n")
    print(f"📊 Source: {response.source}")
    print(f"📚 Citations: {len(response.citations)}")
    
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    
    # System questions should be answered directly
    if not response.source or response.source not in ['local', 'web']:
        print("✅ PASS: System question answered directly (no handoff)")
    else:
        print("❌ FAIL: System question was handed off unnecessarily")


if __name__ == "__main__":
    print("\n🧪 HANDOFF BEHAVIOR TEST SUITE")
    print("=" * 70)
    print("This script tests if the orchestrator properly hands off questions")
    print("to specialist agents (qa_agent, web_agent).")
    print("=" * 70)
    
    try:
        test_stem_question()
        test_system_question()
        
        print("\n\n" + "=" * 70)
        print("✅ TEST SUITE COMPLETE")
        print("=" * 70)
        print("\nIf STEM questions are not being handed off:")
        print("1. Check that OPENAI_API_KEY is set")
        print("2. Check OpenAI traces for handoff events")
        print("3. Verify agent instructions in tutor.py")
        print("4. Try restarting the application")
        
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        print("\nMake sure:")
        print("- OPENAI_API_KEY environment variable is set")
        print("- Dependencies are installed (pip install -e .)")
        print("- Vector store is initialized (if testing with local materials)")
        sys.exit(1)

