# AI Tutor - Demo & Use Cases

## Quick Start

```bash
# Start the application
streamlit run apps/ui.py
```

The app opens with two tabs:
- **💬 Chat & Learn**: Interactive Q&A, quizzes, and visualizations
- **📚 Corpus Management**: Manage your knowledge base

---

## Use Case 1: Question Answering with Custom Documents

### Scenario
Student uploads course materials and asks questions about specific topics.

### Steps

1. **Upload Documents** (Sidebar)
   - Click "Upload Documents" section
   - Select PDFs, TXT, or MD files
   - Files: `Introduction_To_Computer_Science.pdf`, `Calculus_Volume_1.pdf`
   - System auto-ingests on first question

2. **Ask Questions** (Chat)
   ```
   User: "What is a binary search tree?"
   
   Assistant: [Retrieves from uploaded CS document]
   "A binary search tree (BST) is a data structure where each node has 
   at most two children, with left child < parent < right child..."
   
   📚 Retrieved 15 passages from Introduction To Computer Science
   Citations: Introduction To Computer Science (Page 145)
   ```

3. **Follow-up Questions**
   ```
   User: "How does it compare to a hash table?"
   
   Assistant: [Contextual answer with comparisons]
   Citations: Introduction To Computer Science (Page 145, 178)
   ```

### Features Demonstrated
- ✅ Document upload & auto-ingestion
- ✅ Source-filtered retrieval (320x faster)
- ✅ Context-aware answers
- ✅ Citation tracking

---

## Use Case 2: Quiz Generation from Documents

### Scenario
Teacher wants to create a quiz from uploaded course materials.

### Steps

1. **Upload Course Materials**
   - Upload: `collegephysicsvol1.pdf`
   - Wait for green checkmark

2. **Request Quiz** (Chat)
   ```
   User: "Create 10 questions about Newton's laws from the uploaded document"
   
   Assistant: [Generates quiz using source filtering]
   ✅ Found 50 passages from collegephysicsvol1.pdf
   
   📝 Quiz: Newton's Laws (Medium)
   
   1. Which of Newton's laws describes inertia?
      A) First Law
      B) Second Law
      C) Third Law
      D) Law of Universal Gravitation
   
   [... 9 more questions ...]
   ```

3. **Take Quiz**
   - Select answers using radio buttons
   - Click "Submit Quiz"
   - View results with explanations

4. **Download Quiz** (Markdown format)
   - Click "Edit and Download Quiz"
   - Edit questions if needed
   - Download as `.md` file

### Features Demonstrated
- ✅ Dynamic quiz generation (3-40 questions)
- ✅ Topic extraction from documents
- ✅ Interactive quiz interface
- ✅ Markdown export for sharing

---

## Use Case 3: Data Visualization

### Scenario
Student wants to visualize sales data for a business analytics assignment.

### Steps

1. **Upload CSV** (Sidebar)
   - Go to "📊 Data Visualization" section
   - Upload: `sales_2024.csv`
   - Preview shows: 12 rows × 3 columns (month, revenue, expenses)

2. **Request Visualization** (Chat)
   ```
   User: "plot revenue by month"
   
   Assistant: [Analyzes dataset, generates matplotlib code]
   ✅ Visualization created!
   
   [LINE CHART DISPLAYED]
   
   📝 View generated code ▼
   ```

3. **Multiple Visualizations**
   ```
   User: "create a bar chart comparing revenue and expenses"
   
   Assistant: [Generates grouped bar chart]
   [GROUPED BAR CHART DISPLAYED]
   ```

4. **View Generated Code**
   - Expand "📝 View generated code"
   - See Python code (matplotlib/seaborn)
   - Copy for reuse in own projects

### Features Demonstrated
- ✅ CSV upload & preview
- ✅ Natural language plotting
- ✅ Multiple chart types (line, bar, scatter, histogram, etc.)
- ✅ Code generation & display
- ✅ Plot persistence in chat history

---

## Use Case 4: Adaptive Learning Path

### Scenario
Student working through math curriculum with personalized difficulty adjustment.

### Steps

1. **Initial Question**
   ```
   User: "Explain derivatives"
   
   Assistant: [Provides explanation at medium difficulty]
   "A derivative represents the rate of change of a function..."
   ```

2. **Quiz Assessment**
   ```
   User: "Quiz me on derivatives"
   
   Assistant: [Generates 5-question quiz]
   Student scores: 2/5 (40%)
   ```

3. **Adaptive Response**
   ```
   Assistant: "Let me explain the fundamentals more clearly..."
   [Adjusts explanation style based on quiz performance]
   
   Would you like:
   - More practice problems?
   - A video resource?
   - Step-by-step examples?
   ```

4. **Progress Tracking**
   - System stores quiz results
   - Tracks learner profile (`s1`)
   - Adapts future explanations

### Features Demonstrated
- ✅ Personalized learning paths
- ✅ Quiz-based assessment
- ✅ Difficulty adaptation
- ✅ Progress tracking

---

## Use Case 5: Corpus Management

### Scenario
Librarian wants to build a searchable knowledge base from multiple documents.

### Steps

1. **Go to Corpus Management Tab**

2. **Ingest Documents**
   - Select directory: `data/raw/`
   - Click "Ingest Documents from Directory"
   - System processes: 7 PDFs → 1,234 chunks
   - Shows progress and statistics

3. **Inspect Corpus**
   - Click "Show Corpus Statistics"
   ```
   Total chunks: 1,234
   Total documents: 7
   Average chunk size: 512 tokens
   
   Documents:
   - Introduction To Computer Science (234 chunks)
   - Calculus Volume 1 (189 chunks)
   - College Physics Vol 1 (198 chunks)
   ...
   ```

4. **Test Retrieval**
   - Enter test query: "machine learning"
   - View retrieved chunks with relevance scores
   - Verify chunk quality

### Features Demonstrated
- ✅ Bulk document ingestion
- ✅ Corpus statistics
- ✅ Search testing
- ✅ Document management

---

## Use Case 6: Multi-Document Research

### Scenario
Graduate student researching across multiple textbooks.

### Steps

1. **Upload Multiple Documents**
   - Upload 3 PDFs: Physics, Chemistry, Math textbooks
   - Auto-ingest on first query

2. **Cross-Document Query**
   ```
   User: "How is calculus used in physics?"
   
   Assistant: [Retrieves from both Calculus and Physics books]
   
   "Calculus is fundamental to physics, particularly in:
   1. Kinematics: derivatives for velocity/acceleration
   2. Dynamics: integrals for work and energy
   3. Electromagnetism: Maxwell's equations..."
   
   📚 Retrieved 15 passages from 2 documents:
   - Calculus Volume 1 (8 passages)
   - College Physics Vol 1 (7 passages)
   ```

3. **Document-Specific Query**
   ```
   User: "What does the physics book say about momentum?"
   
   Assistant: [Filters to physics document only]
   📚 Found 8 passages from College Physics Vol 1
   ```

### Features Demonstrated
- ✅ Multi-document upload
- ✅ Cross-document retrieval
- ✅ Document filtering
- ✅ Source attribution

---

## Common Workflows

### 🎓 Student Workflow
1. Upload course PDFs → Ask questions → Take quiz → Review mistakes
2. Upload dataset → Request visualizations → Export plots for report
3. Practice problems → Get feedback → Track progress

### 👨‍🏫 Teacher Workflow
1. Upload textbook → Generate quiz → Edit questions → Download markdown
2. Test quiz → Review difficulty → Adjust parameters → Regenerate
3. Share markdown quiz with students

### 📊 Data Analyst Workflow
1. Upload CSV → Explore with questions ("what are the columns?")
2. Request multiple visualizations → Compare charts
3. View generated code → Adapt for own analysis

### 🔬 Researcher Workflow
1. Ingest papers → Search across documents
2. Ask synthesis questions → Get cross-document answers
3. Build comprehensive understanding

---

## Tips & Tricks

### Getting Better Answers
- **Be specific**: "Explain Newton's second law" vs "Explain physics"
- **Reference documents**: "According to the uploaded textbook..."
- **Ask follow-ups**: Build on previous context

### Quiz Generation
- **Specify count**: "Create 10 questions..." (supports 3-40)
- **Set topic**: "...about photosynthesis" (not just "from documents")
- **Set difficulty**: "Create easy/medium/hard questions"

### Visualizations
- **Name chart type**: "bar chart" not just "chart"
- **Specify columns**: "plot 'revenue' by 'month'"
- **Request comparisons**: "compare X and Y"

### Performance
- **Upload fewer files**: Start with 1-2 documents for faster processing
- **Use source filtering**: Mention "uploaded documents" for faster retrieval
- **Clear unused CSVs**: Remove old data to avoid confusion

---

## Troubleshooting

### Quiz Issues
**Problem**: Quiz is too generic  
**Solution**: Upload documents first, then request quiz about specific topic

**Problem**: Wrong number of questions  
**Solution**: Use exact phrasing: "Create 10 questions..." (not "create 10 quizzes")

### Visualization Issues
**Problem**: Plot doesn't appear  
**Solution**: Ensure CSV uploaded, use visualization keywords (plot, chart, graph)

**Problem**: Wrong chart type  
**Solution**: Be explicit: "bar chart" instead of just "show me"

### Document Issues
**Problem**: Documents not found  
**Solution**: Wait for green checkmark before asking questions

**Problem**: Slow retrieval  
**Solution**: Ask specifically about uploaded documents for source filtering

---

## Next Steps

Explore more:
- Try different document types (PDF, TXT, MD)
- Experiment with quiz difficulties
- Create various chart types
- Build your own corpus
- Track learning progress over time

For technical details, see `README.md` and `docs/presentation_report.md`.

