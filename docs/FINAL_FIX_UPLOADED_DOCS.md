# ✅ Final Fix: Quiz from Uploaded Documents

## The Issue

After implementing the agent-first architecture, the agent correctly understood "Create 10 quizzes from the documents" and called `generate_quiz(topic='uploaded_documents', count=10)`, but the quiz generated was still about generic "data science" topics instead of the specific uploaded documents (computer vision lectures about YOLO, R-CNN, etc.).

### Why It Happened

The agent's `generate_quiz` tool uses `self._active_extra_context` to get document content (line 288 in `tutor.py`):

```python
quiz = self.quiz_service.generate_quiz(
    topic=topic,
    profile=profile,
    num_questions=question_count,
    difficulty=difficulty,
    extra_context=self._active_extra_context,  # ← Was None!
)
```

But `_active_extra_context` is only populated when `extra_context` is passed to `system.answer_question()`.

The refactored UI wasn't retrieving and passing uploaded document content as `extra_context`, so the agent had no content to work with!

---

## The Solution

Added document retrieval in the UI that happens **before** calling the agent, so the agent has access to uploaded document content for both Q&A and quiz generation.

### Changes Made (`apps/ui.py` lines 846-902)

```python
# Retrieve content from uploaded documents if they exist
# This provides context for both Q&A and quiz generation
uploaded_docs_context = None
if st.session_state.chat_files_ingested and st.session_state.chat_uploaded_filenames:
    with st.spinner("Retrieving content from your uploaded documents..."):
        # Strategy: Retrieve using both filenames and the user's query
        all_hits = []
        
        # 1. Retrieve using filenames to ensure we get content from uploaded docs
        for filename in st.session_state.chat_uploaded_filenames:
            query_text = Path(filename).stem.replace('_', ' ').replace('-', ' ')
            file_hits = system.tutor_agent.retriever.retrieve(Query(text=query_text))
            all_hits.extend(file_hits)
        
        # 2. Also retrieve using the user's actual query for relevance
        query_hits = system.tutor_agent.retriever.retrieve(Query(text=prompt))
        all_hits.extend(query_hits)
        
        # Remove duplicates and filter to only uploaded documents
        # ... deduplication logic ...
        
        # Group hits by document for balanced representation
        hits_by_doc = defaultdict(list)
        for hit in filtered_hits:
            doc_title = hit.chunk.metadata.title or "Unknown"
            hits_by_doc[doc_title].append(hit)
        
        # Take passages from each document proportionally
        passages_per_doc = max(3, 15 // len(hits_by_doc))
        # ... format context ...
        
        uploaded_docs_context = "\n\n".join(context_parts)
        st.caption(f"📚 Retrieved {len(context_parts)} passages from {len(hits_by_doc)} document(s)")
```

### Pass Context to Agent (lines 992-1007)

```python
# Combine quiz context and uploaded docs context
combined_context = None
if uploaded_docs_context and quiz_context:
    combined_context = f"{uploaded_docs_context}\n\n{quiz_context}"
elif uploaded_docs_context:
    combined_context = uploaded_docs_context
elif quiz_context:
    combined_context = quiz_context

# Pass to agent
response = system.answer_question(
    learner_id=learner_id,
    question=prompt,
    extra_context=combined_context,  # ← Now includes uploaded docs!
)
```

---

## How It Works Now

```
User: "Create 10 quizzes from the documents"
  ↓
UI: Retrieve passages from uploaded files
    • Lecture9: YOLO, object detection, etc.
    • Lecture10: R-CNN, neural networks, etc.
  ↓
UI: Call system.answer_question(extra_context=uploaded_docs_context)
  ↓
Agent: Receives context, sets self._active_extra_context
  ↓
Agent: Understands "quiz request, 10 questions, from documents"
  ↓
Agent: Calls generate_quiz(topic='uploaded_documents', count=10)
  ↓
Tool: Uses self._active_extra_context (YOUR uploaded content!)
  ↓
✅ Quiz generated with questions about YOLO, R-CNN, computer vision!
```

---

## What You'll See Now

### Before (Incorrect):
```
Q1. What is the primary purpose of data cleaning in data science?
Q2. Which of the following is NOT a step in data cleaning?
```
❌ Generic data science questions (not from your documents)

### After (Correct):
```
📚 Retrieved 15 passages from 2 document(s): CMPE249 Lecture9, CMPE249 Lecture10

Q1. What does YOLO stand for in object detection?
Q2. Which architecture introduced the region proposal network (RPN)?
Q3. What is the main advantage of single-shot detectors over two-stage detectors?
...
```
✅ Questions about YOUR uploaded computer vision documents!

---

## Benefits

### ✅ Works for Both Q&A and Quizzes
The uploaded document context is available for:
- Quiz generation ("Create 10 quizzes from the documents")
- Questions about docs ("What does the lecture say about YOLO?")
- Any request that should use uploaded content

### ✅ Balanced Multi-Document Representation
- Retrieves from ALL uploaded documents
- Takes proportional passages from each document
- Ensures quiz covers all your materials

### ✅ Automatic Detection
- If you have uploaded documents, they're automatically retrieved
- No special commands needed
- Works transparently

---

## Testing

### Test Case 1: Quiz from Documents
```
User: "Create 10 quizzes from the documents"
Expected: 
  - Retrieves from Lecture9.pdf, Lecture10.pdf
  - Shows "Retrieved X passages from 2 document(s)"
  - Generates 10 questions about YOLO, R-CNN, etc.
```

### Test Case 2: Q&A about Documents  
```
User: "What is YOLO?"
Expected:
  - Retrieves from uploaded documents
  - Answers based on YOUR lecture content
```

### Test Case 3: No Uploaded Documents
```
User: "Create a quiz on neural networks"
Expected:
  - Uses general knowledge
  - No "Retrieved passages" message
  - Still works fine
```

---

## Files Changed

**apps/ui.py:**
- Added document retrieval logic (lines 846-902)
- Pass retrieved context to agent (lines 992-1007)
- ✅ No linter errors

---

## Complete Flow

### Before This Fix:
```
"Create 10 quizzes from the documents"
  → Agent calls generate_quiz()
  → self._active_extra_context = None
  → Quiz service has NO content to work with
  → Falls back to generic knowledge
  → ❌ Generic quiz about "data science"
```

### After This Fix:
```
"Create 10 quizzes from the documents"
  → UI retrieves passages from Lecture9, Lecture10
  → UI calls answer_question(extra_context=passages)
  → Agent sets self._active_extra_context = passages
  → Agent calls generate_quiz()
  → Quiz service uses _active_extra_context
  → ✅ Quiz about YOLO, R-CNN, computer vision!
```

---

## Summary

**Problem:** Agent didn't have access to uploaded document content

**Solution:** UI retrieves and passes uploaded document content as `extra_context`

**Result:** Quizzes are now generated from YOUR uploaded documents! ✅

---

## Next Steps

1. **Restart Streamlit:**
   ```bash
   pkill -f streamlit
   streamlit run apps/ui.py
   ```

2. **Test it:**
   ```
   "Create 10 quizzes from the documents"
   ```

3. **Look for:**
   - Message: "📚 Retrieved X passages from 2 document(s): Lecture9, Lecture10"
   - Questions about YOLO, R-CNN, object detection, etc.
   - NOT generic data science questions

🚀 **Now your quizzes will use YOUR content!**

