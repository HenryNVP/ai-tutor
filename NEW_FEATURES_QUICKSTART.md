# 🚀 New Features Quick Start Guide

## What's New?

Your AI Tutor now has **3 powerful tabs** with advanced corpus management and quiz generation capabilities!

---

## 🎯 Quick Start: 3 Minutes to Your First Grounded Quiz

### Step 1: Start the App (30 seconds)
```bash
cd /home/henry/Projects/ai-tutor
streamlit run apps/ui.py
```
Open browser to: http://localhost:8501

### Step 2: Ingest Documents (1 minute)
1. Click **📚 Corpus Management** tab
2. Click "Browse files" under "Upload & Ingest Documents"
3. Select PDFs from `data/raw/` (e.g., physics textbooks)
4. Click **🚀 Ingest Files into Vector Store**
5. Wait for success message

### Step 3: Analyze Corpus (30 seconds)
1. Click **🔍 Analyze Corpus** button
2. View statistics and domain distribution
3. Expand "Sample Topics Coverage" to preview content

### Step 4: Generate Quiz (1 minute)
1. Click **📝 Quiz Builder** tab
2. Enter topic: `"Newton's Laws"`
3. Ensure **"Ground quiz in retrieved passages"** is checked
4. Click **✨ Generate Quiz**
5. See message: "Retrieved 5 relevant passages from corpus"

### Step 5: Export Quiz (30 seconds)
1. Review preview (correct answers marked with ✅)
2. Optional: Click **✏️ Edit Quiz** to modify
3. Click **⬇️ Download as Markdown**
4. File saved: `quiz_newtons_laws.md`

**Done!** You now have a quiz grounded in your actual course materials.

---

## 📚 New Tab Overview

### Tab 1: 💬 Chat & Learn
**What's Changed:** Nothing! Same great chat experience.
- Ask questions with citations
- Take embedded quizzes
- View progress feedback

### Tab 2: 📚 Corpus Management (NEW!)
**What It Does:** Manage your permanent knowledge base.

**Features:**
- 📤 Upload multiple PDFs/MD/TXT simultaneously
- 🔄 Process and embed documents automatically
- 📊 View corpus statistics (docs, chunks, domains)
- 📈 See domain distribution with visual progress bars
- 📑 List all documents with IDs
- 🎯 Preview random topic samples

**When to Use:**
- Adding new textbooks to the system
- Checking what content is available
- Analyzing topic coverage gaps

### Tab 3: 📝 Quiz Builder (NEW!)
**What It Does:** Create downloadable quizzes from your corpus.

**Features:**
- 🎯 Generate quizzes on any topic
- ⚙️ Adjust questions (3-8) and difficulty
- 📚 Ground questions in retrieved passages
- 👁️ Preview with answers marked
- ✏️ Edit in markdown format
- ⬇️ Download as `.md` file

**When to Use:**
- Creating practice assessments
- Generating study materials
- Exporting quizzes for students
- Building quiz banks

---

## 🎓 Common Use Cases

### Use Case 1: Building a Physics Course
```
1. Collect physics PDFs (textbooks, lecture notes)
2. Go to Corpus Management → Upload all files
3. Ingest into vector store
4. Analyze to verify coverage
5. Result: Permanent physics knowledge base
```

### Use Case 2: Weekly Quiz Creation
```
1. Go to Quiz Builder tab
2. Enter this week's topic: "Thermodynamics"
3. Enable "Ground in corpus"
4. Generate → System retrieves relevant passages
5. Preview → Edit if needed
6. Download → Share with students
7. Repeat for next topic
```

### Use Case 3: Student Self-Study
```
1. Student asks question in Chat tab
2. Gets answer with citations
3. Clicks "Generate quiz" for practice
4. Takes quiz on same topic
5. Reviews explanations for wrong answers
6. Asks follow-up questions
7. Loop continues
```

---

## 🔑 Key Features Explained

### ✨ Grounded Quiz Generation

**What it means:** Quiz questions are based on actual passages from your textbooks, not just general knowledge.

**How it works:**
1. You enter a topic (e.g., "momentum")
2. System retrieves top-5 most relevant passages from vector store
3. LLM generates questions using those passages as context
4. Result: Questions tied to your specific curriculum

**Benefits:**
- ✅ Accuracy: Questions match your teaching materials
- ✅ Relevance: Covers exactly what you taught
- ✅ Citations: Each question includes references
- ✅ Trust: Students can verify in textbooks

### 📊 Corpus Analysis

**What it shows:**
- **Total Documents**: Number of unique files ingested
- **Total Chunks**: Number of searchable segments (500 tokens each)
- **Domain Distribution**: Breakdown by subject (math/physics/cs/general)
- **Sample Topics**: Random previews of content

**Why it matters:**
- Verify ingestion completed successfully
- Check coverage across domains
- Identify gaps in content
- Monitor corpus growth over time

### ✏️ Edit Before Export

**Why it's useful:**
- Fix formatting issues
- Add custom instructions
- Adjust difficulty on-the-fly
- Localize language
- Add school-specific context

**How to use:**
1. Generate quiz
2. Click "Edit Quiz"
3. Modify markdown text
4. Switch to "Preview" to verify
5. Download updated version

---

## 📁 File Locations

### Ingested Content
- **Vector Store**: `data/vector_store/embeddings.npy`
- **Metadata**: `data/vector_store/metadata.json`
- **Chunks**: `data/processed/chunks.jsonl`

### Generated Quizzes
- Downloads to your browser's default download folder
- Filename format: `quiz_{topic}.md`

### Source Documents
- Original files: `data/raw/`
- Not modified during ingestion

---

## 🛠️ Technical Notes

### Reuses Existing Components
All new features leverage the existing codebase:
- ✅ Same ingestion pipeline as CLI
- ✅ Same vector store as Q&A
- ✅ Same retriever for all searches
- ✅ Same quiz service everywhere

**Benefit:** Consistency and reliability across all features.

### Performance Expectations
- **Ingestion**: ~50 pages/minute (CPU-dependent)
- **Analysis**: <2 seconds for 1000 chunks
- **Quiz Generation**: 5-10 seconds
- **Vector Search**: <100ms

### Storage Requirements
- **Per Document**: ~2KB per chunk of text
- **Typical Textbook**: 200-400 chunks = ~1MB
- **10 Textbooks**: ~10MB total

---

## 🐛 Troubleshooting

### "No documents in corpus" after ingestion
**Problem:** Ingestion failed silently  
**Solution:** Check "Last Ingestion Result" for errors. Common issues:
- PDF is scanned image (needs OCR)
- File is corrupted
- Insufficient disk space

**Fix:** Re-upload valid text-based PDFs

### Quiz not using corpus content
**Problem:** "Ground in corpus" not working  
**Solution:** 
1. Verify corpus has relevant content (check analysis)
2. Try broader topic terms
3. Ensure vector store is loaded (restart if needed)

### Download button not appearing
**Problem:** Quiz state not set  
**Solution:** Generate quiz first, then download button appears

### Indentation errors in downloaded quiz
**Problem:** Markdown formatting issues  
**Solution:** Use "Edit Quiz" to fix formatting before download

---

## 📖 Documentation

Full documentation available in `docs/`:
- **`corpus_management_features.md`**: Complete feature guide
- **`ui_architecture.md`**: Technical architecture
- **`FEATURE_SUMMARY.md`**: Implementation details

---

## 🎉 Summary

You now have a **professional-grade corpus management system** and **advanced quiz builder** integrated into your AI Tutor!

### What You Can Do:
✅ Build permanent knowledge bases from PDFs  
✅ Analyze content coverage  
✅ Generate quizzes grounded in your materials  
✅ Preview and edit before sharing  
✅ Export to markdown format  
✅ Track student progress  

### Next Steps:
1. Ingest your course materials
2. Generate your first quiz
3. Share with students
4. Iterate and improve

**Happy Teaching! 🎓**

---

## 🤝 Need Help?

- **Feature Requests**: Open GitHub issue
- **Bug Reports**: Check logs in `logs/` directory
- **Questions**: Review documentation in `docs/`

Streamlit app running at: **http://localhost:8501**


