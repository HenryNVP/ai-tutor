# Enhanced Streamlit UI Architecture

## Application Structure

```
┌─────────────────────────────────────────────────────────────┐
│                     AI Tutor Streamlit UI                   │
│                      (apps/ui.py)                          │
└──────────────────┬──────────────────┬──────────────────────┘
                   │                  │
        ┌──────────┴──────────┐      └──────────────┐
        │                     │                      │
   ┌────▼────┐          ┌────▼────┐           ┌────▼─────┐
   │ Tab 1:  │          │ Tab 2:  │           │  Tab 3:  │
   │ Chat &  │          │ Corpus  │           │   Quiz   │
   │ Learn   │          │ Mgmt    │           │ Builder  │
   └────┬────┘          └────┬────┘           └────┬─────┘
        │                     │                      │
        │                     │                      │
```

## Tab 1: Chat & Learn (Original)

```
┌─────────────────────────────────────────┐
│          Sidebar                        │
├─────────────────────────────────────────┤
│ • Learner ID input                      │
│ • Upload temporary context              │
│ • Quick quiz generation                 │
└─────────────────────────────────────────┘
          ↓
┌─────────────────────────────────────────┐
│     Chat Interface                      │
├─────────────────────────────────────────┤
│ • Q&A with streaming                    │
│ • Citation display                      │
│ • Embedded quiz taking                  │
│ • Quiz evaluation & feedback            │
└─────────────────────────────────────────┘
```

## Tab 2: Corpus Management (NEW)

```
┌──────────────────────────┐     ┌──────────────────────────┐
│  Column 1: Upload        │     │  Column 2: Analysis      │
├──────────────────────────┤     ├──────────────────────────┤
│                          │     │                          │
│  📤 File Uploader        │     │  📊 Corpus Statistics   │
│  • Multi-select          │     │  • Total documents       │
│  • PDF/MD/TXT            │     │  • Total chunks          │
│  • Size display          │     │  • Avg chunks/doc        │
│                          │     │                          │
│  🚀 Ingest Button        │     │  📈 Domain Distribution │
│  ↓                       │     │  • Physics: 65%          │
│  Temp Dir → Pipeline     │     │  • Math: 25%             │
│  ↓                       │     │  • General: 10%          │
│  Parse → Chunk → Embed   │     │                          │
│  ↓                       │     │  📑 Document List        │
│  Store in Vector DB      │     │  • Title + ID            │
│  ↓                       │     │                          │
│  ✅ Success Message      │     │  🎯 Sample Topics        │
│                          │     │  • Random previews       │
└──────────────────────────┘     └──────────────────────────┘
```

## Tab 3: Quiz Builder (NEW)

```
┌──────────────────────────┐     ┌──────────────────────────┐
│  Column 1: Generate      │     │  Column 2: Export        │
├──────────────────────────┤     ├──────────────────────────┤
│                          │     │                          │
│  🎯 Topic Input          │     │  📥 Quiz Info            │
│  • Text field            │     │  • Topic display         │
│                          │     │  • Difficulty display    │
│  ⚙️ Settings             │     │  • Question count        │
│  • Questions: 3-8        │     │                          │
│  • Difficulty selector   │     │  ✏️ Edit Toggle          │
│                          │     │  • Switch: Preview/Edit  │
│  ☑️ Ground in Corpus     │     │                          │
│  ↓ (if checked)          │     │  ⬇️ Download Button      │
│  Query → Retriever       │     │  • Markdown format       │
│  ↓                       │     │  • Auto filename         │
│  Top-k Passages          │     │                          │
│  ↓                       │     └──────────────────────────┘
│  Context → LLM           │
│  ↓                       │
│  ✨ Generate Button      │
└──────────────────────────┘

         ↓ (After Generation)

┌─────────────────────────────────────────┐
│       Preview / Edit Section            │
├─────────────────────────────────────────┤
│                                         │
│  👁️ Preview Mode:                      │
│  ┌──────────────────────────────────┐  │
│  │ Question 1 (expandable)          │  │
│  │ ✅ A. Correct answer             │  │
│  │ ○  B. Incorrect option           │  │
│  │ ○  C. Incorrect option           │  │
│  │ ○  D. Incorrect option           │  │
│  │ ℹ️  Explanation: ...              │  │
│  │ 📚 References: [1] Title...      │  │
│  └──────────────────────────────────┘  │
│                                         │
│  ✏️ Edit Mode:                         │
│  ┌──────────────────────────────────┐  │
│  │ # Quiz: Topic                    │  │
│  │ ## Question 1                    │  │
│  │ Text here...                     │  │
│  │ ✓ **A.** Correct                │  │
│  │ ○ **B.** Incorrect              │  │
│  │ ...                              │  │
│  │ [Full markdown editor]           │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

## Data Flow Diagram

```
┌─────────────┐
│   User      │
│  Uploads    │
│  Files      │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  Temp Directory │
└──────┬──────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│      system.ingest_directory()           │
│  (Reuses existing pipeline)              │
├──────────────────────────────────────────┤
│  1. parse_path() → Document objects      │
│  2. chunk_document() → Chunks            │
│  3. embedder.embed_documents() → Vectors │
│  4. chunk_store.upsert() → JSONL        │
│  5. vector_store.add() → FAISS index    │
└──────┬───────────────────────────────────┘
       │
       ▼
┌──────────────────┐      ┌──────────────────┐
│  Vector Store    │◄─────┤  Chunk Store     │
│  (embeddings)    │      │  (text+metadata) │
└──────┬───────────┘      └──────────────────┘
       │
       ├──────────────────────────┬─────────────────┐
       │                          │                 │
       ▼                          ▼                 ▼
┌──────────────┐         ┌──────────────┐  ┌──────────────┐
│  Q&A System  │         │   Analysis   │  │Quiz Generator│
│  (Chat tab)  │         │  (Corpus tab)│  │ (Quiz tab)   │
└──────────────┘         └──────────────┘  └──────────────┘
```

## Component Interaction

```
User Action                System Response                   Storage Update
─────────────────────────────────────────────────────────────────────────────

Upload PDFs           →   Save to temp dir                →  None yet
Click "Ingest"        →   Process pipeline                →  Vector DB + JSONL
Click "Analyze"       →   Read chunk_store.stream()       →  None (read-only)
Generate Quiz         →   Retrieve from vector_store      →  None (read-only)
                         + LLM generation
Edit Quiz             →   Update markdown in session       →  Session state
Download Quiz         →   Export to .md file              →  Local download
```

## Session State Management

```
st.session_state
├── messages                    # Chat history
├── documents                   # Temp uploaded docs
├── quiz                        # Current quiz (chat tab)
├── quiz_answers                # User selections
├── quiz_result                 # Evaluation results
├── uploaded_files_for_ingestion  # Files to ingest
├── ingestion_result            # Last ingestion status
├── corpus_analysis             # Corpus statistics
├── quiz_builder_quiz           # Generated quiz (quiz tab)
├── quiz_edit_mode              # Toggle preview/edit
├── edited_quiz_text            # Markdown content
└── learner_id_global           # Shared learner ID
```

## Key Design Decisions

### 1. **Tab Separation**
- **Rationale**: Distinct workflows (chat vs. corpus management vs. quiz creation)
- **Benefit**: Cleaner UI, focused user experience

### 2. **Reuse Existing Pipeline**
- **Rationale**: Don't duplicate ingestion logic
- **Benefit**: Consistency, maintainability

### 3. **Markdown Export Format**
- **Rationale**: Universal, editable, version-controllable
- **Benefit**: Easy distribution, no proprietary formats

### 4. **Grounded Quiz Generation**
- **Rationale**: Ensure accuracy and relevance
- **Benefit**: Questions based on actual course materials

### 5. **Edit Before Export**
- **Rationale**: Educators need customization ability
- **Benefit**: Flexibility without regeneration

## Error Handling

```
Upload → Parse → Chunk → Embed → Store
  ↓       ↓       ↓       ↓       ↓
 OK?    Skip    Skip    Abort   Retry
        file    file    batch   3x
```

- Individual file failures don't block entire ingestion
- Batch embedding failures are reported (rare)
- Vector store write failures logged for debugging

## Performance Optimizations

1. **Batch Embedding**: 256 chunks at once
2. **Lazy Loading**: Corpus analysis on-demand
3. **Session Caching**: TutorSystem loaded once
4. **Progress Bars**: Visual feedback for long operations
5. **Temp Files**: Cleaned up automatically

---

## Summary

The enhanced UI provides:
- ✅ Professional corpus management
- ✅ Advanced quiz generation with grounding
- ✅ Flexible preview and editing
- ✅ Clean separation of concerns
- ✅ Full reuse of existing components
- ✅ Excellent user experience


