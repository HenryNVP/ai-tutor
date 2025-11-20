# Code Review: Routing Logic & Core Features

## Executive Summary

This review focuses on the routing logic and three core features:
1. **QA (Question Answering)** - Retrieval-augmented Q&A from course materials
2. **Quiz Generation** - Creating quizzes from documents
3. **Notes Generation** - Summarizing/creating notes from uploaded documents

## Architecture Overview

The system uses an **agent-first architecture** with:
- **TutorAgent** as the orchestrator
- **Deterministic routing** (keyword-based) with **LLM fallback routing**
- **Specialist agents**: QA, Note, Quiz, Web, Ingestion
- **Shared state** (AgentState) for inter-agent communication

---

## 1. Routing Logic Review

### 1.1 Routing Flow (`src/ai_tutor/agents/routing.py` & `tutor.py`)

**Current Implementation:**
```
User Query
  ↓
apply_deterministic_routing() [keyword-based rules]
  ↓ (if no match)
_route_with_llm() [LLM-based routing agent]
  ↓
RoutingDecision → _execute_decision() → Specialist Agent
```

**Strengths:**
✅ **Two-tier routing** (deterministic + LLM) provides good coverage
✅ **Clear separation** of routing logic from execution
✅ **Source filter extraction** handles document references well
✅ **RoutingDecision dataclass** provides structured metadata

**Recent Fixes:**
- ✅ `_execute_decision()` now calls `_run_quiz_agent` for quiz routes and the fallback path re-routes missed quiz intents through the same agent flow, so quiz requests consistently trigger the `generate_quiz` tool.
```674:683:src/ai_tutor/agents/tutor.py
if decision.target == "quiz":
    answer = await self._run_quiz_agent(prompt, session, on_delta)
    return answer, None
```
- ✅ Quiz count extraction now respects the 40-question limit supported elsewhere.
```20:36:src/ai_tutor/learning/quiz_intent.py
return max(3, min(n, 40))
```
- ✅ Uploaded-document context now includes explicit `SOURCE_FILTER_HINTS`, and `extract_source_mentions` parses them so routing can stay on the correct files even when the learner does not cite filenames verbatim.
```1120:1135:apps/ui.py
hints_line = "SOURCE_FILTER_HINTS: " + ", ".join(filename_hints)
uploaded_docs_context = f"{hints_line}\n\n{uploaded_docs_context}"
```
```37:63:src/ai_tutor/agents/routing.py
metadata_patterns = [
    r"SOURCE_FILTER_HINTS:\s*([^\n\r]+)",
    ...
]
```
- ✅ Low-confidence LLM routing decisions now automatically fall back to QA with logging, preventing accidental hand-offs when the router is unsure.
```410:430:src/ai_tutor/agents/tutor.py
if (
    not routed.deterministic
    and routed.confidence is not None
    and routed.confidence < self.MIN_ROUTING_CONFIDENCE
):
    ...
    return RoutingDecision(target="qa", reason="Low routing confidence ...")
```

**Remaining Issues & Concerns:**

---

## 2. QA (Question Answering) Review

### 2.1 QA Agent Implementation (`src/ai_tutor/agents/qa.py`)

**Strengths:**
✅ **Clear instructions** for handling inline context vs. retrieval
✅ **Proper citation handling** with bracketed references
✅ **Web fallback mechanism** when no local evidence exists
✅ **Source filter support** for document-specific queries

**Issues:**

#### 🟡 **Issue: Inline Context Handling Ambiguity**
```python:67:68:src/ai_tutor/agents/qa.py
"1. If the prompt already includes inline document content (e.g., 'Inline document content', 'Session-provided context'), use that text directly."
```
**Problem:** Instructions mention specific strings ("Inline document content", "Session-provided context") but the actual prompt uses different labels:
- `"Session-provided context (verbatim...)"` in `_build_agent_prompt()`
- `"Document content:"` in quiz generation

**Recommendation:** Standardize context labels or make instructions more generic.

#### 🟡 **Issue: Retrieval Caching**
```python:36:64:src/ai_tutor/agents/retrieval_tools.py
_retrieval_cache: dict[str, str] = {}
# Cache key: f"{question}:{top_k}:{','.join(source_filter or [])}"
```
**Problem:** Cache is **module-level** and never expires, potentially serving stale results across sessions.

**Recommendation:** Use session-scoped cache or add TTL.

#### 🟢 **Good: Source Filter Fallback**
```python:75:82:src/ai_tutor/agents/retrieval_tools.py
if source_filter and not hits:
    logger.warning("No hits found using source_filter. Retrying without filter.")
    hits = _run_query(None)
    fallback_used = True
```
**Good practice:** Graceful degradation when source filter yields no results.

---

## 3. Quiz Generation Review

### 3.1 Quiz Service (`src/ai_tutor/learning/quiz.py`)

**Strengths:**
✅ **Dynamic token calculation** based on question count
✅ **Uploaded document handling** with `extra_context` prioritization
✅ **Strict JSON schema validation** with Pydantic
✅ **Profile-based personalization** support

**Issues:**

#### ✅ **Fixed: Uploaded Document Detection Logic**
QuizService now keys off the presence/length of `extra_context` rather than topic keywords before deciding whether to skip vector-store retrieval, preventing uploaded-doc quizzes from mixing in unrelated passages.

#### 🟡 **Issue: Quiz Topic Extraction Still Generic**

#### 🟡 **Issue: Quiz Topic Extraction for Uploaded Docs**
```python:38:49:src/ai_tutor/learning/quiz_intent.py
def extract_quiz_topic(message: str) -> str:
    doc_patterns = [
        r"(?:from|using)\s+(?:the|my|these|uploaded)?\s*(?:document|documents|files|pdfs)",
        # ...
    ]
    if any(re.search(p, message_lower) for p in doc_patterns):
        return "uploaded documents"
```
**Problem:** Returns generic "uploaded documents" string, losing document-specific context.

**Recommendation:** Extract actual document names/titles when available.

#### 🟡 **Issue: Question Count Extraction Cap**
```python:20:35:src/ai_tutor/learning/quiz_intent.py
def extract_quiz_num_questions(message: str) -> int:
    # ...
    if m:
        n = int(m.group(1))
        return min(n, 20)  # Hard cap at 20
```
**Problem:** Hard cap at 20, but `QuizService.generate_quiz()` supports up to 40 questions (see `tutor.py:928`).

**Recommendation:** Align caps or make configurable.

#### 🟢 **Good: Dynamic Token Calculation**
```python:219:224:src/ai_tutor/learning/quiz.py
required_tokens = (num_questions * 150) + 500
max_tokens_for_quiz = max(1024, min(required_tokens, 4000))
```
**Good practice:** Prevents truncation by calculating required tokens.

---

## 4. Notes Generation Review

### 4.1 Note Agent (`src/ai_tutor/agents/note.py`)

**Strengths:**
✅ **Clear workflow** for comprehensive summaries
✅ **High top_k recommendation** (50+) for full document coverage
✅ **File writing support** via MCP filesystem server
✅ **Citation handling** with bracketed references

**Issues:**

#### 🟡 **Issue: Source Filter Handling**
```python:38:39:src/ai_tutor/agents/note.py
"1. ALWAYS ground your notes in uploaded documents. Pass the provided `source_filter` straight into retrieve_local_context so you stay within those files."
```
**Problem:** Instructions assume `source_filter` is always provided, but routing may not extract it for generic requests like "summarize my documents".

**Recommendation:** Enhance routing to extract document names from `extra_context` or session state.

#### 🟡 **Issue: Top-K Guidance**
```python:39:40:src/ai_tutor/agents/note.py
"For comprehensive summaries, call retrieve_local_context ONCE with top_k=50 (or higher for very large documents)"
```
**Problem:** Hardcoded guidance may not scale for very large documents (1000+ pages).

**Recommendation:** Make top_k adaptive based on document size or add pagination.

#### 🟢 **Good: MCP Integration**
```python:29:33:src/ai_tutor/agents/note.py
active_mcp_servers = [server for server in (mcp_servers or []) if server]
if active_mcp_servers:
    logger.info("[Note Agent] MCP servers detected (%d)", len(active_mcp_servers))
```
**Good practice:** Proper MCP server detection and logging.

---

## 5. Document Upload & Context Flow

### 5.1 UI Context Preparation (`apps/ui.py`)

**Current Flow:**
```
User uploads files → Stored in session state
  ↓
User asks question → UI retrieves from uploaded files
  ↓
Context passed as `extra_context` → Routing → Agent
```

**Issues:**

#### 🟡 **Issue: Context Size Management**
```python:1214:apps/ui.py
extra_context=combined_context,  # No size limit
```
**Problem:** `combined_context` can grow unbounded if multiple large documents are uploaded.

**Recommendation:** Add size limits or truncation with summarization.

#### 🟡 **Issue: Pre-retrieval Runs For Every Turn**
```1071:1125:apps/ui.py
if st.session_state.chat_files_ingested ...:
    filtered_hits = service.retrieve_multiple_queries(... top_k=50)
```
**Problem:** The UI pre-fetches up to 50 passages from uploaded docs for **every** prompt once files exist, even if the learner is asking unrelated questions. This adds latency and vector-store cost, and could be deferred until routing actually requests document-grounded work.

**Recommendation:** Gate the retrieval behind intent checks (e.g., only when question references documents or routing demands it) or switch to lightweight metadata hints without pulling full passages.

---

## 6. Cross-Cutting Issues

### 6.1 Session Management
✅ **Good:** Daily rotation and turn-based pruning prevent token overflow
✅ **Good:** Session keys include date and turn batch

### 6.2 Error Handling
🟡 **Issue:** Some agent failures return generic messages without actionable error details.

### 6.3 Logging
✅ **Good:** Comprehensive logging with prefixes (`[QA Agent]`, `[Note Agent]`)
🟡 **Issue:** Some critical paths lack logging (e.g., quiz routing bypass)

---

## 7. Recommendations Summary

### High Priority
1. **Leverage routing confidence** - degrade to LLM router / confirmation when low
2. **Clamp/session-scope retrieval cache** - avoid stale responses across learners
3. **Improve quiz topic extraction** - recover real document titles for uploaded-doc quizzes

### Medium Priority
4. **Standardize context labels** - Match agent instructions with actual prompt sections
5. **Add context size limits** - Prevent token overflow from large uploads
6. **Reduce redundant retrieval cost** - UI still pre-fetches 50 passages for every turn even if the question ignores uploads

### Low Priority
7. **Adaptive top_k for notes** - Scale with document size

---

## 8. Testing Recommendations

### Unit Tests Needed
- [ ] Routing decision logic with various query patterns
- [ ] Source filter extraction edge cases
- [ ] Quiz topic/count extraction accuracy
- [ ] Uploaded document detection logic

### Integration Tests Needed
- [ ] End-to-end quiz generation from uploaded documents
- [ ] Notes generation with source filtering
- [ ] QA with mixed inline + retrieved context
- [ ] Routing fallback when deterministic rules fail

### Edge Cases to Test
- [ ] Very large documents (>1000 pages)
- [ ] Multiple uploaded documents simultaneously
- [ ] Generic queries like "summarize my documents" without specific names
- [ ] Quiz requests with ambiguous topic extraction

---

## Conclusion

The architecture is **well-designed** with clear separation of concerns and good use of specialist agents. However, there are **critical bugs** in quiz routing and uploaded document handling that need immediate attention. The routing logic is solid but could benefit from better source extraction and confidence-based fallbacks.

**Overall Assessment:** ⭐⭐⭐⭐ (4/5)
- Strong architecture and design
- Good code organization
- Critical bugs need fixing
- Some edge cases need better handling

