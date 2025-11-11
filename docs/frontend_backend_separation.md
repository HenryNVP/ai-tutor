# Frontend/Backend Separation Guide

## Current Problems

The UI (`apps/ui.py`) has **significant business logic** that interferes with agents:

### 1. **Direct Agent/Retriever Manipulation** ❌
```python
# UI directly modifies retriever config
original_top_k = system.tutor_agent.retriever.config.top_k
system.tutor_agent.retriever.config.top_k = 50
system.tutor_agent.retriever.retrieve(Query(...))
system.tutor_agent.retriever.config.top_k = original_top_k
```

**Problems:**
- UI knows about internal agent structure
- Config changes can leak between requests
- Tight coupling makes testing difficult
- Violates separation of concerns

### 2. **Direct LLM Calls** ❌
```python
# UI bypasses agents and calls LLM directly
llm_response = system.llm_client.generate(messages)
response = TutorResponse(...)  # UI constructs response objects
```

**Problems:**
- Bypasses agent orchestration
- Duplicates logic that agents should handle
- Inconsistent behavior between UI paths

### 3. **Business Logic in UI** ❌
- Complex retrieval logic (filtering, deduplication, formatting)
- Context formatting and citation generation
- Document-specific query strategies
- Hit grouping and balancing

### 4. **Tight Coupling** ❌
- UI imports backend classes directly (`TutorResponse`, `Query`, etc.)
- UI knows about agent internals
- Hard to swap implementations

## Solution: Service Layer

Created `TutorService` class that provides a **clean API** for UI interactions.

### Architecture

```
UI (apps/ui.py)
  ↓
TutorService (services/tutor_service.py)  ← Clean API layer
  ↓
TutorSystem (system.py)
  ↓
TutorAgent (agents/tutor.py)
  ↓
Agents, Retrievers, etc.
```

### Service Layer Methods

#### 1. **`answer_question()`** - Main Q&A
```python
service = TutorService(system)
response = service.answer_question(
    learner_id="user123",
    question="What is Bernoulli equation?",
    extra_context=context
)
```

#### 2. **`retrieve_from_uploaded_documents()`** - Document-specific search
```python
hits = service.retrieve_from_uploaded_documents(
    query_text="neural networks",
    filenames=["lecture1.pdf", "notes.pdf"],
    top_k=50
)
```

**Benefits:**
- Handles config management internally
- Manages source filtering
- Removes duplicates
- No direct retriever access needed

#### 3. **`retrieve_multiple_queries()`** - Multi-query search
```python
hits = service.retrieve_multiple_queries(
    queries=["filename query", "user question", "broad topic"],
    filenames=["doc1.pdf"],
    top_k=50
)
```

#### 4. **`format_context_from_hits()`** - Context formatting
```python
context, citations = service.format_context_from_hits(
    hits=hits,
    max_passages=15,
    passages_per_doc=5
)
```

**Benefits:**
- Encapsulates formatting logic
- Handles document balancing
- Generates citations automatically

#### 5. **`answer_with_context()`** - Direct context Q&A
```python
response = service.answer_with_context(
    learner_id="user123",
    question="Explain this concept",
    context=pre_retrieved_context
)
```

**Benefits:**
- Uses LLM with provided context
- Returns proper `TutorResponse`
- No need to construct response objects in UI

## Refactoring Guide

### Before (Current UI Code)
```python
# ❌ Direct retriever manipulation
original_top_k = system.tutor_agent.retriever.config.top_k
system.tutor_agent.retriever.config.top_k = 50
hits = system.tutor_agent.retriever.retrieve(Query(...))
system.tutor_agent.retriever.config.top_k = original_top_k

# ❌ Manual formatting
context_parts = []
for hit in hits:
    context_parts.append(f"[{idx}] {hit.chunk.metadata.title}...")
context = "\n\n".join(context_parts)

# ❌ Direct LLM calls
llm_response = system.llm_client.generate(messages)
response = TutorResponse(...)
```

### After (Using Service Layer)
```python
# ✅ Clean service API
service = load_service(api_key)

# Document-specific retrieval
hits = service.retrieve_from_uploaded_documents(
    query_text=prompt,
    filenames=uploaded_filenames,
    top_k=50
)

# Formatting handled by service
context, citations = service.format_context_from_hits(hits)

# Answer with context
response = service.answer_with_context(
    learner_id=learner_id,
    question=prompt,
    context=context
)
```

## Migration Steps

1. **Replace direct retriever access**:
   - Find all `system.tutor_agent.retriever.*` calls
   - Replace with `service.retrieve_*()` methods

2. **Replace manual formatting**:
   - Find all context formatting code
   - Replace with `service.format_context_from_hits()`

3. **Replace direct LLM calls**:
   - Find all `system.llm_client.generate()` calls
   - Replace with `service.answer_with_context()` or `service.answer_question()`

4. **Remove backend imports from UI**:
   - Remove `from ai_tutor.data_models import Query`
   - Remove `from ai_tutor.agents.tutor import TutorResponse`
   - UI should only import `TutorService`

## Benefits

✅ **Separation of Concerns**: UI only handles presentation, service handles business logic  
✅ **Testability**: Service layer can be tested independently  
✅ **Maintainability**: Changes to agents don't affect UI  
✅ **Consistency**: All retrieval goes through same code paths  
✅ **Safety**: Config changes are properly managed and restored  
✅ **Flexibility**: Can swap implementations without changing UI  

## Next Steps

1. Update UI to use `TutorService` instead of direct system access
2. Move remaining business logic from UI to service layer
3. Add unit tests for service layer
4. Consider creating a REST API layer for future web frontend


