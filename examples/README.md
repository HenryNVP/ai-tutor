# LLM-Based Intent Detection Examples

## Overview

This directory contains examples of using **LLM Function Calling** for intelligent intent detection, replacing brittle keyword matching with natural language understanding.

## Files

### 1. `llm_function_calling_quiz.py`
Demonstrates basic LLM function calling for quiz vs Q&A detection.

**Run:**
```bash
export OPENAI_API_KEY="your-key-here"
python examples/llm_function_calling_quiz.py
```

**Output:**
```
📝 User: "Create 10 quizzes from the documents"
🤖 LLM understood intent and wants to call:
   Function: generate_quiz
   Arguments: {
     "topic": "uploaded_documents",
     "num_questions": 10,
     "from_uploaded_documents": true
   }
```

---

### 2. `integrate_llm_function_calling.py`
Shows how to integrate function calling into the AI Tutor system.

**Run:**
```bash
python examples/integrate_llm_function_calling.py
```

---

### 3. Production Implementation
**Location:** `src/ai_tutor/agents/intent_detector.py`

This is the production-ready version you can use in your app!

**Test it:**
```bash
export OPENAI_API_KEY="your-key-here"
python src/ai_tutor/agents/intent_detector.py
```

**Example output:**
```
📝 User: "Create 10 quizzes from the documents"
📁 Has docs: True (Lecture9.pdf, Lecture10.pdf)
✅ Action: GENERATE QUIZ
   Topic: uploaded_documents
   Questions: 10
   From docs: True
   Confidence: high
```

---

## Integration into Your App

### Quick Start

```python
from ai_tutor.agents.intent_detector import TutorIntentDetector

# Initialize (once)
detector = TutorIntentDetector()

# Detect intent
intent = detector.detect_intent(
    user_message="Create 10 quizzes from the documents",
    has_uploaded_docs=True,
    uploaded_doc_info="Lecture9.pdf, Lecture10.pdf"
)

# Use the result
if intent['action'] == 'generate_quiz':
    params = intent['params']
    generate_quiz(
        topic=params['topic'],
        num_questions=params.get('num_questions', 4),
        from_docs=params.get('from_uploaded_documents', False)
    )
```

### Replace in `apps/ui.py`

**Before (keyword matching):**
```python
if detect_quiz_request(prompt):
    # Manual parameter extraction...
    count = extract_count(prompt)
    from_docs = "from documents" in prompt.lower()
```

**After (LLM detection):**
```python
intent = st.session_state.intent_detector.detect_intent(
    user_message=prompt,
    has_uploaded_docs=len(st.session_state.uploaded_file_names) > 0,
    uploaded_doc_info=", ".join(st.session_state.uploaded_file_names)
)

if intent['action'] == 'generate_quiz':
    params = intent['params']
    # All parameters already extracted!
```

---

## Documentation

- **Migration Guide:** `../INTENT_DETECTION_UPGRADE.md`
- **Comparison:** `../docs/llm_vs_keyword_detection.md`

---

## Benefits

### ✅ Natural Language Understanding
- Handles: "gimme practice questions", "I need to study", "test my knowledge"
- Not just: "create quiz", "generate quiz"

### ✅ Automatic Parameter Extraction
- Count: "Create **10** quizzes" → `num_questions: 10`
- Topic: "quiz me on **neural networks**" → `topic: "neural networks"`
- Source: "from **my documents**" → `from_uploaded_documents: true`

### ✅ Context Awareness
- Knows about uploaded files
- Understands user's learning context
- Makes intelligent inferences

### ✅ Easy to Extend
Want to add "Create Study Plan"? Just add a tool definition:

```python
{
    "type": "function",
    "function": {
        "name": "create_study_plan",
        "description": "Create personalized study plan",
        "parameters": { ... }
    }
}
```

Done! The LLM automatically knows when to call it.

---

## Cost

Using `gpt-4o-mini`:
- **Per request:** ~$0.0001 (one hundredth of a cent)
- **1000 requests:** $0.10
- **10,000 requests:** $1.00

**Negligible compared to development time saved!**

---

## Requirements

```bash
pip install openai
export OPENAI_API_KEY="your-key-here"
```

Already in your `requirements.txt`!

---

## Next Steps

1. **Test the examples:**
   ```bash
   export OPENAI_API_KEY="sk-..."
   python src/ai_tutor/agents/intent_detector.py
   ```

2. **Read the comparison:**
   ```bash
   cat docs/llm_vs_keyword_detection.md
   ```

3. **Integrate into your app:**
   - See `INTENT_DETECTION_UPGRADE.md`
   - Update `apps/ui.py`
   - Test with natural language!

---

## Questions?

The intent detector is **production-ready** and can handle:
- Quiz generation requests
- Q&A requests  
- Parameter extraction
- Multi-file context
- Natural language variations

**Try it with your quiz app!** 🚀

