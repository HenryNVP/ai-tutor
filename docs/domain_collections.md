# Domain-Based Collections in ChromaDB

## Overview

This document describes the domain-based collection system for ChromaDB, which organizes documents into separate collections by academic domain (math, physics, cs, chemistry, biology, general). The system supports:

- **Primary and secondary domain metadata**: Documents can have a primary domain and up to 2 secondary domains
- **Predefined categories and tags**: Each domain has predefined tags and keywords for classification
- **AI-powered domain detection**: Automatic domain classification for new documents using LLM
- **Domain-based collections**: Separate ChromaDB collections per domain for efficient organization

## Architecture

### Domain Classification

The system uses a two-stage classification approach:

1. **Rule-based classification** (fast): Analyzes filename and content keywords
2. **AI-based classification** (accurate): Uses LLM to analyze document content

### Collections Structure

Each domain gets its own ChromaDB collection:
- `ai_tutor_math` - Mathematics documents
- `ai_tutor_physics` - Physics documents
- `ai_tutor_cs` - Computer Science documents
- `ai_tutor_chemistry` - Chemistry documents
- `ai_tutor_biology` - Biology documents
- `ai_tutor_general` - General/uncategorized documents

### Metadata Structure

Each chunk stores domain metadata:
- `primary_domain`: Main domain (required)
- `secondary_domains`: Related domains (0-2 domains, comma-separated)
- `domain_tags`: Specific topics within the domain (comma-separated)
- `domain_confidence`: Classification confidence (0.0-1.0)

## Usage

### Basic Ingestion

The ingestion pipeline automatically classifies documents:

```python
from pathlib import Path
from ai_tutor.config import load_settings
from ai_tutor.ingestion.embeddings import EmbeddingClient
from ai_tutor.ingestion.pipeline import IngestionPipeline
from ai_tutor.retrieval.factory import create_vector_store
from ai_tutor.storage import ChunkJsonlStore

# Load settings
settings = load_settings()

# Initialize components
embedder = EmbeddingClient(settings.embeddings)
vector_store = create_vector_store(settings.paths.vector_store_dir)
chunk_store = ChunkJsonlStore(settings.paths.chunks_index)

# Create pipeline (AI detection enabled by default)
pipeline = IngestionPipeline(
    settings=settings,
    embedder=embedder,
    vector_store=vector_store,
    chunk_store=chunk_store,
    use_ai_domain_detection=True  # Enable AI classification
)

# Ingest documents
documents = [Path("data/raw/calculus_textbook.pdf")]
result = pipeline.ingest_paths(documents)

# Check classification results
for doc in result.documents:
    print(f"{doc.metadata.source_path.name}:")
    print(f"  Primary: {doc.metadata.primary_domain}")
    print(f"  Secondary: {doc.metadata.secondary_domains}")
    print(f"  Tags: {doc.metadata.domain_tags}")
    print(f"  Confidence: {doc.metadata.domain_confidence:.2f}")
```

### Manual Domain Classification

You can also classify documents manually:

```python
from ai_tutor.ingestion.domain_classifier import DomainClassifier
from ai_tutor.agents.llm_client import LLMClient
from ai_tutor.config import load_settings

settings = load_settings()
llm_client = LLMClient(settings.model)

classifier = DomainClassifier(
    llm_client=llm_client,
    use_ai_detection=True
)

# Classify from path (fast, rule-based)
path = Path("data/raw/physics_textbook.pdf")
classification = classifier.classify_from_path(path)

# Classify from content (accurate, AI-based)
with open(path, 'r') as f:
    text = f.read()
classification = classifier.classify_from_content(text, filename=path.name)

print(f"Primary: {classification.primary_domain}")
print(f"Secondary: {classification.secondary_domains}")
print(f"Tags: {classification.tags}")
print(f"Confidence: {classification.confidence}")
```

### Domain-Based Retrieval

Search within specific domains:

```python
from ai_tutor.data_models import Query
from ai_tutor.retrieval.retriever import Retriever

# Create retriever
retriever = Retriever(config, embedder, vector_store)

# Search in specific domain
query = Query(
    text="What is quantum mechanics?",
    domain="physics"  # Only search physics collection
)
hits = retriever.retrieve(query)

# Search across all domains
# (requires direct access to ChromaVectorStore)
if hasattr(vector_store, 'search'):
    hits = vector_store.search(
        embedding=embedder.embed_query("What is machine learning?"),
        top_k=10,
        search_all_domains=True  # Search all collections
    )
```

### Predefined Domains and Tags

The system includes predefined domain categories:

**Mathematics** (`math`):
- Tags: algebra, calculus, geometry, trigonometry, statistics, probability, linear-algebra, etc.
- Keywords: equation, theorem, proof, derivative, integral, matrix, vector, function, etc.

**Physics** (`physics`):
- Tags: mechanics, thermodynamics, electromagnetism, optics, quantum-mechanics, relativity, etc.
- Keywords: force, energy, momentum, wave, particle, field, electric, magnetic, etc.

**Computer Science** (`cs`):
- Tags: programming, algorithms, data-structures, software-engineering, machine-learning, etc.
- Keywords: algorithm, programming, code, software, data structure, computer, network, etc.

**Chemistry** (`chemistry`):
- Tags: organic-chemistry, inorganic-chemistry, physical-chemistry, biochemistry, etc.
- Keywords: molecule, reaction, compound, element, bond, catalyst, etc.

**Biology** (`biology`):
- Tags: cell-biology, genetics, evolution, ecology, anatomy, physiology, etc.
- Keywords: cell, DNA, gene, organism, evolution, ecosystem, protein, etc.

**General** (`general`):
- Default category for uncategorized documents

## Configuration

### Enable/Disable Domain Collections

Domain-based collections are enabled by default. To use a single collection (legacy mode):

```python
from ai_tutor.retrieval.chroma_store import ChromaVectorStore

# Legacy mode: single collection
vector_store = ChromaVectorStore(
    directory=Path("data/vector_store"),
    collection_name="ai_tutor_chunks",
    use_domain_collections=False
)
```

### Disable AI Detection

To use only rule-based classification (faster, less accurate):

```python
pipeline = IngestionPipeline(
    settings=settings,
    embedder=embedder,
    vector_store=vector_store,
    chunk_store=chunk_store,
    use_ai_domain_detection=False  # Rule-based only
)
```

## Implementation Details

### Domain Classifier

The `DomainClassifier` class provides:

- `classify_from_path(path)`: Fast rule-based classification from filename
- `classify_from_content(text, filename, initial_classification)`: AI-based classification from content
- `get_collection_name(primary_domain)`: Get ChromaDB collection name for a domain

### ChromaVectorStore Updates

The `ChromaVectorStore` class now:

- Maintains separate collections per domain
- Routes chunks to appropriate collections based on `primary_domain`
- Supports domain-filtered search
- Supports cross-domain search (`search_all_domains=True`)

### Data Models

Updated data models include:

- `DocumentMetadata`: `primary_domain`, `secondary_domains`, `domain_tags`, `domain_confidence`
- `ChunkMetadata`: Same domain fields (inherited from document)

Legacy `domain` field is maintained for backward compatibility.

## Migration

### Existing Data

Existing data in a single collection will continue to work. To migrate to domain-based collections:

1. Re-ingest documents (they will be automatically classified and routed to domain collections)
2. Or manually migrate chunks using the domain metadata

### Backward Compatibility

- Legacy `domain` field is preserved
- Single collection mode still supported via `use_domain_collections=False`
- Existing code using `domain` field continues to work

## Examples

### Example 1: Ingesting a Physics Textbook

```python
# File: data/raw/collegephysicsvol1.pdf
result = pipeline.ingest_paths([Path("data/raw/collegephysicsvol1.pdf")])

# Result:
# Primary domain: physics
# Secondary domains: []
# Tags: ['mechanics', 'thermodynamics', 'wave-mechanics']
# Confidence: 0.92
# Collection: ai_tutor_physics
```

### Example 2: Ingesting a Math-Physics Hybrid Document

```python
# File: data/raw/mathematical_physics.pdf
result = pipeline.ingest_paths([Path("data/raw/mathematical_physics.pdf")])

# Result:
# Primary domain: math
# Secondary domains: ['physics']
# Tags: ['calculus', 'differential-equations', 'mechanics']
# Confidence: 0.85
# Collection: ai_tutor_math (primary domain)
```

### Example 3: User Upload with Auto-Detection

When a user uploads a document, the system automatically:

1. Parses the document
2. Classifies domain using AI (if enabled)
3. Routes to appropriate collection
4. Stores with full domain metadata

```python
# User uploads: "my_cs_notes.pdf"
# System automatically:
# - Detects primary domain: cs
# - Adds tags: ['programming', 'algorithms']
# - Routes to: ai_tutor_cs collection
# - Stores metadata for retrieval
```

## Troubleshooting

### AI Detection Not Working

If AI detection fails:
- Check that `OPENAI_API_KEY` is set
- Verify LLM configuration in settings
- System falls back to rule-based classification automatically

### Documents in Wrong Collection

If documents are misclassified:
- Check classification confidence scores
- Review domain tags to understand classification
- Manually re-classify if needed
- Adjust domain keywords/tags in `domain_classifier.py`

### Performance

- Rule-based classification: ~1ms per document
- AI-based classification: ~500-1000ms per document (depends on LLM)
- Use rule-based only for bulk ingestion if speed is critical

## Future Enhancements

Potential improvements:
- Custom domain definitions
- Domain-specific embedding models
- Multi-domain document support (store in multiple collections)
- Domain-based retrieval ranking
- Domain statistics and analytics

