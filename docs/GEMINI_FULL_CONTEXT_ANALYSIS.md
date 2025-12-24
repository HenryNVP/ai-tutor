# Gemini Full Context Window Analysis

## Overview

This document analyzes using Google Gemini (with 1M+ token context window) to process entire documents directly, eliminating the need for chunking and retrieval for summarization tasks.

## Current Architecture

### Document Processing Flow
1. **Ingestion**: Documents → Chunked (500 tokens, 80 overlap) → Embedded → Stored in ChromaDB
2. **Summarization**: Note Agent calls `fetch_full_document()` → Retrieves ALL chunks sequentially → Concatenates → Sends to GPT-4o-mini
3. **QA**: QA Agent uses semantic search → Retrieves top-k chunks → Sends to GPT-4o-mini

### Current Limitations
- **Chunking overhead**: Documents split into ~500-token chunks
- **Sequential retrieval**: `fetch_full_document()` must query ChromaDB and reconstruct full document
- **Context window**: GPT-4o-mini has ~128k context, but `max_output_tokens: 2048` limits response
- **Token waste**: Full document concatenation may exceed optimal context size for smaller docs

## Proposed Approach: Gemini Full Context

### Concept
- Use **Gemini 1.5 Pro** (1M token context window)
- For summarization: Feed entire document text directly (no chunking/retrieval)
- For QA: Still use retrieval for precision, but can include more context

### Gemini Model Specifications

| Model | Context Window | Input Cost | Output Cost | Best For |
|-------|---------------|------------|-------------|----------|
| Gemini 1.5 Pro | 1M tokens | $1.25/$5 per 1M tokens | $5/$15 per 1M tokens | Large documents, code |
| Gemini 1.5 Flash | 1M tokens | $0.075/$0.30 per 1M tokens | $0.30/$0.60 per 1M tokens | Fast, cost-effective |
| GPT-4o-mini (current) | 128k tokens | $0.15/$0.60 per 1M tokens | $0.60/$1.80 per 1M tokens | General purpose |

*Note: Pricing varies by region and usage tier*

## Pros and Cons

### ✅ Advantages

1. **Simpler Architecture**
   - No need for `fetch_full_document()` tool
   - Direct document → LLM pipeline
   - Eliminates chunk reconstruction complexity

2. **Better Coherence**
   - Full document context = better understanding of structure
   - No information loss at chunk boundaries
   - Preserves document flow and relationships

3. **Handles Large Documents**
   - Can process entire textbooks (up to ~750k tokens)
   - No need to split multi-chapter documents
   - Better for comprehensive summaries

4. **Cost Efficiency (for large docs)**
   - Single API call vs multiple chunk retrievals
   - Reduced embedding storage (optional for summarization)
   - Lower latency (one request vs many)

5. **Better for Structured Content**
   - Preserves table structures, code blocks, equations
   - Maintains cross-references and citations
   - Better handling of hierarchical content

### ❌ Disadvantages

1. **Cost at Scale**
   - Processing 1M tokens costs $1.25-$5 per request
   - For small documents (<10k tokens), current approach is cheaper
   - No caching benefit (each request sends full doc)

2. **Still Need Retrieval for QA**
   - QA benefits from semantic search (precision)
   - Full document context may include irrelevant info
   - Retrieval helps focus on specific topics

3. **Latency for Very Large Docs**
   - Processing 1M tokens takes time (30-60 seconds)
   - May timeout if document is too large
   - Need fallback strategy

4. **Token Limits**
   - Even 1M tokens may not cover:
     - Multiple large documents simultaneously
     - Very long textbooks (1000+ pages)
     - Codebases with thousands of files

5. **Loss of Granular Citations**
   - Current system: Citations point to specific chunks/pages
   - Full context: Harder to cite exact locations
   - May need hybrid approach

## When to Use Full Context vs Retrieval

### Use Full Context (Gemini) For:
- ✅ **Summarization tasks** ("summarize this document")
- ✅ **Note generation** ("create notes from this file")
- ✅ **Single document processing** (one file at a time)
- ✅ **Structured content** (tables, code, equations)
- ✅ **Documents < 500k tokens** (sweet spot)

### Keep Retrieval (Current) For:
- ✅ **QA across multiple documents** ("what is X across all files?")
- ✅ **Precise fact-finding** ("what page mentions Y?")
- ✅ **Multi-document queries** (search across corpus)
- ✅ **Small documents** (< 5k tokens, retrieval is faster/cheaper)
- ✅ **Citation requirements** (need exact page/chunk references)

## Hybrid Approach (Recommended)

### Strategy: Use Both Based on Task

```python
def route_to_strategy(task_type: str, document_size: int) -> str:
    if task_type == "summarize" and document_size < 500_000:
        return "full_context"  # Use Gemini
    elif task_type == "qa" or document_size > 500_000:
        return "retrieval"  # Use current RAG
    else:
        return "hybrid"  # Use retrieval + full context for key sections
```

### Implementation Plan

1. **Add Gemini Support**
   - Extend `LLMClient` to support Gemini API
   - Add `provider: "gemini"` option to `ModelConfig`
   - Create `GeminiLLMClient` class

2. **Document Size Detection**
   - Add `get_document_size()` helper
   - Check token count before choosing strategy
   - Cache document sizes

3. **Note Agent Enhancement**
   - For small-medium docs: Use Gemini full context
   - For large docs: Use retrieval + Gemini for key sections
   - Fallback to current approach if Gemini unavailable

4. **Keep QA Agent as-is**
   - QA benefits from retrieval precision
   - Can optionally include more context (top-20 chunks vs top-5)

## Implementation Considerations

### 1. Code Changes Required

**New Files:**
- `src/ai_tutor/agents/llm_client_gemini.py` - Gemini API client
- `src/ai_tutor/utils/document_utils.py` - Document size helpers

**Modified Files:**
- `src/ai_tutor/agents/llm_client.py` - Add provider abstraction
- `src/ai_tutor/agents/note.py` - Add full-context path
- `src/ai_tutor/config/schema.py` - Add Gemini provider option

### 2. Configuration

```yaml
model:
  name: "gemini-1.5-pro"  # or "gemini-1.5-flash"
  provider: "gemini"
  temperature: 0.7
  max_output_tokens: 8192  # Gemini supports larger outputs

# Optional: Strategy selection
summarization:
  use_full_context: true
  max_tokens_for_full_context: 500000  # Use full context below this
  fallback_to_retrieval: true
```

### 3. Cost Analysis

**Example: 100-page PDF (~200k tokens)**

| Approach | API Calls | Cost (approx) | Latency |
|---------|-----------|---------------|---------|
| Current (chunks) | 1 retrieval + 1 LLM | $0.10 | ~5s |
| Gemini Full | 1 LLM | $0.25-$1.00 | ~10-20s |
| Hybrid | 1 retrieval + 1 LLM (Gemini) | $0.30-$1.10 | ~8-15s |

*Note: Costs vary by region and usage tier*

### 4. Error Handling

- **Rate limits**: Fallback to retrieval if Gemini rate-limited
- **Timeout**: Set max document size (e.g., 500k tokens)
- **API failures**: Graceful degradation to current approach

## Recommendations

### ✅ Recommended: Hybrid Approach

1. **For Note Agent (Summarization)**
   - Use Gemini full context for documents < 500k tokens
   - Use retrieval + Gemini for larger documents
   - Keep current approach as fallback

2. **For QA Agent**
   - Keep retrieval-based approach (better precision)
   - Optionally increase `top_k` from 5 to 10-20 for more context
   - Use Gemini for final answer generation (better reasoning)

3. **For Quiz Agent**
   - Keep current approach (needs retrieval for topic-specific questions)
   - Can use Gemini for question generation (better quality)

### Implementation Priority

1. **Phase 1** (Quick Win): Add Gemini support, use for Note Agent only
2. **Phase 2** (Optimization): Add document size detection, hybrid routing
3. **Phase 3** (Enhancement): Increase QA context, improve citations

## Implementation Status

✅ **Implemented**: Gemini support via LiteLLM for Note Agent

### Configuration

Add to `config/default.yaml`:

```yaml
note_agent:
  model: "gemini/gemini-1.5-pro"  # or "gemini/gemini-1.5-flash"
  api_key: null  # Set GEMINI_API_KEY env var or provide here
  use_full_context: true
```

### Setup

1. **Install dependencies**:
   ```bash
   pip install "openai-agents[litellm]"
   ```

2. **Set API key**:
   ```bash
   export GEMINI_API_KEY="your-gemini-api-key"
   ```

3. **Configure model** in `config/default.yaml`:
   ```yaml
   note_agent:
     model: "gemini/gemini-1.5-pro"
   ```

### Usage

The Note Agent will automatically use Gemini when configured. No code changes needed - just update the config file.

### How It Works

- **Note Agent** uses `LitellmModel` wrapper when `model` starts with `"gemini/"`
- Falls back to default `gpt-4o-mini` if:
  - LiteLLM not installed
  - API key not found
  - Model creation fails
- **Other agents** (QA, Quiz) continue using default model

## Conclusion

**Using Gemini for full document context is a good idea for summarization**, but:
- ✅ Simplifies Note Agent significantly
- ✅ Better quality for single-document tasks
- ⚠️ Keep retrieval for QA (precision matters)
- ⚠️ Consider cost for high-volume usage
- ⚠️ Need fallback strategy for large docs/timeouts

**Recommendation**: Implement hybrid approach - use Gemini full context for Note Agent when document size < 500k tokens, keep retrieval for QA and large documents.

**Status**: ✅ Implemented and ready to use!

