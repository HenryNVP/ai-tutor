# Remaining Issues After Refactor

## Summary

After the refactor, the system is significantly improved, but several issues remain that should be addressed.

## 🔴 Critical Issues

### 1. Documentation Inconsistencies ✅ FIXED

**Location:** `docs/BACKEND_SUMMARY.md`

**Status:** ✅ Fixed - Updated documentation to reflect single `ai_tutor_master` collection architecture.

**Changes Made:**
- Updated Vector Store section to describe single master collection
- Removed domain collection references
- Updated performance optimizations section
- Fixed documentation links

---

### 2. Hardcoded Path Variations in `fetch_full_document` ✅ FIXED

**Location:** `src/ai_tutor/retrieval/chroma_store.py` and `src/ai_tutor/services/tutor_service.py`

**Status:** ✅ Fixed - Removed all hardcoded CMPE249-specific paths.

**Changes Made:**
- Removed hardcoded CMPE249 folder paths from `fetch_full_document`
- Removed hardcoded lecture pattern matching from `tutor_service.py`
- Now relies on fuzzy matching fallback for path variations
- More general solution that works for any course/folder structure

---

### 3. Performance Issue: Fuzzy Matching Loads All Chunks ✅ FIXED

**Location:** `src/ai_tutor/retrieval/chroma_store.py:607`

**Status:** ✅ Fixed - Reduced limit from 10000 to 2000 chunks.

**Changes Made:**
- Changed `limit=10000` to `limit=2000` (FUZZY_MATCH_LIMIT constant)
- Added comment explaining the limit choice
- Reduces memory usage by 80% for fuzzy matching
- Still sufficient to find documents in most cases

---

## 🟠 High Priority Issues

### 4. Complex Filename Variation Logic in Pre-Retrieval

**Location:** `src/ai_tutor/services/tutor_service.py:511-545`

**Problem:** Very complex filename variation logic with hardcoded paths and patterns.

**Issues:**
- Hardcoded CMPE249 paths (line 534-535)
- Complex lecture number extraction (line 537-545)
- Duplicated logic with `fetch_full_document`
- Maintenance burden

**Recommendation:**
- Extract to shared utility function
- Remove hardcoded paths
- Simplify to common patterns only

---

### 5. Legacy Domain Collections Code Still Present

**Location:** `src/ai_tutor/retrieval/chroma_store.py`

**Problem:** Code still supports `use_domain_collections=True` mode, adding complexity.

**Impact:**
- Unused code paths
- Increased maintenance burden
- Confusion about which mode is active

**Recommendation:**
- Remove domain collections support entirely (breaking change)
- Or clearly document it as legacy-only
- Update all references to single collection

---

### 6. Note Agent Still Taking Too Long to Save

**Location:** `src/ai_tutor/agents/note.py:148-157`

**Problem:** Despite instructions, note agent may still regenerate notes when asked to save.

**Current Instructions:**
- Tells agent to check conversation history
- But agent may not have easy access to previous messages
- Could still trigger retrieval/regeneration

**Recommendation:**
- Pass previous notes explicitly in prompt when saving
- Or implement a dedicated "save_notes" tool that takes content directly
- Add timeout handling for long operations

---

## 🟡 Medium Priority Issues

### 7. Error Messages Could Be More Actionable

**Location:** `src/ai_tutor/services/tutor_service.py:640-654`

**Problem:** Error messages are verbose but may not help users fix the issue.

**Recommendation:**
- Provide specific next steps
- Include diagnostic commands users can run
- Link to troubleshooting guide

---

### 8. No Rate Limiting on API Endpoints

**Location:** `apps/api.py`

**Problem:** No rate limiting on `/sessions/{learner_id}/events` or `/ingest` endpoints.

**Impact:**
- Could be abused
- No protection against DoS
- Resource exhaustion risk

**Recommendation:**
- Add rate limiting middleware
- Per-user limits
- Per-endpoint limits

---

### 9. File Cleanup Race Condition

**Location:** `apps/api.py:357-365`

**Problem:** Files are cleaned up immediately after ingestion, but if ingestion fails partially, some files may remain.

**Current Code:**
```python
# Clean up after ingestion
for saved_path in saved_paths:
    if saved_path.exists():
        saved_path.unlink()
```

**Recommendation:**
- Use transaction-like pattern
- Only clean up on complete success
- Or use temp directory that auto-cleans

---

### 10. Source Path Normalization Inconsistency

**Location:** `src/ai_tutor/ingestion/chunker.py:63-84`

**Problem:** Complex normalization logic that may not handle all edge cases.

**Issues:**
- Multiple normalization rules
- May not match retrieval expectations
- Temp path detection relies on parent name pattern

**Recommendation:**
- Standardize on single normalization function
- Use consistent path format throughout
- Document expected path formats

---

## 🟢 Low Priority / Future Enhancements

### 11. No Migration Tool for Legacy Collections

**Problem:** Users with old domain-based collections need to manually re-ingest.

**Recommendation:**
- Create migration script
- Copy chunks from domain collections to master
- Preserve metadata

---

### 12. Limited Testing Coverage

**Problem:** No automated tests for critical paths like `fetch_full_document`, path matching, etc.

**Recommendation:**
- Add unit tests for path matching
- Integration tests for retrieval
- Test edge cases (temp paths, special characters, etc.)

---

### 13. No Monitoring/Observability

**Problem:** Limited visibility into system performance and errors.

**Recommendation:**
- Add metrics (retrieval time, hit rates, etc.)
- Structured logging
- Health check endpoints with diagnostics

---

### 14. Context Window Management

**Location:** `src/ai_tutor/services/tutor_service.py:579-583`

**Problem:** Pre-retrieval can retrieve up to 50 passages, which may exceed context window.

**Current:**
```python
max_passages=50,  # Include many passages for comprehensive context
```

**Recommendation:**
- Calculate token count
- Truncate if exceeds model context
- Or let agent handle truncation

---

## Summary by Priority

| Priority | Count | Issues |
|----------|-------|--------|
| 🔴 Critical | 3 | Documentation, hardcoded paths, fuzzy matching performance |
| 🟠 High | 3 | Complex filename logic, legacy code, note agent timeout |
| 🟡 Medium | 4 | Error messages, rate limiting, cleanup, normalization |
| 🟢 Low | 4 | Migration, testing, monitoring, context management |

## Recommended Action Plan

### Immediate (This Week)
1. ✅ Fix documentation inconsistencies
2. ✅ Remove hardcoded CMPE249 paths
3. ✅ Optimize fuzzy matching (limit/pagination)

### Short Term (This Month)
4. Refactor filename variation logic
5. Remove or document legacy domain collections
6. Improve note agent save performance

### Medium Term (Next Quarter)
7. Add rate limiting
8. Improve error messages
9. Add automated tests
10. Add monitoring/observability

