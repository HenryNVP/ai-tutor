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

**Issues & Concerns:**

#### 🔴 **Critical Issue: Quiz Routing Bypass**
```python:674:679:src/ai_tutor/agents/tutor.py
if decision.target == "quiz":
    guidance = (
        "Quiz creation is available from the Quiz Builder tab in the app. "
        "Please open the quiz tab to generate and take a quiz."
    )
    return guidance, None
```
**Problem:** Quiz requests are **completely bypassed** in `_execute_decision()`, returning a static message instead of calling `quiz_agent`. This contradicts the architecture where quiz_agent should handle quiz generation.

**Impact:** 
- Quiz requests routed to "quiz" target never generate quizzes
- Users get a redirect message instead of actual quiz generation
- The `quiz_agent` and `generate_quiz` tool are never invoked through normal routing

**Recommendation:** 
```python
if decision.target == "quiz":
    answer = await self._run_quiz_agent(prompt, session, on_delta)
    # quiz_agent will call generate_quiz tool internally
    return answer, self.state.last_quiz
```

#### 🟡 **Issue: Inconsistent Quiz Handling**
There are **three different paths** for quiz generation:
1. `decision.target == "quiz"` → Returns static message (broken)
2. `_should_force_quiz()` → Directly calls `quiz_service.generate_quiz()` (bypasses agent)
3. `_process_quiz_directive()` → Parses JSON from agent response (legacy)

**Recommendation:** Consolidate to single path through `quiz_agent`.

#### 🟡 **Issue: Source Filter Extraction Limitations**
```python:37:63:src/ai_tutor/agents/routing.py
def extract_source_mentions(message: str) -> List[str]:
    # Only extracts:
    # - Quoted strings
    # - Filenames with extensions
    # - "lecture/chapter/module N" patterns
```
**Problem:** Doesn't handle:
- Generic references like "my uploaded documents" (filtered out by `GENERIC_SOURCE_TOKENS`)
- Document titles without quotes
- Contextual references from `extra_context`

**Recommendation:** Enhance extraction to handle document titles from metadata.

#### 🟡 **Issue: Routing Confidence Not Used**
```python:26:34:src/ai_tutor/agents/routing.py
@dataclass
class RoutingDecision:
    confidence: float = 1.0  # Set but never used
```
**Problem:** Confidence score is calculated but never used for fallback or validation.

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

#### 🔴 **Critical Issue: Uploaded Document Detection Logic**
```python:155:164:src/ai_tutor/learning/quiz.py
is_uploaded_doc_request = topic and any(x in topic.lower() for x in ['uploaded', 'document', 'file', 'upload'])

if extra_context and len(extra_context) > 500:
    context_sections.append("Document content:\n" + extra_context.strip())
    # Only do retrieval if NOT an uploaded document request
    if topic and not is_uploaded_doc_request:
        hits = list(self.retriever.retrieve(Query(text=topic)))
```
**Problem:** 
- Detection is **topic-based** (checks if topic contains keywords), not based on actual `extra_context` source
- If topic is "machine learning" but `extra_context` contains uploaded docs, it will still do vector store retrieval
- Logic is inverted: should check if `extra_context` is from uploaded docs, not if topic mentions "document"

**Impact:** Quiz generation may mix uploaded document content with vector store content when it should be exclusive.

**Recommendation:** 
```python
# Better: Check if extra_context is substantial (indicates uploaded docs)
is_uploaded_doc_context = extra_context and len(extra_context) > 500

if is_uploaded_doc_context:
    context_sections.append("Document content:\n" + extra_context.strip())
    # Skip vector store retrieval for uploaded docs to avoid mixing sources
    if not topic or topic.lower() == "uploaded documents":
        # Only use uploaded content
        pass
else:
    # Normal flow: retrieve from vector store
    hits = list(self.retriever.retrieve(Query(text=topic)))
```

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

#### 🟡 **Issue: Duplicate Context Retrieval**
```python:1150:1183:apps/ui.py
if filter_to_uploaded:
    with st.spinner("Searching uploaded documents..."):
        filtered_hits = service.retrieve_multiple_queries(...)
        # Format context
        uploaded_docs_context_for_agent = "\n\n---\n\n".join(agent_context_parts)
```
**Problem:** UI retrieves context **before** routing, then agents may retrieve again. This duplicates work.

**Recommendation:** Let agents handle retrieval, or pass document IDs instead of full context.

#### 🟡 **Issue: Context Size Management**
```python:1214:apps/ui.py
extra_context=combined_context,  # No size limit
```
**Problem:** `combined_context` can grow unbounded if multiple large documents are uploaded.

**Recommendation:** Add size limits or truncation with summarization.

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
1. **Fix quiz routing bypass** - Call `quiz_agent` instead of returning static message
2. **Fix uploaded document detection** - Use `extra_context` presence, not topic keywords
3. **Consolidate quiz generation paths** - Single path through `quiz_agent`

### Medium Priority
4. **Enhance source filter extraction** - Handle document titles and generic references
5. **Standardize context labels** - Consistent naming across agents
6. **Add context size limits** - Prevent token overflow from large uploads
7. **Use routing confidence** - Implement fallback or validation

### Low Priority
8. **Session-scoped retrieval cache** - Prevent stale results
9. **Adaptive top_k for notes** - Scale with document size
10. **Extract document names** - Better topic extraction for uploaded docs

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

