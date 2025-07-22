# pdf_utils/classify_headings.py

import json
import statistics
import re
import os
import spacy
import collections
from operator import itemgetter

# No ML model reliance for maximum heuristic precision under given constraints.
# HEADING_CLASSIFIER_MODEL_PATH = "models/heading_classifier.pkl"
# heading_classifier_model = None

SPACY_MODEL_NAME = "xx_ent_wiki_sm" # Stick to this one for size/offline constraints
nlp = None
try:
    # Use disable=['parser', 'ner', 'textcat'] for faster loading and smaller memory footprint
    nlp = spacy.load(SPACY_MODEL_NAME, disable=['parser', 'ner', 'textcat'])
    print(f"Loaded spaCy model: {SPACY_MODEL_NAME} for multilingual analysis.")
except OSError:
    print(f"SpaCy model '{SPACY_MODEL_NAME}' not found. Multilingual features will be limited. Please ensure it's downloaded manually for offline use.")
except Exception as e:
    print(f"Error loading spaCy model: {e}. Multilingual features will be limited.")


def build_logical_blocks(raw_blocks):
    """
    Groups raw extracted lines into logical blocks (paragraphs, multi-line list items)
    based on vertical and horizontal proximity, and flow indicators.
    This function processes blocks from PyMuPDF, which are already somewhat grouped.
    The goal here is to further merge lines that clearly belong to the same logical unit.
    """
    if not raw_blocks:
        return []

    # Ensure blocks are sorted by page, then top, then x0 at the very start
    raw_blocks.sort(key=itemgetter("page", "top", "x0"))

    logical_blocks = []
    i = 0
    while i < len(raw_blocks):
        current_block = raw_blocks[i]
        
        # Initialize logical_block with a copy of the current block
        # Make a deep copy if block contents include mutable types that you want to preserve separately
        # For dictionaries with basic types, shallow copy is fine initially.
        logical_block = current_block.copy()
        
        j = i + 1
        while j < len(raw_blocks):
            next_block = raw_blocks[j]

            # Conditions for merging
            # 1. Same page
            if next_block["page"] != logical_block["page"]:
                break

            # 2. Vertical Proximity: Is the gap between current and next small?
            vertical_gap = next_block["top"] - logical_block["bottom"]
            # Use line_height of the current block for relative comparison
            avg_line_height = logical_block.get("line_height", logical_block.get("height", 12))
            is_close_vertically = 0 <= vertical_gap < avg_line_height * 0.8 # Allow for slight overlap or small gap

            # 3. Horizontal Alignment: Do they align sufficiently?
            # Consider both starting point alignment and whether they fall within a similar column
            is_aligned_horizontally = abs(next_block["x0"] - logical_block["x0"]) < 15 # Tolerance for slight indents within a paragraph
            is_within_current_block_x_range = next_block["x0"] >= logical_block["x0"] - 5 and \
                                              next_block["x0"] < logical_block["x0"] + logical_block["width"] + 10


            # 4. Font Similarity: Are font sizes and names similar?
            is_similar_font_size = abs(next_block["font_size"] - logical_block["font_size"]) < 0.5
            is_similar_font_name = next_block["font_name"] == logical_block["font_name"] or \
                                   (next_block["font_name"] and logical_block["font_name"] and \
                                    next_block["font_name"].split('+')[-1] == logical_block["font_name"].split('+')[-1])

            # 5. Text Flow Indicators: Heuristics to decide if they are part of the same sentence/paragraph
            current_ends_sentence = re.search(r'[.?!]$', logical_block["text"].strip())
            current_ends_hyphen = logical_block["text"].strip().endswith('-')
            is_connecting_punctuation_at_end = re.search(r'[,;:]$', logical_block["text"].strip())
            next_starts_lowercase = next_block["text"].strip() and next_block["text"].strip()[0].islower()
            is_very_short_next = len(next_block["text"].split()) < 5

            # Do not merge if the next block looks like a new, distinct element (e.g., a sub-heading, bullet point, or new paragraph)
            next_starts_heading_cue = (
                next_block.get("is_bold", False) and next_block["font_size"] > logical_block["font_size"] * 1.15 # Significantly larger font for new heading
            ) or re.match(r"^\s*(\d+(\.\d+)*\s*[.)\]]?\s*|[A-Za-z]\s*[.)\]]?\s*|[IVXLCDM]+\s*[.)\]]?\s*|[O●■*◆→])", next_block["text"].strip())
            
            # Prevent merging across clear paragraph breaks
            is_large_gap_to_next = vertical_gap > avg_line_height * 1.5 # A more significant vertical gap
            next_starts_uppercase_and_new_sentence = next_block["text"].strip() and \
                                                     next_block["text"].strip()[0].isupper() and \
                                                     not current_ends_hyphen and \
                                                     current_ends_sentence


            should_merge = False
            if is_close_vertically and (is_aligned_horizontally or is_within_current_block_x_range) and is_similar_font_size and is_similar_font_name:
                if current_ends_hyphen or is_connecting_punctuation_at_end or \
                   (next_starts_lowercase and not current_ends_sentence) or \
                   is_very_short_next or \
                   (not current_ends_sentence and not next_starts_heading_cue and not is_large_gap_to_next):
                    should_merge = True
                # Special case for titles/labels that span multiple lines, often bold and then regular
                elif re.match(r"^\s*[A-Z][A-Z\s]*:\s*$", logical_block["text"].strip()) and next_block["x0"] >= logical_block["x0"]:
                    should_merge = True
            
            # Final checks to prevent over-merging
            if next_starts_uppercase_and_new_sentence and is_large_gap_to_next and not current_ends_hyphen:
                should_merge = False
            
            # Avoid merging if the combined text becomes excessively long for a single logical block
            if should_merge and (len(logical_block["text"]) + len(next_block["text"])) > 500: # Arbitrary limit for a block
                should_merge = False


            if should_merge:
                merged_text = logical_block["text"]
                if merged_text.strip().endswith('-'):
                    merged_text = merged_text.strip()[:-1]  # Remove hyphen
                else:
                    merged_text += " " # Add space between merged lines

                logical_block["text"] = (merged_text + next_block["text"]).strip()
                logical_block["bottom"] = next_block["bottom"]
                logical_block["height"] = logical_block["bottom"] - logical_block["top"]
                logical_block["x0"] = min(logical_block["x0"], next_block["x0"]) # Expand x0 to the left if next block starts earlier
                logical_block["x1"] = max(logical_block.get("x1", logical_block["x0"] + logical_block["width"]), next_block.get("x1", next_block["x0"] + next_block["width"]))
                logical_block["width"] = logical_block["x1"] - logical_block["x0"]

                # Preserve bold/italic if any part was bold/italic
                logical_block["is_bold"] = logical_block.get("is_bold", False) or next_block.get("is_bold", False)
                logical_block["is_italic"] = logical_block.get("is_italic", False) or next_block.get("is_italic", False)
                logical_block["line_height"] = logical_block["height"] # Recalculate line height based on new extent

                j += 1
            else:
                break # Cannot merge current and next

        logical_blocks.append(logical_block)
        i = j
    
    # After merging, re-sort as merging can slightly alter order if x0 was significantly adjusted
    logical_blocks.sort(key=itemgetter("page", "top", "x0"))
    return logical_blocks


def calculate_all_features(blocks, page_dimensions):
    """
    Calculates intrinsic and contextual features for all blocks.
    Assumes blocks are already sorted by page, then top, then x0.
    page_dimensions: A dictionary {page_num: {"width", "height"}}
    """
    if not blocks:
        return [], 0

    # First, run `build_logical_blocks` to get coherent text units
    # This might already be done in extract_blocks, but doing it here ensures consistency
    # and accounts for any further merging desired specifically for classification.
    logical_blocks = build_logical_blocks(blocks)
    blocks = logical_blocks # Use these now for feature extraction

    all_font_sizes = [block_item["font_size"] for block_item in blocks if block_item["font_size"] is not None and block_item["font_size"] > 0]
    
    if not all_font_sizes:
        most_common_font_size = 12.0 # Default if no font sizes
    else:
        try:
            # Use median as it's more robust to outliers than mode for "common" text size
            most_common_font_size = statistics.median(all_font_sizes)
        except statistics.StatisticsError: # If only one unique size
            most_common_font_size = all_font_sizes[0] if all_font_sizes else 12.0
        
        if most_common_font_size == 0:
            most_common_font_size = 12.0


    blocks_by_page = collections.defaultdict(list)
    for block_item in blocks:
        blocks_by_page.setdefault(block_item["page"], []).append(block_item)
    
    page_layout_info = {}
    for page_num, page_blocks_list in blocks_by_page.items():
        if not page_blocks_list: continue # Skip empty pages
        min_x0_page = min(b["x0"] for b in page_blocks_list)
        max_x1_page = max(b["x0"] + b["width"] for b in page_blocks_list)
        
        # Consider average text line x0 as a more stable reference than absolute min_x0
        # Exclude header/footers from this average as they might skew it
        content_x0s = [b["x0"] for b in page_blocks_list if not b.get("is_header_footer", False) and b["text"].strip()]
        avg_x0_page = statistics.mean(content_x0s) if content_x0s else min_x0_page # Fallback

        page_layout_info[page_num] = {
            "min_x0": min_x0_page,
            "max_x1": max_x1_page,
            "avg_x0": avg_x0_page,
        }
        if page_num in page_dimensions:
            page_layout_info[page_num]["page_width"] = page_dimensions[page_num]["width"]
            page_layout_info[page_num]["page_height"] = page_dimensions[page_num]["height"]
        else:
            page_layout_info[page_num]["page_width"] = 595.0 # A4 width in points
            page_layout_info[page_num]["page_height"] = 842.0 # A4 height in points


    processed_blocks = []
    for i, block_orig in enumerate(blocks):
        features = {
            "text": block_orig["text"],
            "font_size": block_orig.get("font_size", most_common_font_size),
            "is_bold": block_orig.get("is_bold", False),
            "is_italic": block_orig.get("is_italic", False),
            "x0": block_orig["x0"],
            "top": block_orig["top"],
            "bottom": block_orig.get("bottom", block_orig["top"] + block_orig.get("height", most_common_font_size)),
            "width": block_orig["width"],
            "height": block_orig.get("height", most_common_font_size),
            "page": block_orig["page"],
            "line_height": block_orig.get("line_height", block_orig.get("height", most_common_font_size)),
            "lang": "und", # Undetermined
            "is_all_caps": False,
            "line_length": len(block_orig["text"]),
            "num_words": 0,
            "starts_with_number_or_bullet": False,
            "is_short_line": False,
            "is_decorative_line": False,
            "is_pure_number_or_symbol_line": False,
            "is_table_like_element": False,
            "is_quote_or_citation": False,
            "is_form_field_label": False,
            "is_tagline_or_url": False,
            "is_fragmented_noise": False,
            "is_header_footer": block_orig.get("is_header_footer", False),
            "is_smaller_than_predecessor_and_not_body": False,
            "x0_normalized": 0.0, # Normalized x0 relative to page width or text frame
            "relative_x0_to_common": 0.0 # Relative to common text block x0 on page
        }

        # Handle zero font size
        if features["font_size"] == 0:
            features["font_size"] = most_common_font_size

        features["font_size_ratio_to_common"] = features["font_size"] / most_common_font_size
        features["font_size_deviation_from_common"] = features["font_size"] - most_common_font_size

        if nlp:
            try:
                # Use a smaller slice for faster language detection if the block is very long
                doc = nlp(features["text"][:500])
                # Access _ attribute for LanguageDetector result
                if hasattr(doc, "_") and hasattr(doc._, "language") and doc._.language['language'] != "un":
                    features["lang"] = doc._.language['language']
            except Exception:
                pass # Lang detection can fail, default to "und"
        
        is_cjk = features["lang"] in ["zh", "ja", "ko"]

        features["is_all_caps"] = False if is_cjk else (features["text"].isupper() and 2 < len(features["text"]) < 50 and any(c.isalpha() for c in features["text"]))
        
        features["num_words"] = len(features["text"]) if is_cjk else len(features["text"].split())

        features["starts_with_number_or_bullet"] = bool(
            re.match(r"^\s*(\d+(\.\d+)*[\s.)\]}]?\s*|[A-Za-z][.)\]}]?\s*|[IVXLCDM]+\s*[.)\]]?\s*|[O●■*◆→\-])", features["text"].strip()) and \
            not re.fullmatch(r'[\s\-—_]{3,}', features["text"].strip()) # Exclude pure separators
        )
        
        cleaned_text = features["text"].strip()
        # Refined decorative line detection
        if (len(cleaned_text) > 2 and re.fullmatch(r'[\s\-—_•*●■]*', cleaned_text) and len(set(cleaned_text.replace(" ", ""))) < 3) or \
           (len(cleaned_text) == 1 and cleaned_text in "O●■*" and not features["starts_with_number_or_bullet"]) or \
           (len(cleaned_text) == 1 and cleaned_text.lower() == "o" and not features["is_bold"] and features["font_size_ratio_to_common"] < 1.05 and not features["starts_with_number_or_bullet"]) or \
           (re.fullmatch(r'^-+$', cleaned_text)): # Pure dashes as separators
            features["is_decorative_line"] = True
            features["is_pure_number_or_symbol_line"] = True # Often overlaps

        alphanumeric_content = re.sub(r'[^a-zA-Z0-9]', '', cleaned_text)
        
        # Refined pure number/symbol line detection
        if not alphanumeric_content and len(cleaned_text) < 15: # No alphanumeric content, very short
            features["is_pure_number_or_symbol_line"] = True
        elif (cleaned_text.isdigit() or (cleaned_text.endswith('.') and cleaned_text[:-1].isdigit())) and len(cleaned_text) <= 5:
            if features["num_words"] == 1 and not features["is_bold"] and features["font_size_ratio_to_common"] < 1.15:
                features["is_pure_number_or_symbol_line"] = True
        elif (re.fullmatch(r'^[IVXLCDM]+\.$', cleaned_text) or re.fullmatch(r'^[A-Z]\.$', cleaned_text)) and (len(cleaned_text) <= 3 and not features["is_bold"]):
             features["is_pure_number_or_symbol_line"] = True


        features["is_short_line"] = (len(features["text"]) < 70) and \
                                     ((features["num_words"] < 12) or (is_cjk and features["num_words"] < 25))


        prev_block = blocks[i-1] if i > 0 and blocks[i-1]["page"] == block_orig["page"] else None
        next_block = blocks[i+1] if i < len(blocks) - 1 and blocks[i+1]["page"] == block_orig["page"] else None

        features["is_first_on_page"] = (prev_block is None) or (prev_block["page"] != features["page"])
        features["is_last_on_page"] = (next_block is None) or (next_block["page"] != features["page"])

        if prev_block:
            features["prev_font_size"] = prev_block["font_size"]
            features["prev_y_gap"] = abs(features["top"] - prev_block["bottom"])
            features["prev_x_diff"] = features["x0"] - prev_block["x0"]
            
            # Use average line height of current block for relative comparison
            current_line_height = features.get("line_height", features.get("height", most_common_font_size))
            features["is_preceded_by_larger_gap"] = features["prev_y_gap"] > current_line_height * 1.8 # Larger gap before
            
            # Check for font size regression indicating a sub-item, not a major heading
            if features["font_size"] < prev_block["font_size"] * 0.9 and \
               features["font_size_ratio_to_common"] > 0.95 and \
               not prev_block.get("is_bold", False) and \
               len(prev_block["text"].strip()) > 10 and \
               not re.match(r'[.?!]$', prev_block["text"].strip()): # If previous block doesn't end a sentence
                features["is_smaller_than_predecessor_and_not_body"] = True
            else:
                features["is_smaller_than_predecessor_and_not_body"] = False

        else:
            features["prev_font_size"] = 0
            features["prev_y_gap"] = 0
            features["prev_x_diff"] = 0
            features["is_preceded_by_larger_gap"] = True # First block on page might act like one if positioned well
            features["is_smaller_than_predecessor_and_not_body"] = False


        if next_block:
            features["next_font_size"] = next_block["font_size"]
            features["next_y_gap"] = abs(next_block["top"] - features["bottom"])
            features["next_x_diff"] = next_block["x0"] - features["x0"]
            features["is_followed_by_smaller_text"] = next_block["font_size"] < features["font_size"] * 0.9
            
            # Use average line height of current block for relative comparison
            current_line_height = features.get("line_height", features.get("height", most_common_font_size))
            features["is_followed_by_larger_gap"] = features["next_y_gap"] > current_line_height * 1.8
        else:
            features["next_font_size"] = 0
            features["next_y_gap"] = 0
            features["next_x_diff"] = 0
            features["is_followed_by_smaller_text"] = False
            features["is_followed_by_larger_gap"] = True # Last block on page might act like one

        page_info = page_layout_info.get(features["page"])
        if page_info and page_info["page_width"] > 0:
            page_width = page_info["page_width"]
            page_height = page_info["page_height"]
            
            block_center_x = features["x0"] + features["width"] / 2
            page_center_x = page_width / 2
            features["is_centered"] = abs(block_center_x - page_center_x) < (page_width * 0.05) # Within 5% of center

            # Normalize x0 relative to page width
            features["x0_normalized"] = features["x0"] / page_width
            
            # Relative x0 to common starting point of main body text
            # Ensure avg_x0_page is not None/0 before subtraction
            features["relative_x0_to_common"] = features["x0"] - page_info["avg_x0"] if page_info.get("avg_x0") else 0


        else:
            features["is_centered"] = False
            features["x0_normalized"] = features["x0"] / 595.0 # Fallback to A4 width
            features["relative_x0_to_common"] = 0.0 # Cannot calculate without avg_x0


        # Table-like element detection (e.g., side-by-side text, list items with multiple columns)
        current_page_blocks_list = blocks_by_page.get(features["page"], [])
        num_short_bold_neighbors_at_same_y = 0
        y_tolerance = features["line_height"] * 0.7 # Tolerance for being on the same visual line
        
        for other_block in current_page_blocks_list:
            if other_block == block_orig: continue # Don't compare with self
            
            # Check if another block is on roughly the same horizontal level (y-axis)
            is_same_y_level = (other_block["top"] >= features["top"] - y_tolerance and
                               other_block["top"] <= features["top"] + y_tolerance) or \
                              (other_block["bottom"] >= features["bottom"] - y_tolerance and
                               other_block["bottom"] <= features["bottom"] + y_tolerance)


            if is_same_y_level and \
               other_block["x0"] != features["x0"] and \
               len(other_block["text"].strip()) < 50 and \
               (other_block.get("is_bold", False) or other_block.get("starts_with_number_or_bullet", False) or (other_block.get("font_size_ratio_to_common", 0) > 1.05)):
                num_short_bold_neighbors_at_same_y += 1
        
        if num_short_bold_neighbors_at_same_y >= 1:
            features["is_table_like_element"] = True

        # Form field label heuristic
        if re.match(r"^\s*[A-Z][A-Z\s]*:\s*$", cleaned_text) or \
           (len(cleaned_text.split()) <= 4 and cleaned_text.endswith(":") and features["is_bold"] and features["font_size_ratio_to_common"] >= 1.0):
            features["is_form_field_label"] = True
            features["is_table_like_element"] = True # Form labels are often tabular in nature

        # Quote or citation detection
        if re.match(r"^\s*[\"„“\u201c\u201d]", cleaned_text) or \
           (features["x0"] > (page_info["min_x0"] + 20 if page_info else 20) and # Indented
            features["width"] < (page_info["page_width"] * 0.75 if page_info else 450) and # Narrower
            features["font_size_ratio_to_common"] < 1.05 and # Not a heading font
            features["is_italic"] and len(cleaned_text) > 50): # Longer italic block
            features["is_quote_or_citation"] = True

        # Tagline or URL detection
        if re.match(r"^(www\.|http[s]?://|ftp://)", cleaned_text, re.IGNORECASE) or \
           (features["is_last_on_page"] and features["font_size_ratio_to_common"] < 0.9 and len(cleaned_text.split()) < 15 and not features["starts_with_number_or_bullet"] and not features["is_all_caps"] and not features["is_bold"]):
            features["is_tagline_or_url"] = True

        block_orig.update(features)
        processed_blocks.append(block_orig)
    return processed_blocks, most_common_font_size

def dynamic_thresholds(all_font_sizes, most_common_font_size):
    """
    Calculates dynamic font size thresholds based on the distribution of font sizes in the document.
    Prioritizes distinct large font sizes.
    """
    if not all_font_sizes or most_common_font_size == 0:
        return {"H1": 16.0, "H2": 14.0, "H3": 12.0, "H4": 11.0} # Fallback to default

    # Filter out very small or very large outliers (e.g., logos, single characters)
    filtered_sizes = [s for s in all_font_sizes if most_common_font_size * 0.7 < s < most_common_font_size * 3.0]
    if not filtered_sizes:
        filtered_sizes = all_font_sizes # Use all if filtering made it empty

    # Count occurrences of each unique size
    size_counts = collections.Counter(filtered_sizes)
    # Sort unique sizes by value (descending)
    unique_sorted_sizes = sorted(size_counts.keys(), reverse=True)

    thresholds = {}
    
    # Identify potential heading sizes based on distinct font jumps
    # Start with sizes significantly larger than the common body text
    candidate_heading_sizes = [s for s in unique_sorted_sizes if s >= most_common_font_size * 1.1] # Lower threshold for candidates
    candidate_heading_sizes = sorted(list(set(candidate_heading_sizes)), reverse=True) # Ensure uniqueness and sort again

    # Assign levels based on relative size, trying to find distinct jumps
    if len(candidate_heading_sizes) > 0:
        thresholds["H1"] = candidate_heading_sizes[0]
        # Iterate to find distinct levels, with a minimum size difference between levels
        current_h_level = 2
        for i in range(1, len(candidate_heading_sizes)):
            prev_size = candidate_heading_sizes[i-1]
            current_size = candidate_heading_sizes[i]
            # If there's a noticeable drop from the previous largest heading candidate
            if (prev_size - current_size) >= 1.0 and current_size >= most_common_font_size * 1.05:
                 if current_h_level <= 4:
                     thresholds[f"H{current_h_level}"] = current_size
                     current_h_level += 1
                 else:
                     break # Found enough heading levels

    # Ensure a sensible hierarchy and minimum size differences if not enough distinct sizes found
    if "H1" not in thresholds:
        thresholds["H1"] = most_common_font_size + 6.0
    
    # Ensure H2 is smaller than H1, etc., with a minimum step down
    if "H2" not in thresholds or thresholds["H2"] >= thresholds["H1"] - 0.75:
        thresholds["H2"] = thresholds["H1"] - 2.0
    
    if "H3" not in thresholds or thresholds["H3"] >= thresholds["H2"] - 0.75:
        thresholds["H3"] = thresholds["H2"] - 1.5

    if "H4" not in thresholds or thresholds["H4"] >= thresholds["H3"] - 0.75:
        thresholds["H4"] = thresholds["H3"] - 1.0

    # Ensure no heading is smaller than common font size
    for key in ["H1", "H2", "H3", "H4"]:
        if thresholds[key] < most_common_font_size * 1.05:
            thresholds[key] = most_common_font_size * 1.05

    return thresholds


def classify_block_heuristic(block, dynamic_th, common_font_size):
    """
    Classifies a single block using a weighted heuristic scoring approach,
    leveraging intrinsic and contextual features.
    Returns the heading level (e.g., "H1", "H2") or None if it's body text/other.
    """
    # IMMEDIATE AND CRITICAL FILTERING FOR NON-MEANINGFUL / DECORATIVE LINES / TABLE ELEMENTS / QUOTES / TAGLINES / HEADERS/FOOTERS
    if block.get("is_decorative_line", False) or \
       block.get("is_pure_number_or_symbol_line", False) or \
       block.get("is_table_like_element", False) or \
       block.get("is_quote_or_citation", False) or \
       block.get("is_tagline_or_url", False) or \
       block.get("is_header_footer", False) or \
       len(block["text"].strip()) < 2: # Very short texts are rarely headings unless they are numbers/bullets handled below
        return None

    weights_base = {
        "font_size_prominence": 4.0,
        "is_bold": 4.0,
        "is_centered": 4.5,
        "is_preceded_by_larger_gap": 3.5,
        "is_followed_by_smaller_text": 3.5,
        "starts_with_number_or_bullet": 3.5,
        "is_first_on_page": 2.5,
        "is_all_caps": 1.2,
        "is_short_line": 1.0,
        "length_penalty_factor": -0.2,
        "is_smaller_than_predecessor_and_not_body": 1.5,
        "font_size_ratio_H1_boost": 2.0,
        "font_size_ratio_H2_boost": 1.5,
        "font_size_ratio_H3_boost": 1.2,
        "font_size_ratio_H4_boost": 1.0,
        "x0_indent_penalty": -0.5 # Penalty for significant indentation if trying to be a top-level heading
    }

    level_scores = {"H1": 0.0, "H2": 0.0, "H3": 0.0, "H4": 0.0}
    
    # Calculate base prominence based on font size relative to common
    base_prominence = (block["font_size_ratio_to_common"] - 1.0) * weights_base["font_size_prominence"]
    if base_prominence < 0: base_prominence = 0

    is_bold = block.get("is_bold", False)
    is_centered = block.get("is_centered", False)
    is_preceded_by_larger_gap = block.get("is_preceded_by_larger_gap", False)
    is_followed_by_smaller_text = block.get("is_followed_by_smaller_text", False)
    starts_with_number_or_bullet = block.get("starts_with_number_or_bullet", False)
    is_first_on_page = block.get("is_first_on_page", False)
    is_all_caps = block.get("is_all_caps", False)
    is_short_line = block.get("is_short_line", False)
    num_words = block.get("num_words", 0)
    is_form_field_label = block.get("is_form_field_label", False)
    is_smaller_than_predecessor_and_not_body = block.get("is_smaller_than_predecessor_and_not_body", False)
    relative_x0_to_common = block.get("relative_x0_to_common", 0)

    # Conciseness Penalty: Penalize longer lines that are unlikely to be headings
    length_penalty = 0
    if num_words > 15:
        length_penalty = (num_words - 15) * abs(weights_base["length_penalty_factor"])
    if block["line_length"] > 75: # Character length penalty
        length_penalty = max(length_penalty, (block["line_length"] - 75) * abs(weights_base["length_penalty_factor"]))
    
    # Penalize if it looks like a paragraph that just happens to be bold/large
    if num_words > 25 and not starts_with_number_or_bullet and not is_all_caps and block["font_size_ratio_to_common"] < 1.3:
        length_penalty += 5.0 # Stronger penalty

    # H1 Scoring
    score_h1 = base_prominence * weights_base["font_size_ratio_H1_boost"]
    if block["font_size"] >= dynamic_th.get("H1", float('inf')) * 0.95: # Direct font size match
        score_h1 += 10.0
    if is_bold: score_h1 += weights_base["is_bold"] * 2.5
    if is_centered: score_h1 += weights_base["is_centered"] * 2.5
    if is_preceded_by_larger_gap: score_h1 += weights_base["is_preceded_by_larger_gap"] * 2.0
    if is_first_on_page: score_h1 += weights_base["is_first_on_page"] * 2.5
    if is_all_caps: score_h1 += weights_base["is_all_caps"] * 1.8
    if is_short_line and num_words < 12: score_h1 += weights_base["is_short_line"] * 1.8
    if abs(relative_x0_to_common) < 15: score_h1 += 2.0 # Close to main text block start
    
    level_scores["H1"] = score_h1 - length_penalty


    # H2 Scoring
    score_h2 = base_prominence * weights_base["font_size_ratio_H2_boost"]
    if block["font_size"] >= dynamic_th.get("H2", float('inf')) * 0.95:
        score_h2 += 8.0
    if is_bold: score_h2 += weights_base["is_bold"] * 2.0
    if is_preceded_by_larger_gap: score_h2 += weights_base["is_preceded_by_larger_gap"] * 1.5
    if is_followed_by_smaller_text: score_h2 += weights_base["is_followed_by_smaller_text"] * 1.8
    if starts_with_number_or_bullet: score_h2 += weights_base["starts_with_number_or_bullet"] * 3.5
    if is_all_caps: score_h2 += weights_base["is_all_caps"] * 1.0
    if is_short_line and num_words < 18: score_h2 += weights_base["is_short_line"] * 1.5
    if is_centered: score_h2 += weights_base["is_centered"] * 1.2
    if is_form_field_label: score_h2 += weights_base["starts_with_number_or_bullet"] * 2.5
    if is_smaller_than_predecessor_and_not_body: score_h2 += weights_base["is_smaller_than_predecessor_and_not_body"] * 1.5
    
    # Penalty for large indentation for H2 unless it's a specific numbered list format
    if relative_x0_to_common > 30 and not starts_with_number_or_bullet:
        score_h2 += weights_base["x0_indent_penalty"] * 1.0

    level_scores["H2"] = score_h2 - length_penalty

    # H3 Scoring
    score_h3 = base_prominence * weights_base["font_size_ratio_H3_boost"]
    if block["font_size"] >= dynamic_th.get("H3", float('inf')) * 0.95:
        score_h3 += 6.0
    if is_bold: score_h3 += weights_base["is_bold"] * 1.5
    if is_preceded_by_larger_gap: score_h3 += weights_base["is_preceded_by_larger_gap"] * 1.2
    if starts_with_number_or_bullet: score_h3 += weights_base["starts_with_number_or_bullet"] * 4.0
    if is_followed_by_smaller_text: score_h3 += weights_base["is_followed_by_smaller_text"] * 1.5
    if is_short_line and num_words < 25: score_h3 += weights_base["is_short_line"] * 1.5
    if is_form_field_label: score_h3 += weights_base["starts_with_number_or_bullet"] * 3.0
    if is_smaller_than_predecessor_and_not_body: score_h3 += weights_base["is_smaller_than_predecessor_and_not_body"] * 1.0
    
    if relative_x0_to_common > 40 and not starts_with_number_or_bullet:
        score_h3 += weights_base["x0_indent_penalty"] * 1.5 # Stronger penalty for H3 if deeply indented
    
    level_scores["H3"] = score_h3 - length_penalty

    # H4 Scoring
    score_h4 = base_prominence * weights_base["font_size_ratio_H4_boost"]
    if block["font_size"] >= dynamic_th.get("H4", float('inf')) * 0.95:
        score_h4 += 4.0
    if is_bold: score_h4 += weights_base["is_bold"] * 1.0
    if is_preceded_by_larger_gap: score_h4 += weights_base["is_preceded_by_larger_gap"] * 1.0
    if starts_with_number_or_bullet: score_h4 += weights_base["starts_with_number_or_bullet"] * 5.0 # Very strong for H4 as list items
    if is_short_line and num_words < 30: score_h4 += weights_base["is_short_line"] * 1.8
    if is_form_field_label: score_h4 += weights_base["starts_with_number_or_bullet"] * 3.5
    if is_smaller_than_predecessor_and_not_body: score_h4 += weights_base["is_smaller_than_predecessor_and_not_body"] * 0.8
    
    if relative_x0_to_common > 50 and not starts_with_number_or_bullet:
        score_h4 += weights_base["x0_indent_penalty"] * 2.0 # Very strong penalty for H4 if deeply indented

    level_scores["H4"] = score_h4 - length_penalty

    # Determine best level based on scores and confidence thresholds
    min_confidence = {
        "H1": 12.0, # Increased confidence thresholds
        "H2": 9.0,
        "H3": 7.0,
        "H4": 5.0
    }

    best_level = None
    max_score = -1.0
    
    # Iterate from H1 down to H4 to prioritize higher levels
    for level_key in ["H1", "H2", "H3", "H4"]:
        current_score = level_scores[level_key]
        if current_score >= min_confidence.get(level_key, 0.0) and current_score > max_score:
            max_score = current_score
            best_level = level_key

    # Additional filtering rules to reduce false positives
    if best_level:
        # If it's very short, not bold, and not significantly larger font, it's probably not a heading
        if len(block["text"].strip()) < 10 and not is_bold and block["font_size_ratio_to_common"] < 1.15:
            if not (starts_with_number_or_bullet and num_words < 5): # Allow short numbered/bulleted items
                return None
        
        # If it's a numeric-only string and not bold, likely a page number or artifact
        if re.fullmatch(r'^\s*\d+\s*$', block["text"].strip()) and not is_bold and block["font_size_ratio_to_common"] < 1.2:
            return None
        
        # If it's just a single letter or short sequence and not bold, often a list marker or noise
        if len(block["text"].strip()) <= 3 and re.match(r'^[A-Za-z]\s*$', block["text"].strip()) and not is_bold and not starts_with_number_or_bullet:
            return None

        # If it's a "body-like" block (long, not bold, not large font) but got a score,
        # it might be a false positive
        if num_words > 20 and block["font_size_ratio_to_common"] < 1.1 and not is_bold and not starts_with_number_or_bullet and not is_all_caps:
            return None # Likely a regular paragraph
        
        # If a block is identified as "is_smaller_than_predecessor_and_not_body" it needs strong cues to be a heading
        if is_smaller_than_predecessor_and_not_body and not (is_bold or starts_with_number_or_bullet):
            return None
        
        # Avoid classifying highly indented items as top-level headings if not explicitly bold/large/numbered
        if best_level in ["H1", "H2"] and relative_x0_to_common > 50 and not (is_bold or is_centered or starts_with_number_or_bullet):
            return None

    return best_level


def smooth_heading_levels(blocks):
    """
    Applies post-classification smoothing to correct common hierarchical issues.
    Ensures a logical flow of headings (e.g., H1 -> H2 -> H3, no H1 -> H3 directly).
    Also tries to promote lower levels if they are the first "heading-like" item on a page.
    """
    if not blocks:
        return []

    smoothed_blocks = []
    # Using a list to track the last seen heading for each level on the current page
    # Index 0 for H1, 1 for H2, etc. Value is the block itself or None.
    page_level_stack = [None, None, None, None] 
    last_page = -1

    for block in blocks:
        # Reset stack if new page
        if block["page"] != last_page:
            page_level_stack = [None, None, None, None]
            last_page = block["page"]

        if block.get("is_header_footer", False): # Exclude headers/footers from level smoothing
            smoothed_blocks.append(block)
            continue
            
        original_level = block.get("level")
        
        if original_level:
            level_num = int(original_level[1:]) - 1 # Convert to 0-indexed (H1->0, H2->1)
            
            # --- Promotion Logic ---
            # If it's the first classified heading on the page, try to promote it to H1 or H2
            # unless a very clear higher-level heading already exists.
            is_first_non_hf_on_page = True
            for prev_block in smoothed_blocks:
                if prev_block["page"] == block["page"] and not prev_block.get("is_header_footer", False):
                    is_first_non_hf_on_page = False
                    break # Found a previous non-HF block on the same page

            if is_first_non_hf_on_page:
                # If H2 or H3 is the first significant heading on a page, promote to H1 or H2
                if level_num == 1 and block["font_size_ratio_to_common"] > 1.3: # H2 candidate
                    block["level"] = "H1"
                    level_num = 0
                elif level_num == 2 and block["font_size_ratio_to_common"] > 1.2 and not block.get("is_bold", False): # H3 candidate
                    # If H3 but not bold, if it's the first text, it might be H2
                    block["level"] = "H2"
                    level_num = 1
            
            # --- Demotion/Adjustment Logic ---
            # Ensure current level is at most one deeper than its immediate parent
            # If H1 -> H3, it should become H1 -> H2
            if level_num > 0 and page_level_stack[level_num - 1] is None:
                # If immediate parent (e.g., H1 for an H2) is missing, try to attach to highest available parent
                # or promote if it's a significant jump
                actual_parent_level_idx = -1
                for l_idx in range(level_num - 1, -1, -1):
                    if page_level_stack[l_idx] is not None:
                        actual_parent_level_idx = l_idx
                        break
                
                if actual_parent_level_idx != -1:
                    # If current level is more than one step from its actual parent, promote it
                    if level_num > actual_parent_level_idx + 1:
                        block["level"] = f"H{actual_parent_level_idx + 2}" # +1 for 1-indexing, +1 for next level
                        level_num = actual_parent_level_idx + 1
                elif level_num > 0: # No higher parent found, but not H1. Demote to H1 if it looks like it, else treat as body.
                     # This can happen if an H2 appears without any H1. Consider it H1.
                    if block["font_size_ratio_to_common"] > 1.4 and block.get("is_bold", False) and block.get("is_short_line", False):
                        block["level"] = "H1"
                        level_num = 0
                    else: # If it doesn't meet H1 criteria, it might be body text misclassified
                        block["level"] = None # Treat as body text
                        level_num = -1 # Mark as no heading

            # Update the stack
            if level_num != -1: # Only update if it's a valid heading level
                for l in range(level_num + 1, 4): # Clear deeper levels below current heading
                    page_level_stack[l] = None
                page_level_stack[level_num] = block
            else: # If it was demoted to no heading, ensure its spot in stack is cleared
                for l in range(0, 4):
                    if page_level_stack[l] == block:
                        page_level_stack[l] = None
                        break

        smoothed_blocks.append(block)

    # Final pass to remove any blocks that might have been effectively demoted to None
    return [b for b in smoothed_blocks if b.get("level") is not None and b["text"].strip()]


def run(blocks, page_dimensions, most_common_font_size=None):
    """
    Classifies text blocks into heading levels H1-H4 using dynamic thresholds
    and contextual features.
    Accepts blocks and page_dimensions directly (in-memory processing).
    Returns the classified blocks.
    """
    if not blocks:
        print("No blocks to classify.")
        return []

    # Sort blocks by page, then top, then x0, which is crucial for feature calculation
    blocks.sort(key=itemgetter("page", "top", "x0"))

    blocks_with_features, calculated_common_font_size = calculate_all_features(blocks, page_dimensions)
    if most_common_font_size is None: # Use calculated if not explicitly provided
        most_common_font_size = calculated_common_font_size


    dynamic_thresholds_map = dynamic_thresholds(
        [b["font_size"] for b in blocks_with_features if b["font_size"] is not None], most_common_font_size
    )
    print(f"Dynamically determined heading thresholds: {dynamic_thresholds_map}")

    classified_blocks_output = []
    for block in blocks_with_features:
        # ML model part is removed for a purely heuristic approach as per request for maximum precision
        # if heading_classifier_model:
        #     pass
        
        level = classify_block_heuristic(block, dynamic_thresholds_map, most_common_font_size)

        if level:
            block["level"] = level
        else:
            block["level"] = None # Explicitly set to None if not classified as a heading
        classified_blocks_output.append(block)

    # Apply smoothing to ensure hierarchical consistency
    final_classified_blocks = smooth_heading_levels(classified_blocks_output)

    return final_classified_blocks
