# main.py

import os
import sys
import json
import fitz  # PyMuPDF
from tqdm import tqdm

# Get the directory where the main.py script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Add this script's directory to the Python path to find pdf_utils
if script_dir not in sys.path:
    sys.path.append(script_dir)

from pdf_utils import (
    extract_blocks,
    classify_headings,
    structure_outline,
    language,
    summarizer
)

# --- Configuration ---
INPUT_DIR = os.path.join(script_dir, "inputs")
OUTPUT_DIR = os.path.join(script_dir, "outputs")
# INTERMEDIATES_SUBDIR is no longer strictly needed for in-memory processing,
# but can be kept if you still want to write intermediate files for debugging.

def process_pdf_hybrid(pdf_path, output_dir):
    """
    Processes a single PDF file using a hybrid approach, combining fast text
    extraction and NLP with robust heuristic-based outline structuring.
    """
    base_filename = os.path.basename(pdf_path)
    name_without_ext = os.path.splitext(base_filename)[0]
    
    final_output_path = os.path.join(output_dir, f"{name_without_ext}.json")
    # Intermediate path is now for *optional* debugging output if needed, not for pipeline flow
    # intermediate_output_dir = os.path.join(output_dir, INTERMEDIATES_SUBDIR)
    # intermediate_path = os.path.join(intermediate_output_dir, f"{name_without_ext}_intermediate_blocks.json")

    print(f"\nStarting hybrid processing for: {base_filename}")
    
    doc = None # Initialize doc to ensure it's closed in finally block
    try:
        # --- NLP & PyMuPDF Part (Fast Text Extraction and Analysis) ---
        doc = fitz.open(pdf_path)
        full_text_parts = []
        # Extract text page by page for better memory management for very large PDFs
        # Using a generator for page text to avoid creating a huge list of strings
        for page_num in range(doc.page_count):
            full_text_parts.append(doc[page_num].get_text("text"))
        full_text = "\n".join(full_text_parts)

        print("  Stage 1: Language Detection...")
        lang = language.detect_language(full_text)
        nlp = language.get_multilingual_nlp(lang)
        
        print(f"  Stage 2: Summarizing document (Language: {lang})...")
        summary = summarizer.summarize_text(full_text, nlp)

        # --- Heuristics Part (Robust Outline Structuring) ---
        print(f"  Stage 3: Extracting detailed blocks with PyMuPDF for heuristic analysis...")
        # Now extract_blocks.run returns data directly, no intermediate file write/read here
        # (extract_blocks.run will still write for its own debugging, but that's separate)
        all_blocks, page_dimensions = extract_blocks.run(pdf_path, None) # Pass None or dummy path if no intermediate dump needed by extract_blocks

        print(f"  Stage 4: Classifying headings with enhanced heuristics...")
        # Pass blocks and dimensions directly; classify_headings now returns modified blocks
        classified_blocks = classify_headings.run(all_blocks, page_dimensions, most_common_font_size=None) # most_common_font_size will be calculated internally

        print(f"  Stage 5: Structuring outline with robust heuristics...")
        # structure_outline now operates on in-memory classified_blocks
        structured_data = structure_outline.run(classified_blocks, page_dimensions, name_without_ext)

        # --- Final Combination ---
        print(f"  Stage 6: Combining NLP results and heuristic outline...")
        
        final_output = {
            "title": structured_data.get("title", name_without_ext),
            "summary": summary,
            "outline": structured_data.get("outline", [])
        }

        with open(final_output_path, 'w', encoding='utf-8') as f:
            json.dump(final_output, f, indent=2, ensure_ascii=False)

        print(f"Successfully generated hybrid output for {base_filename} to {final_output_path}")

    except Exception as e:
        print(f"ERROR: Failed to process {base_filename}. Reason: {e}")
        # No intermediate file cleanup in main.py if not written by this module directly
    finally:
        if doc:
            doc.close() # Ensure the PDF document is always closed

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # os.makedirs(os.path.join(OUTPUT_DIR, INTERMEDIATES_SUBDIR), exist_ok=True) # Not strictly needed if no intermediates written

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
