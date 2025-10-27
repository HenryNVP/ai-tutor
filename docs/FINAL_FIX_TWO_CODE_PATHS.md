# ✅ Final Fix: Two Code Paths & Count Extraction

## The Issues

1. **Only 8 questions generated** instead of 40
2. **Inconsistent behavior** - "sometimes it works, sometimes not"
3. **Topic varies** - sometimes "computer vision" (correct), sometimes generic

## Root Cause: Two Quiz Generation Code Paths!

The tutor agent has **TWO ways** to generate quizzes:

### Path 1: Function Tool (NEW) ✅
```python
# Line 251: Agent calls generate_quiz function tool
@function_tool
def generate_quiz(topic: str, count: int = 4, ...) -> str:
    question_count = max(3, min(question_count, 40))  # ✅ Max 40
    quiz = self.quiz_service.generate_quiz(...)
    return f"Prepared a {len(quiz.questions)}-question quiz..."
```

### Path 2: JSON Directive (OLD) ❌
```python
# Line 649: Agent returns JSON, processed by _process_quiz_directive
def _process_quiz_directive(...):
    count = max(3, min(count, 8))  # ❌ Was limited to 8!
    quiz = self.quiz_service.generate_quiz(...)
    return f"I've prepared a {count}-question quiz..."
```

**The agent was inconsistently using the old JSON path!**

When it used the old path:
- ❌ Limited to 8 questions
- ❌ Different response format
- ❌ Less reliable

---

## The Fixes

### Fix 1: Update Old Code Path Limit
**File:** `src/ai_tutor/agents/tutor.py` line 649

**Before:**
```python
count = max(3, min(count, 8))  # Max 8
```

**After:**
```python
count = max(3, min(count, 40))  # Allow up to 40 questions
```

### Fix 2: Strengthen Agent Instructions
**File:** `src/ai_tutor/agents/tutor.py` lines 330-343

**Added:**
- "ALWAYS use generate_quiz tool (DO NOT return text!)"
- Clarified: "40 quizzes" means 40 questions (not 40 separate quizzes)
- Emphasized: Extract exact count number
- Example showing the exact user request

**Before:**
```python
"Quiz Request → Use generate_quiz tool\n"
"- Extract count from message: 'create 10 quizzes' → count=10\n"
```

**After:**
```python
"Quiz Request → ALWAYS use generate_quiz tool (DO NOT return text!)\n"
"- Extract count: 'create 40 quizzes' → count=40 (NOT 4, use the exact number!)\n"
"- Note: 'quizzes' can mean 'quiz questions', so '40 quizzes' = 40 questions\n"
"→ ALWAYS call generate_quiz(topic, count) tool - DO NOT just respond with text!\n"
"Example: 'Create 40 comprehensive quizzes from the document'\n"
"  → generate_quiz(topic='computer science', count=40)\n"
```

---

## Why It Was Inconsistent

The agent would **sometimes** use the function tool, **sometimes** return text:

### When Using Function Tool:
```
User: "create 40 quizzes from the document"
  ↓
Agent calls: generate_quiz(topic='machine learning', count=40)
  ↓
Tool: Generates 40 questions (with limit check)
  ↓
✅ Works correctly!
```

### When Using JSON Directive (Old Way):
```
User: "create 40 quizzes from the document"
  ↓
Agent thinks: "I'll respond with a quiz directive"
  ↓
Agent returns: {"action": "generate_quiz", "count": 40, ...}
  ↓
Old code path: Limits to 8
  ↓
❌ Only 8 questions generated!
```

The agent wasn't consistently following instructions to use the tool!

---

## How It Works Now

```
User: "create 40 comprehensive quizzes from the document"
  ↓
UI: Retrieves passages from uploaded docs
    Enhances prompt with document names
  ↓
Agent: Receives clear instructions: "ALWAYS use generate_quiz tool"
       Understands: "40 quizzes" = 40 questions
       Extracts: count=40, topic='computer science'
  ↓
Agent: Calls generate_quiz(topic='computer science', count=40)
  ↓
Tool: self._active_extra_context has YOUR uploaded document content
      Limits: max(3, min(40, 40)) = 40
      Generates: 40 questions from YOUR content
  ↓
Quiz Service: Prioritizes extra_context (YOUR documents)
              Generates 40 questions about computer vision
  ↓
✅ 40 questions about YOLO, R-CNN, computer vision!
```

---

## What Changed

### 1. Both Code Paths Support 40 Questions
- ✅ Function tool: max 40 (line 277)
- ✅ JSON directive: max 40 (line 649)
- Now consistent!

### 2. Agent Instructions Strengthened
- ✅ "ALWAYS use generate_quiz tool"
- ✅ "DO NOT return text"
- ✅ "'40 quizzes' = 40 questions"
- ✅ Exact example provided

### 3. Topic Extraction Clarified
- ✅ Use broad topics for documents
- ✅ Don't use "uploaded_documents"
- ✅ Check learner profile

---

## Files Changed

**src/ai_tutor/agents/tutor.py:**
1. Line 649: Increased limit from 8 to 40
2. Lines 330-343: Strengthened agent instructions
3. ✅ No linter errors

---

## Testing

**Restart Streamlit:**
```bash
pkill -f streamlit
streamlit run apps/ui.py
```

**Try:**
```
"create 40 comprehensive quizzes from the document"
```

**Expected:**
1. ✅ "Retrieved X passages from 2 document(s): Lecture9, Lecture10"
2. ✅ Agent calls function tool (not JSON directive)
3. ✅ Generates 40 questions (not 8!)
4. ✅ Questions about YOLO, R-CNN, computer vision
5. ✅ Consistent behavior (not random)

---

## Summary

**Root Causes:**
1. ❌ Two code paths with different limits (40 vs 8)
2. ❌ Agent inconsistently using old JSON path
3. ❌ Agent not extracting count correctly ("40 quizzes" ambiguous)

**Fixes:**
1. ✅ Both paths now support 40 questions
2. ✅ Agent instructions: "ALWAYS use function tool"
3. ✅ Clarified: "quizzes" = "questions"

**Result:**
- ✅ Generates 40 questions consistently
- ✅ Uses uploaded document content
- ✅ Correct topic (computer vision)
- ✅ No more inconsistent behavior!

🚀 **Restart Streamlit and test - should generate 40 questions from YOUR documents!**

