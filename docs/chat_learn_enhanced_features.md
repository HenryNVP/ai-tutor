# Chat & Learn Tab - Enhanced Features

## Overview

The **Chat & Learn** tab now supports automatic document ingestion and intelligent quiz generation with preview/edit capabilities. This enhancement allows users to upload documents directly in the chat interface and have them automatically ingested into the vector store when asking questions or generating quizzes.

## Key Features

### 1. **Document Upload & Auto-Ingestion** 📤

Users can upload multiple documents (PDF, Markdown, TXT) directly in the Chat & Learn tab sidebar.

**How it works:**
- Upload documents using the file uploader
- Files are **NOT immediately ingested** (performance optimization)
- When you ask your first question, the system automatically ingests all uploaded files
- A confirmation message is displayed after ingestion
- Subsequent questions use the ingested content via RAG retrieval

**Benefits:**
- Seamless user experience - no manual ingestion step
- Efficient - only ingests when needed
- Persistent - documents remain in vector store for the entire session
- Reuses the robust ingestion pipeline from Corpus Management

**UI Indicators:**
- 📁 Yellow info: "X file(s) ready. Ask a question to auto-ingest!"
- ✅ Green success: "X file(s) ingested and ready!"

### 2. **Intelligent Quiz Detection** 🎯

The system automatically detects when users request quizzes through natural language.

**Trigger phrases:**
- "Create a quiz on..."
- "Generate a quiz about..."
- "Quiz me on..."
- "Test me on..."
- "Create questions from..."
- "Generate practice questions..."
- "Make a downloadable quiz..."

**Topic extraction:**
The system intelligently extracts the quiz topic from your request:
- "Create a quiz on photosynthesis" → Topic: "photosynthesis"
- "Quiz me about Newton's laws" → Topic: "Newton's laws"
- Fallback: uses the entire message if no specific pattern matched

### 3. **Grounded Quiz Generation** 📚

When documents are uploaded and ingested, quizzes are **grounded in the actual content** of those documents.

**How it works:**
1. User uploads documents about a specific topic (e.g., physics textbook)
2. User requests: "Create a quiz on projectile motion"
3. System retrieves the top 5 most relevant passages about projectile motion
4. LLM generates quiz questions **based on the retrieved passages**
5. Quiz is scoped to the uploaded documents - no out-of-scope questions

**Verification:**
- UI shows: "📚 Retrieved X passages from uploaded documents"
- Ensures quiz questions are answerable from the provided materials

### 4. **Quiz Preview & Edit Interface** ✏️

Generated quizzes can be previewed, edited, and downloaded as Markdown files.

**Features:**
- **Preview Mode**: Rendered markdown view of the quiz
- **Edit Mode**: Text area to modify quiz content directly
- **Download**: Save as `.md` file with proper formatting
- **Clear**: Remove quiz from view

**UI Controls:**
- Toggle between Preview and Edit modes
- Download button available in both modes
- Clear button to dismiss the quiz

## User Workflow Examples

### Example 1: Q&A with Custom Documents

```
1. User uploads: "quantum_mechanics.pdf", "wave_functions.md"
2. User asks: "What is wave-particle duality?"
3. System: 
   - Auto-ingests documents (shows progress)
   - Retrieves relevant chunks
   - Generates answer with citations
4. User asks follow-up: "How does the uncertainty principle work?"
5. System:
   - Skips ingestion (already done)
   - Retrieves and answers
```

### Example 2: Quiz Generation from Documents

```
1. User uploads: "organic_chemistry_chapter3.pdf"
2. User asks: "Create a quiz on functional groups from the document"
3. System:
   - Auto-ingests document
   - Retrieves passages about functional groups
   - Generates 4-question quiz grounded in retrieved content
4. User:
   - Switches to Edit mode
   - Adjusts question wording
   - Downloads as "quiz_functional_groups.md"
```

### Example 3: Mixed Interaction

```
1. User uploads documents
2. User asks regular questions (ingestion happens automatically)
3. User asks: "Now quiz me on what we discussed"
4. System generates quiz from conversation + documents
5. User previews, edits, and downloads
6. User continues asking questions
```

## Technical Implementation

### Auto-Ingestion Logic

```python
if uploaded_files and not files_ingested:
    # Create temp directory
    # Save uploaded files to temp directory
    # Call system.ingest_directory(temp_path)
    # Mark files as ingested
    # Proceed with answering the question
```

### Quiz Detection

```python
def detect_quiz_request(message: str) -> bool:
    """Check if message contains quiz request keywords"""
    quiz_keywords = [
        "create a quiz", "generate a quiz", 
        "quiz me", "test me", ...
    ]
    return any(keyword in message.lower() for keyword in quiz_keywords)
```

### Quiz Grounding

```python
if chat_files_ingested:
    # Retrieve relevant passages using RAG
    hits = retriever.retrieve(Query(text=topic))
    
    # Format context from top 5 hits
    extra_context = format_hits(hits[:5])
    
    # Generate quiz with context
    quiz = system.generate_quiz(
        topic=topic,
        extra_context=extra_context  # Grounds quiz in documents
    )
```

## Session State Management

New session state variables for Chat & Learn:

| Variable | Purpose |
|----------|---------|
| `chat_uploaded_files` | List of uploaded file objects |
| `chat_files_ingested` | Boolean flag - whether files have been ingested |
| `chat_quiz_preview` | Quiz object for preview/edit |
| `chat_quiz_markdown` | Markdown string of current quiz |
| `chat_quiz_edit_mode` | Boolean - edit mode vs preview mode |

## Benefits Over Previous Approach

### Before (Old Temporary Context):
- Documents passed as `extra_context` string
- Not persisted in vector store
- No semantic retrieval
- Lost when session cleared
- Limited to short documents (token limits)

### After (New Auto-Ingestion):
- Documents ingested into vector store
- Full RAG retrieval pipeline
- Persistent across questions
- Handles large documents via chunking
- Semantic search for relevant passages

## Legacy Features (Preserved)

The old "Quick Quiz Tools" are still available in a collapsible expander for backward compatibility:
- Manual quiz topic input
- Question count slider
- Generate button

These remain functional but don't leverage the new grounding capabilities.

## Future Enhancements

Potential improvements:
1. **Batch ingestion feedback**: Show per-file ingestion status
2. **Smart re-ingestion**: Detect if same file uploaded twice
3. **Quiz difficulty**: Allow user to specify difficulty level
4. **Multi-modal support**: Images in quiz questions
5. **Quiz templates**: Predefined quiz formats (e.g., SAT-style, AP-style)

## Testing Checklist

- [ ] Upload 1 PDF, ask question → auto-ingest works
- [ ] Upload 3 files, ask question → all ingested
- [ ] Ask follow-up questions → no re-ingestion
- [ ] Request quiz via "Quiz me on X" → detected
- [ ] Generated quiz shows retrieval indicator
- [ ] Preview mode renders markdown correctly
- [ ] Edit mode allows modifications
- [ ] Download button creates valid .md file
- [ ] Clear button removes quiz
- [ ] Request quiz without uploads → works (falls back to general knowledge)

---

**Implementation Date**: October 24, 2025  
**Author**: AI Tutor Development Team  
**Version**: 2.0


