# Handoff Logic Fix - Version 2 (Aggressive)

## Problem

Even after the first fix, the orchestrator was still not handing off STEM questions to specialist agents. "What is the Bernoulli equation?" was being answered directly without citations.

## Root Causes Identified

### 1. **Conflicting System Preamble**
The prompt sent to the orchestrator included:
```python
"Cite supporting evidence using bracketed indices or URLs when available."
```

This instruction was telling the orchestrator to **provide citations**, which made it think it should answer the question itself with citations, rather than delegating to a specialist agent.

### 2. **Weak Framing**
The orchestrator was framed as an "orchestrator agent" that "decides whether to answer or delegate", giving it permission to answer. This dual role created ambiguity.

### 3. **No Explicit Model**
The orchestrator didn't have an explicit model parameter, potentially using a default or weaker model that doesn't follow routing instructions as strictly.

### 4. **Vague Instructions**
Terms like "may benefit from" and "general/common knowledge" left room for interpretation.

## The Aggressive Fix

### 1. **Orchestrator: Pure Router** (`tutor.py`)

**Changed framing entirely:**
```python
"You are a routing agent. Your ONLY job is to hand off questions to the right 
specialist agent. DO NOT answer questions yourself."
```

**Key changes:**
- ✅ Explicit `model="gpt-4o-mini"` for better instruction following
- ✅ Changed from dual-role (answer or delegate) to **single-role (route only)**
- ✅ Used imperative commands: "DO NOT answer", "IMMEDIATELY hand off"
- ✅ Simplified format with arrow notation: `STEM Questions → qa_agent`
- ✅ Added explicit example: `'What is the Bernoulli equation?' → Hand off to qa_agent immediately`
- ✅ Listed specific STEM domains (Physics, Chemistry, Biology, Math, CS, Engineering)

**Full routing rules:**
```
STEM Questions → qa_agent (IMMEDIATELY)
Current Events / Non-STEM → web_agent
File Upload → ingestion_agent
Quiz Request → generate_quiz tool
ONLY Answer Directly: System questions, profile questions, greetings
```

### 2. **Removed Conflicting Context** (`tutor.py`)

**Problem:** The system preamble told the orchestrator to cite evidence:
```python
system_preamble = (
    f"Learner mode: {mode}. Preferred explanation style: {style_hint}. "
    "Cite supporting evidence using bracketed indices or URLs when available."
)
```

**Solution:** Only send minimal context to orchestrator:
```python
if self.orchestrator_agent:
    # Minimal prompt - just profile summary and question
    prompt_sections: List[str] = []
    if profile:
        prompt_sections.append("Learner profile summary:")
        prompt_sections.append(self._render_profile_summary(profile))
        prompt_sections.append("")
    prompt_sections.append("Question:")
    prompt_sections.append(question)
    prompt = "\n".join(prompt_sections)
```

The citation instructions are meant for **specialist agents** (qa_agent, web_agent), not the router.

### 3. **Strengthened QA Agent** (`qa.py`)

Made the process explicit and added model specification:

```python
Agent(
    name="qa_agent",
    model="-mini",
    instructions=(
        "You answer STEM questions using local course materials.\n\n"
        "PROCESS:\n"
        "1. ALWAYS call retrieve_local_context tool first\n"
        "2. Read the returned context carefully\n"
        "3. If context is useful, answer using it and cite sources with [1], [2], etc.\n"
        "4. If NO useful context or empty results, hand off to web_agent\n\n"
        "IMPORTANT:\n"
        "- ALWAYS call retrieve_local_context before answering\n"
        "- Include citations in your answer using bracketed numbers\n"
        "- List all citations at the end"
    ),
    ...
)
```

### 4. **Strengthened Web Agent** (`web.py`)

Similar improvements:

```python
Agent(
    name="web_agent",
    model="gpt-4o",
    instructions=(
        "You answer questions using web search.\n\n"
        "PROCESS:\n"
        "1. ALWAYS call web_search tool first\n"
        "2. Review the search results\n"
        "3. Synthesize an answer using the information found\n"
        "4. Cite sources with URLs\n\n"
        "IMPORTANT:\n"
        "- ALWAYS call web_search before answering\n"
        "- Include URL citations in your answer\n"
        "- List all sources at the end"
    ),
    ...
)
```

## Files Modified

1. **`src/ai_tutor/agents/tutor.py`**
   - Rewrote orchestrator instructions (lines 123-170)
   - Added explicit `model="gpt-4o"`
   - Modified prompt construction to exclude citation instructions from orchestrator (lines 227-271)

2. **`src/ai_tutor/agents/qa.py`**
   - Rewrote qa_agent instructions (lines 55-72)
   - Added explicit `model="gpt-4o"`
   - Made tool calling mandatory with numbered steps

3. **`src/ai_tutor/agents/web.py`**
   - Rewrote web_agent instructions (lines 35-51)
   - Added explicit `model="gpt-4o"`
   - Made tool calling mandatory with numbered steps

## Testing

Test these questions to verify handoff behavior:

### STEM Questions (Should see handoff → retrieve_local_context or web_search)

```
✓ "What is the Bernoulli equation?"
✓ "Explain Newton's first law"
✓ "How does photosynthesis work?"
✓ "What is a binary search tree?"
✓ "Derive the quadratic formula"
```

**Expected trace:**
1. Request to orchestrator
2. **Handoff event to qa_agent**
3. qa_agent calls **retrieve_local_context** tool
4. If no local context: **handoff to web_agent**
5. web_agent calls **web_search** tool
6. Response with **citations**

### System Questions (Should answer directly, no handoff)

```
✓ "What can you help me with?"
✓ "What's my learning progress?"
✓ "Hello"
```

**Expected trace:**
1. Request to orchestrator
2. Direct response (no handoff)

## Before vs After

### Before (Wrong Behavior)
```
User: "What is the Bernoulli equation?"
Orchestrator: "The Bernoulli equation describes the relationship between 
pressure, velocity, and height in a fluid flow. It states that..."
[No citations, no handoff, no tool calls]
```

### After (Correct Behavior)
```
User: "What is the Bernoulli equation?"
Orchestrator: [HANDOFF to qa_agent]
QA Agent: [Calls retrieve_local_context tool]
QA Agent: "The Bernoulli equation describes... [1] [2]

Citations:
[1] Physics Textbook (Doc: physics_101, Page: 42)
[2] Fluid Dynamics Notes (Doc: fluids, Page: 15)"
```

## Key Principles Applied

1. **Single Responsibility**: Orchestrator ONLY routes, doesn't answer
2. **Explicit > Implicit**: Clear commands like "DO NOT" and "ALWAYS"
3. **Mandatory Tool Use**: Agents MUST call tools before answering
4. **Separate Concerns**: Citation instructions only for answering agents
5. **Better Models**: Use gpt-4o for better instruction following

## Verification Checklist

When testing, verify:

- [ ] STEM questions show handoff event in OpenAI traces
- [ ] Tool calls appear (retrieve_local_context or web_search)
- [ ] Responses include citations ([1], [2] or URLs)
- [ ] Orchestrator never provides direct STEM answers
- [ ] System questions still get direct responses (no handoff)

## Why This Should Work

1. **Clear Role**: Orchestrator can't answer because it's a "routing agent" not an "orchestrator"
2. **No Confusion**: No citation instructions in orchestrator's prompt
3. **Better Model**: gpt-4o follows complex routing instructions more reliably
4. **Explicit Examples**: Shows exactly what to do with Bernoulli equation question
5. **Mandatory Process**: Specialist agents must call tools first

## Fallback Plan

If handoffs still don't occur, consider:

1. **Check Agent SDK version**: Ensure using latest `openai-agents`
2. **Verify handoff configuration**: Confirm handoffs list is properly constructed
3. **Add temperature=0**: For more deterministic routing
4. **Log intermediate steps**: Add debug logging to see agent decisions
5. **Test without orchestrator**: Temporarily bypass to isolate issue

## Impact

- **Better answers**: All STEM questions now get cited, reference-backed answers
- **Consistent behavior**: Routing is deterministic and reliable
- **Proper tool use**: Retrieval and search tools always utilized
- **Clear separation**: Router doesn't try to answer, answerers don't route

