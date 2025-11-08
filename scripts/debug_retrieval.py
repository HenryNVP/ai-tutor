#!/usr/bin/env python3
"""Debug script to test retrieval for a specific query."""

import sys
import logging
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(name)s - %(message)s'
)

from ai_tutor.system import TutorSystem
from ai_tutor.config.loader import load_settings
from ai_tutor.data_models import Query

def main():
    """Test retrieval for Bernoulli equation."""
    print("=" * 80)
    print("DEBUG: Retrieval Test for 'Bernoulli equation'")
    print("=" * 80)
    
    # Load settings
    settings = load_settings()
    print(f"\nVector store directory: {settings.paths.vector_store_dir}")
    print(f"Retrieval top_k: {settings.retrieval.top_k}")
    
    # Initialize system
    print("\nInitializing TutorSystem...")
    system = TutorSystem.from_config()
    
    # Test query
    query_text = "What is Bernoulli equation?"
    print(f"\n{'='*80}")
    print(f"Query: {query_text}")
    print(f"{'='*80}\n")
    
    # Test retrieval directly
    query = Query(text=query_text)
    print("Calling retriever.retrieve()...")
    hits = system.tutor_agent.retriever.retrieve(query)
    
    print(f"\nTotal hits retrieved: {len(hits)}")
    
    if hits:
        print("\nTop hits:")
        for i, hit in enumerate(hits[:10], 1):
            print(f"\n{i}. Score: {hit.score:.4f}")
            print(f"   Title: {hit.chunk.metadata.title}")
            print(f"   Domain: {getattr(hit.chunk.metadata, 'primary_domain', hit.chunk.metadata.domain)}")
            print(f"   Doc ID: {hit.chunk.metadata.doc_id}")
            print(f"   Page: {hit.chunk.metadata.page}")
            print(f"   Text preview: {hit.chunk.text[:200]}...")
    else:
        print("\n❌ No hits found!")
        print("\nChecking vector store...")
        
        # Check vector store directly
        if hasattr(system.vector_store, 'client'):
            try:
                collections = system.vector_store.client.list_collections()
                print(f"\nCollections in database: {len(collections)}")
                for col in collections:
                    collection = system.vector_store.client.get_collection(col.name)
                    count = collection.count()
                    print(f"  - {col.name}: {count} documents")
            except Exception as e:
                print(f"Error checking collections: {e}")
    
    # Test with min_confidence filter
    min_confidence = 0.2
    print(f"\n{'='*80}")
    print(f"Filtering with min_confidence={min_confidence}")
    print(f"{'='*80}\n")
    
    filtered = [h for h in hits if h.score >= min_confidence]
    print(f"Filtered hits: {len(filtered)} (out of {len(hits)} total)")
    
    if filtered:
        print("\nFiltered hits:")
        for i, hit in enumerate(filtered[:5], 1):
            print(f"{i}. Score: {hit.score:.4f} - {hit.chunk.metadata.title}")
    else:
        print("\n❌ No hits above confidence threshold!")
        if hits:
            print(f"All {len(hits)} hits were below {min_confidence}")
            print("Top scores:")
            for i, hit in enumerate(hits[:5], 1):
                print(f"  {i}. {hit.score:.4f}")

if __name__ == "__main__":
    main()

