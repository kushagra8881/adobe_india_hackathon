import os
import sys
import json
import fitz  # PyMuPDF
from tqdm import tqdm
import re

# Get the directory where the main.py script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Add this script's directory to the Python path to find pdf_utils
if script_dir not in sys.path:
    sys.path.append(script_dir)

# Ensure pdf_utils is in sys.path for direct imports
pdf_utils_dir = os.path.join(script_dir, "pdf_utils")
if pdf_utils_dir not in sys.path:
    sys.path.append(pdf_utils_dir)

from pdf_utils import (
    extract_blocks,
    classify_headings,
    structure_outline,
    language,
    summarizer
)

# --- Configuration ---
INPUT_DIR = os.path.join(script_dir, "input")
OUTPUT_DIR = os.path.join(script_dir, "output")
INTERMEDIATES_SUBDIR = "intermediates" 

def process_pdf_hybrid(pdf_path, output_dir):
    """
    Processes a single PDF file using a hybrid approach, combining text
    extraction, line-by-line analysis, specific pruning, and outline structuring.
    """
    base_filename = os.path.basename(pdf_path)
    name_without_ext = os.path.splitext(base_filename)[0]
    
    final_output_path = os.path.join(output_dir, f"{name_without_ext}.json")
    intermediate_output_dir = os.path.join(output_dir, INTERMEDIATES_SUBDIR)
    
    # Paths for intermediate files
    intermediate_raw_blocks_path = os.path.join(intermediate_output_dir, f"{name_without_ext}_intermediate_raw_blocks.json")
    intermediate_processed_blocks_path = os.path.join(intermediate_output_dir, f"{name_without_ext}_intermediate_processed_blocks.json")


    print(f"\nStarting hybrid processing for: {base_filename}")
    
    doc = None 
    try:
        # Step 1: Initial Text Extraction (line by line / span by span)
        doc = fitz.open(pdf_path)
        
        # Extract first 2500 chars from the first page for language detection
        temp_lang_detect_string = ""
        for page_num in range(min(doc.page_count, 1)): # Sample only the first page
            if len(temp_lang_detect_string) < 2500:
                temp_lang_detect_string += doc[page_num].get_text("text")
            else:
                break
        temp_lang_detect_string = temp_lang_detect_string[:2500]
        
        print("   Stage 1: Extracting detailed blocks with PyMuPDF...")
        all_raw_spans, page_dimensions = extract_blocks.run(pdf_path, intermediate_raw_blocks_path)
        
        # Step 2: Language Detection (on the basis of the temp string)
        print("   Stage 2: Language Detection (NLP)..")
        lang = language.detect_language(temp_lang_detect_string)
        
        # Get NLP model *once* here. It's used for meaningful fragment checks and summarization.
        nlp_for_all_nlp_tasks = language.get_multilingual_nlp(lang)

        # Step 3: Analyze line changes, merge, and prune based on new logic
        print("   Stage 3: Analyzing line changes, merging, and initial pruning..")
        processed_blocks_for_outline_and_summary = classify_headings.run_with_custom_logic(
            all_raw_spans, page_dimensions, detected_lang=lang, nlp_model_for_quality_checks=nlp_for_all_nlp_tasks
        )

        # Save the processed blocks after classify_headings logic
        print(f"   Saving intermediate processed blocks to {intermediate_processed_blocks_path}")
        os.makedirs(os.path.dirname(intermediate_processed_blocks_path), exist_ok=True)
        with open(intermediate_processed_blocks_path, 'w', encoding='utf-8') as f:
            json.dump(processed_blocks_for_outline_and_summary, f, indent=2, ensure_ascii=False)


        # Step 4: Summarize relevant body text
        # Collects all blocks that are NOT headers/footers AND are marked as meaningful fragments.
        print(f"   Stage 4: Summarizing relevant body text (Language: {lang}, using NLP)..")
        body_text_for_summary_parts = []
        for block in processed_blocks_for_outline_and_summary:
            if not block.get("is_header_footer", False) and \
               block.get("is_meaningful_fragment", True) and \
               block["text"].strip(): 
                body_text_for_summary_parts.append(block["text"])
        
        body_text_for_summary = "\n".join(body_text_for_summary_parts)
        summary = summarizer.summarize_text(body_text_for_summary, nlp_for_all_nlp_tasks)


        # Step 5: Structure Outline and Determine Title
        print("   Stage 5: Structuring outline and determining final title..")
        
        # First, structure the outline from the classified blocks
        # Pass the original page count to outline for length constraint
        structured_outline_result = structure_outline.run(processed_blocks_for_outline_and_summary, doc.page_count, name_without_ext)

        # Now, derive the title using the new, stricter logic from the summary and outline headings
        final_title = structure_outline.derive_title_from_summary_and_outline(
            summary, 
            structured_outline_result.get("outline", []), # Pass the actual structured outline for relevance check
            name_without_ext, 
            nlp_for_all_nlp_tasks # Pass NLP model for semantic similarity
        )
        
        # Final cleaning of the determined title
        final_title = re.sub(r'[\u201c\u201d"\'`]+', '', final_title).strip()
        final_title = re.sub(r'\s+', ' ', final_title).strip()
        if not final_title or re.fullmatch(r'[\s\d\W_]+', final_title):
            final_title = name_without_ext

        # Step 6: Combine & Save Output (Summary is now just a field, not outline part)
        print("   Stage 6: Combining results and saving to JSON.")
        final_output = {
            "title": final_title,
            "summary": summary, 
            "outline": structured_outline_result.get("outline", []) 
        }

        with open(final_output_path, 'w', encoding='utf-8') as f:
            json.dump(final_output, f, indent=2, ensure_ascii=False)

        print(f"Successfully generated hybrid output for {base_filename} to {final_output_path}")

    except Exception as e:
        print(f"ERROR: Failed to process {base_filename}. Reason: {e}")
    finally:
        if doc:
            doc.close()

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, INTERMEDIATES_SUBDIR), exist_ok=True)

    if not os.path.exists(INPUT_DIR):
        print(f"Input directory '{INPUT_DIR}' not found. Please create it and place your PDF files inside.")
    else:
        pdf_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".pdf")]
        if not pdf_files:
            print(f"No PDF files found in '{INPUT_DIR}'.")
        else:
            for filename in tqdm(pdf_files, desc="Processing PDFs"):
                pdf_path = os.path.join(INPUT_DIR, filename)
                process_pdf_hybrid(pdf_path, OUTPUT_DIR)

    print("\nAll processing complete.")