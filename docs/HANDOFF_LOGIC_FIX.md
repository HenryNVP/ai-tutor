# Orchestrator Handoff Logic Fix

## Issue

When asking STEM questions like "What is the Bernoulli equation?", the `tutor_orchestrator` agent was answering directly instead of handing off to `qa_agent` or `web_agent` for cited, reference-backed answers.

### Root Cause

The orchestrator instructions contained an ambiguous clause:

```python
"- If the question is about the tutoring system itself, the student profile, 
   learning progress, progress history, or general/common knowledge, 
   you should answer directly."
```

The phrase **"or general/common knowledge"** was too vague. The LLM was interpreting well-known STEM questions (like asking about the Bernoulli equation) as "general/common knowledge" and answering directly without consulting course materials or web sources.

This conflicted with the delegation rule for STEM content:
```python
"- If the question involves STEM content (math, science, coding, etc.) 
   and may benefit from local course materials or citations, 
   hand it off to the qa_agent."
```

The weak phrasing "may benefit from" also left room for the orchestrator to skip delegation.

## Fix

### New Instruction Structure

Restructured the orchestrator instructions with **explicit, numbered rules** that leave no ambiguity:

```python
"DELEGATION RULES (follow strictly):

1. ALWAYS DELEGATE STEM CONTENT:
   - Any question about math, physics, chemistry, biology, engineering, 
     computer science, or other STEM subjects MUST be handed off to `qa_agent`.
   - This includes definitions, equations, formulas, concepts, theories, 
     laws, principles, or explanations.
   - Examples: 'What is the Bernoulli equation?', 'Explain Newton's laws', 
     'How does photosynthesis work?', 'What is a linked list?'
   - The qa_agent will provide cited answers from course materials. 
     If no local materials exist, it will hand off to web_agent.

2. HAND OFF TO WEB_AGENT:
   - Questions about current events, news, recent developments, 
     or topics clearly outside STEM.

3. HAND OFF TO INGESTION_AGENT:
   - User explicitly asks to upload, ingest, index, or add files/documents.

4. USE GENERATE_QUIZ TOOL:
   - Learner explicitly asks for a quiz, practice exam, test, or questions.

5. ANSWER DIRECTLY (only these cases):
   - Questions about the tutoring system itself
   - Questions about the learner's own profile, progress, or history
   - Simple greetings or small talk

IMPORTANT: When in doubt, ALWAYS delegate to a specialist agent. 
Do NOT answer STEM questions directly even if you know the answer. 
The specialist agents provide better answers with references and citations."
```

### Key Improvements

1. **Removed ambiguous "general/common knowledge" clause**
   - Eliminates confusion about what the orchestrator should answer

2. **Stronger STEM delegation mandate**
   - Changed from "may benefit from" to "MUST be handed off"
   - Added "ALWAYS DELEGATE" to the rule title
   - Included explicit examples of STEM questions

3. **Clear numbered rules**
   - Easier for LLM to parse and follow
   - Hierarchical structure with clear priorities

4. **Explicit "ANSWER DIRECTLY" scope**
   - Only 3 narrow categories where direct answers are acceptable
   - Everything else should be delegated

5. **Strong closing reminder**
   - "Do NOT answer STEM questions directly even if you know the answer"
   - Emphasizes that specialist agents provide better answers

## Testing

Test the fix with these questions:

### Should Hand Off to QA Agent ✅
```
- "What is the Bernoulli equation?"
- "Explain Newton's first law"
- "How does photosynthesis work?"
- "What is a binary search tree?"
- "Derive the quadratic formula"
- "What is Ohm's law?"
```

### Should Hand Off to Web Agent ✅
```
- "What happened in the 2024 election?"
- "Who won the latest Nobel Prize in Physics?"
- "What are recent developments in AI?"
```

### Should Answer Directly ✅
```
- "What can you help me with?"
- "How do I use this tutoring system?"
- "What's my current learning progress?"
- "Hello, how are you?"
```

### Should Use Generate Quiz Tool ✅
```
- "Give me a quiz on thermodynamics"
- "Test me on calculus"
- "I want 5 practice questions on biology"
```

## Verification Steps

1. **Check OpenAI Traces**
   - Look for handoff events to `qa_agent` or `web_agent`
   - Should see tool calls to `retrieve_local_context` or `web_search`

2. **Check Response Source**
   - STEM answers should include citations
   - Citations should reference course materials or web URLs

3. **Compare Before/After**
   - Before: "The Bernoulli equation is..." (direct answer, no citations)
   - After: "[1] Physics Textbook (Page 42)..." (cited answer with references)

## Files Modified

- **`src/ai_tutor/agents/tutor.py`**
  - Updated `self.orchestrator_agent` instructions (lines 125-160)
  - Changed from loose rules to strict numbered delegation rules

## Related Components

The orchestrator works with these specialist agents:

- **`qa_agent`** (in `src/ai_tutor/agents/qa.py`)
  - Retrieves local course materials via `retrieve_local_context` tool
  - Provides cited answers with page references
  - Hands off to web_agent if no local context found

- **`web_agent`** (in `src/ai_tutor/agents/web.py`)
  - Uses `web_search` tool for external information
  - Provides answers with URL citations

- **`ingestion_agent`** (in `src/ai_tutor/agents/ingestion.py`)
  - Handles document ingestion requests

## Impact

### Before Fix
- ❌ STEM questions answered without citations
- ❌ No use of local course materials
- ❌ Inconsistent behavior (sometimes delegates, sometimes doesn't)
- ❌ Lower quality answers for technical questions

### After Fix
- ✅ All STEM questions delegated to qa_agent
- ✅ Answers include citations and references
- ✅ Consistent delegation behavior
- ✅ Better use of local course materials
- ✅ Fallback to web search when needed
- ✅ Higher quality, more authoritative answers

## Migration Notes

- No breaking changes
- Existing sessions will benefit from improved delegation immediately
- No user-facing changes needed
- OpenAI traces will show more handoff events (this is expected and desired)

## Future Improvements

Consider these enhancements:

1. **Domain-Specific Agents**
   - Separate agents for math, physics, biology, etc.
   - More specialized knowledge per domain

2. **Confidence-Based Routing**
   - Route based on retrieval confidence scores
   - Skip qa_agent if no relevant local materials

3. **Hybrid Answers**
   - Combine local + web sources for comprehensive answers
   - Cross-reference multiple sources

4. **Learner Preference**
   - Allow learners to prefer local-only or include web sources
   - Personalize delegation behavior

## Testing Commands

```bash
# Run the web tutor interface
python scripts/tutor_web.py

# Or use the REPL
python scripts/tutor_repl.py

# Test with different questions and check OpenAI traces
```

## Conclusion

This fix ensures that **all STEM questions are properly delegated** to specialist agents that can provide **cited, reference-backed answers** from course materials or web sources. The orchestrator now has clear, unambiguous rules that prevent it from answering technical questions directly.

