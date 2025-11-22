#!/usr/bin/env python3
"""
Quick script to ingest the CMPE249 folder.
"""
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ai_tutor.system import TutorSystem

def main():
    print("🔄 Initializing TutorSystem...")
    system = TutorSystem.from_config()
    
    directory = Path("data/raw/CMPE249Fa25Shared-2025")
    if not directory.exists():
        print(f"❌ Error: Directory not found: {directory}")
        print(f"   Current directory: {Path.cwd()}")
        return 1
    
    print(f"📂 Ingesting documents from: {directory}")
    print("   This may take a few minutes...\n")
    
    try:
        result = system.ingest_directory(directory)
        
        print("\n" + "="*60)
        print("✅ INGESTION COMPLETE")
        print("="*60)
        print(f"📄 Documents processed: {len(result.documents)}")
        print(f"📝 Chunks created: {len(result.chunks)}")
        print(f"⏭️  Files skipped: {len(result.skipped)}")
        
        if result.skipped:
            print(f"\n⚠️  Skipped files:")
            for skip in result.skipped:
                print(f"   - {skip}")
        
        # Show domain classification
        from collections import Counter
        domain_stats = Counter()
        for doc in result.documents:
            primary = getattr(doc.metadata, "primary_domain", doc.metadata.domain or "general")
            domain_stats[primary] += 1
        
        if domain_stats:
            print(f"\n📊 Domain Classification:")
            for domain, count in sorted(domain_stats.items()):
                print(f"   {domain}: {count} documents")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error during ingestion: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

