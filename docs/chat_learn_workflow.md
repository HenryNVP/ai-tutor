# Chat & Learn Enhanced Workflow

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Chat & Learn Tab                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Sidebar:                                                       │
│  ┌──────────────────────────────────────┐                      │
│  │ 📤 Upload Documents                   │                      │
│  │  • PDF, MD, TXT files                 │                      │
│  │  • Multiple files supported           │                      │
│  │  • Not immediately ingested           │                      │
│  └──────────────────────────────────────┘                      │
│                                                                 │
│  Main Chat Area:                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  User: [Uploads files]                                    │  │
│  │  System: 📁 3 file(s) ready. Ask a question to ingest!   │  │
│  │                                                            │  │
│  │  User: "Explain quantum entanglement"                     │  │
│  │  System: 🔄 Auto-ingesting...                             │  │
│  │          ✅ Ingested 3 documents into 142 chunks!         │  │
│  │          [Answer with citations...]                       │  │
│  │                                                            │  │
│  │  User: "Create a quiz on this topic"                      │  │
│  │  System: 🎯 Generating quiz on: quantum entanglement      │  │
│  │          📚 Retrieved 5 passages from uploaded docs       │  │
│  │          ✅ Quiz generated! Scroll down to preview.       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Quiz Preview Section:                                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  🎯 Generated Quiz Preview                                │  │
│  │  [Preview Mode] | [Edit Mode]                             │  │
│  │                                                            │  │
│  │  # Quiz: Quantum Entanglement                             │  │
│  │                                                            │  │
│  │  ## Question 1                                            │  │
│  │  What is quantum entanglement?                            │  │
│  │  A) ...                                                   │  │
│  │  B) ...                                                   │  │
│  │                                                            │  │
│  │  💾 Download Quiz (Markdown)                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Workflow Sequence Diagrams

### Scenario 1: Q&A with Auto-Ingestion

```
User                    UI                      System              Vector Store
 |                       |                         |                      |
 |--[Upload files]------>|                         |                      |
 |                       |                         |                      |
 |                       |--[Display: Files ready] |                      |
 |                       |                         |                      |
 |--[Ask question]------>|                         |                      |
 |                       |                         |                      |
 |                       |--[Check: files ingested?]                      |
 |                       |   NO                    |                      |
 |                       |                         |                      |
 |                       |--[Create temp dir]      |                      |
 |                       |--[Save uploaded files]  |                      |
 |                       |                         |                      |
 |                       |--[Call ingest_directory]->                     |
 |                       |                         |                      |
 |                       |                         |--[Parse, chunk]--->  |
 |                       |                         |                      |
 |                       |                         |<--[Store embeddings]-|
 |                       |                         |                      |
 |                       |<--[Ingestion complete]--|                      |
 |                       |                         |                      |
 |                       |--[Mark: files_ingested = True]                 |
 |                       |                         |                      |
 |                       |--[Retrieve relevant chunks]------------------->|
 |                       |                         |                      |
 |                       |<--[Return chunks]--------------------------------|
 |                       |                         |                      |
 |                       |--[Generate answer]----->|                      |
 |                       |                         |                      |
 |<--[Display answer]----|<--[Return answer]-------|                      |
 |   with citations      |                         |                      |
 |                       |                         |                      |
```

### Scenario 2: Quiz Generation with Grounding

```
User                    UI                      System              Retriever
 |                       |                         |                      |
 |--["Quiz me on X"]---->|                         |                      |
 |                       |                         |                      |
 |                       |--[detect_quiz_request()]                       |
 |                       |   TRUE                  |                      |
 |                       |                         |                      |
 |                       |--[extract_quiz_topic()]                        |
 |                       |   topic = "X"           |                      |
 |                       |                         |                      |
 |                       |--[Check: files_ingested?]                      |
 |                       |   YES                   |                      |
 |                       |                         |                      |
 |                       |--[Retrieve passages]-----------------------X   |
 |                       |   Query(text="X")       |                      |
 |                       |                         |                      |
 |                       |<--[Return top 5 hits]-----------------------X  |
 |                       |                         |                      |
 |                       |--[Format context]       |                      |
 |                       |                         |                      |
 |                       |--[generate_quiz()]----->|                      |
 |                       |   topic="X"             |                      |
 |                       |   extra_context=[...]   |                      |
 |                       |                         |                      |
 |                       |<--[Return quiz]---------|                      |
 |                       |                         |                      |
 |                       |--[Store in chat_quiz_preview]                  |
 |                       |--[Convert to markdown]  |                      |
 |                       |                         |                      |
 |<--[Display quiz]------|                         |                      |
 |   preview section     |                         |                      |
 |                       |                         |                      |
```

### Scenario 3: Quiz Edit & Download

```
User                    UI                      Browser
 |                       |                         |
 |--[Click "Edit Mode"]->|                         |
 |                       |                         |
 |                       |--[Show text area]       |
 |                       |   with markdown         |
 |                       |                         |
 |<--[Display editor]----|                         |
 |                       |                         |
 |--[Modify text]------->|                         |
 |                       |                         |
 |                       |--[Update session_state] |
 |                       |   chat_quiz_markdown    |
 |                       |                         |
 |--[Click "Download"]-->|                         |
 |                       |                         |
 |                       |--[Create download link]----------------->|
 |                       |   file_name="quiz_X.md" |              |
 |                       |   mime="text/markdown"  |              |
 |                       |                         |              |
 |<--[Browser downloads]----------------------------[Save file]---|
 |   quiz_X.md           |                         |              |
 |                       |                         |              |
```

## State Transitions

```
┌─────────────────┐
│  No Files       │
│  Uploaded       │
└────────┬────────┘
         │
         │ User uploads files
         ▼
┌─────────────────┐
│  Files Ready    │
│  (Not Ingested) │
└────────┬────────┘
         │
         │ User asks first question
         ▼
┌─────────────────┐
│  Auto-Ingesting │
│  (Show progress)│
└────────┬────────┘
         │
         │ Ingestion completes
         ▼
┌─────────────────┐
│  Files Ingested │
│  (Ready for Q&A)│
└────────┬────────┘
         │
         ├──────────────┬──────────────┐
         │              │              │
         │ Regular Q    │ Quiz Request │ Clear Files
         ▼              ▼              ▼
┌─────────────┐  ┌──────────────┐  ┌──────────┐
│ Answer with │  │ Generate Quiz│  │ No Files │
│ Citations   │  │ (Grounded)   │  │ Uploaded │
└─────────────┘  └──────┬───────┘  └──────────┘
                        │
                        │ Quiz generated
                        ▼
                 ┌──────────────┐
                 │ Quiz Preview │
                 │ Available    │
                 └──────┬───────┘
                        │
                        ├──────────┬──────────┐
                        │          │          │
                        │ Preview  │ Edit     │ Download
                        ▼          ▼          ▼
                 ┌──────────┐ ┌──────┐ ┌──────────┐
                 │ Render   │ │ Modify│ │ Save .md │
                 │ Markdown │ │ Text  │ │ File     │
                 └──────────┘ └──────┘ └──────────┘
```

## Decision Flow: Quiz Grounding

```
                    User requests quiz
                           |
                           ▼
              ┌─────────────────────────┐
              │ Are files ingested?     │
              └──────────┬──────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
             YES                   NO
              │                     │
              ▼                     ▼
    ┌──────────────────┐   ┌──────────────────┐
    │ Retrieve passages│   │ Generate quiz    │
    │ from vector store│   │ (general         │
    └────────┬─────────┘   │  knowledge)      │
             │              └──────────────────┘
             │
             ▼
    ┌──────────────────┐
    │ Format context   │
    │ from top 5 hits  │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ Generate quiz    │
    │ WITH context     │
    │ (grounded)       │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ Show retrieval   │
    │ indicator to user│
    └──────────────────┘
```

## Key Features Highlight

### 🔄 Auto-Ingestion
- **Trigger**: First question after file upload
- **One-time**: Subsequent questions skip ingestion
- **Feedback**: Progress spinner + success message

### 🎯 Smart Quiz Detection
- **Patterns**: "quiz me", "create a quiz", "test me", etc.
- **Topic Extraction**: Regex-based topic identification
- **Fallback**: Uses entire message as topic if no pattern matched

### 📚 Grounded Generation
- **Retrieval**: Top 5 most relevant passages
- **Context**: Formatted with titles and page numbers
- **Scoping**: Questions answerable from uploaded content only

### ✏️ Interactive Preview
- **Modes**: Preview (rendered) vs Edit (text area)
- **Real-time**: Changes reflected immediately
- **Export**: One-click markdown download

---

**Visual Guide Version**: 1.0  
**Last Updated**: October 24, 2025







