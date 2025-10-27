# ✅ Fix: Agent Extracting Wrong Question Count

## The Issues

### Issue 1: Agent Answering Instead of Calling Tool
**User:** "Create 20 quizzes from the uploaded documents"

**Agent Response:**
```
Based on the provided context, here are 20 quiz questions:

What is one of the main advantages of R-CNN?
What is a significant disadvantage of R-CNN regarding training time?
...
```

**Problem:** Agent generated quiz questions as TEXT instead of calling `generate_quiz` tool ❌

### Issue 2: Agent Extracting Wrong Count  
**User:** "create 20 quizzes from the documents"

**Agent Response:**
```
I've prepared a 10-question quiz based on your documents about CMPE249.
```

**Problem:** Agent called the tool ✅ but used `count=10` instead of `count=20` ❌

---

## Root Causes

### Issue 1: LLM Answering Directly
**Why:** LLMs are trained to be helpful and answer questions. When asked to "create quizzes", the LLM's instinct is to generate quiz questions in the response, not call a tool.

**This is a classic agent design problem:** The LLM doesn't naturally understand that calling a tool is BETTER than answering directly.

### Issue 2: Count Extraction Failure
**Why:** The function tool docstring said:
```python
count : int, default=4
    Number of questions to generate. Clamped to range [3, 8].
```

**Problems:**
1. Says "Clamped to range [3, 8]" (outdated - should be [3, 40])
2. Doesn't emphasize using the user's exact number
3. No example showing "create 20" → count=20
4. Default value (4) might be biasing the LLM

---

## The Solutions

### Fix 1: Stronger Tool Call Enforcement

**Added explicit forbidden/required rules:**

```python
"Quiz Request → ⚠️ MANDATORY: USE generate_quiz TOOL - NEVER ANSWER WITH TEXT! ⚠️\n"
"- ❌ FORBIDDEN: Generating quiz questions in your response text\n"
"- ❌ FORBIDDEN: Listing questions like 'Here are 20 quiz questions:'\n"
"- ✅ REQUIRED: Call generate_quiz(topic, count) tool\n"
"- ✅ REQUIRED: Let the tool handle quiz generation\n"
```

**Added wrong/correct examples:**

```python
"Examples:\n"
"  'Create 20 comprehensive quizzes from the uploaded document'\n"
"    → ❌ WRONG: 'Here are 20 quiz questions: 1. What is...'\n"
"    → ✅ CORRECT: generate_quiz(topic='computer science', count=20)\n"
```

**Updated critical rules:**

```python
"CRITICAL RULES:\n"
"- For QUIZ requests:\n"
"  ❌ DO NOT generate quiz questions in your response text\n"
"  ❌ DO NOT write 'Here are 20 quiz questions:' followed by questions\n"
"  ❌ DO NOT create a text-based quiz in your answer\n"
"  ✅ ALWAYS CALL the generate_quiz(topic, count) tool instead\n"
"  ✅ Let the tool create the interactive quiz interface\n"
```

**Key Changes:**
- ✅ Used emojis (⚠️, ❌, ✅) for visual emphasis
- ✅ Explicitly showed WRONG examples (what NOT to do)
- ✅ Explicitly showed CORRECT examples (what TO do)
- ✅ Used "MANDATORY", "FORBIDDEN", "REQUIRED" (strong language)
- ✅ Repeated the instruction multiple times

### Fix 2: Improved Count Extraction

**Enhanced count extraction instructions:**

```python
"- COUNT EXTRACTION (CRITICAL!):\n"
"  * 'create 20 quizzes' → count=20 (use EXACT number user says!)\n"
"  * 'create 10 quizzes' → count=10\n"
"  * 'create 5 questions' → count=5\n"
"  * 'quiz me' (no number) → count=4 (default)\n"
"  * Note: 'quizzes' = 'quiz questions', so '20 quizzes' means count=20\n"
"  * DO NOT use count=10 as default when user specifies a number!\n"
```

**Updated function docstring:**

```python
def generate_quiz(topic: str, count: int = 4, difficulty: str | None = None) -> str:
    """
    Generate an interactive quiz on a given topic.
    
    Parameters
    ----------
    count : int, default=4
        Number of questions to generate. Valid range: 3 to 40.
        IMPORTANT: If user says "create 20 quizzes", use count=20 (their exact number).
        Only use default (4) if user doesn't specify a number.
    
    Examples
    --------
    User says: "create 20 quizzes from documents"
    → Call: generate_quiz(topic='computer science', count=20)
    
    User says: "quiz me on calculus"  
    → Call: generate_quiz(topic='calculus', count=4)
    """
```

**Key Changes:**
- ✅ Changed "Clamped to range [3, 8]" → "Valid range: 3 to 40"
- ✅ Added "IMPORTANT" emphasis about using user's exact number
- ✅ Added specific examples in docstring
- ✅ Clarified when to use default vs user's number
- ✅ Multiple extraction examples with different numbers

---

## How It Works Now

### User Input Processing:

```
User: "create 20 quizzes from the documents"
  ↓
Orchestrator Agent Reads Instructions:
  • "⚠️ MANDATORY: USE generate_quiz TOOL"
  • "❌ FORBIDDEN: Generating quiz questions in your response text"
  • "COUNT EXTRACTION (CRITICAL!): 'create 20 quizzes' → count=20"
  ↓
Orchestrator Agent Reads Function Docstring:
  • "IMPORTANT: If user says 'create 20 quizzes', use count=20"
  • Example: "create 20 quizzes" → generate_quiz(..., count=20)
  ↓
Agent Decision:
  • Recognizes quiz request
  • Extracts count=20 (user's exact number)
  • Extracts topic='computer science' (from uploaded docs context)
  ↓
Tool Call:
  ✅ generate_quiz(topic='computer science', count=20)
  ❌ NOT: Generating questions in text
  ❌ NOT: Using count=4 or count=10
  ↓
Tool Execution:
  • Calculates max_tokens = (20 * 150) + 500 = 3500
  • Calls LLM with proper context
  • Generates 20 questions
  • Returns confirmation message
  ↓
UI Display:
  ✅ Interactive quiz with 20 questions!
```

---

## Files Changed

**src/ai_tutor/agents/tutor.py**

**1. Orchestrator Instructions (lines 330-370)**
- Added "⚠️ MANDATORY" and forbidden/required rules
- Added wrong/correct examples
- Enhanced count extraction with multiple examples
- Added "CRITICAL" emphasis
- ✅ No linter errors

**2. Function Tool Docstring (lines 251-282)**
- Updated range from [3, 8] to [3, 40]
- Added "IMPORTANT" note about using user's exact number
- Added specific examples in docstring
- Clarified default vs user-specified behavior
- ✅ No linter errors

---

## Why This Was Hard

### Challenge 1: LLM Helpfulness
LLMs are trained to be helpful and answer questions. When you ask "create 20 quizzes", the LLM thinks:
- "I can generate quiz questions!"
- "I'll be helpful and create them right now!"
- "The user wants questions, so I'll list them!"

But we want:
- "I should call the tool!"
- "The tool creates better interactive quizzes!"
- "My job is routing, not answering!"

**This goes against the LLM's training!**

### Challenge 2: Parameter Extraction
Function calling LLMs often struggle with parameter extraction when:
- There's a default value (biases toward default)
- The docstring is unclear about when to use default
- No explicit examples showing the exact user phrasing

**Solution:** Be EXTREMELY explicit with multiple examples!

### Challenge 3: Instruction Following
LLMs don't always follow instructions perfectly, especially when:
- Instructions are subtle ("prefer to call tool")
- No explicit wrong examples shown
- Instruction competes with training (being helpful)

**Solution:** Make instructions IMPOSSIBLE to ignore:
- Use strong language ("MANDATORY", "FORBIDDEN")
- Show explicit WRONG examples
- Repeat the instruction multiple times
- Use visual cues (⚠️, ❌, ✅)

---

## Testing

**Restart Streamlit:**
```bash
pkill -f streamlit
streamlit run apps/ui.py
```

**Test Cases:**

**1. Basic quiz request with count:**
```
User: "create 20 quizzes from the documents"
Expected: 
  ✅ Calls generate_quiz tool (not text answer)
  ✅ Uses count=20 (user's number, not default)
  ✅ Interactive quiz with 20 questions
```

**2. Quiz request without count:**
```
User: "quiz me on physics"
Expected:
  ✅ Calls generate_quiz tool
  ✅ Uses count=4 (default, since no number specified)
  ✅ Interactive quiz with 4 questions
```

**3. Different count values:**
```
User: "create 5 quizzes on calculus"
Expected: count=5

User: "create 10 questions about biology"  
Expected: count=10

User: "create 40 quizzes from documents"
Expected: count=40 (maximum)
```

**4. Without number:**
```
User: "test me"
Expected: count=4 (default)
```

---

## Related Patterns

This fix demonstrates important agent design patterns:

### Pattern 1: Strong Instruction Language
```
❌ Weak:   "Prefer to call the tool"
✅ Strong: "⚠️ MANDATORY: CALL THE TOOL - DO NOT ANSWER WITH TEXT"
```

### Pattern 2: Explicit Wrong Examples
```
❌ Without: "Call generate_quiz for quiz requests"
✅ With:    "❌ WRONG: 'Here are 20 questions: ...'"
           "✅ CORRECT: generate_quiz(count=20)"
```

### Pattern 3: Multiple Extraction Examples
```
❌ One:    "'create quizzes' → use generate_quiz"
✅ Many:   "'create 20 quizzes' → count=20"
           "'create 10 quizzes' → count=10"
           "'create 5 questions' → count=5"
           "'quiz me' → count=4 (default)"
```

### Pattern 4: Docstring as Instruction
```
Function docstrings are read by the LLM during tool calling!
Add examples and emphasis in the docstring itself.
```

---

## Lessons Learned

1. **LLMs need EXPLICIT instructions** - subtle hints don't work
2. **Show wrong examples** - tell the LLM what NOT to do
3. **Repeat important instructions** - say it multiple times
4. **Use visual emphasis** - emojis, caps, formatting help
5. **Docstrings matter** - the LLM reads them during tool calling
6. **Default values can bias** - clarify when to override defaults
7. **Test with exact user phrasing** - use real examples

---

## Summary

**Issue 1:** Agent generating quiz questions as text instead of calling tool

**Solution:** Explicit forbidden/required rules with wrong/correct examples

**Issue 2:** Agent using count=10 instead of count=20

**Solution:** Enhanced count extraction instructions + improved docstring

**Result:** 
- ✅ Agent calls tool (not text answer)
- ✅ Agent uses user's exact count (not default)
- ✅ Interactive quiz with correct number of questions

---

## All Fixes Complete

1. ✅ Agent-first architecture
2. ✅ Quiz tool limit: 40 questions
3. ✅ Document retrieval in UI
4. ✅ Quiz service prioritizes docs
5. ✅ Topic extraction improved
6. ✅ Count extraction fixed (part of this)
7. ✅ Agent never refuses
8. ✅ Aggressive retrieval
9. ✅ Stronger topic restrictions
10. ✅ Source filtering
11. ✅ Dynamic max_tokens
12. ✅ **Tool call enforcement** ⭐ THIS FIX
13. ✅ **Count extraction** ⭐ THIS FIX

🚀 **Restart and test: "create 20 quizzes from the documents"**

Should now:
- ✅ Call the tool (not answer with text)
- ✅ Use count=20 (your exact number)
- ✅ Generate all 20 questions
- ✅ Display interactive quiz

