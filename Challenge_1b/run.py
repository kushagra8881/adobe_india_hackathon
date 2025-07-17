#!/usr/bin/env python3
import os
import sys
import json
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Check for required packages
required_packages = [
    "pymupdf", "sentence_transformers", "nltk", "torch", "huggingface_hub"
]

missing_packages = []
for package in required_packages:
    try:
        __import__(package.replace("-", "_"))
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
try:
    from model_manager import ModelManager
    from isolated_document_processor import IsolatedDocumentProcessor
    from relevance_ranker import RelevanceRanker
    from subsection_analyzer import SubsectionAnalyzer
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print("Make sure all required files are in the same directory as run.py")
    sys.exit(1)

def parse_arguments():
    parser = argparse.ArgumentParser(description="Document Intelligence System")
    parser.add_argument("--input-dir", type=str, required=True, 
                        help="Directory containing input PDF files")
    parser.add_argument("--persona", type=str, required=True,
                        help="Description of the user persona")
    parser.add_argument("--job", type=str, required=True,
                        help="Job to be done by the persona")
    parser.add_argument("--output-file", type=str, default="challenge1b_output.json",
                        help="Path to output JSON file")
    parser.add_argument("--top-sections", type=int, default=5,
                        help="Number of top sections to extract")
    parser.add_argument("--top-subsections", type=int, default=5,
                        help="Number of top subsections to analyze")
    parser.add_argument("--models-dir", type=str, default="./models",
                        help="Directory to store downloaded models")
    parser.add_argument("--use-large-models", action="store_true",
                        help="Use larger, more accurate models (requires more memory)")
    parser.add_argument("--setup-models", action="store_true",
                        help="Download and setup all models before processing")
    parser.add_argument("--use-ocr", action="store_true", default=True,
                        help="Use OCR for image-based text extraction")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose logging")
    
    return parser.parse_args()

def ensure_dir_exists(path):
    """Make sure the directory exists for the output file."""
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

def main():
    args = parse_arguments()
    
    # Setup logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Record start time
    start_time = time.time()
    
    logger.info(f"Starting Document Intelligence System")
    logger.info(f"Persona: {args.persona}")
    logger.info(f"Job: {args.job}")
    
    # Ensure input directory exists
    if not os.path.exists(args.input_dir):
        logger.error(f"Input directory '{args.input_dir}' does not exist.")
        sys.exit(1)
    
    # Get all PDF files in the input directory
    pdf_files = sorted([f for f in os.listdir(args.input_dir) 
                       if f.lower().endswith('.pdf')])
    
    if not pdf_files:
        logger.error(f"No PDF files found in input directory '{args.input_dir}'")
        sys.exit(1)
    
    # Ensure output directory exists
    ensure_dir_exists(args.output_file)
    
    pdf_paths = [os.path.join(args.input_dir, pdf) for pdf in pdf_files]
    
    logger.info(f"Found {len(pdf_files)} PDF files: {', '.join(pdf_files)}")
    
    # Initialize model manager
    try:
        logger.info("Initializing model manager...")
        model_manager = ModelManager(args.models_dir)
        
        # Setup models if requested
        if args.setup_models:
            logger.info("Setting up all models...")
            model_manager.setup_all_models(use_large_models=args.use_large_models)
        
        # Show system info
        system_info = model_manager.get_system_info()
        logger.info(f"System info: {json.dumps(system_info, indent=2)}")
        
    except Exception as e:
        logger.error(f"Error initializing model manager: {str(e)}")
        sys.exit(1)
    
    # Initialize components
    try:
        logger.info("Initializing processing components...")
        document_processor = IsolatedDocumentProcessor(use_ocr=args.use_ocr)
        relevance_ranker = RelevanceRanker(model_manager, use_large_model=args.use_large_models)
        subsection_analyzer = SubsectionAnalyzer(model_manager)
        
    except Exception as e:
        logger.error(f"Error initializing components: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Process documents
    try:
        logger.info(f"Processing {len(pdf_files)} documents...")
        processing_start = time.time()
        
        documents = document_processor.process_documents(pdf_paths)
        
        if not documents:
            logger.error("No documents were successfully processed")
            logger.info("This could be due to:")
            logger.info("  - Corrupted or password-protected PDF files")
            logger.info("  - PDF files with complex layouts or images")
            logger.info("  - Insufficient permissions to read the files")
            logger.info("Suggestion: Try with simpler PDF files or check file permissions")
            sys.exit(1)
            
        processing_time = time.time() - processing_start
        logger.info(f"Document processing completed in {processing_time:.2f} seconds")
        
        # Rank sections based on persona and job
        logger.info("Ranking sections by relevance...")
        ranking_start = time.time()
        
        ranked_sections = relevance_ranker.rank_sections(
            documents, args.persona, args.job, top_n=args.top_sections
        )
        
        ranking_time = time.time() - ranking_start
        logger.info(f"Section ranking completed in {ranking_time:.2f} seconds")
        
        if not ranked_sections:
            logger.warning("No relevant sections found - this might indicate:")
            logger.warning("  - Documents don't contain relevant content for the given persona/job")
            logger.warning("  - Text extraction quality issues")
            logger.warning("  - Very specific persona/job combination")
            # Continue anyway to generate some output
        
        # Analyze subsections
        logger.info("Analyzing subsections...")
        analysis_start = time.time()
        
        subsection_analysis = subsection_analyzer.analyze_subsections(
            documents, ranked_sections, args.persona, args.job, top_n=args.top_subsections
        )
        
        analysis_time = time.time() - analysis_start
        logger.info(f"Subsection analysis completed in {analysis_time:.2f} seconds")
        
    except Exception as e:
        logger.error(f"Error during processing: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Create output structure
    total_processing_time = time.time() - start_time
    
    output = {
        "metadata": {
            "input_documents": pdf_files,
            "persona": args.persona,
            "job_to_be_done": args.job,
            "processing_timestamp": datetime.now().isoformat(),
            "processing_time_seconds": round(total_processing_time, 2),
            "system_info": {
                "models_used": {
                    "sentence_transformer": "locally_cached" if model_manager.is_model_downloaded("sentence_transformer") else "remote",
                    "use_large_models": args.use_large_models,
                    "use_ocr": args.use_ocr
                },
                "documents_processed": len(documents),
                "total_sections_found": sum(len(doc.get("sections", [])) for doc in documents)
            }
        },
        "extracted_sections": ranked_sections,
        "subsection_analysis": subsection_analysis
    }
    
    # Write output to file
    try:
        with open(args.output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=4, ensure_ascii=False)
        logger.info(f"Output written to {args.output_file}")
        
    except Exception as e:
        logger.error(f"Error writing output file: {str(e)}")
        sys.exit(1)
    
    # Summary
    logger.info(f"Processing completed in {total_processing_time:.2f} seconds")
    logger.info(f"Processed {len(documents)} documents")
    logger.info(f"Found {len(ranked_sections)} relevant sections")
    logger.info(f"Generated {len(subsection_analysis)} subsection analyses")
    
    # Performance breakdown
    logger.info("Performance breakdown:")
    logger.info(f"  Document processing: {processing_time:.2f}s")
    logger.info(f"  Section ranking: {ranking_time:.2f}s") 
    logger.info(f"  Subsection analysis: {analysis_time:.2f}s")

if __name__ == "__main__":
    main()
