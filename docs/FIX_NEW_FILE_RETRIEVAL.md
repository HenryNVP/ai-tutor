# ✅ Fix: Newly Uploaded File Not Being Retrieved

## The Issue

User uploaded: **"cmpe249 midterm review.pdf"** (31 chunks ingested)

When creating quiz, retrieval returned:
- ❌ collegephysicsvol2.pdf (old file)
- ❌ cmpe249 lecture9 (old file)
- ❌ principles-of-data-science (old file)
- ❌ **NEW file not found!**

Result:
- Quiz generated with topic "uploaded documents" (wrong!)
- No content from the new file
- Agent stuck/slow

---

## Root Causes

### Problem 1: Weak Retrieval Query
The filename "cmpe249 midterm review" doesn't match the content well:
- Query: "cmpe249 midterm review"
- Content: Might be about specific CS topics
- Result: OLD documents with better semantic match returned

### Problem 2: Agent Using Wrong Topic
Agent called: `generate_quiz(topic='uploaded_documents', ...)`
- This is NOT a searchable topic!
- We explicitly said NOT to use this
- But agent ignored instructions

### Problem 3: Insufficient Retrieval Attempts
Only tried 2 queries:
1. Filename-based
2. User's query

Not enough for newly uploaded content!

---

## The Fixes

### Fix 1: More Aggressive Retrieval (`apps/ui.py` lines 857-879)

**Added multiple retrieval strategies:**

```python
# 1. Retrieve using filenames (with spaces)
query_text = Path(filename).stem.replace('_', ' ').replace('-', ' ')
file_hits = system.tutor_agent.retriever.retrieve(Query(text=query_text))

# 2. Also try full filename without modification
full_name_query = Path(filename).stem
more_hits = system.tutor_agent.retriever.retrieve(Query(text=full_name_query))

# 3. For newly uploaded files, try broad subject queries
if st.session_state.get('chat_files_just_ingested', False):
    broad_queries = ["computer science", "engineering", "mathematics", "lecture", "course material"]
    for broad_query in broad_queries:
        broad_hits = system.tutor_agent.retriever.retrieve(Query(text=broad_query))
        all_hits.extend(broad_hits[:5])
```

**Why this works:**
- ✅ Tries filename with AND without space replacement
- ✅ Adds broad subject queries for newly uploaded files
- ✅ Casts a wider net to catch new content
- ✅ More hits = better chance of finding new file

### Fix 2: Stronger Agent Instructions (`tutor.py` lines 337-342)

**Made it CRYSTAL CLEAR:**

```python
"- When user says 'from document/files/PDFs/uploaded':\n"
"  * Use BROAD, SEARCHABLE topic: 'computer science', 'machine learning', 'engineering', 'mathematics', 'physics', 'biology'\n"
"  * Check learner profile for recently studied topics\n"
"  * CRITICAL: NEVER use 'uploaded_documents', 'uploaded', 'document', or 'file' as topic!\n"
"  * These are NOT searchable topics - use actual subject names!\n"
"  * System automatically includes document content via extra_context\n"
```

**Key changes:**
- ✅ "CRITICAL: NEVER use..."
- ✅ "These are NOT searchable topics"
- ✅ Listed ALL forbidden topic names
- ✅ Explained WHY (not searchable)

---

## How It Works Now

```
User uploads: "cmpe249 midterm review.pdf"
  ↓
31 chunks ingested ✅
  ↓
User: "create 20 comprehensive quizzes from the uploaded document"
  ↓
UI Retrieval (AGGRESSIVE):
  1. Query: "cmpe249 midterm review" (with spaces)
  2. Query: "cmpe249midtermreview" (without)
  3. Query: "create 20 comprehensive quizzes..." (user's request)
  4. Query: "computer science" (broad)
  5. Query: "engineering" (broad)
  6. Query: "mathematics" (broad)
  7. Query: "lecture" (broad)
  8. Query: "course material" (broad)
  ↓
Collect ALL hits, deduplicate, filter to uploaded file
  ↓
✅ HIGH chance of finding "cmpe249 midterm review.pdf"!
  ↓
Agent: Reads instructions - "NEVER use 'uploaded_documents'"
       Uses: topic='computer science' (searchable!)
  ↓
Quiz Service: Has extra_context from YOUR new file
              Prioritizes it over retrieval
  ↓
✅ Quiz generated from YOUR new file!
```

---

## What Changed

### Before (Weak Retrieval):
```
Queries:
1. "cmpe249 midterm review" (weak match)
2. "create 20 quizzes..." (doesn't match content)

Result: Old docs returned, new file not found ❌
```

### After (Aggressive Retrieval):
```
Queries:
1. "cmpe249 midterm review" (spaces)
2. "cmpe249midtermreview" (no spaces)
3. "create 20 quizzes..."
4. "computer science" (broad)
5. "engineering" (broad)
6. "mathematics" (broad)
7. "lecture" (broad)
8. "course material" (broad)

Result: Many hits, new file likely found ✅
```

---

## Files Changed

**1. apps/ui.py (lines 857-879)**
- Added double filename query (with/without space replacement)
- Added broad subject queries for newly uploaded files
- Retrieves from 8+ queries instead of 2
- ✅ No linter errors

**2. src/ai_tutor/agents/tutor.py (lines 337-342)**
- Made "NEVER use uploaded_documents" more explicit
- Listed ALL forbidden topic names
- Explained WHY they're forbidden
- ✅ No linter errors

---

## Testing

**Restart Streamlit:**
```bash
pkill -f streamlit
streamlit run apps/ui.py
```

**Test steps:**
1. Upload a new file (e.g., "cmpe249 midterm review.pdf")
2. Immediately request: "create 20 quizzes from the uploaded document"
3. Check the debug output

**Expected:**
- ✅ See your file in "🔍 Debug: Filename Matching" with "✅ MATCH"
- ✅ NOT "0/1 uploaded files found"
- ✅ Quiz generated with proper topic (NOT "uploaded documents")
- ✅ Questions from YOUR new file
- ✅ NO stuck/slow behavior

---

## Why It Was Failing

### Timing Issue:
Newly uploaded files have fresh embeddings that might not rank as high in semantic search against generic queries.

### Solution:
Cast a wider net with multiple query strategies, especially broad subject queries that are more likely to match educational content.

### Agent Issue:
Agent was using "uploaded documents" as topic despite instructions.

### Solution:
Made instructions IMPOSSIBLE to misunderstand:
- "CRITICAL: NEVER use..."
- Listed exact strings to avoid
- Explained they're not searchable

---

## All Fixes Summary

1. ✅ Agent-first architecture
2. ✅ Quiz tool limit: 40 questions (both paths)
3. ✅ Document retrieval in UI
4. ✅ Quiz service prioritizes uploaded docs
5. ✅ Topic extraction improved
6. ✅ Count extraction ("quizzes" = "questions")
7. ✅ Agent never refuses
8. ✅ Aggressive retrieval for new files ⭐ THIS FIX
9. ✅ Stronger topic restrictions ⭐ THIS FIX

---

## Summary

**Issue:** Newly uploaded file not found in retrieval

**Root Causes:**
1. Weak retrieval - only 2 queries, not enough
2. Agent using "uploaded documents" as topic

**Solutions:**
1. 8+ retrieval queries including broad subjects
2. Explicit "NEVER use" instructions for topic

**Result:** New files should be found and used! ✅

🚀 **Restart Streamlit and test with a fresh file upload!**

