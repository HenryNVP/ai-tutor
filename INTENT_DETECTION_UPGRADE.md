# Upgrading from Keyword Matching to LLM Intent Detection

## Current Approach (Rule-Based)

```python
# apps/ui.py - OLD WAY
def detect_quiz_request(message: str) -> bool:
    """Brittle keyword matching"""
    message_lower = message.lower()
    patterns = [
        r"\b(create|generate|make)\s+.*?\bquiz",
        r"\bquiz\s+me\b",
        # ... many patterns
    ]
    for pattern in patterns:
        if re.search(pattern, message_lower):
            return True
    return False

# Then manually extract parameters
if "10" in prompt:
    num_questions = 10
```

### Problems:
- ❌ Breaks on variations ("gimme questions", "i need practice")
- ❌ Manual parameter extraction
- ❌ Hard to maintain (add patterns constantly)
- ❌ Doesn't understand context
- ❌ Can't handle typos or informal language

---

## New Approach (LLM-Based)

```python
# apps/ui.py - NEW WAY
from ai_tutor.agents.intent_detector import TutorIntentDetector

# Initialize once
detector = TutorIntentDetector()

# Detect intent
intent = detector.detect_intent(
    user_message=prompt,
    has_uploaded_docs=len(st.session_state.uploaded_file_names) > 0,
    uploaded_doc_info=", ".join(st.session_state.uploaded_file_names[:3])
)

# Act on intent
if intent['action'] == 'generate_quiz':
    params = intent['params']
    # All parameters already extracted!
    topic = params['topic']
    num_questions = params.get('num_questions', 4)
    from_docs = params.get('from_uploaded_documents', False)
    
    # Generate quiz
    quiz_data = generate_quiz(topic, num_questions, from_docs)
```

### Benefits:
- ✅ Understands natural language ("gimme some practice questions")
- ✅ Automatic parameter extraction (count, topic, source)
- ✅ Handles typos and variations
- ✅ Context-aware (knows about uploaded docs)
- ✅ Easy to extend (just modify tool descriptions)
- ✅ Self-documenting (tool descriptions explain intent)

---

## Integration Steps

### Step 1: Install the Intent Detector

The file `src/ai_tutor/agents/intent_detector.py` is already created!

### Step 2: Update `apps/ui.py`

Replace the quiz detection logic:

```python
# At top of file
from ai_tutor.agents.intent_detector import TutorIntentDetector

# In TutorApp.__init__
def __init__(self):
    # ... existing code ...
    
    # Add intent detector
    if 'intent_detector' not in st.session_state:
        try:
            st.session_state.intent_detector = TutorIntentDetector()
        except Exception as e:
            st.warning(f"Intent detector not available: {e}")
            st.session_state.intent_detector = None

# In render() method, replace quiz detection
def render(self):
    # ... existing code ...
    
    if prompt:
        # NEW WAY - LLM understands intent
        if st.session_state.get('intent_detector'):
            # Get uploaded doc info
            doc_info = None
            if st.session_state.uploaded_file_names:
                doc_info = ", ".join(st.session_state.uploaded_file_names[:3])
            
            # Detect intent
            intent = st.session_state.intent_detector.detect_intent(
                user_message=prompt,
                has_uploaded_docs=len(st.session_state.uploaded_file_names) > 0,
                uploaded_doc_info=doc_info
            )
            
            # Handle based on intent
            if intent['action'] == 'generate_quiz':
                params = intent['params']
                self._handle_quiz_request(
                    topic=params.get('topic', 'general'),
                    num_questions=params.get('num_questions', 4),
                    from_docs=params.get('from_uploaded_documents', False)
                )
            else:
                # Regular Q&A
                self._handle_question(
                    question=params.get('question', prompt),
                    search_docs=params.get('search_uploaded_documents', False)
                )
        else:
            # FALLBACK - use old keyword matching if detector unavailable
            if detect_quiz_request(prompt):
                # ... old logic ...
```

### Step 3: Test

```bash
# Set your OpenAI API key (if not already set)
export OPENAI_API_KEY="your-key-here"

# Run the intent detector test
python src/ai_tutor/agents/intent_detector.py

# Then test in your UI
streamlit run apps/ui.py
```

---

## Test Cases

The new detector handles all these naturally:

| User Input | Detected Action | Parameters |
|------------|----------------|------------|
| "Create 10 quizzes from the documents" | `generate_quiz` | topic: uploaded_documents, num: 10, from_docs: True |
| "gimme some practice questions on CNN" | `generate_quiz` | topic: CNN, num: 4 (default) |
| "Test me on what I uploaded" | `generate_quiz` | topic: uploaded_documents, from_docs: True |
| "I need to practice" | `generate_quiz` | topic: uploaded_documents (if docs present) |
| "What is YOLO?" | `answer_question` | question: What is YOLO?, search_docs: False |
| "What does my PDF say about YOLO?" | `answer_question` | question: ..., search_docs: True |
| "make me 5 mcq on neural nets" | `generate_quiz` | topic: neural nets, num: 5 |

---

## Cost Considerations

**Per intent detection call:**
- Model: `gpt-4o-mini`
- Input: ~200 tokens (system + user message + tool definitions)
- Output: ~50 tokens (function call)
- Cost: **$0.0001 per request** (basically free)

For 1000 quiz requests: **$0.10**

This is negligible compared to the actual quiz generation cost!

---

## Migration Strategy

### Option 1: Gradual (Recommended)

Keep both systems running:

```python
# Try LLM detection first
if st.session_state.get('intent_detector'):
    intent = detector.detect_intent(...)
    if intent['confidence'] == 'high':
        # Use LLM result
    else:
        # Fallback to keyword matching
else:
    # Use keyword matching
```

### Option 2: Full Switch

Replace all keyword matching immediately.

---

## Extending the System

Want to add new capabilities? Just add a new tool:

```python
# In intent_detector.py TOOLS list
{
    "type": "function",
    "function": {
        "name": "create_study_plan",
        "description": "Create a personalized study plan for the student",
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "duration_weeks": {"type": "integer"},
                "goals": {"type": "array", "items": {"type": "string"}}
            }
        }
    }
}
```

The LLM will automatically know when to call it!

---

## Summary

**Before:**
```python
if "create quiz" in message or "generate quiz" in message:
    # Manual parsing
    if "10" in message:
        num = 10
```

**After:**
```python
intent = detector.detect_intent(message)
# Everything parsed: topic, count, source, etc.
```

**Result:** More robust, maintainable, and user-friendly! 🚀

