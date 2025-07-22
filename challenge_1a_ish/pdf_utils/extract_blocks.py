# pdf_utils/extract_blocks.py

import json
import os
import collections
import re
import fitz # PyMuPDF
from operator import itemgetter

def merge_nearby_blocks(blocks_on_page, y_tolerance_factor=0.6, x_tolerance=10.0, max_line_height_diff_ratio=0.2):
    """
    Performs a post-extraction merge of blocks that are vertically very close, horizontally aligned,
    and share similar font properties, likely representing single logical lines or phrases split by PDF rendering.
    Filters out near-duplicates.
    """
    if not blocks_on_page:
        return []

    # Sort by top, then x0 for consistent processing
    blocks_on_page.sort(key=itemgetter("top", "x0"))

    merged_output = []
    i = 0
    while i < len(blocks_on_page):
        current = blocks_on_page[i]
        merged_current = current.copy()

        j = i + 1
        while j < len(blocks_on_page):
            next_block = blocks_on_page[j]

            # Basic spatial checks
            # 1. Same page
            if next_block["page"] != current["page"]:
                break

            # 2. Vertical proximity: Is the next block very close vertically?
            # Use average line height of current block as reference for tolerance
            avg_line_height_current = merged_current.get("line_height", merged_current["height"])
            is_close_vertically = abs(next_block["top"] - merged_current["bottom"]) < avg_line_height_current * y_tolerance_factor

            # 3. Horizontal alignment: Do the blocks start at roughly the same X position?
            # Using a slightly larger tolerance for merging, as fragments can be slightly off
            is_aligned_horizontally = abs(next_block["x0"] - merged_current["x0"]) < x_tolerance
            # Also check if next block starts within the previous block's X range + a small margin
            is_within_current_block_x_range = next_block["x0"] >= merged_current["x0"] - 5 and \
                                              next_block["x0"] < merged_current["x0"] + merged_current["width"] + 10


            # 4. Font similarity: Are font sizes very similar and fonts (mostly) the same?
            is_similar_font_size = abs(next_block["font_size"] - merged_current["font_size"]) < 0.5
            is_similar_font_name = next_block["font_name"] == merged_current["font_name"] or \
                                   (next_block["font_name"] and merged_current["font_name"] and \
                                    next_block["font_name"].split('+')[-1] == merged_current["font_name"].split('+')[-1])

            # Check if next block is a near-duplicate (can happen with some PDF renderers)
            is_near_duplicate = (next_block["text"].strip().lower() == merged_current["text"].strip().lower() and
                                 abs(next_block["x0"] - merged_current["x0"]) < 5 and
                                 abs(next_block["top"] - merged_current["top"]) < 5)

            if is_near_duplicate:
                j += 1 # Skip duplicate
                continue

            # Advanced text flow heuristic conditions for merging
            current_ends_sentence = re.search(r'[.?!]$', merged_current["text"].strip())
            current_ends_hyphen = merged_current["text"].strip().endswith('-')
            is_connecting_punctuation = re.search(r'[,;:]$', merged_current["text"].strip()) # Ends with connecting punctuation
            next_starts_lowercase = next_block["text"].strip() and next_block["text"].strip()[0].islower()
            is_very_short_next = len(next_block["text"].split()) < 5

            # Do not merge if the next block clearly looks like a new structural element (e.g., a heading)
            next_is_larger_font = next_block["font_size"] > merged_current["font_size"] * 1.15
            next_is_bold_and_larger = next_block.get("is_bold", False) and next_is_larger_font
            next_starts_common_heading_pattern = re.match(r"^\s*(\d+(\.\d+)*\s*[.)\]]?\s*|[A-Za-z]\s*[.)\]]?\s*|[IVXLCDM]+\s*[.)\]]?\s*|[O●■*◆→])", next_block["text"].strip())
            
            # Prevent merging across clear paragraph breaks (larger vertical gap and new sentence start)
            is_large_gap_to_next = vertical_gap > avg_line_height_current * 1.2
            next_starts_uppercase_and_new_sentence = next_block["text"].strip() and \
                                                     next_block["text"].strip()[0].isupper() and \
                                                     not current_ends_hyphen and current_ends_sentence


            if next_is_bold_and_larger or (next_starts_common_heading_pattern and next_is_larger_font) or \
               next_starts_uppercase_and_new_sentence and is_large_gap_to_next:
                break # Don't merge if next block is clearly a new, larger heading or new paragraph

            # Primary merge conditions
            # Check if next block is on the same page and passes general spatial/font checks
            if is_close_vertically and \
               (is_aligned_horizontally or is_within_current_block_x_range) and \
               is_similar_font_size and \
               is_similar_font_name:

                # Merge if:
                # 1. Current line ends with hyphen (word split)
                # 2. Current line ends with connecting punctuation (e.g., comma, semicolon)
                # 3. Next line starts with lowercase and current line doesn't end a sentence (continuation of paragraph)
                # 4. Next line is very short and likely a fragment of the current line
                # 5. The merge would form a more complete sentence/thought
                if current_ends_hyphen or \
                   is_connecting_punctuation or \
                   (next_starts_lowercase and not current_ends_sentence) or \
                   is_very_short_next or \
                   (not current_ends_sentence and not next_starts_common_heading_pattern): # General continuation
                    
                    # Merge text
                    merged_text_segment = merged_current["text"]
                    if current_ends_hyphen:
                        merged_text_segment = merged_text_segment.strip()[:-1] # Remove hyphen for merge
                    else:
                        merged_text_segment += " " # Add space between words/lines

                    merged_current["text"] = (merged_text_segment + next_block["text"]).strip()

                    # Update bounding box and other properties
                    merged_current["bottom"] = next_block["bottom"]
                    merged_current["height"] = merged_current["bottom"] - merged_current["top"]
                    merged_current["x0"] = min(merged_current["x0"], next_block["x0"])
                    merged_current["x1"] = max(merged_current.get("x1", merged_current["x0"] + merged_current["width"]), next_block.get("x1", next_block["x0"] + next_block["width"]))
                    merged_current["width"] = merged_current["x1"] - merged_current["x0"]

                    merged_current["font_size"] = max(merged_current["font_size"], next_block["font_size"])
                    merged_current["is_bold"] = merged_current.get("is_bold", False) or next_block.get("is_bold", False)
                    merged_current["is_italic"] = merged_current.get("is_italic", False) or next_block.get("is_italic", False)
                    merged_current["line_height"] = merged_current["height"] # Re-calculate based on new height

                    j += 1
                else:
                    break # Conditions not met for merging current and next
            else:
                break # Conditions not met (e.g., not close, not aligned, different font)

        merged_output.append(merged_current)
        i = j

    return merged_output

def detect_and_mark_headers_footers(blocks, page_dimensions_map, min_pages_threshold=0.3, y_margin_percent=0.15):
    """
    Identifies and marks likely headers/footers by looking for repeating text
    at consistent vertical positions across a significant number of pages.
    page_dimensions_map: Map of page_num to {"width", "height"}
    """
    if not blocks:
        return blocks

    position_text_counts = collections.defaultdict(lambda: collections.defaultdict(int))
    page_presence = collections.defaultdict(bool) # Track which pages have content

    for block in blocks:
        page_presence[block["page"]] = True
        page_height_for_block = page_dimensions_map.get(block["page"], {}).get("height", 792)

        # Normalize Y position to a coarser grid to group similar positions
        norm_y_pos_top = round(block["top"] / 5) * 5
        norm_y_pos_bottom = round(block["bottom"] / 5) * 5
        text_hash = block["text"].strip().lower()

        # Check for header zone
        if norm_y_pos_top < page_height_for_block * y_margin_percent:
            position_text_counts["header"][(norm_y_pos_top, text_hash)] += 1
        # Check for footer zone
        elif norm_y_pos_bottom > page_height_for_block * (1 - y_margin_percent):
            position_text_counts["footer"][(norm_y_pos_bottom, text_hash)] += 1

    total_unique_pages = len(page_presence)
    if total_unique_pages <= 1: # Cannot reliably detect recurring headers/footers on single-page docs
        for block in blocks:
            block["is_header_footer"] = False
        return blocks

    header_footer_candidates = set()
    for category in ["header", "footer"]:
        for (pos, text_hash), count in position_text_counts[category].items():
            # A candidate must appear on a significant percentage of pages
            # and not be excessively long (likely body text misclassified as header/footer zone content)
            if count >= total_unique_pages * min_pages_threshold and \
               2 < len(text_hash) < 100: # Text length heuristic
                header_footer_candidates.add((pos, text_hash))

    for block in blocks:
        norm_y_pos_top = round(block["top"] / 5) * 5
        norm_y_pos_bottom = round(block["bottom"] / 5) * 5
        text_hash = block["text"].strip().lower()
        page_height_for_block = page_dimensions_map.get(block["page"], {}).get("height", 792)

        is_hf = False

        # Check if the block matches a common header/footer candidate
        if ((norm_y_pos_top, text_hash) in header_footer_candidates and norm_y_pos_top < page_height_for_block * y_margin_percent) or \
           ((norm_y_pos_bottom, text_hash) in header_footer_candidates and norm_y_pos_bottom > page_height_for_block * (1 - y_margin_percent)):
            is_hf = True
        
        # Additional heuristic for page numbers: short, numeric, at top/bottom of page
        if not is_hf and (len(text_hash) <= 5 and text_hash.isdigit()): # Short numeric string
            if (norm_y_pos_top < page_height_for_block * 0.10) or \
               (norm_y_pos_bottom > page_height_for_block * 0.90):
                is_hf = True
        
        # Heuristic for short, repeating common phrases (e.g., document title on every page)
        if not is_hf and (len(text_hash.split()) <= 10 and len(text_hash) > 5) : # short phrase
            # Check if this phrase appears very frequently across pages at consistent position
            if position_text_counts["header"][(norm_y_pos_top, text_hash)] >= total_unique_pages * 0.5 and norm_y_pos_top < page_height_for_block * 0.15:
                 is_hf = True
            if position_text_counts["footer"][(norm_y_pos_bottom, text_hash)] >= total_unique_pages * 0.5 and norm_y_pos_bottom > page_height_for_block * 0.85:
                 is_hf = True

        block["is_header_footer"] = is_hf

    return blocks

def extract_text_blocks_pymu(pdf_path):
    """
    Extracts text blocks with detailed metadata using PyMuPDF (Fitz).
    Returns the list of blocks and a dictionary of page dimensions (mediabox).
    """
    doc = fitz.open(pdf_path)
    all_raw_blocks = []
    page_dimensions = {}

    for page_num in range(doc.page_count):
        page = doc[page_num]
        
        page_width = page.rect.width
        page_height = page.rect.height
        page_dimensions[page_num] = {"width": page_width, "height": page_height}

        # Use get_text("dict") for structured block information
        page_content = page.get_text("dict", flags=fitz.TEXTFLAGS_RAW | fitz.TEXTFLAGS_NO_FONTS)

        for b_idx, block_dict in enumerate(page_content['blocks']):
            if block_dict['type'] == 0:  # text block
                for l_idx, line_dict in enumerate(block_dict['lines']):
                    line_text = ""
                    x0_min, y0_min, x1_max, y1_max = float('inf'), float('inf'), float('-inf'), float('-inf')
                    font_sizes = []
                    font_names = []
                    is_bold_flags = []
                    is_italic_flags = []

                    for s_idx, span_dict in enumerate(line_dict['spans']):
                        line_text += span_dict['text']
                        x0_min = min(x0_min, span_dict['bbox'][0])
                        y0_min = min(y0_min, span_dict['bbox'][1])
                        x1_max = max(x1_max, span_dict['bbox'][2])
                        y1_max = max(y1_max, span_dict['bbox'][3])
                        font_sizes.append(span_dict['size'])
                        font_names.append(span_dict['font'])

                        font_name_lower = span_dict['font'].lower()
                        is_bold_flags.append("bold" in font_name_lower or "bd" in font_name_lower or "heavy" in font_name_lower)
                        is_italic_flags.append("italic" in font_name_lower or "it" in font_name_lower)

                    if not line_text.strip():
                        continue
                    
                    # Calculate average font size for the line, accounting for potential empty font_sizes list
                    avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 0
                    if avg_font_size == 0 and font_sizes: # If all font sizes were 0, use the first one if possible
                        avg_font_size = font_sizes[0]
                    elif avg_font_size == 0: # Fallback if no font size detected
                        avg_font_size = 12.0 # Default fallback

                    most_common_font_name = max(set(font_names), key=font_names.count) if font_names else "Unknown"

                    # Check for empty bbox (can happen with some parsing issues)
                    if x0_min == float('inf') or y0_min == float('inf') or x1_max == float('-inf') or y1_max == float('-inf'):
                        continue # Skip invalid blocks

                    all_raw_blocks.append({
                        "text": line_text,
                        "font_size": avg_font_size,
                        "font_name": most_common_font_name,
                        "x0": x0_min,
                        "top": y0_min, # PyMuPDF y0 is top, y1 is bottom
                        "bottom": y1_max,
                        "width": x1_max - x0_min,
                        "height": y1_max - y0_min,
                        "page": page_num,
                        "is_bold": any(is_bold_flags),
                        "is_italic": any(is_italic_flags),
                        "line_height": y1_max - y0_min # Represents the height of the line
                    })
    
    doc.close()

    # Sort blocks for merging
    all_raw_blocks.sort(key=lambda b: (b["page"], b["top"], b["x0"]))

    # Apply merging for each page
    merged_blocks_output = []
    blocks_by_page_for_merge = collections.defaultdict(list)
    for block in all_raw_blocks:
        blocks_by_page_for_merge[block["page"]].append(block)

    for page_num in sorted(blocks_by_page_for_merge.keys()):
        # Apply slightly different tolerances for the first page (often has titles, less structured)
        if page_num == 0:
            merged_blocks_output.extend(merge_nearby_blocks(blocks_by_page_for_merge[page_num],
                                                             y_tolerance_factor=0.8,
                                                             x_tolerance=15.0))
        else:
            merged_blocks_output.extend(merge_nearby_blocks(blocks_by_page_for_merge[page_num],
                                                             y_tolerance_factor=0.6,
                                                             x_tolerance=10.0))

    final_processed_blocks = detect_and_mark_headers_footers(merged_blocks_output, page_dimensions)

    return final_processed_blocks, page_dimensions

def run(pdf_path, output_path=None): # output_path is now optional
    """
    Main function to run the block extraction process using PyMuPDF.
    Returns the list of blocks and page dimensions.
    If output_path is provided, it also writes the blocks to that path.
    """
    try:
        all_blocks, page_dimensions = extract_text_blocks_pymu(pdf_path)
    except Exception as e:
        raise RuntimeError(f"Error during PyMuPDF extraction from {pdf_path}: {e}")

    # Optionally write to file if output_path is provided (for debugging)
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(all_blocks, f, indent=2)
        except IOError as e:
            print(f"Warning: Error writing intermediate blocks to {output_path}: {e}") # Log as warning, don't raise
    
    return all_blocks, page_dimensions
