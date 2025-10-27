# Ingestion Pipeline Deduplication Behavior

## Quick Answer

**YES, but only partially.** The pipeline avoids duplicates **by filename**, not by content.

### Key Behaviors:

✅ **Re-ingesting the same filename** → Chunks are **updated** (not duplicated)  
⚠️ **Ingesting renamed copies** → Creates **duplicate content** (different doc_id)  
⚠️ **Ingesting files with same content but different names** → Creates **duplicates**

---

## How It Works

### 1. Document ID Generation

The `doc_id` is generated from the **filename stem** (name without extension):

```python
# In parsers.py
doc_id = path.stem

# Examples:
# "textbook.pdf" → doc_id = "textbook"
# "physics_vol1.pdf" → doc_id = "physics_vol1"
# "notes.md" → doc_id = "notes"
```

**Location:** `src/ai_tutor/ingestion/parsers.py`
- Line 31: TextParser
- Line 44: MarkdownParser  
- Line 73: PdfParser

### 2. Chunk ID Generation

Each chunk gets a deterministic ID based on:
- Document ID
- Chunk index (position in document)
- First 100 characters of chunk text

```python
# In chunker.py
def _hash_chunk(text: str, doc_id: str, index: int) -> str:
    digest = hashlib.sha1(f"{doc_id}:{index}:{text[:100]}".encode("utf-8")).hexdigest()
    return f"{doc_id}-{index}-{digest[:8]}"

# Example chunk_id:
# "textbook-0-a3f8b2d1"
# "textbook-1-c9e4f7a2"
```

**Location:** `src/ai_tutor/ingestion/chunker.py`, lines 11-14

### 3. Upsert (Update or Insert) Logic

When chunks are stored, the `ChunkJsonlStore` uses **upsert** semantics:

```python
# In jsonl_store.py
def upsert(self, chunks: Iterable[Chunk]) -> None:
    """Merge chunks into storage, replacing existing entries with matching IDs."""
    existing = {chunk.metadata.chunk_id: chunk for chunk in self.load()}
    for chunk in chunks:
        existing[chunk.metadata.chunk_id] = chunk  # ← Overwrites if ID exists
    # Write back to disk
```

**Location:** `src/ai_tutor/storage/jsonl_store.py`, lines 31-39

**Result:** Chunks with the same ID are **replaced**, not duplicated.

---

## Deduplication Scenarios

### ✅ Scenario 1: Re-ingesting the Same File

**Setup:**
```bash
# First ingestion
ingest("data/raw/physics_textbook.pdf")
# Result: 250 chunks created

# Later, re-ingest the same file
ingest("data/raw/physics_textbook.pdf")
# Result: 250 chunks updated (not added)
```

**What Happens:**
1. Same filename → Same `doc_id` ("physics_textbook")
2. Same content → Same `chunk_id` for each chunk
3. Upsert → Old chunks **overwritten**
4. Total chunks in system: **250** (not 500)

**Verdict:** ✅ **Deduplication works perfectly**

---

### ⚠️ Scenario 2: Ingesting a Renamed Copy

**Setup:**
```bash
# First ingestion
ingest("data/raw/physics_textbook.pdf")
# Result: 250 chunks (doc_id = "physics_textbook")

# Copy and rename the file
cp data/raw/physics_textbook.pdf data/raw/physics_textbook_v2.pdf

# Ingest the renamed copy
ingest("data/raw/physics_textbook_v2.pdf")
# Result: 250 NEW chunks (doc_id = "physics_textbook_v2")
```

**What Happens:**
1. Different filename → Different `doc_id`
2. Same content → Different `chunk_id` (because doc_id is different)
3. Upsert → Treats as **new chunks**
4. Total chunks in system: **500** (duplicate content!)

**Verdict:** ⚠️ **Deduplication FAILS - creates duplicates**

---

### ⚠️ Scenario 3: Multiple Files with Overlapping Content

**Setup:**
```bash
# Ingest chapter 1
ingest("data/raw/chapter1.pdf")
# Result: 100 chunks

# Ingest full textbook (includes chapter 1)
ingest("data/raw/full_textbook.pdf")
# Result: 500 chunks (includes duplicate content from chapter 1)
```

**What Happens:**
1. Different filenames → Different `doc_id`s
2. Overlapping content → Different `chunk_id`s
3. Total chunks: **600** (with duplicate content)

**Verdict:** ⚠️ **Deduplication FAILS - creates duplicates**

---

### ✅ Scenario 4: Updating a Document

**Setup:**
```bash
# First version
ingest("data/raw/syllabus.md")
# Result: 50 chunks

# Edit the file, then re-ingest
ingest("data/raw/syllabus.md")
# Result: 50 chunks updated
```

**What Happens:**
1. Same filename → Same `doc_id`
2. Modified content → Same `chunk_id`s (deterministic from doc_id + index)
3. Upsert → **Replaces old chunks with new versions**
4. Total chunks: **50** (updated, not duplicated)

**Verdict:** ✅ **Works as intended - updates existing content**

---

## Why This Design?

### Pros:
1. **Simple and Fast**: No content hashing required
2. **Deterministic**: Same file always produces same IDs
3. **Update-Friendly**: Easy to update existing documents
4. **Low Overhead**: No need to compare full file contents

### Cons:
1. **Filename-Dependent**: Renames create duplicates
2. **No Content Deduplication**: Doesn't detect identical content in different files
3. **Manual Management**: User must ensure unique filenames

---

## Best Practices

### ✅ DO:

1. **Use Unique, Descriptive Filenames**
   ```
   ✅ physics_vol1.pdf
   ✅ calculus_chapter3.pdf
   ✅ chemistry_2024_edition.pdf
   ```

2. **Keep Original Filenames**
   - If you need to update a document, use the same filename

3. **Organize by Subject**
   ```
   data/raw/
   ├── physics/
   │   ├── textbook_vol1.pdf
   │   └── textbook_vol2.pdf
   ├── math/
   │   └── calculus_textbook.pdf
   ```

4. **Check Corpus Before Adding**
   - Use "Analyze Corpus" tab to see existing documents
   - Avoid adding files with similar names

### ❌ DON'T:

1. **Don't Use Generic Names**
   ```
   ❌ textbook.pdf (ambiguous)
   ❌ chapter1.pdf (which book?)
   ❌ notes.pdf (from what course?)
   ```

2. **Don't Rename and Re-ingest**
   ```
   ❌ Ingesting both:
       - physics_textbook.pdf
       - physics_textbook_copy.pdf
   ```

3. **Don't Ingest Overlapping Content**
   ```
   ❌ Ingesting both:
       - chapter3.pdf
       - full_textbook.pdf (includes chapter 3)
   ```

---

## Workarounds for True Deduplication

If you need content-based deduplication, here are options:

### Option 1: Manual Filename Management
```bash
# Before ingestion, check for duplicates by name
ls data/raw/ | grep "physics"

# Remove or rename before ingesting
```

### Option 2: Content Hashing (Custom Script)
```python
import hashlib
from pathlib import Path

def get_file_hash(path: Path) -> str:
    """Get SHA256 hash of file content."""
    return hashlib.sha256(path.read_bytes()).hexdigest()

# Before ingestion
seen_hashes = {}
for file in Path("data/raw").glob("*.pdf"):
    file_hash = get_file_hash(file)
    if file_hash in seen_hashes:
        print(f"Duplicate: {file} matches {seen_hashes[file_hash]}")
    else:
        seen_hashes[file_hash] = file
```

### Option 3: Database-Level Deduplication
```python
# Check if doc_id already exists before ingesting
existing_chunks = system.chunk_store.load()
existing_doc_ids = {chunk.metadata.doc_id for chunk in existing_chunks}

for file in files_to_ingest:
    doc_id = file.stem
    if doc_id in existing_doc_ids:
        print(f"Skipping {file} - already ingested")
        continue
    # Proceed with ingestion
```

---

## Code References

### Where doc_id is Set:
- `src/ai_tutor/ingestion/parsers.py`
  - Line 31: `doc_id=path.stem` (TextParser)
  - Line 44: `doc_id=path.stem` (MarkdownParser)
  - Line 73: `doc_id=path.stem` (PdfParser)

### Where chunk_id is Generated:
- `src/ai_tutor/ingestion/chunker.py`
  - Line 11-14: `_hash_chunk()` function
  - Line 41: Called during chunking

### Where Upsert Happens:
- `src/ai_tutor/storage/jsonl_store.py`
  - Line 31-39: `upsert()` method

### Pipeline Flow:
- `src/ai_tutor/ingestion/pipeline.py`
  - Line 230: `parse_path()` (generates doc_id)
  - Line 242: `chunk_document()` (generates chunk_ids)
  - Line 257: `chunk_store.upsert()` (deduplicates by chunk_id)

---

## Summary Table

| Scenario | Same Filename? | Duplicate Created? | Behavior |
|----------|----------------|-------------------|----------|
| Re-ingest same file | ✅ Yes | ❌ No | Chunks updated |
| Ingest renamed copy | ❌ No | ✅ Yes | New doc_id → duplicate |
| Update file content | ✅ Yes | ❌ No | Chunks replaced |
| Different files, same content | ❌ No | ✅ Yes | No detection |
| Chapter + full book | ❌ No | ✅ Yes | Overlapping content duplicated |

---

## Recommendation

**For Production Use:**

1. **Implement a pre-ingestion check** to prevent accidental duplicates:
   ```python
   def should_ingest(file: Path, system: TutorSystem) -> bool:
       """Check if file should be ingested."""
       existing_chunks = system.chunk_store.load()
       existing_doc_ids = {c.metadata.doc_id for c in existing_chunks}
       return file.stem not in existing_doc_ids
   ```

2. **Add warning in UI** when doc_id already exists

3. **Track ingestion history** with timestamps

4. **Consider adding content-based deduplication** for production systems

---

## Future Improvements

Potential enhancements for better deduplication:

1. **Content-Based doc_id**:
   ```python
   # Instead of filename
   doc_id = hashlib.sha256(document.text.encode()).hexdigest()[:16]
   ```

2. **Similarity Detection**:
   - Check if new chunks are similar to existing ones
   - Warn user before creating duplicates

3. **Ingestion Metadata**:
   - Track when files were ingested
   - Store original filenames
   - Allow rollback of ingestion

4. **UI Enhancements**:
   - Show list of ingested files before upload
   - Highlight potential duplicates
   - Provide "replace" vs "add" options


