# 🗑️ Removable Legacy Code Analysis

## Overview

With the new **agent-first architecture**, several legacy components are now unused and can be safely removed. The agent now handles quiz generation through the `generate_quiz` tool, making old direct-call pathways obsolete.

---

## Architecture: Old vs New

### OLD Architecture (Legacy):
```
User → UI Button → system.generate_quiz() 
                     ↓
                   agent.create_quiz()
                     ↓
                   quiz_service.generate_quiz()
```

### NEW Architecture (Agent-First):
```
User → Chat Message → agent.answer()
                        ↓
                      agent decides to call generate_quiz tool
                        ↓
                      quiz_service.generate_quiz()
```

**Key Difference:** The agent now decides when and how to generate quizzes based on conversation context, rather than responding to button clicks.

---

## Removable Components

### 1. ✅ REMOVABLE: Legacy Quick Quiz Tools (UI)

**Location:** `apps/ui.py` lines 772-793

**Code:**
```python
with st.expander("🎯 Quick Quiz Tools (Legacy)"):
    quiz_topic = st.text_input("Quiz topic", key="quiz_topic_input")
    quiz_questions = st.slider("Questions", min_value=3, max_value=8, value=4, key="quiz_question_count")
    if st.button("Generate quiz", use_container_width=True):
        if not quiz_topic.strip():
            st.warning("Enter a quiz topic before generating.")
        else:
            quiz = system.generate_quiz(
                learner_id=learner_id,
                topic=quiz_topic.strip(),
                num_questions=quiz_questions,
            )
            st.session_state.quiz = quiz.model_dump(mode="json")
            st.session_state.quiz_answers = {}
            st.session_state.quiz_result = None
            st.success(f"Created quiz for {quiz.topic}.")
            st.rerun()
    if st.button("Clear quiz state", use_container_width=True):
        st.session_state.quiz = None
        st.session_state.quiz_answers = {}
        st.session_state.quiz_result = None
        st.rerun()
```

**Why Removable:**
- ✅ Labeled as "Legacy" in the UI itself
- ✅ Replaced by chat-based quiz generation
- ✅ Limited functionality (max 8 questions, vs 40 in new system)
- ✅ No document upload support
- ✅ User explicitly confirmed it's removable

---

### 2. ⚠️ KEEP (For Now): Quiz Builder Tab

**Location:** `apps/ui.py` lines 571-665

**Why Keep:**
- ❓ Provides teacher-facing quiz generation interface
- ❓ Has "Quick Download" feature (generate without taking)
- ❓ Has corpus grounding checkbox
- ❓ User hasn't confirmed this is legacy

**Recommendation:** Ask user if this should be removed or integrated with agent.

---

### 3. ⚠️ MAYBE REMOVABLE: system.generate_quiz()

**Location:** `src/ai_tutor/system.py` lines 367-386

**Code:**
```python
def generate_quiz(
    self,
    learner_id: str,
    topic: str,
    num_questions: int = 4,
    extra_context: Optional[str] = None,
) -> Quiz:
    """Produce a multiple-choice quiz tailored to the learner and topic."""
    profile = self.personalizer.load_profile(learner_id)
    style = self.personalizer.select_style(profile, None)
    difficulty = self._style_to_difficulty(style)
    quiz = self.tutor_agent.create_quiz(
        topic=topic,
        profile=profile,
        num_questions=num_questions,
        difficulty=difficulty,
        extra_context=extra_context,
    )
    self.personalizer.save_profile(profile)
    return quiz
```

**Used By:**
- `apps/ui.py` line 623 (Quiz Builder tab)
- `apps/ui.py` line 652 (Quick Download feature)
- `apps/ui.py` line 779 (Legacy Quick Quiz Tools) ← WILL BE REMOVED

**Recommendation:** 
- If Quiz Builder tab is kept → Keep this
- If Quiz Builder tab is removed → Remove this too

---

### 4. ⚠️ MAYBE REMOVABLE: agent.create_quiz()

**Location:** `src/ai_tutor/agents/tutor.py` lines 396-412

**Code:**
```python
def create_quiz(
    self,
    *,
    topic: str,
    profile: Optional[LearnerProfile],
    num_questions: int = 4,
    difficulty: Optional[str] = None,
    extra_context: Optional[str] = None,
) -> Quiz:
    """Generate a multiple-choice quiz tailored to the learner."""
    return self.quiz_service.generate_quiz(
        topic=topic,
        profile=profile,
        num_questions=num_questions,
        difficulty=difficulty,
        extra_context=extra_context,
    )
```

**Used By:**
- `src/ai_tutor/system.py` line 378 (system.generate_quiz)

**Recommendation:**
- Same as above - depends on Quiz Builder tab decision

---

### 5. ✅ KEEP: quiz_service.generate_quiz()

**Location:** `src/ai_tutor/learning/quiz.py` lines 143-237

**Why Keep:**
- ✅ Core quiz generation logic
- ✅ Used by NEW agent tool
- ✅ Used by old system methods (if kept)
- ✅ Essential functionality

**Status:** **DO NOT REMOVE**

---

### 6. ⚠️ CHECK: evaluate_quiz methods

**Locations:**
- `src/ai_tutor/system.py` lines 388-402 (system.evaluate_quiz)
- `src/ai_tutor/agents/tutor.py` lines 414-426 (agent.evaluate_quiz)

**Used By:** Quiz taking interface (when user submits answers)

**Recommendation:** Keep if quiz-taking is still used, check usage.

---

## Recommended Removal Plan

### Phase 1: Safe Removal (Confirmed Legacy)

**Remove immediately:**
```
1. apps/ui.py lines 772-793 (Legacy Quick Quiz Tools)
```

**Impact:** None, explicitly marked as legacy

---

### Phase 2: Check Quiz Builder Usage

**Ask user:**
- Is the "Quiz Builder" tab (Teacher mode) still needed?
- Should it be replaced with agent-based quiz creation?
- Do teachers use the "Quick Download" feature?

**If Answer is "Not Needed":**
```
Remove:
2. apps/ui.py lines 571-665 (Quiz Builder tab)
3. src/ai_tutor/system.py lines 367-386 (system.generate_quiz)
4. src/ai_tutor/agents/tutor.py lines 396-412 (agent.create_quiz)
```

---

## Code Dependencies Graph

```
quiz_service.generate_quiz()  ← Core, DO NOT REMOVE
    ↑
    ├─── agent tool generate_quiz()  ← NEW, actively used ✅
    │
    └─── agent.create_quiz()  ← Legacy wrapper
            ↑
            └─── system.generate_quiz()  ← Legacy API
                    ↑
                    ├─── UI: Quiz Builder tab (lines 623, 652)
                    └─── UI: Quick Quiz Tools (line 779) ← REMOVE
```

---

## What Would Break If We Remove Everything?

### If we remove ONLY Quick Quiz Tools (line 772-793):
- ✅ **Nothing breaks** - this is safe

### If we remove Quiz Builder tab + related methods:
- ❌ Teacher mode quiz generation UI would be gone
- ❌ "Quick Download" feature would be gone
- ✅ Chat-based quiz generation still works
- ✅ Students can still request quizzes via chat

### If we accidentally remove quiz_service.generate_quiz():
- ❌ **EVERYTHING BREAKS** - this is core functionality

---

## Testing After Removal

### Test Case 1: Chat-based quiz generation still works
```
1. Go to Chat & Learn tab
2. Upload a document
3. Say "create 20 quizzes from the documents"
4. Verify:
   ✅ Agent calls generate_quiz tool
   ✅ 20 questions generated
   ✅ Interactive quiz appears
```

### Test Case 2: Quiz Builder tab removed (if applicable)
```
1. Check that "Quiz Builder" tab is gone
2. Verify no UI errors
3. Confirm chat-based quiz generation is the only way
```

---

## Recommendation Summary

### Immediate Action (Safe):
```bash
# Remove legacy quick quiz tools
# Delete lines 772-793 in apps/ui.py
```

### Follow-up Question for User:
**"Should we also remove the Quiz Builder tab (Teacher mode)?**
- If YES → Remove lines 571-665 (ui.py), line 367-386 (system.py), line 396-412 (tutor.py)
- If NO → Keep those for teacher-facing UI

---

## Migration Path (If Removing Quiz Builder)

### Instead of Quiz Builder UI:
Teachers can use the chat interface:
```
Teacher: "Generate a 10-question quiz on Newton's Laws for beginners"
Agent: *creates quiz*
Teacher: "Download this quiz as markdown"
Agent: *provides download*
```

**Benefits:**
- ✅ Unified interface (chat for everything)
- ✅ More flexible (natural language)
- ✅ Simpler codebase (less UI code)

**Drawbacks:**
- ❌ Less discoverable (no buttons/sliders)
- ❌ Teachers may prefer form-based UI

---

## Conclusion

**Definitely Remove:**
1. ✅ Legacy Quick Quiz Tools (apps/ui.py lines 772-793)

**User Decision Needed:**
2. ❓ Quiz Builder tab and related methods
   - Need to know if teachers actively use this
   - Could be replaced with chat-based workflow

**Never Remove:**
3. ❌ quiz_service.generate_quiz() - core functionality

---

## Command to Remove Legacy Quick Quiz Tools

```python
# In apps/ui.py, delete lines 772-793
# That's the entire "with st.expander('🎯 Quick Quiz Tools (Legacy)'):" block
```

This is safe and confirmed by user as removable.

