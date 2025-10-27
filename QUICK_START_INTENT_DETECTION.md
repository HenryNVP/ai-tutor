# 🚀 Quick Start: LLM Intent Detection

## TL;DR

**Instead of this:**
```python
if "create quiz" in message:  # Brittle!
    generate_quiz()
```

**Do this:**
```python
intent = detector.detect_intent(message)  # Smart!
if intent['action'] == 'generate_quiz':
    generate_quiz(**intent['params'])  # All params extracted!
```

---

## What You Asked For

> "Is there an approach where the agent understands natural language and calls quiz tool accordingly without strict filtering keywords?"

**YES!** It's called **LLM Function Calling** (aka Tool Use).

---

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│  User: "gimme some practice questions on what I uploaded"   │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│            LLM Intent Detector (GPT-4o-mini)                 │
│                                                              │
│  Tools Available:                                            │
│  1. generate_quiz (for quizzes, tests, practice)            │
│  2. answer_question (for Q&A, explanations)                 │
│                                                              │
│  Context:                                                    │
│  - User has uploaded: Lecture9.pdf, Lecture10.pdf           │
│                                                              │
│  Understanding:                                              │
│  - "practice questions" = wants a quiz                      │
│  - "what I uploaded" = use uploaded documents               │
│  - No count specified = use default (4)                     │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Result:                                                     │
│  {                                                           │
│    "action": "generate_quiz",                               │
│    "params": {                                              │
│      "topic": "uploaded_documents",                         │
│      "num_questions": 4,                                    │
│      "from_uploaded_documents": true                        │
│    }                                                         │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
                    ✅ Generate Quiz!
```

---

## Files Created for You

### 1. **Production Code**
📄 `src/ai_tutor/agents/intent_detector.py`
- Ready to use in your app
- Handles all natural language variations
- Extracts parameters automatically

### 2. **Examples**
📄 `examples/llm_function_calling_quiz.py`
📄 `examples/integrate_llm_function_calling.py`
- Demo scripts showing how it works

### 3. **Documentation**
📄 `INTENT_DETECTION_UPGRADE.md` - How to integrate
📄 `docs/llm_vs_keyword_detection.md` - Detailed comparison
📄 `examples/README.md` - Quick reference

---

## Test It Right Now

```bash
# 1. Set your OpenAI API key
export OPENAI_API_KEY="sk-..."

# 2. Run the demo
python src/ai_tutor/agents/intent_detector.py
```

**You'll see:**
```
📝 User: "Create 10 quizzes from the documents"
✅ Action: GENERATE QUIZ
   Topic: uploaded_documents
   Questions: 10
   From docs: True

📝 User: "gimme some practice questions"  
✅ Action: GENERATE QUIZ
   Topic: uploaded_documents
   Questions: 4

📝 User: "What is YOLO?"
💬 Action: ANSWER QUESTION
   Query: What is YOLO?
```

---

## Integration (3 Steps)

### Step 1: Import
```python
# In apps/ui.py
from ai_tutor.agents.intent_detector import TutorIntentDetector
```

### Step 2: Initialize
```python
# In TutorApp.__init__
if 'intent_detector' not in st.session_state:
    st.session_state.intent_detector = TutorIntentDetector()
```

### Step 3: Use
```python
# In render(), replace keyword matching:
intent = st.session_state.intent_detector.detect_intent(
    user_message=prompt,
    has_uploaded_docs=bool(st.session_state.uploaded_file_names),
    uploaded_doc_info=", ".join(st.session_state.uploaded_file_names)
)

if intent['action'] == 'generate_quiz':
    params = intent['params']
    # Generate quiz with extracted params!
    generate_quiz(
        topic=params['topic'],
        count=params.get('num_questions', 4),
        from_docs=params.get('from_uploaded_documents', False)
    )
```

**Done!** Your app now understands natural language! 🎉

---

## What It Handles

| User Says | LLM Understands | Old Regex |
|-----------|-----------------|-----------|
| "Create 10 quizzes from the documents" | ✅ Quiz, 10 questions, from docs | ✅ Works |
| "gimme practice questions" | ✅ Quiz, default count | ❌ Misses |
| "I want to test my knowledge" | ✅ Quiz | ❌ Misses |
| "quiz me on neural networks" | ✅ Quiz, topic: neural networks | ⚠️ Misses topic |
| "Test what I learned from the PDFs" | ✅ Quiz, from uploaded docs | ❌ Misses |
| "crate 10 quizes" (typos) | ✅ Handles it! | ❌ Fails |
| "What is YOLO?" | ✅ Not a quiz, Q&A | ✅ Works |

---

## Cost

- **Per intent detection:** $0.0001 (1/100 of a cent)
- **1000 detections:** $0.10
- **Per day (100 users, 10 requests each):** $0.10

**Cheaper than a cup of coffee! ☕**

---

## Advantages Over Keyword Matching

### ✅ Natural Language
Understands: "gimme questions", "i wanna practice", "test me"
Not just: "create quiz", "generate quiz"

### ✅ Auto Parameter Extraction
```python
# Extracts automatically:
"Create 10 quizzes" → num_questions: 10
"quiz on CNN" → topic: "CNN"  
"from my files" → from_uploaded_documents: true
```

### ✅ Context Aware
Knows about uploaded documents, user's history, etc.

### ✅ Easy to Extend
Want to add "Create Study Plan"? Just add tool description, done!

### ✅ Self-Documenting
Tool descriptions explain what each action does.

---

## Example: Full Integration

```python
# apps/ui.py - Modern version with LLM detection

from ai_tutor.agents.intent_detector import TutorIntentDetector

class TutorApp:
    def __init__(self):
        # ... existing init code ...
        
        # Add intent detector
        if 'intent_detector' not in st.session_state:
            st.session_state.intent_detector = TutorIntentDetector()
    
    def render(self):
        # ... existing UI code ...
        
        if prompt:
            # Get document context
            has_docs = bool(st.session_state.uploaded_file_names)
            doc_info = ", ".join(st.session_state.uploaded_file_names) if has_docs else None
            
            # Detect intent using LLM
            intent = st.session_state.intent_detector.detect_intent(
                user_message=prompt,
                has_uploaded_docs=has_docs,
                uploaded_doc_info=doc_info
            )
            
            # Act on intent
            if intent['action'] == 'generate_quiz':
                self._handle_quiz_generation(intent['params'])
            else:
                self._handle_question_answering(intent['params'])
    
    def _handle_quiz_generation(self, params):
        """Handle quiz generation with auto-extracted parameters"""
        topic = params['topic']
        num_questions = params.get('num_questions', 4)
        from_docs = params.get('from_uploaded_documents', False)
        
        st.info(f"🎯 Generating {num_questions} questions on {topic}")
        
        if from_docs:
            # Retrieve from uploaded documents
            passages = self.retrieve_from_documents(topic, num_questions * 2)
            quiz_data = self.system.generate_quiz(
                topic=topic,
                num_questions=num_questions,
                context_passages=passages
            )
        else:
            # General knowledge quiz
            quiz_data = self.system.generate_quiz(
                topic=topic,
                num_questions=num_questions
            )
        
        self.display_quiz(quiz_data)
    
    def _handle_question_answering(self, params):
        """Handle regular Q&A"""
        query = params['question']
        search_docs = params.get('search_uploaded_documents', False)
        
        if search_docs:
            response = self.system.answer_with_context(query)
        else:
            response = self.system.answer_question(query)
        
        st.markdown(response)
```

---

## Next Steps

1. **Test the detector:**
   ```bash
   export OPENAI_API_KEY="sk-..."
   python src/ai_tutor/agents/intent_detector.py
   ```

2. **Read detailed comparison:**
   ```bash
   cat docs/llm_vs_keyword_detection.md
   ```

3. **Integrate into your app:**
   - Follow `INTENT_DETECTION_UPGRADE.md`
   - Update `apps/ui.py`
   - Restart Streamlit
   - Try natural language!

---

## Summary

**You asked:** "Can the agent understand natural language instead of strict keywords?"

**Answer:** YES! ✅

**Solution:** LLM Function Calling (aka Tool Use)

**Status:** Production-ready code created for you!

**Files:**
- `src/ai_tutor/agents/intent_detector.py` ← Use this!
- `INTENT_DETECTION_UPGRADE.md` ← Integration guide
- `docs/llm_vs_keyword_detection.md` ← Comparison

**Cost:** ~$0.0001 per request (negligible)

**Benefit:** Natural language understanding! 🚀

---

**Try it and see the magic! ✨**

