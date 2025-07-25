import os
import sys
import json
import fitz        # PyMuPDF
from tqdm import tqdm
import re
import shutil # Import shutil for directory operations
from operator import itemgetter # Ensure itemgetter is imported for main.py's own uses

# Get the directory where the main.py script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Add this script's directory and pdf_utils to the Python path
# This ensures that modules within pdf_utils can be imported correctly
if script_dir not in sys.path:
    sys.path.append(script_dir)

pdf_utils_dir = os.path.join(script_dir, "pdf_utils")
if pdf_utils_dir not in sys.path:
    sys.path.append(pdf_utils_dir)

# Import functions from pdf_utils sub-modules
from pdf_utils import (
    extract_blocks,        # extract_blocks.py
    classify_headings,     # classify_headings.py (your latest improvised code)
    structure_outline,     # structure_outline.py (the one with derive_title_from_sampled_text_and_filename)
    language,              # language.py
)

# --- Configuration ---
INPUT_DIR = os.path.join(script_dir, "input")
OUTPUT_DIR = os.path.join(script_dir, "output")
INTERMEDIATES_SUBDIR = "intermediates" 

def _process_and_truncate_title(raw_title: str, processed_blocks: list, filename_base: str, detected_lang: str) -> str:
    """
    Enhanced title processing that extracts meaningful titles from document content
    and truncates appropriately based on language.
    """
    is_cjk = detected_lang in ["zh", "ja", "ko"]
    
    # Strategy 1: If raw_title is just filename, try to extract from document content
    if raw_title == filename_base or len(raw_title) < 5:
        print(f"    Raw title '{raw_title}' seems to be filename/insufficient. Extracting from content...")
        
        # Look for the best heading in first few pages
        early_headings = [b for b in processed_blocks 
                         if b.get("level") and b.get("page", 0) <= 2 and b.get("text", "").strip()]
        
        if early_headings:
            # Sort by page and level priority
            early_headings.sort(key=lambda x: (x.get("page", 0), int(x.get("level", "H4")[1:])))
            
            # Find the longest, most complete heading from the first page
            best_candidate = None
            for heading in early_headings:
                text = heading.get("text", "").strip()
                # Remove truncation indicators
                text = re.sub(r'\.{3,}$', '', text)  # Remove trailing ellipsis
                
                if len(text) > 8:  # Reasonable length for a title
                    best_candidate = text
                    break
            
            if best_candidate:
                raw_title = best_candidate
                print(f"    Extracted title from content: '{raw_title}'")
    
    # Strategy 2: Clean and normalize the title
    title = re.sub(r'[\u201c\u201d"\'`""'']+', '', raw_title).strip()
    title = re.sub(r'\s+', ' ', title).strip()
    
    # Strategy 3: Apply length limits based on language
    if is_cjk:
        # For CJK languages, count characters and limit to ~20 characters
        max_chars = 20
        if len(title) > max_chars:
            title = title[:max_chars].rstrip()
            print(f"    Truncated CJK title to {max_chars} characters")
    else:
        # For non-CJK languages, count words and limit to 7 words
        words = title.split()
        max_words = 7
        if len(words) > max_words:
            title = ' '.join(words[:max_words])
            print(f"    Truncated title to {max_words} words")
    
    # Strategy 4: Final validation and fallback
    if not title or len(title) < 3 or re.fullmatch(r'[\s\d\W_]+', title):
        print(f"    Title validation failed. Using processed filename.")
        # Create a meaningful title from filename
        fallback = re.sub(r'[_-]+', ' ', filename_base).strip()
        fallback = ' '.join(word.capitalize() for word in fallback.split())
        title = fallback
    
    return title

def process_pdf_hybrid(pdf_path: str, output_dir: str):
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
        num_pages_total = doc.page_count

        # --- Stage 1: Initial Text Sampling for Language Detection & Title Derivation ---
        # Collect raw text and blocks from early pages for language detection and title.
        
        # Max pages for sample: smaller of total pages or 5
        pages_to_sample_for_meta = min(num_pages_total, 5) 
        # Max characters for sample: 15% of document's estimated chars (1000 chars/page) or 5000 chars, whichever is smaller
        max_chars_for_sample = min(int(num_pages_total * 0.15 * 1000), 5000) 
        
        sampled_text_for_title_and_lang = ""
        sampled_raw_blocks_for_title = [] # This will store simplified block data (text, font_size, x0, top, page)

        print("  Stage 1: Sampling initial pages for language and title candidates...")
        for page_num in range(pages_to_sample_for_meta):
            page = doc[page_num]
            
            # For quick text sample (language detection)
            current_page_text = page.get_text("text")
            if len(sampled_text_for_title_and_lang) < max_chars_for_sample:
                sampled_text_for_title_and_lang += current_page_text + "\n"
            
            # For detailed block info (for title derivation's font/position scoring)
            page_content = page.get_text("dict")
            for b_dict in page_content['blocks']:
                if b_dict['type'] == 0: # text block
                    for l_dict in b_dict['lines']:
                        for s_dict in l_dict['spans']:
                            # Ensure coordinates are valid and text is not empty before adding
                            x0, y0, x1, y1 = s_dict['bbox']
                            if s_dict['text'].strip() and all(isinstance(val, (int, float)) for val in [x0, y0, x1, y1]):
                                # Collect comprehensive data for title derivation
                                sampled_raw_blocks_for_title.append({
                                    "text": s_dict['text'],
                                    "font_size": s_dict['size'],
                                    "font_name": s_dict['font'],
                                    "x0": x0,
                                    "x1": x1,
                                    "top": y0,
                                    "bottom": y1,
                                    "width": x1 - x0,
                                    "height": y1 - y0,
                                    "line_height": y1 - y0,
                                    "page": page_num
                                })
            
            # Early exit for sampling if enough data is collected
            if len(sampled_text_for_title_and_lang) >= max_chars_for_sample and len(sampled_raw_blocks_for_title) > 50: 
                break 
        
        # Sort sampled_raw_blocks_for_title for consistent processing in derive_title
        sampled_raw_blocks_for_title.sort(key=itemgetter("page", "top", "x0"))

        # --- Stage 2: Language Detection ---
        print("  Stage 2: Detecting document language...")
        lang = language.detect_language(sampled_text_for_title_and_lang) 
        # Load NLP model once for consistency across classification and title derivation
        nlp_model = language.get_multilingual_nlp(lang)

        # --- Stage 3: Full Document Block Extraction ---
        print("  Stage 3: Extracting detailed blocks from full document with PyMuPDF (language-aware)...")
        # `extract_blocks.run` handles pre-merging (horizontal fragments) and initial header/footer marking
        # Pass the detected language to extract_blocks for language-aware filtering at that stage
        all_raw_spans, page_dimensions = extract_blocks.run(pdf_path, intermediate_raw_blocks_path, detected_lang=lang)
        
        # --- Stage 4: Heading Classification ---
        print("  Stage 4: Classifying headings with heuristics and strict pruning (language-aware)...")
        # Pass the detected language and the loaded NLP model to classify_headings.run
        processed_blocks_for_outline = classify_headings.run(
            all_raw_spans, 
            page_dimensions, 
            detected_lang=lang, 
            nlp_model_for_all_nlp_tasks=nlp_model 
        )

        print(f"  Saving intermediate processed blocks to {intermediate_processed_blocks_path}")
        os.makedirs(os.path.dirname(intermediate_processed_blocks_path), exist_ok=True)
        with open(intermediate_processed_blocks_path, 'w', encoding='utf-8') as f:
            json.dump(processed_blocks_for_outline, f, indent=2, ensure_ascii=False)

        # --- Stage 5: Enhanced Title Derivation ---
        print("  Stage 5: Determining document title (language-aware)...")
        # First try the existing title derivation
        raw_title = structure_outline.derive_title_from_sampled_text_and_filename(
            sampled_raw_blocks_for_title, 
            name_without_ext, 
            nlp_model, 
            detected_lang=lang
        )
        
        # Then apply enhanced processing and truncation
        final_title = _process_and_truncate_title(raw_title, processed_blocks_for_outline, name_without_ext, lang)
        print(f"  Final title: \"{final_title}\"")

        # --- Stage 6: Outline Structuring and Pruning ---
        print("  Stage 6: Structuring and pruning the outline (language-aware)...")
        # Pass processed_blocks_for_outline, total pages, filename, and detected language
        structured_outline_result = structure_outline.run(
            processed_blocks_for_outline, 
            num_pages_total, 
            name_without_ext,
            detected_lang=lang # Pass the detected language
        )
        
        # --- Stage 7: Combine Results and Save ---
        print("  Stage 7: Combining results and saving to final JSON output.")
        final_output = {
            "title": final_title,
            "outline": structured_outline_result.get("outline", []) 
        }

        with open(final_output_path, 'w', encoding='utf-8') as f:
            json.dump(final_output, f, indent=2, ensure_ascii=False)

        print(f"Successfully processed {base_filename} to {final_output_path}")
        
        # --- Stage 8: Cleanup Intermediate Files ---
        print("  Stage 8: Cleaning up intermediate files...")
        try:
            # Remove individual intermediate files for this PDF
            if os.path.exists(intermediate_raw_blocks_path):
                os.remove(intermediate_raw_blocks_path)
                print(f"    Removed: {intermediate_raw_blocks_path}")
            
            if os.path.exists(intermediate_processed_blocks_path):
                os.remove(intermediate_processed_blocks_path)
                print(f"    Removed: {intermediate_processed_blocks_path}")
            
            # Check if intermediates directory is empty and remove it
            if os.path.exists(intermediate_output_dir) and not os.listdir(intermediate_output_dir):
                os.rmdir(intermediate_output_dir)
                print(f"    Removed empty intermediates directory: {intermediate_output_dir}")
                
        except Exception as cleanup_error:
            print(f"    Warning: Failed to cleanup some intermediate files: {cleanup_error}")

    except Exception as e:
        print(f"ERROR: Failed to process {base_filename}. Reason: {e}")
        # Optional: Print traceback for more detailed debugging
        # import traceback
        # traceback.print_exc()
    finally:
        if doc:
            doc.close()

if __name__ == "__main__":
    # Create output and intermediates directories
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
            # Process each PDF file with a progress bar
            for filename in tqdm(pdf_files, desc="Processing PDFs"):
                pdf_path = os.path.join(INPUT_DIR, filename)
                process_pdf_hybrid(pdf_path, OUTPUT_DIR)
            
            # Final cleanup of intermediates directory if it still exists and is empty
            intermediates_full_path = os.path.join(OUTPUT_DIR, INTERMEDIATES_SUBDIR)
            try:
                if os.path.exists(intermediates_full_path):
                    if not os.listdir(intermediates_full_path):
                        os.rmdir(intermediates_full_path)
                        print(f"\nFinal cleanup: Removed empty intermediates directory: {intermediates_full_path}")
                    else:
                        print(f"\nNote: Intermediates directory still contains files: {intermediates_full_path}")
            except Exception as final_cleanup_error:
                print(f"\nWarning: Final cleanup failed: {final_cleanup_error}")
            
            print(f"\nCompleted processing {len(pdf_files)} PDF files.")
