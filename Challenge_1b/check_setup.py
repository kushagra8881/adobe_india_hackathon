#!/usr/bin/env python3
import os
import sys
import fitz  # PyMuPDF

def check_installation():
    print("Checking installation...")
    
    # Check for PDF files
    documents_dir = "./documents"
    if not os.path.exists(documents_dir):
        print(f"❌ Error: '{documents_dir}' directory not found")
        return False
    
    pdf_files = [f for f in os.listdir(documents_dir) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print(f"❌ Error: No PDF files found in '{documents_dir}'")
        return False
    print(f"✅ Found {len(pdf_files)} PDF files in '{documents_dir}'")
    
    # Try to open a PDF file
    try:
        test_pdf = os.path.join(documents_dir, pdf_files[0])
        doc = fitz.open(test_pdf)
        print(f"✅ Successfully opened '{pdf_files[0]}' ({doc.page_count} pages)")
        
        # Try to extract text from first page
        first_page = doc[0]
        text = first_page.get_text()
        print(f"✅ Text extraction successful ({len(text)} characters)")
        print(f"First few characters: {text[:50]}...")
    except Exception as e:
        print(f"❌ Error processing PDF: {str(e)}")
        return False
    
    # Check for other dependencies
    try:
        import torch
        print(f"✅ PyTorch installed (version {torch.__version__})")
        
        import sentence_transformers
        print(f"✅ Sentence Transformers installed (version {sentence_transformers.__version__})")
        
        import nltk
        print(f"✅ NLTK installed (version {nltk.__version__})")
    except ImportError as e:
        print(f"❌ Missing dependency: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    if check_installation():
        print("\n✅ Setup looks good! You should be able to run the document intelligence system.")
    else:
        print("\n❌ There are issues with your setup. Please fix them before running the main script.")