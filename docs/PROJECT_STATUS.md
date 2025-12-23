# AI Tutor - Project Status

## Current Implementation

### Architecture
- **Single Collection Vector Store**: All documents stored in `ai_tutor_master` collection (ChromaDB)
- **Agent-First Design**: Orchestrator routes to specialized agents (QA, Quiz, Note, Visualization, Web, Ingestion)
- **Source-Filtered Retrieval**: Pre-filtering via ChromaDB `where` clause for uploaded documents (320x faster)
- **Full Document Retrieval**: `fetch_full_document` tool retrieves all chunks sequentially for summaries
- **Session Management**: SQLite-based, one session per learner (simplified, no rotation/pruning)

### Key Features
- **Document Ingestion**: PDF/TXT/MD → chunking → embeddings → ChromaDB storage
- **Q&A with Citations**: Retrieval-augmented generation from local documents
- **Lesson Notes Generation**: Automatic note creation from uploaded documents
- **Quiz Generation**: 3-40 questions from documents with interactive UI
- **Data Visualization**: CSV upload → natural language plotting → matplotlib code generation
- **Generated Files Manager**: Track, preview, download notes/quizzes/charts/code

### Retrieval System
- **Vector Store**: ChromaDB with single `ai_tutor_master` collection
- **Embeddings**: `all-MiniLM-L6-v2` (384 dimensions)
- **Filtering**: Pre-query filtering by `source_path` with fallback to post-filtering for temp paths
- **Path Normalization**: Centralized utility (`path_utils.py`) handles temp paths, `data/uploads/`, `data/raw/`

### File Management
- **Uploaded Files**: Stored in `data/uploads/`, ingested, then cleaned up
- **Generated Files**: Organized in `data/generated/` (quizzes/, code/, visualizations/)
- **Session Files**: Only files generated in current session appear in UI

### Agent Workflows
- **QA Agent**: Uses `retrieve_local_context` for semantic search
- **Note Agent**: Uses `fetch_full_document` for summaries, `retrieve_local_context` for topic research
- **Quiz Agent**: Uses `generate_quiz` tool only (no direct quiz generation in chat)
- **Visualization Agent**: Generates matplotlib code from CSV data

## Remaining Issues

### Medium Priority

**7. Error Messages Could Be More Actionable**
- Location: `src/ai_tutor/services/tutor_service.py`
- Issue: Error messages are verbose but may not help users fix issues
- Recommendation: Provide specific next steps and diagnostic commands

**8. No Rate Limiting on API Endpoints**
- Location: `apps/api.py`
- Issue: No protection against abuse or DoS
- Recommendation: Add rate limiting middleware per user/endpoint

**9. File Cleanup Race Condition**
- Location: `apps/api.py`
- Issue: Files cleaned up immediately; partial failures may leave orphaned files
- Recommendation: Use transaction-like pattern or auto-cleaning temp directory

### Low Priority

**11. No Migration Tool for Legacy Collections**
- Issue: Users with old domain-based collections need manual re-ingestion
- Recommendation: Create migration script to copy chunks to master collection

**12. Limited Testing Coverage**
- Issue: No automated tests for critical paths (fetch_full_document, path matching)
- Recommendation: Add unit and integration tests for retrieval and path matching

**13. No Monitoring/Observability**
- Issue: Limited visibility into system performance and errors
- Recommendation: Add metrics, structured logging, health check endpoints

**14. Context Window Management**
- Location: `src/ai_tutor/services/tutor_service.py`
- Issue: Pre-retrieval can retrieve up to 50 passages, may exceed context window
- Recommendation: Calculate token count and truncate if needed

## Summary

**Completed**: Single collection architecture, full document retrieval, pre-query filtering, path normalization, note generation, quiz improvements, file management

**Remaining**: Error message improvements, rate limiting, file cleanup, migration tool, testing, monitoring, context window management

