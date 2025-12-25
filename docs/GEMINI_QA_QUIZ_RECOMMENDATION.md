# Recommendation: Should QA and Quiz Agents Use Gemini?

## Decision Matrix

### Option 1: Conditional Gemini (Recommended)

**Use Gemini when:**
- ✅ Uploaded documents detected (`source_filter` present)
- ✅ `documents_only=True` (user explicitly wants uploaded docs)
- ✅ `extra_context` is substantial (>500 chars, indicates uploaded docs)

**Use Current Model + RAG when:**
- ✅ General queries (no `source_filter`)
- ✅ Corpus-wide search
- ✅ No uploaded documents in context

**Pros:**
- Cost-effective (Gemini only when needed)
- Best of both worlds
- Maintains RAG for general queries

**Cons:**
- More complex (conditional logic)
- Two different models to manage

### Option 2: Always Gemini

**Use Gemini for all queries, but:**
- Uploaded docs → Feed full document(s)
- General queries → Use RAG to find chunks, then send to Gemini

**Pros:**
- Consistent model
- Better reasoning (Gemini is more capable)
- Simpler (one model)

**Cons:**
- More expensive (Gemini for everything)
- Still need RAG for general queries

### Option 3: Keep Current (Not Recommended)

**Keep current model + RAG for everything**

**Pros:**
- No changes needed
- Cost-effective

**Cons:**
- Missing opportunity for better quality
- Can't leverage full document context

## Recommendation: Option 1 (Conditional Gemini)

### Implementation Strategy

#### 1. QA Agent

```python
def build_qa_agent(
    retriever,
    state,
    min_confidence: float,
    model_name: Optional[str] = None,  # Add model config
    model_api_key: Optional[str] = None,
    mcp_servers: Optional[List[Any]] = None,
    mcp_server_names: Optional[List[str]] = None,
) -> Agent:
    # Create model (Gemini or default)
    agent_model = _create_agent_model(model_name, model_api_key)
    
    # Add tool for full document access (when using Gemini)
    @function_tool
    def read_full_document(filename: str) -> str:
        """Read full document text (for Gemini with large context)."""
        # Parse document directly (skip chunking)
        document = parse_path(filename)
        return document.text
    
    # Keep retrieve_local_context for RAG (general queries)
    retrieve_local_context = build_retrieve_local_context_tool(...)
    
    instructions = """
    You answer STEM questions using local course materials.
    
    STRATEGY SELECTION:
    1. If source_filter is provided (uploaded documents):
       - Use read_full_document() to get full document text
       - Answer using full document context
       - Better coherence and completeness
    
    2. If no source_filter (general query):
       - Use retrieve_local_context() for semantic search
       - Answer using retrieved relevant chunks
       - More precise and cost-effective
    """
    
    return Agent(
        name="qa_agent",
        model=agent_model,  # Gemini or default
        instructions=instructions,
        tools=[retrieve_local_context, read_full_document],  # Both tools
        mcp_servers=active_mcp_servers,
    )
```

#### 2. Quiz Agent

```python
def build_quiz_agent(
    quiz_service: QuizService,
    state,
    get_profile: Callable[[], Optional[LearnerProfile]],
    get_extra_context: Callable[[], Optional[str]],
    get_source_filter: Callable[[], Optional[List[str]]],
    get_documents_only: Callable[[], bool],
    model_name: Optional[str] = None,  # Add model config
    model_api_key: Optional[str] = None,
) -> Agent:
    # Create model (Gemini or default)
    agent_model = _create_agent_model(model_name, model_api_key)
    
    # QuizService will handle model selection internally
    # based on source_filter and extra_context
    
    return Agent(
        name="quiz_agent",
        model=agent_model,  # Gemini or default
        instructions=instructions,
        tools=[generate_quiz],
    )
```

#### 3. QuizService Updates

```python
class QuizService:
    def __init__(
        self,
        retriever: Retriever,
        llm_client: LLMClient,
        progress_tracker: ProgressTracker | None,
        use_gemini_for_uploaded_docs: bool = True,  # New flag
    ):
        self.retriever = retriever
        self.llm = llm_client
        self.use_gemini_for_uploaded_docs = use_gemini_for_uploaded_docs
    
    def generate_quiz(
        self,
        *,
        topic: str,
        profile: LearnerProfile | None,
        num_questions: int = 4,
        difficulty: Optional[str] = None,
        extra_context: Optional[str] = None,
        source_filter: Optional[List[str]] = None,
        documents_only: bool = False,
    ) -> Quiz:
        # Check if we should use full document approach
        has_uploaded_docs = (
            source_filter and len(source_filter) > 0
        ) or (extra_context and len(extra_context) > 500)
        
        if has_uploaded_docs and self.use_gemini_for_uploaded_docs:
            # Use full document(s) with Gemini
            context = self._get_full_document_context(source_filter)
        else:
            # Use RAG (semantic search)
            context = self._get_rag_context(topic, source_filter)
        
        # Generate quiz using context
        return self._generate_from_context(context, topic, num_questions, ...)
    
    def _get_full_document_context(self, source_filter: List[str]) -> str:
        """Read full documents directly (for Gemini)."""
        documents = []
        for filename in source_filter:
            try:
                doc = parse_path(Path(filename))
                documents.append(f"--- {filename} ---\n{doc.text}")
            except Exception as e:
                logger.warning(f"Failed to read {filename}: {e}")
        return "\n\n".join(documents)
    
    def _get_rag_context(self, topic: str, source_filter: Optional[List[str]]) -> str:
        """Use RAG to find relevant chunks."""
        query = Query(text=topic, source_filter=source_filter)
        hits = self.retriever.retrieve(query)
        return _render_hit_context(hits)
```

## Configuration

### Add to Config Schema

```python
class AgentConfig(BaseModel):
    """Configuration for individual agents."""
    
    model: str | None = Field(
        None,
        description="Model name. For Gemini via LiteLLM, use 'gemini/gemini-1.5-pro'."
    )
    api_key: str | None = Field(
        None,
        description="API key (or use env var)."
    )
    use_full_context: bool = Field(
        True,
        description="Use full document context when uploaded docs detected."
    )

class Settings(BaseModel):
    # ... existing fields ...
    qa_agent: AgentConfig = Field(default_factory=AgentConfig)
    quiz_agent: AgentConfig = Field(default_factory=AgentConfig)
    note_agent: NoteAgentConfig = Field(default_factory=NoteAgentConfig)
```

### Config File

```yaml
# QA Agent Configuration
qa_agent:
  model: "gemini/gemini-2.0-flash"  # Fast, cost-effective
  api_key: null  # Uses GEMINI_API_KEY env var
  use_full_context: true  # Use full docs when uploaded

# Quiz Agent Configuration  
quiz_agent:
  model: "gemini/gemini-2.0-flash"  # Fast, cost-effective
  api_key: null  # Uses GEMINI_API_KEY env var
  use_full_context: true  # Use full docs when uploaded

# Note Agent Configuration (already implemented)
note_agent:
  model: "gemini/gemini-1.5-pro"  # Best quality for summaries
  api_key: null
  use_full_context: true
```

## Implementation Steps

### Phase 1: Add Model Configuration (Quick)

1. Extend `AgentConfig` in `schema.py`
2. Add `qa_agent` and `quiz_agent` configs
3. Update `default.yaml` with agent configs

### Phase 2: Update QA Agent (Medium)

1. Add model parameter to `build_qa_agent()`
2. Create `_create_agent_model()` helper (reuse from Note Agent)
3. Add `read_full_document()` tool
4. Update instructions to use both strategies

### Phase 3: Update Quiz Agent (Medium)

1. Add model parameter to `build_quiz_agent()`
2. Update `QuizService` to detect uploaded docs
3. Add `_get_full_document_context()` method
4. Conditional context selection

### Phase 4: Integration (Easy)

1. Pass agent configs from `TutorAgent` to agents
2. Update `TutorSystem` to pass configs
3. Test with uploaded docs vs general queries

## Cost Analysis

### Example: 100-page PDF (~200k tokens)

**Current (GPT-4o-mini + RAG):**
- Ingestion: ~10s (chunk + embed)
- Query: ~2s (search + top-5 chunks)
- Cost: ~$0.01 per query

**Proposed (Gemini Flash + Full Doc):**
- Ingestion: ~2s (parse only)
- Query: ~10-15s (send full doc)
- Cost: ~$0.15-$0.60 per query

**Break-even**: 
- If querying same doc 3+ times → RAG is cheaper
- If querying once → Full doc is simpler

## Final Recommendation

### ✅ Yes, Switch QA and Quiz Agents to Gemini

**But with conditions:**

1. **Use Gemini Flash** (not Pro)
   - Faster and cheaper
   - Good enough quality
   - 1M token context

2. **Conditional Strategy**
   - Uploaded docs → Full document
   - General queries → RAG (still use Gemini, but with retrieved chunks)

3. **Keep RAG Infrastructure**
   - Still need embeddings for general queries
   - Can skip chunking/embedding for uploaded docs only
   - Hybrid approach

### Implementation Priority

1. **High Priority**: QA Agent with Gemini (most common use case)
2. **Medium Priority**: Quiz Agent with Gemini
3. **Low Priority**: Optimize ingestion (skip chunking for uploaded docs)

### Expected Benefits

- ✅ Better quality answers (Gemini is more capable)
- ✅ Simpler for uploaded documents (no chunking needed)
- ✅ Better coherence (full document context)
- ✅ Still efficient for general queries (RAG)

**Bottom line**: Yes, switch to Gemini for QA and Quiz agents, but use conditional strategy - full document for uploaded docs, RAG for general queries.

