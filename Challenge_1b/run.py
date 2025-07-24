#!/usr/bin/env python3
"""
Document Intelligence System
Extracts and prioritizes relevant sections from documents based on persona and job.
"""
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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import project modules
try:
    from model_manager import ModelManager
    from document_processor import DocumentProcessor
    from relevance_ranker import RelevanceRanker
    from subsection_analyzer import SubsectionAnalyzer
except ImportError as e:
    print(f"❌ Error importing project modules: {e}")
    print("Make sure all required files are in the same directory as run.py")
    sys.exit(1)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Document Intelligence System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py --persona "travel planner" --job "plan south france trip"
  python run.py --persona "student" --job "research acrobat features"
        """
    )
    parser.add_argument("--persona", type=str, required=True,
                        help="Description of the user persona")
    parser.add_argument("--job", type=str, required=True,
                        help="Job to be done by the persona")
    parser.add_argument("--top-sections", type=int, default=5,
                        help="Number of top sections to extract")
    parser.add_argument("--top-subsections", type=int, default=5,
                        help="Number of top subsections to analyze")
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

    logger.info("🚀 Starting Document Intelligence System")
    logger.info(f"👤 Persona: {args.persona}")
    logger.info(f"🎯 Job: {args.job}")

    # Ensure input directory exists
    if not os.path.exists("./input"):
        logger.error("❌ Input directory ./input does not exist.")
        sys.exit(1)

    # Get all PDF files in the input directory
    pdf_files = sorted([f for f in os.listdir("./input")
                       if f.lower().endswith('.pdf')])

    if not pdf_files:
        logger.error("❌ No PDF files found in input directory ./input")
        sys.exit(1)

    # Ensure output directory exists
    ensure_dir_exists(f"./output/out_{datetime.now().isoformat()}.json")

    logger.info(f"📄 Found {len(pdf_files)} PDF files: {', '.join(pdf_files)}")

    # Initialize components
    try:
        logger.info("🔧 Initializing processing components...")
        model_manager = ModelManager()
        document_processor = DocumentProcessor(use_ocr=args.use_ocr)
        relevance_ranker = RelevanceRanker(model_manager)
        subsection_analyzer = SubsectionAnalyzer(model_manager)

        logger.info("✅ Components initialized successfully")

    except Exception as e:
        logger.error(f"❌ Error initializing components: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Process documents
    try:
        logger.info(f"📄 Processing {len(pdf_files)} documents...")
        processing_start = time.time()

        pdf_paths = [os.path.join("./input", pdf_file)
                     for pdf_file in pdf_files]
        documents = document_processor.process_documents(pdf_paths)

        if not documents:
            logger.error("❌ No documents were successfully processed")
            logger.info("💡 This could be due to:")
            logger.info("   - Corrupted or password-protected PDF files")
            logger.info("   - PDF files with complex layouts or images")
            logger.info("   - Insufficient permissions to read the files")
            logger.info(
                "💡 Suggestion: Try with simpler PDF files or check file permissions")
            sys.exit(1)

        processing_time = time.time() - processing_start
        logger.info(
            f"✅ Document processing completed in {processing_time:.2f} seconds")

        # Rank sections based on persona and job
        logger.info("🎯 Ranking sections by relevance...")
        ranking_start = time.time()

        ranked_sections = relevance_ranker.rank_sections(
            documents, args.persona, args.job, top_n=args.top_sections
        )

        ranking_time = time.time() - ranking_start
        logger.info(f"Section ranking completed in {ranking_time:.2f} seconds")

        if not ranked_sections:
            logger.warning("No relevant sections found - this might indicate:")
            logger.warning(
                "  - Documents don't contain relevant content for the given persona/job")
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
        logger.info(
            f"Subsection analysis completed in {analysis_time:.2f} seconds")

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
        with open(f"./output/out_{datetime.now().isoformat()}.json", 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=4, ensure_ascii=False)
        logger.info("Output written to ./output/out_#.json")

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
