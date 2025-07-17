#!/usr/bin/env python3
"""
Quick start guide for the Enhanced Document Intelligence System
"""
import os
import sys

def print_banner():
    banner = """
🚀 Enhanced Document Intelligence System
=========================================

Key Improvements Made:
✅ Local model management and caching
✅ Enhanced PDF processing with OCR support
✅ Advanced relevance ranking with multi-query matching
✅ Robust error handling and fallback mechanisms
✅ Comprehensive testing suite
✅ Better performance monitoring
✅ Improved text refinement algorithms

📁 Files Added/Modified:
- model_manager.py (NEW) - Handles local model downloads and caching
- relevance_ranker.py (ENHANCED) - Better ranking with content scoring
- document_processor.py (ENHANCED) - OCR support and better text extraction
- subsection_analyzer.py (ENHANCED) - Advanced text refinement
- run.py (ENHANCED) - Model management integration and better logging
- setup.py (NEW) - Automated setup and model download
- enhanced_test.py (NEW) - Comprehensive testing
- requirements.txt (UPDATED) - Additional dependencies
- README.md (ENHANCED) - Complete documentation

🎯 Quick Start Commands:
"""
    print(banner)

def print_commands():
    commands = """
# 1. Setup (download models and dependencies)
python setup.py

# 2. Test the system
python enhanced_test.py

# 3. Run on Collection 1 (Travel Planning)
python run.py \\
    --input-dir "./Collection 1/PDFs" \\
    --persona "Travel Planner" \\
    --job "Plan a trip of 4 days for a group of 10 college friends" \\
    --output-file "./Collection 1/enhanced_output.json" \\
    --verbose

# 4. Run on Collection 2 (Software Training)
python run.py \\
    --input-dir "./Collection 2/PDFs" \\
    --persona "Software Trainer" \\
    --job "Create Adobe Acrobat training for new employees" \\
    --output-file "./Collection 2/enhanced_output.json" \\
    --use-large-models \\
    --verbose

# 5. Get help
python run.py --help
"""
    print(commands)

def check_collections():
    print("\n📂 Available Collections:")
    collections = ["Collection 1", "Collection 2", "Collection 3", "documents"]
    
    for collection in collections:
        if os.path.exists(collection):
            pdf_dir = os.path.join(collection, "PDFs") if collection.startswith("Collection") else collection
            if os.path.exists(pdf_dir):
                pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
                status = f"✅ {len(pdf_files)} PDFs" if pdf_files else "❌ No PDFs"
                print(f"  {collection}: {status}")
            else:
                print(f"  {collection}: ❌ PDFs directory not found")
        else:
            print(f"  {collection}: ❌ Not found")

def main():
    print_banner()
    print_commands()
    check_collections()
    
    print("""\n🎉 Next Steps:
1. Run 'python setup.py' to download models (required for first use)
2. Test with 'python enhanced_test.py'
3. Try the example commands above
4. Check README.md for detailed documentation

💡 Pro Tips:
- Use --use-large-models for better accuracy (requires more memory)
- Use --verbose to see detailed processing information
- Models are cached locally after first download
- OCR is enabled by default for image-based text extraction
""")

if __name__ == "__main__":
    main()
