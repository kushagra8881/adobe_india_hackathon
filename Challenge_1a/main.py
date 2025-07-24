import os
import sys
import json
import fitz  # PyMuPDF
from tqdm import tqdm
import re
import shutil # Import shutil for directory operations
from operator import itemgetter # Ensure itemgetter is imported for main.py's own uses

# Get the directory where the main.py script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Add this script's directory to the Python path to find pdf_utils
if script_dir not in sys.path:
    sys.path.append(script_dir)

# Ensure pdf_utils is in sys.path for direct imports
pdf_utils_dir = os.path.join(script_dir, "pdf_utils")
if pdf_utils_dir not in sys.path:
    sys.path.append(pdf_utils_dir) # Fixed typo here: should be sys.path.append

from pdf_utils import (
    extract_blocks,
    classify_headings, # This will be the provided classify.py
    structure_outline,
    language,
    # summarizer # REMOVED: Summarizer is no longer used for output
)

# --- Configuration ---
INPUT_DIR = os.path.join(script_dir, "inputs")
OUTPUT_DIR = os.path.join(script_dir, "outputs")
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
        doc = fitz.open(pdf_path)
        
        # Determine text sample for language detection and title derivation
        # Early 3-5 pages or 15% of the document, whichever shorter.
        pages_for_sample = min(doc.page_count, 5) # Max 5 pages
        # Estimate characters for 15% (assume ~1000 chars/page for density estimate)
        max_chars_for_sample = min(int(doc.page_count * 0.15 * 1000), 5000) 
        
        sampled_text_for_title_and_lang = ""
        sampled_raw_blocks_for_title = [] # Collect raw spans for title's font/position info

        for page_num in range(min(doc.page_count, pages_for_sample)):
            page = doc[page_num]
            
            # Use get_text("text") for general text to get a large sample quickly
            if len(sampled_text_for_title_and_lang) < max_chars_for_sample:
                sampled_text_for_title_and_lang += page.get_text("text") + "\n"
            
            # Extract detailed spans from sampled pages to know their font sizes/positions for title scoring
            page_content = page.get_text("dict")
            for b_dict in page_content['blocks']:
                if b_dict['type'] == 0: # text block
                    for l_dict in b_dict['lines']:
                        for s_dict in l_dict['spans']:
                            x0, y0, x1, y1 = s_dict['bbox']
                            if all(isinstance(val, (int, float)) for val in [x0, y0, x1, y1]):
                                sampled_raw_blocks_for_title.append({
                                    "text": s_dict['text'],
                                    "font_size": s_dict['size'],
                                    "x0": x0,
                                    "top": y0, # Store y0 as top for consistency
                                    "page": page_num
                                })
            
            if len(sampled_text_for_title_and_lang) >= max_chars_for_sample and len(sampled_raw_blocks_for_title) > 50: 
                break # Stop sampling if enough characters/blocks are collected
        
        sampled_text_for_title_and_lang = sampled_text_for_title_and_lang[:max_chars_for_sample]
        sampled_raw_blocks_for_title.sort(key=itemgetter("page", "top")) # Sort for consistent title processing


        print("   Stage 1: Extracting detailed blocks with PyMuPDF...")
        # `extract_blocks.run` will handle `_pre_merge_horizontal_fragments`
        all_raw_spans, page_dimensions = extract_blocks.run(pdf_path, intermediate_raw_blocks_path)
        
        print("   Stage 2: Language Detection (NLP)..")
        lang = language.detect_language(sampled_text_for_title_and_lang) 
        
        # NLP model for classify_headings
        nlp_model_for_classify = language.get_multilingual_nlp(lang)

        # Using classify_headings.run (the provided version)
        print("   Stage 3: Classifying headings with heuristics and initial pruning..")
        # Ensure parameter name matches the provided classify_headings.py's run function signature
        processed_blocks_for_outline = classify_headings.run(
            all_raw_spans, page_dimensions, detected_lang=lang, nlp_model_for_all_nlp_tasks=nlp_model_for_classify 
        )

        print(f"   Saving intermediate processed blocks to {intermediate_processed_blocks_path}")
        os.makedirs(os.path.dirname(intermediate_processed_blocks_path), exist_ok=True)
        with open(intermediate_processed_blocks_path, 'w', encoding='utf-8') as f:
            json.dump(processed_blocks_for_outline, f, indent=2, ensure_ascii=False)

        # Stage 4: Summarization processing is removed.

        print("   Stage 5: Structuring outline and determining final title..")
        
        # Pass sampled_raw_blocks_for_title (with font/pos info) to the new title derivation function
        final_title = structure_outline.derive_title_from_sampled_text_and_filename(
            sampled_raw_blocks_for_title, 
            name_without_ext, 
            nlp_model_for_classify # Pass NLP model for semantic similarity
        )
        
        # Pass processed_blocks_for_outline and total pages for the outline structuring and pruning
        structured_outline_result = structure_outline.run(
            processed_blocks_for_outline, 
            doc.page_count, 
            name_without_ext
        )
        
        final_title = re.sub(r'[\u201c\u201d"\'`]+', '', final_title).strip()
        final_title = re.sub(r'\s+', ' ', final_title).strip()
        if not final_title or re.fullmatch(r'[\s\d\W_]+', final_title):
            final_title = name_without_ext

        print("   Stage 6: Combining results and saving to JSON.")
        final_output = {
            "title": final_title,
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
    intermediates_full_path = os.path.join(OUTPUT_DIR, INTERMEDIATES_SUBDIR)
    os.makedirs(intermediates_full_path, exist_ok=True)

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

    if os.path.exists(intermediates_full_path):
        try:
            shutil.rmtree(intermediates_full_path)
            print(f"Cleaned up intermediate folder: '{intermediates_full_path}'")
        except OSError as e:
            print(f"Error deleting intermediate folder '{intermediates_full_path}': {e}")