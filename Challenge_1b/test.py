#!/usr/bin/env python3
import os
import sys
import json
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Check for required packages
required_packages = [
    "pymupdf", "sentence_transformers", "nltk", "torch"
]

missing_packages = []
for package in required_packages:
    try:
        __import__(package)
    except ImportError:
        missing_packages.append(package)

if missing_packages:
    print("Error: Missing required Python packages. Please install them using pip:")
    print(f"pip install {' '.join(missing_packages)}")
    print("\nYou may also need to install system packages:")
    print("- For Ubuntu/Debian: sudo apt-get install tesseract-ocr libtesseract-dev poppler-utils")
    print("- For macOS: brew install tesseract poppler")
    sys.exit(1)

# Import project modules
from document_processor import DocumentProcessor
from relevance_ranker import RelevanceRanker
from subsection_analyzer import SubsectionAnalyzer

def parse_arguments():
    parser = argparse.ArgumentParser(description="Document Intelligence System")
    parser.add_argument("--input-dir", type=str, required=True, 
                        help="Directory containing input PDF files")
    parser.add_argument("--persona", type=str, required=True,
                        help="Description of the user persona")
    parser.add_argument("--job", type=str, required=True,
                        help="Job to be done by the persona")
    parser.add_argument("--output-file", type=str, default="output.json",
                        help="Path to output JSON file")
    parser.add_argument("--top-sections", type=int, default=5,
                        help="Number of top sections to extract")
    parser.add_argument("--top-subsections", type=int, default=5,
                        help="Number of top subsections to analyze")
    
    return parser.parse_args()

def ensure_dir_exists(path):
    """Make sure the directory exists for the output file."""
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

def main():
    args = parse_arguments()
    
    # Record start time
    start_time = time.time()
    
    # Ensure input directory exists
    if not os.path.exists(args.input_dir):
        print(f"Error: Input directory '{args.input_dir}' does not exist.")
        sys.exit(1)
    
    # Get all PDF files in the input directory
    pdf_files = sorted([f for f in os.listdir(args.input_dir) 
                       if f.lower().endswith('.pdf')])
    
    if not pdf_files:
        print(f"No PDF files found in input directory '{args.input_dir}'")
        sys.exit(1)
    
    # Ensure output directory exists
    ensure_dir_exists(args.output_file)
    
    pdf_paths = [os.path.join(args.input_dir, pdf) for pdf in pdf_files]
    
    print(f"Found {len(pdf_files)} PDF files: {', '.join(pdf_files)}")
    
    # Initialize components
    try:
        document_processor = DocumentProcessor()
        relevance_ranker = RelevanceRanker()
        subsection_analyzer = SubsectionAnalyzer()
    except Exception as e:
        print(f"Error initializing components: {str(e)}")
        sys.exit(1)
    
    # Process documents
    try:
        print(f"Processing {len(pdf_files)} documents...")
        documents = document_processor.process_documents(pdf_paths)
        
        # Rank sections based on persona and job
        print("Ranking sections by relevance...")
        ranked_sections = relevance_ranker.rank_sections(
            documents, args.persona, args.job, top_n=args.top_sections
        )
        
        # Analyze subsections
        print("Analyzing subsections...")
        subsection_analysis = subsection_analyzer.analyze_subsections(
            documents, ranked_sections, args.persona, args.job, top_n=args.top_subsections
        )
    except Exception as e:
        print(f"Error during processing: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Create output structure
    output = {
        "metadata": {
            "input_documents": pdf_files,
            "persona": args.persona,
            "job_to_be_done": args.job,
            "processing_timestamp": datetime.now().isoformat()
        },
        "extracted_sections": ranked_sections,
        "subsection_analysis": subsection_analysis
    }
    
    # Write output to file
    try:
        with open(args.output_file, 'w') as f:
            json.dump(output, f, indent=4)
    except Exception as e:
        print(f"Error writing output file: {str(e)}")
        sys.exit(1)
    
    elapsed_time = time.time() - start_time
    print(f"Processing completed in {elapsed_time:.2f} seconds")
    print(f"Output written to {args.output_file}")

if __name__ == "__main__":
    main()
