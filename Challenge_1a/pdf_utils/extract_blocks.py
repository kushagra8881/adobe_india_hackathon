import json
import os
import collections
import re
from operator import itemgetter # Ensure itemgetter is imported here
import numpy as np
import fitz # PyMuPDF


# NEW: Helper for pre-merging very tight horizontal fragments
def _pre_merge_horizontal_fragments(blocks):
    """
    Performs an aggressive, early merge of blocks that are extremely close horizontally
    and have overlapping vertical bounds, suggesting they are fragments of the same logical span.
    This fixes issues like "RFP: R RFP: Re" by stitching split words/phrases.
    """
    if not blocks:
        return []

    blocks.sort(key=itemgetter("top", "x0")) # Ensure sorted for contiguous processing

    merged_output = []
    i = 0
    while i < len(blocks):
        current = blocks[i]
        temp_merged = current.copy()
        
        # Ensure x1 is present and numerical
        temp_merged.setdefault("x1", temp_merged["x0"] + temp_merged.get("width", 0.0))
        temp_merged["x1"] = float(temp_merged["x1"]) # Ensure float

        j = i + 1
        while j < len(blocks):
            next_block = blocks[j]
            
            # Ensure next_block has numerical coords
            next_block.setdefault("x0", 0.0)
            next_block.setdefault("x1", next_block["x0"] + next_block.get("width", 0.0))
            next_block.setdefault("top", 0.0)
            next_block.setdefault("bottom", next_block["top"] + next_block.get("height", 0.0))

            if next_block["page"] != temp_merged["page"]:
                break
            
            horizontal_gap = next_block["x0"] - temp_merged["x1"]
            vertical_overlap = min(temp_merged["bottom"], next_block["bottom"]) - max(temp_merged["top"], next_block["top"])
            
            # Conditions for aggressive horizontal merge: very small horizontal gap (can be negative for overlap),
            # significant vertical overlap (meaning they are on the same effective line), and very similar fonts.
            if horizontal_gap < 5 and horizontal_gap > -5 and \
               vertical_overlap > min(temp_merged.get("height", 0.0), next_block.get("height", 0.0)) * 0.8 and \
               abs(next_block.get("font_size", 0.0) - temp_merged.get("font_size", 0.0)) < 0.2 and \
               next_block.get("font_name", "").split('+')[-1] == temp_merged.get("font_name", "").split('+')[-1]:
                
                temp_merged["text"] += next_block["text"]
                temp_merged["x1"] = next_block["x1"] 
                temp_merged["width"] = temp_merged["x1"] - temp_merged["x0"]
                temp_merged["bottom"] = max(temp_merged["bottom"], next_block["bottom"])
                temp_merged["height"] = temp_merged["bottom"] - temp_merged["top"]
                temp_merged["is_bold"] = temp_merged.get("is_bold", False) or next_block.get("is_bold", False)
                temp_merged["is_italic"] = temp_merged.get("is_italic", False) or next_block.get("is_italic", False)
                temp_merged["font_size"] = max(temp_merged.get("font_size", 0.0), next_block.get("font_size", 0.0)) 
                
                j += 1
            else:
                break
        
        merged_output.append(temp_merged)
        i = j

    return merged_output


def detect_columns(blocks_on_page, page_width, x_tolerance=10.0, min_column_width_ratio=0.05):
    """
    Detects text columns on a page based on x0 coordinates.
    Returns a list of column ranges (x_min, x_max).
    """
    if not blocks_on_page:
        return [(0, page_width)] 

    relevant_blocks_x0 = [b["x0"] for b in blocks_on_page if b["width"] > 5 and b["width"] < page_width * 0.9]
    x0_coords = np.array(relevant_blocks_x0)
    
    if len(x0_coords) < 2:
        return [(0, page_width)] 

    sorted_unique_x0s = np.sort(np.unique(x0_coords))

    gaps = sorted_unique_x0s[1:] - sorted_unique_x0s[:-1]
    
    column_break_indices = np.where(gaps > x_tolerance)[0]

    columns = []
    current_column_start_x = sorted_unique_x0s[0]

    for i, break_idx in enumerate(column_break_indices):
        column_end_x = sorted_unique_x0s[break_idx]
        if (column_end_x - current_column_start_x) > page_width * min_column_width_ratio:
            columns.append((current_column_start_x, column_end_x + x_tolerance)) 
        current_column_start_x = sorted_unique_x0s[break_idx + 1]

    if (page_width - current_column_start_x) > page_width * min_column_width_ratio:
        columns.append((current_column_start_x, page_width)) 

    if not columns: 
        return [(0, page_width)]
    
    columns.sort(key=itemgetter(0))

    merged_columns = []
    if columns:
        current_merged_start, current_merged_end = columns[0]
        for i in range(1, len(columns)):
            next_start, next_end = columns[i]
            if next_start <= current_merged_end + x_tolerance: 
                current_merged_end = max(current_merged_end, next_end)
            else:
                merged_columns.append((current_merged_start, current_merged_end))
                current_merged_start, current_merged_end = next_start, next_end
        merged_columns.append((current_merged_start, current_merged_end))
    
    if len(merged_columns) == 1 and (merged_columns[0][1] - merged_columns[0][0]) < page_width * 0.9:
        return [(0, page_width)] 
    
    merged_columns = [col for col in merged_columns if (col[1] - col[0]) > page_width * 0.01]
    
    if not merged_columns: 
        return [(0, page_width)]

    return merged_columns

def merge_nearby_blocks_simple(blocks_in_column, y_tolerance_factor=0.6, x_tolerance=10.0):
    """
    Performs a basic post-extraction merge of blocks that are vertically very close,
    horizontally aligned, and share similar font properties, likely representing 
    single logical lines or phrases split by PDF rendering.
    """
    if not blocks_in_column:
        return []

    blocks_in_column.sort(key=itemgetter("top", "x0"))

    merged_output = []
    i = 0
    while i < len(blocks_in_column):
        current = blocks_in_column[i]
        merged_current = current.copy()

        j = i + 1
        while j < len(blocks_in_column):
            next_block = blocks_in_column[j]

            if next_block["page"] != merged_current["page"]:
                break
            
            is_near_duplicate = (next_block["text"].strip().lower() == merged_current["text"].strip().lower() and
                                 abs(next_block["x0"] - merged_current["x0"]) < 5 and
                                 abs(next_block["top"] - merged_current["top"]) < 5)
            if is_near_duplicate:
                j += 1 
                continue

            avg_line_height_current = merged_current.get("line_height", merged_current["height"])
            vertical_gap = next_block["top"] - merged_current["bottom"]
            is_very_close_vertically = abs(vertical_gap) < (avg_line_height_current * y_tolerance_factor) and vertical_gap >= -5.0 
            is_aligned_horizontally = abs(next_block["x0"] - merged_current["x0"]) < x_tolerance
            is_similar_font_size = abs(next_block["font_size"] - merged_current["font_size"]) < 0.5
            font_name_current_base = merged_current["font_name"].split('+')[-1] if merged_current["font_name"] else ""
            font_name_next_base = next_block["font_name"].split('+')[-1] if next_block["font_name"] else ""
            is_similar_font_name = font_name_next_base == font_name_current_base

            should_merge = False
            if is_very_close_vertically and is_aligned_horizontally and is_similar_font_size and is_similar_font_name:
                if merged_current["text"].strip().endswith('-') or \
                   (not re.search(r'[.?!]$', merged_current["text"].strip()) and len(next_block["text"].strip().split()) > 0 and next_block["text"].strip()[0].islower()):
                    should_merge = True
                
            if should_merge:
                merged_text = merged_current["text"]
                if merged_text.strip().endswith('-'):
                    merged_text = merged_text.strip()[:-1] 
                else:
                    merged_text += " " 

                merged_current["text"] = (merged_text + next_block["text"]).strip()
                merged_current["bottom"] = next_block["bottom"]
                merged_current["height"] = merged_current["bottom"] - merged_current["top"]
                merged_current["x0"] = min(merged_current["x0"], next_block["x0"]) 
                merged_current["x1"] = max(merged_current.get("x1", merged_current["x0"] + merged_current["width"]), next_block.get("x1", next_block["x0"] + next_block["width"]))
                merged_current["width"] = merged_current["x1"] - merged_current["x0"]
                merged_current["font_size"] = max(merged_current["font_size"], next_block["font_size"]) 
                merged_current["is_bold"] = merged_current.get("is_bold", False) or next_block.get("is_bold", False)
                merged_current["is_italic"] = merged_current.get("is_italic", False) or next_block.get("is_italic", False)
                merged_current["line_height"] = max(merged_current.get("line_height", 0), next_block.get("line_height", 0), merged_current["height"])

                j += 1
            else:
                break

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
    page_presence = collections.defaultdict(bool)

    for block in blocks:
        page_presence[block["page"]] = True
        page_height_for_block = page_dimensions_map.get(block["page"], {}).get("height", 792)

        norm_y_pos_top = round(block["top"] / 5) * 5 
        norm_y_pos_bottom = round(block["bottom"] / 5) * 5
        text_hash = block["text"].strip().lower()

        if norm_y_pos_top < page_height_for_block * y_margin_percent:
            position_text_counts["header"][(norm_y_pos_top, text_hash)] += 1
        elif norm_y_pos_bottom > page_height_for_block * (1 - y_margin_percent):
            position_text_counts["footer"][(norm_y_pos_bottom, text_hash)] += 1

    total_unique_pages = len(page_presence)
    if total_unique_pages <= 1:
        for block in blocks:
            block["is_header_footer"] = False
        return blocks

    header_footer_candidates = set()
    for category in ["header", "footer"]:
        for (pos, text_hash), count in position_text_counts[category].items():
            if count >= total_unique_pages * min_pages_threshold and \
               2 < len(text_hash) < 100:
                header_footer_candidates.add((pos, text_hash))
            if len(text_hash) <= 5 and text_hash.isdigit() and count >= total_unique_pages * 0.5:
                header_footer_candidates.add((pos, text_hash))


    for block in blocks:
        norm_y_pos_top = round(block["top"] / 5) * 5
        norm_y_pos_bottom = round(block["bottom"] / 5) * 5
        text_hash = block["text"].strip().lower()
        page_height_for_block = page_dimensions_map.get(block["page"], {}).get("height", 792)

        is_hf = False

        if ((norm_y_pos_top, text_hash) in header_footer_candidates and norm_y_pos_top < page_height_for_block * y_margin_percent) or \
           ((norm_y_pos_bottom, text_hash) in header_footer_candidates and norm_y_pos_bottom > page_height_for_block * (1 - y_margin_percent)):
            is_hf = True
        
        if not is_hf and (len(text_hash) <= 5 and text_hash.isdigit()):
            if (norm_y_pos_top < page_height_for_block * 0.10 and position_text_counts["header"][(norm_y_pos_top, text_hash)] >= total_unique_pages * 0.5) or \
               (norm_y_pos_bottom > page_height_for_block * 0.90 and position_text_counts["footer"][(norm_y_pos_bottom, text_hash)] >= total_unique_pages * 0.5):
                is_hf = True
        
        if not is_hf and (len(text_hash.split()) <= 10 and len(text_hash) > 5) :
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
    Blocks are raw spans, with a very simple initial merge.
    """
    doc = fitz.open(pdf_path)
    all_raw_spans_with_metadata = [] 

    page_dimensions = {}

    for page_num in range(doc.page_count):
        page = doc[page_num]
        
        page_width = page.rect.width
        page_height = page.rect.height
        page_dimensions[page_num] = {"width": page_width, "height": page_height}

        page_content = page.get_text("dict")  

        page_spans_raw = [] 
        for b_dict in page_content['blocks']:
            if b_dict['type'] == 0: 
                for l_dict in b_dict['lines']:
                    for s_dict in l_dict['spans']:
                        line_text = s_dict['text']
                        if not line_text.strip(): continue

                        font_name_lower = s_dict['font'].lower()
                        is_bold = "bold" in font_name_lower or "bd" in font_name_lower or "heavy" in font_name_lower or "black" in font_name_lower
                        is_italic = "italic" in font_name_lower or "it" in font_name_lower or "oblique" in font_name_lower

                        x0, y0, x1, y1 = s_dict['bbox']
                        if not all(isinstance(val, (int, float)) for val in [x0, y0, x1, y1]):
                            continue 

                        page_spans_raw.append({
                            "text": line_text,
                            "font_size": s_dict['size'],
                            "font_name": s_dict['font'],
                            "x0": x0,
                            "top": y0,
                            "bottom": y1,
                            "width": x1 - x0,
                            "height": y1 - y0,
                            "page": page_num,
                            "is_bold": is_bold,
                            "is_italic": is_italic,
                            "line_height": y1 - y0
                        })
        
        page_spans_raw.sort(key=itemgetter("top", "x0"))

        # NEW: Apply aggressive horizontal fragment pre-merging here
        page_spans_pre_merged = _pre_merge_horizontal_fragments(page_spans_raw)

        columns = detect_columns(page_spans_pre_merged, page_width) # Use pre_merged blocks for column detect
        
        blocks_in_columns = collections.defaultdict(list)
        unassigned_blocks = [] 

        for block in page_spans_pre_merged: # Use pre_merged blocks for column assignment
            assigned_to_column = False
            for col_idx, (col_x_min, col_x_max) in enumerate(columns):
                block_center_x = block["x0"] + block["width"] / 2
                
                if (col_x_min <= block_center_x <= col_x_max) or \
                   (len(columns) == 1 and block["width"] > page_width * 0.7): 
                    blocks_in_columns[col_idx].append(block)
                    assigned_to_column = True
                    break
            if not assigned_to_column:
                unassigned_blocks.append(block)

        columnar_merged_blocks = []
        for col_idx in sorted(blocks_in_columns.keys()):
            column_blocks = blocks_in_columns[col_idx]
            # Use the simpler merge here, the main logical merge is in classify_headings
            merged_column_blocks = merge_nearby_blocks_simple(column_blocks, y_tolerance_factor=0.6, x_tolerance=5.0) 
            columnar_merged_blocks.extend(merged_column_blocks)
        
        unassigned_blocks.sort(key=itemgetter("top", "x0"))
        merged_unassigned_blocks = merge_nearby_blocks_simple(unassigned_blocks, y_tolerance_factor=0.8, x_tolerance=20.0) 

        all_raw_spans_with_metadata.extend(columnar_merged_blocks)
        all_raw_spans_with_metadata.extend(merged_unassigned_blocks) 
            
    doc.close()

    # Apply header/footer detection to the initial set of blocks
    final_blocks_with_hf_marked = detect_and_mark_headers_footers(all_raw_spans_with_metadata, page_dimensions)

    final_blocks_with_hf_marked.sort(key=itemgetter("page", "top", "x0")) # Use itemgetter directly

    return final_blocks_with_hf_marked, page_dimensions

def run(pdf_path, output_path=None): 
    """
    Main function to run the block extraction process using PyMuPDF.
    Returns the list of blocks and page dimensions.
    If output_path is provided, it also writes the blocks to that path.
    """
    try:
        all_blocks, page_dimensions = extract_text_blocks_pymu(pdf_path)
    except Exception as e:
        raise RuntimeError(f"Error during PyMuPDF extraction from {pdf_path}: {e}")

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(all_blocks, f, indent=2)
        except IOError as e:
            print(f"Warning: Error writing intermediate blocks to {output_path}: {e}")
    
    return all_blocks, page_dimensions