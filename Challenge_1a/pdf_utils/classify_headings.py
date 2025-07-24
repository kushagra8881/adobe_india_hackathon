import json
import statistics
import re
import collections
from operator import itemgetter
import numpy as np
import math

def _has_unclosed_parentheses_brackets(text):
    """
    Checks if a string has unclosed parentheses, brackets, or braces.
    Returns True if unclosed, False otherwise.
    """
    stack = []
    mapping = {")": "(", "]": "[", "}": "{"}
    for char in text:
        if char in mapping.values():
            stack.append(char)
        elif char in mapping:
            if not stack or stack.pop() != mapping[char]:
                return True # Mismatched or unclosed
    return len(stack) > 0 # Any left in stack means unclosed

def _get_heading_regex_matches(text):
    """
    Returns a list of potential heading levels a text matches based on regex patterns,
    along with a confidence score for that regex match.
    Gives very high precision for common patterns.
    """
    matches = []
    cleaned_text = text.strip()

    # --- H1 Patterns (Highest Confidence) ---
    # CHAPTER/SECTION/ARTICLE followed by number/Roman/letter
    # Added optional text after the number/letter for titles
    if re.match(r'^\s*(CHAPTER|SECTION|ARTICLE)\s+([\dIVXLCDM]+\.?|\w\.?)(?:\s+[\S].*)?$', cleaned_text, re.IGNORECASE):
        matches.append({"level": "H1", "confidence": 0.98})
    # Single level numeric headings (e.g., "1. Introduction", "2. Methodology")
    # Must start with capital letter if text follows.
    elif re.match(r'^\s*(\d+)\.?[. ]+\s*[A-Z].*$', cleaned_text):
        matches.append({"level": "H1", "confidence": 0.95})
    # Long all-caps text (e.g., "TERMS AND CONDITIONS")
    elif re.match(r'^\s*[A-Z][A-Z\s]{10,}[A-Z\d]?\s*$', cleaned_text) and len(cleaned_text.split()) > 2: # Min 3 words for all-caps H1
        matches.append({"level": "H1", "confidence": 0.90})

    # --- H2 Patterns ---
    # Two-level numeric (e.g., "1.1 Subtitle")
    if re.match(r'^\s*(\d+\.\d+)\.?[. ]+\s*[A-Z].*$', cleaned_text):
        matches.append({"level": "H2", "confidence": 0.88})
    # Roman numeral headings (e.g., "I. Introduction")
    elif re.match(r'^\s*(I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII|XIV|XV|XVI|XVII|XVIII|XIX|XX)\.?[. ]+\s*[A-Z].*$', cleaned_text):
        matches.append({"level": "H2", "confidence": 0.85})
    # Single capital letter followed by text (e.g., "A. Overview")
    elif re.match(r'^\s*([A-Z])\.?[. ]+\s*[A-Z].*$', cleaned_text):
        matches.append({"level": "H2", "confidence": 0.82})

    # --- H3 Patterns ---
    # Three-level numeric (e.g., "1.1.1 Detail")
    if re.match(r'^\s*(\d+\.\d+\.\d+)\.?[. ]+\s*[A-Z].*$', cleaned_text):
        matches.append({"level": "H3", "confidence": 0.78})
    # Lowercase letter in parentheses (e.g., "(a) Sub-point")
    elif re.match(r'^\s*\([a-z]\)\s+[A-Z].*$', cleaned_text):
        matches.append({"level": "H3", "confidence": 0.75})
    # Simple dash/bullet point with capital letter (if very common heading style)
    elif re.match(r'^\s*[-•]\s+[A-Z].*$', cleaned_text):
        matches.append({"level": "H3", "confidence": 0.70})

    # --- H4 Patterns ---
    # Four or more level numeric (e.g., "1.1.1.1 Item")
    if re.match(r'^\s*(\d+\.\d+\.\d+\.\d+)\.?[. ]+\s*\S.*$', cleaned_text):
        matches.append({"level": "H4", "confidence": 0.68})
    # Any other letter/number in parentheses (e.g., "(1) Item")
    elif re.match(r'^\s*\((\d+|[A-Z])\)\s+\S.*$', cleaned_text):
        matches.append({"level": "H4", "confidence": 0.65})
        
    return sorted(matches, key=itemgetter("confidence"), reverse=True)


def analyze_line_changes_and_merge(blocks_with_precalculated_features):
    """
    Iterates through blocks (which should already have basic features like x0_normalized,
    font_size_ratio_to_common), infers line change reasons dynamically, and performs merging
    based on those reasons and the specific new logic.
    Marks blocks with `_exclude_from_outline_classification = True` if they represent
    a "complete word body" that is > 15 words.
    """
    if not blocks_with_precalculated_features:
        return []

    # --- Step 0: Pre-merge very tightly spaced horizontal fragments (e.g., "RFP: R RFP: Re" blunder fix) ---
    pre_merged_blocks = []
    i = 0
    while i < len(blocks_with_precalculated_features):
        current_block = blocks_with_precalculated_features[i]
        temp_merged_block = current_block.copy()
        
        # Ensure x1 is present when copying for the first time
        temp_merged_block.setdefault("x1", temp_merged_block["x0"] + temp_merged_block["width"])


        j = i + 1
        while j < len(blocks_with_precalculated_features):
            next_block = blocks_with_precalculated_features[j]
            
            # Ensure next_block has x1 for comparison, though PyMuPDF should provide it
            next_block.setdefault("x1", next_block["x0"] + next_block["width"])

            if next_block["page"] != temp_merged_block["page"]:
                break
            
            # Condition for merging very tight horizontal fragments
            horizontal_gap = next_block["x0"] - temp_merged_block["x1"]
            vertical_overlap = min(temp_merged_block["bottom"], next_block["bottom"]) - max(temp_merged_block["top"], next_block["top"])
            
            if horizontal_gap < 5 and horizontal_gap > -5 and \
               vertical_overlap > min(temp_merged_block["height"], next_block["height"]) * 0.8 and \
               abs(next_block["font_size"] - temp_merged_block["font_size"]) < 0.2 and \
               next_block["font_name"].split('+')[-1] == temp_merged_block["font_name"].split('+')[-1]:
                
                temp_merged_block["text"] += next_block["text"]
                # Crucially, update x1 here!
                temp_merged_block["x1"] = next_block["x1"] 
                temp_merged_block["width"] = temp_merged_block["x1"] - temp_merged_block["x0"]
                temp_merged_block["bottom"] = max(temp_merged_block["bottom"], next_block["bottom"])
                temp_merged_block["height"] = temp_merged_block["bottom"] - temp_merged_block["top"]
                temp_merged_block["is_bold"] = temp_merged_block.get("is_bold", False) or next_block.get("is_bold", False)
                temp_merged_block["is_italic"] = temp_merged_block.get("is_italic", False) or next_block.get("is_italic", False)
                j += 1
            else:
                break
        
        pre_merged_blocks.append(temp_merged_block)
        i = j

    # Use pre_merged_blocks for subsequent analysis
    blocks_to_analyze = pre_merged_blocks


    # --- Step 1: Collect Vertical Gaps and Line Heights for Dynamic Analysis ---
    significant_vertical_gaps = []
    line_height_candidates = [] 
    
    all_font_sizes = [b["font_size"] for b in blocks_to_analyze if b.get("font_size") and b["font_size"] > 0]
    if not all_font_sizes:
        most_common_font_size = 12.0
    else:
        try:
            most_common_font_size = statistics.median(all_font_sizes)
        except statistics.StatisticsError:
            most_common_font_size = all_font_sizes[0]
            
    mean_line_height = most_common_font_size * 1.2 # A common heuristic for line height from font size

    for i, block in enumerate(blocks_to_analyze):
        line_height_candidates.append(block.get("line_height", block.get("height", mean_line_height)))
        if i > 0 and blocks_to_analyze[i-1]["page"] == block["page"]:
            prev_block = blocks_to_analyze[i-1]
            vertical_gap = block["top"] - prev_block["bottom"]
            x_diff = block["x0"] - prev_block["x0"]

            is_aligned_horizontally = abs(x_diff) < 15 
            is_similar_font_size = abs(block["font_size"] - prev_block["font_size"]) < 0.5
            font_name_prev_base = prev_block["font_name"].split('+')[-1] if prev_block["font_name"] else ""
            font_name_curr_base = block["font_name"].split('+')[-1] if block["font_name"] else ""
            is_similar_font_name = font_name_prev_base == font_name_curr_base

            if vertical_gap > -5 and vertical_gap < 50 and is_aligned_horizontally and is_similar_font_size and is_similar_font_name:
                significant_vertical_gaps.append(vertical_gap)

    # --- Step 2: Calculate Dynamic Gap Thresholds ---
    if not line_height_candidates:
        calculated_mean_line_height = 12.0
    else:
        calculated_mean_line_height = np.mean([lh for lh in line_height_candidates if lh > 0])

    if len(significant_vertical_gaps) < 10: 
        typical_line_spacing_threshold = calculated_mean_line_height * 0.6
        paragraph_break_threshold = calculated_mean_line_height * 1.5
    else:
        gaps_sorted = np.sort(significant_vertical_gaps)
        tight_gap_upper_bound = np.percentile(gaps_sorted, 40) 
        paragraph_gap_lower_bound = np.percentile(gaps_sorted, 75) 
        
        typical_line_spacing_threshold = max(0.5, min(tight_gap_upper_bound, calculated_mean_line_height * 0.7))
        paragraph_break_threshold = max(calculated_mean_line_height * 1.0, paragraph_gap_lower_bound * 1.2)
        
        if paragraph_break_threshold <= typical_line_spacing_threshold + calculated_mean_line_height * 0.3:
            paragraph_break_threshold = typical_line_spacing_threshold + calculated_mean_line_height * 0.5

    # --- Step 3: First Pass: Tag blocks with line change reasons using dynamic thresholds ---
    blocks_tagged_with_line_features = []
    for i, block in enumerate(blocks_to_analyze):
        block_features = block.copy() 
        
        block_features["is_line_wrapped"] = False 
        block_features["is_intentional_newline"] = False 
        block_features["is_paragraph_start"] = False 

        prev_block = blocks_to_analyze[i-1] if i > 0 and blocks_to_analyze[i-1]["page"] == block["page"] else None

        if prev_block:
            vertical_gap = block["top"] - prev_block["bottom"]
            x_diff = block["x0"] - prev_block["x0"]
            
            if vertical_gap <= typical_line_spacing_threshold and abs(x_diff) < 5 and \
               not re.search(r'[.?!]$', prev_block["text"].strip()):
                block_features["is_line_wrapped"] = True
            
            elif vertical_gap >= paragraph_break_threshold or abs(x_diff) > 15: 
                block_features["is_intentional_newline"] = True
                block_features["is_paragraph_start"] = True
            
            elif (vertical_gap > typical_line_spacing_threshold and vertical_gap < paragraph_break_threshold) or \
                 (re.search(r'[.?!]$', prev_block["text"].strip()) and block["text"].strip() and block["text"].strip()[0].isupper()):
                block_features["is_intentional_newline"] = True
                block_features["is_paragraph_start"] = True 

            else:
                 block_features["is_intentional_newline"] = True 
                 block_features["is_paragraph_start"] = True

        else: 
            block_features["is_paragraph_start"] = True

        blocks_tagged_with_line_features.append(block_features)

    # --- Step 4: Second pass: Perform merges to form "complete word bodies" ---
    final_logical_blocks = []
    i = 0
    while i < len(blocks_tagged_with_line_features):
        current_block = blocks_tagged_with_line_features[i]
        
        merged_block_candidate = current_block.copy()
        
        is_body_paragraph_candidate = False
        if current_block["is_intentional_newline"] and \
           (current_block.get("font_size_ratio_to_common", 1.0) > 0.9 and current_block.get("font_size_ratio_to_common", 1.0) < 1.15) and \
           not current_block.get("is_bold", False) and \
           current_block.get("relative_x0_to_common", 0) > -5 and current_block.get("relative_x0_to_common", 0) < 20: 
            is_body_paragraph_candidate = True 

        merged_block_candidate["is_descriptive_continuation_of_numbered_heading"] = False

        j = i + 1
        while j < len(blocks_tagged_with_line_features):
            next_block = blocks_tagged_with_line_features[j]

            if next_block["page"] != merged_block_candidate["page"]:
                break 

            if next_block["is_intentional_newline"]:
                break 

            should_merge_this_iteration = False
            if next_block["is_line_wrapped"] and not next_block.get("is_header_footer", False):
                if abs(next_block["font_size"] - merged_block_candidate["font_size"]) < 0.5 and \
                   next_block["font_name"].split('+')[-1] == merged_block_candidate["font_name"].split('+')[-1]:
                    should_merge_this_iteration = True
            
            # NEW MERGE CLAUSE: Prioritize merge if current block has unclosed parentheses/brackets
            if _has_unclosed_parentheses_brackets(merged_block_candidate["text"]) and \
               re.search(r'[\)\]\}]', next_block["text"].strip()): 
                should_merge_this_iteration = True
                
            # NEW MERGE CLAUSE: Merge if the current block is a numbered/bulleted item and the next line is its descriptive continuation
            if merged_block_candidate.get("starts_with_number_or_bullet", False) and \
               not merged_block_candidate.get("is_body_paragraph_candidate", False) and \
               (abs(next_block["x0"] - merged_block_candidate["x0"]) < 10 or (next_block["x0"] > merged_block_candidate["x0"] and next_block["x0"] < merged_block_candidate["x0"] + 50)) and \
               abs(next_block["font_size"] - merged_block_candidate["font_size"]) < 0.5 and \
               not re.search(r'[.?!]$', merged_block_candidate["text"].strip()) and \
               not next_block.get("starts_with_number_or_bullet", False) and \
               not next_block["is_intentional_newline"]: 
                should_merge_this_iteration = True
                merged_block_candidate["is_descriptive_continuation_of_numbered_heading"] = True 

            if should_merge_this_iteration:
                if len(merged_block_candidate["text"]) + len(next_block["text"]) > 1000: 
                    break 

                merged_text = merged_block_candidate["text"]
                if merged_text.strip().endswith('-'):
                    merged_text = merged_text.strip()[:-1] 
                else:
                    merged_text += " " 

                merged_block_candidate["text"] = (merged_text + next_block["text"]).strip()
                merged_block_candidate["bottom"] = next_block["bottom"]
                merged_block_candidate["height"] = merged_block_candidate["bottom"] - merged_block_candidate["top"]
                merged_block_candidate["x0"] = min(merged_block_candidate["x0"], next_block["x0"]) 
                merged_block_candidate["x1"] = max(merged_block_candidate.get("x1", merged_block_candidate["x0"] + merged_block_candidate["width"]), next_block.get("x1", next_block["x0"] + next_block["width"]))
                merged_block_candidate["width"] = merged_block_candidate["x1"] - merged_block_candidate["x0"]
                merged_block_candidate["font_size"] = max(merged_block_candidate["font_size"], next_block["font_size"])
                merged_block_candidate["is_bold"] = merged_block_candidate.get("is_bold", False) or next_block.get("is_bold", False)
                merged_block_candidate["is_italic"] = merged_block_candidate.get("is_italic", False) or next_block.get("is_italic", False)
                merged_block_candidate["line_height"] = max(merged_block_candidate.get("line_height", 0), next_block.get("line_height", 0), merged_block_candidate["height"])

                j += 1
            else:
                break 

        num_words_merged_body = len(merged_block_candidate["text"].split())
        merged_block_candidate["_exclude_from_outline_classification"] = False 

        if num_words_merged_body > 15:
            merged_block_candidate["_exclude_from_outline_classification"] = True
        
        merged_block_candidate["is_body_paragraph_candidate"] = is_body_paragraph_candidate

        final_logical_blocks.append(merged_block_candidate)
        i = j 
    
    return final_logical_blocks


def check_meaningful_fragment(text, nlp_model, detected_lang="und"):
    """
    Uses NLP to check if a block of text is a complete sentence or a meaningful fragment.
    This version is designed to be more permissive for structured, short fragments
    that are common in PDFs (e.g., list items, labels), while still catching gibberish.
    Date-time specific pruning is *removed* from here and handled later.
    Returns True if meaningful/likely part of content, False if likely noise/gibberish.
    """
    if not text or not nlp_model:
        return False
    
    cleaned_text_strip = text.strip()
    if not cleaned_text_strip:
        return False

    # Allow very short numeric/alphanumeric items like "1", "A", "2003"
    if len(cleaned_text_strip) < 5 and any(c.isalnum() for c in cleaned_text_strip) and \
       re.match(r'^[\d\w.\-]+$', cleaned_text_strip): 
        return True 

    doc = nlp_model(cleaned_text_strip)
    is_cjk = detected_lang in ["zh", "ja", "ko"]

    # --- Rule 1: Very low alphanumeric content suggests noise ---
    alpha_digit_count = sum(1 for c in cleaned_text_strip if c.isalnum())
    total_chars = len(cleaned_text_strip) + 1e-9
    alpha_digit_ratio = alpha_digit_count / total_chars 
    
    if alpha_digit_ratio < 0.10: 
        if re.match(r'^\s*(\d{1,4}([-/\\.]\d{1,4}){0,2}|[A-Za-z]\d{1,3})\s*$', cleaned_text_strip): 
            return True
        return False 

    # --- Rule 2: Fragmentation heuristics (for non-CJK) ---
    if not is_cjk:
        num_sentences = len(list(doc.sents))
        if num_sentences == 0: 
            if len(cleaned_text_strip.split()) < 3 and len(cleaned_text_strip) < 10:
                if re.match(r'^\s*([A-Za-z]+\d*|\d+[A-Za-z]*)$', cleaned_text_strip): 
                    return True
                return False
            if len(cleaned_text_strip.split()) > 5 and not re.search(r'[a-zA-Z]', cleaned_text_strip):
                return False

    # --- Rule 3: Heuristic for fragmented appearance (few spaces in long text) - primarily for non-CJK ---
    if not is_cjk:
        space_count = cleaned_text_strip.count(' ')
        if len(cleaned_text_strip) > 50 and space_count / (len(cleaned_text_strip) + 1e-9) < 0.01:
            return False

    # --- Rule 4: Detect and filter general standalone meaningless content explicitly ---
    
    # Check for pure list markers / short roman numerals (allow if bold/large, otherwise prune)
    if re.fullmatch(r"^\s*(\d+(\.\d+)*\s*|[A-Z]\s*|[IVXLCDM]+\s*|[O●■*◆→\-])\s*$", cleaned_text_strip):
        if len(cleaned_text_strip) <= 4 and re.fullmatch(r'[\d\.]+', cleaned_text_strip):
            return False 
        return True 
    
    # Common short labels/phrases that are meaningful (e.g., "Name:", "Contact Info")
    if len(cleaned_text_strip) < 50 and re.match(r'^\s*([A-Z][a-z\s]*){1,6}:?\s*$', cleaned_text_strip):
        if sum(c.isalpha() for c in cleaned_text_strip) < 5 and not cleaned_text_strip.endswith(':'):
            return False 
        return True

    return True 


def filter_blocks_for_classification(logical_blocks, nlp_model, detected_lang):
    """
    Applies strict pruning rules to logical blocks before feature calculation and classification.
    This now has a two-tiered pruning: hard prune (continue) for absolute garbage,
    and soft prune (setting flags) for meaningful content that's not for outline headings.
    """
    filtered_blocks = []
    for block in logical_blocks:
        cleaned_text = block["text"].strip()
        
        # --- Tier 1: Hard Prune (discard for both outline AND summary) ---
        # 1. Drop header-footer
        if block.get("is_header_footer", False):
            continue

        # 2. Drop empty blocks or blocks with very little content that's purely whitespace
        if not cleaned_text:
            continue

        # 3. Drop lines with decorative lines only (e.g., '---', '....')
        if re.fullmatch(r'[\s\-—_•*●■]*', cleaned_text) and len(set(cleaned_text.replace(" ", ""))) < 3:
            if len(cleaned_text) > 2: 
                continue 

        # 4. Drop lines with only numbers/symbols and NO alphanumeric content, or are short numbers
        alphanumeric_content = re.sub(r'[^a-zA-Z0-9]', '', cleaned_text)
        if not alphanumeric_content and len(cleaned_text) < 20: 
            continue 

        # Check specifically for standalone short numbers or roman numerals that are often just page numbers
        if re.fullmatch(r'^\s*(\d{1,5}|\(?[\d]+\)?|\s*[IVXLCDM]+\s*)\s*$', cleaned_text, re.IGNORECASE) and len(cleaned_text) < 8:
            if not block.get("is_bold", False) and block.get("font_size_ratio_to_common", 1.0) < 1.1:
                continue 

        # 5. Drop lines that don't have a continuous text sequences (e.g., scrambled text)
        is_cjk = detected_lang in ["zh", "ja", "ko"]
        if not is_cjk:
            has_meaningful_sequence = False
            words = cleaned_text.split()
            if not words and len(cleaned_text) > 5: 
                continue 

            for word in words:
                alpha_chars = ''.join(c for c in word if c.isalpha())
                if len(alpha_chars) >= 3 and any(vowel in alpha_chars.lower() for vowel in 'aeiou'):
                    has_meaningful_sequence = True
                    break
                if len(alpha_chars) >= 3 and sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars) > 0.5:
                    has_meaningful_sequence = True
                    break
            if not has_meaningful_sequence and len(cleaned_text) < 20: 
                continue
        
        # --- Tier 2: Soft Prune (mark for outline exclusion, but retain for summary) ---
        block["_exclude_from_outline_classification"] = block.get("_exclude_from_outline_classification", False)

        # Apply NLP-based meaningful fragment check (strict for outline, but passes for summary if True)
        if nlp_model and not check_meaningful_fragment(cleaned_text, nlp_model, detected_lang):
            block["is_meaningful_fragment"] = False 
            continue 
        else:
            block["is_meaningful_fragment"] = True 

        if block.get("is_body_paragraph_candidate", False): 
            block["_exclude_from_outline_classification"] = True

        filtered_blocks.append(block)
    return filtered_blocks


def calculate_all_features(blocks, page_dimensions, detected_lang="und"):
    """
    Calculates intrinsic and contextual features for all blocks.
    Assumes blocks are already sorted by page, then top, then x0.
    Adds `is_standalone_date_time_combo` flag and `font_size_rank`.
    """
    if not blocks:
        return [], 0

    all_font_sizes = [block_item["font_size"] for block_item in blocks if block_item["font_size"] is not None and block_item["font_size"] > 0]
    
    if not all_font_sizes:
        most_common_font_size = 12.0 
    else:
        try:
            most_common_font_size = statistics.median(all_font_sizes)
        except statistics.StatisticsError:
            most_common_font_size = all_font_sizes[0] if all_font_sizes else 12.0
        
        if most_common_font_size == 0:
            most_common_font_size = 12.0 

    blocks_by_page = collections.defaultdict(list) 
    for block_item in blocks:
        blocks_by_page.setdefault(block_item["page"], []).append(block_item)
    
    page_layout_info = {}
    for page_num, page_blocks_list in blocks_by_page.items():
        if not page_blocks_list: continue 
        min_x0_page = min(b["x0"] for b in page_blocks_list)
        max_x1_page = max(b["x0"] + b["width"] for b in page_blocks_list)
        
        content_x0s = [b["x0"] for b in page_blocks_list if not b.get("is_header_footer", False) and b["text"].strip()]
        avg_x0_page = statistics.mean(content_x0s) if content_x0s else min_x0_page 

        page_layout_info[page_num] = {
            "min_x0": min_x0_page,
            "max_x1": max_x1_page,
            "avg_x0": avg_x0_page,
        }
        if page_num in page_dimensions:
            page_layout_info[page_num]["page_width"] = page_dimensions[page_num]["width"]
            page_layout_info[page_num]["page_height"] = page_dimensions[page_num]["height"]
        else:
            page_layout_info[page_num]["page_width"] = 595.0 
            page_layout_info[page_num]["page_height"] = 842.0 

    processed_blocks = []
    unique_font_sizes_sorted = sorted(list(set(s for s in all_font_sizes if s > 0)), reverse=True) 
    font_size_rank_map = {size: rank for rank, size in enumerate(unique_font_sizes_sorted)}

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
            "lang": detected_lang, 
            "is_all_caps": False, 
            "line_length": len(block_orig["text"]),
            "num_words": 0, 
            "starts_with_number_or_bullet": False, 
            "is_short_line": False, 
            "is_header_footer": block_orig.get("is_header_footer", False), 
            "is_smaller_than_predecessor_and_not_body": False,
            "x0_normalized": 0.0, 
            "relative_x0_to_common": 0.0,
            "is_meaningful_fragment": block_orig.get("is_meaningful_fragment", True), 
            "_exclude_from_outline_classification": block_orig.get("_exclude_from_outline_classification", False), 
            "is_body_paragraph_candidate": block_orig.get("is_body_paragraph_candidate", False),
            "is_standalone_date_time_combo": False,
            "font_size_rank": font_size_rank_map.get(block_orig.get("font_size"), len(unique_font_sizes_sorted)) 
        }

        if features["font_size"] == 0:
            features["font_size"] = most_common_font_size

        features["font_size_ratio_to_common"] = features["font_size"] / most_common_font_size
        features["font_size_deviation_from_common"] = features["font_size"] - most_common_font_size

        is_cjk = features["lang"] in ["zh", "ja", "ko"] 

        if not is_cjk and len(features["text"]) > 2 and features["text"].isupper() and any(c.isalpha() for c in features["text"]):
            features["is_all_caps"] = True
        
        features["num_words"] = len(features["text"]) if is_cjk else len(features["text"].split())

        features["starts_with_number_or_bullet"] = bool(
            re.match(r"^\s*(\d+(\.\d+)*[\s.)\]}]?\s*|[A-Za-z][.)\]}]?\s*|[IVXLCDM]+\s*[.)\]]?\s*|[O●■*◆→\-])", features["text"].strip())
        )
        
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
            
            current_line_height = features.get("line_height", features.get("height", most_common_font_size))
            features["is_preceded_by_larger_gap"] = features["prev_y_gap"] > current_line_height * 1.8 
            
            if features["font_size"] < prev_block["font_size"] * 0.9 and \
               features["font_size_ratio_to_common"] > 0.95 and \
               not prev_block.get("is_bold", False) and \
               len(prev_block["text"].strip()) > 10 and \
               not re.match(r'[.?!]$', prev_block["text"].strip()): 
                features["is_smaller_than_predecessor_and_not_body"] = True
            else:
                features["is_smaller_than_predecessor_and_not_body"] = False

        else:
            features["prev_font_size"] = 0
            features["prev_y_gap"] = 0
            features["prev_x_diff"] = 0
            features["is_preceded_by_larger_gap"] = True
            features["is_smaller_than_predecessor_and_not_body"] = False

        if next_block:
            features["next_font_size"] = next_block["font_size"]
            features["next_y_gap"] = abs(next_block["top"] - features["bottom"])
            features["next_x_diff"] = next_block["x0"] - features["x0"]
            features["is_followed_by_smaller_text"] = next_block["font_size"] < features["font_size"] * 0.9
            
            current_line_height = features.get("line_height", features.get("height", most_common_font_size))
            features["is_followed_by_larger_gap"] = features["next_y_gap"] > current_line_height * 1.8
        else:
            features["next_font_size"] = 0
            features["next_y_gap"] = 0
            features["next_x_diff"] = 0
            features["is_followed_by_smaller_text"] = False
            features["is_followed_by_larger_gap"] = True

        page_info = page_layout_info.get(features["page"])
        if page_info and page_info["page_width"] > 0:
            page_width = page_info["page_width"]
            
            block_center_x = features["x0"] + features["width"] / 2
            page_center_x = page_width / 2
            features["is_centered"] = abs(block_center_x - page_center_x) < (page_width * 0.05)

            features["x0_normalized"] = features["x0"] / page_width
            features["relative_x0_to_common"] = features["x0"] - page_info["avg_x0"] if page_info.get("avg_x0") else 0
        else:
            features["is_centered"] = False
            features["x0_normalized"] = features["x0"] / 595.0 
            features["relative_x0_to_common"] = 0.0 
        
        date_time_patterns = [
            r'^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s*\d{1,2}\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*\d{4}\s*\d{1,2}:\d{2}:\d{2}(?:\s*(?:AM|PM))?$', 
            r'^\d{1,2}[-/\\.]\d{1,2}[-/\\.]\d{2,4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:AM|PM))?)?$', 
            r'^\d{4}[-/\\.]\d{1,2}[-/\\.]\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:AM|PM))?)?$', 
            r'^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*\d{1,2},?\s*\d{4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:AM|PM))?)?$', 
            r'^\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:AM|PM))?$', 
            r'^\d{4}$' 
        ]
        is_date_time_combo = False
        for pattern in date_time_patterns:
            if re.fullmatch(pattern, features["text"].strip(), re.IGNORECASE):
                is_date_time_combo = True
                break
        
        if is_date_time_combo and not features["is_bold"] and features["font_size_ratio_to_common"] < 1.15 and not features["starts_with_number_or_bullet"]:
            features["is_standalone_date_time_combo"] = True
        else:
            features["is_standalone_date_time_combo"] = False 

        block_orig.update(features)
        processed_blocks.append(block_orig)
    return processed_blocks, most_common_font_size

def dynamic_thresholds(all_font_sizes, most_common_font_size):
    """
    Calculates dynamic font size thresholds based on the distribution of font sizes in the document.
    Prioritizes distinct large font sizes.
    """
    if not all_font_sizes or most_common_font_size == 0:
        return {"H1": 16.0, "H2": 14.0, "H3": 12.0, "H4": 11.0} 

    filtered_sizes = [s for s in all_font_sizes if most_common_font_size * 0.7 < s < most_common_font_size * 3.0]
    if not filtered_sizes:
        filtered_sizes = all_font_sizes 

    unique_sorted_sizes = sorted(list(set(s for s in filtered_sizes if s >= most_common_font_size * 1.05)), reverse=True) 
    
    thresholds = {}
    
    if len(unique_sorted_sizes) > 0:
        thresholds["H1"] = unique_sorted_sizes[0]
        current_h_level = 2
        for i in range(1, len(unique_sorted_sizes)):
            prev_size = unique_sorted_sizes[i-1]
            current_size = unique_sorted_sizes[i]
            if (prev_size - current_size) >= 0.75 and current_size >= most_common_font_size * 1.05: 
                 if current_h_level <= 4:
                    thresholds[f"H{current_h_level}"] = current_size
                    current_h_level += 1
                 else:
                    break 

    if "H1" not in thresholds:
        thresholds["H1"] = most_common_font_size + 6.0
    
    h_keys = ["H1", "H2", "H3", "H4"]
    for i in range(1, len(h_keys)):
        current_key = h_keys[i]
        prev_key = h_keys[i-1]
        
        if current_key not in thresholds or thresholds[current_key] >= thresholds[prev_key] - 0.5:
            thresholds[current_key] = thresholds[prev_key] - (2.0 if current_key == "H2" else 1.5 if current_key == "H3" else 1.0)
        
        if current_key == "H2" and thresholds[current_key] < most_common_font_size * 1.15: thresholds[current_key] = most_common_font_size * 1.15
        if current_key == "H3" and thresholds[current_key] < most_common_font_size * 1.1: thresholds[current_key] = most_common_font_size * 1.1
        if current_key == "H4" and thresholds[current_key] < most_common_font_size * 1.05: thresholds[current_key] = most_common_font_size * 1.05

    for i in range(1, len(h_keys)):
        if thresholds[h_keys[i]] >= thresholds[h_keys[i-1]]:
            thresholds[h_keys[i]] = thresholds[h_keys[i-1]] - 0.5 

    return thresholds


def classify_block_hybrid_score(block, dynamic_th, common_font_size):
    """
    Classifies a single block using a weighted heuristic scoring approach,
    combining regex matches with visual and contextual features.
    Strongly penalizes blocks marked for outline exclusion or as body paragraphs.
    Applies strict text length constraints for outline headings.
    """
    cleaned_text = block["text"].strip()
    
    is_bold = block.get("is_bold", False)
    starts_with_number_or_bullet = block.get("starts_with_number_or_bullet", False)
    font_size_ratio_to_common = block.get("font_size_ratio_to_common", 1.0)
    font_size = block.get("font_size", common_font_size)
    font_size_rank = block.get("font_size_rank", 999) 
    is_followed_by_smaller_text = block.get("is_followed_by_smaller_text", False)
    num_words = block.get("num_words", 0)
    line_length = block.get("line_length", 0)
    is_centered = block.get("is_centered", False)
    is_preceded_by_larger_gap = block.get("is_preceded_by_larger_gap", False)
    is_first_on_page = block.get("is_first_on_page", False)
    is_all_caps = block.get("is_all_caps", False)
    is_short_line = block.get("is_short_line", False)
    is_smaller_than_predecessor_and_not_body = block.get("is_smaller_than_predecessor_and_not_body", False)
    relative_x0_to_common = block.get("relative_x0_to_common", 0)
    
    _exclude_from_outline_classification = block.get("_exclude_from_outline_classification", False)
    is_body_paragraph_candidate = block.get("is_body_paragraph_candidate", False)
    is_standalone_date_time_combo = block.get("is_standalone_date_time_combo", False)

    regex_matches = _get_heading_regex_matches(cleaned_text)
    
    weights_base = {
        "font_size_prominence": 4.5, 
        "is_bold": 7.0, 
        "is_centered": 8.0, 
        "is_preceded_by_larger_gap": 5.5, 
        "is_followed_by_smaller_text": 5.5, 
        "starts_with_number_or_bullet": 7.0, 
        "is_first_on_page": 4.5,
        "is_all_caps": 3.0,
        "is_short_line": 2.5,
        "length_penalty_factor": -0.5, 
        "is_smaller_than_predecessor_and_not_body": 3.5, 
        "font_size_ratio_H1_boost": 4.0, 
        "font_size_ratio_H2_boost": 3.5,
        "font_size_ratio_H3_boost": 3.0, 
        "font_size_ratio_H4_boost": 2.5,
        "x0_indent_penalty": -2.0, 
        "body_text_penalty": -40.0, 
        "numbered_heading_short_penalty": -8.0,
        "standalone_date_time_penalty": -25.0,
        "regex_match_boost": 20.0 
    }

    level_scores = {"H1": 0.0, "H2": 0.0, "H3": 0.0, "H4": 0.0}
    
    base_prominence = (font_size_ratio_to_common - 1.0) * weights_base["font_size_prominence"]
    if base_prominence < 0: base_prominence = 0

    length_penalty = 0
    if num_words > 5:
        length_penalty = (num_words - 5) * abs(weights_base["length_penalty_factor"]) * 5 
    if line_length > 50: 
        length_penalty = max(length_penalty, (line_length - 50) * abs(weights_base["length_penalty_factor"]) * 5)
    
    if num_words > 20: 
        length_penalty += 100.0 

    if _exclude_from_outline_classification or is_body_paragraph_candidate:
        length_penalty += abs(weights_base["body_text_penalty"])

    if is_standalone_date_time_combo: 
        length_penalty += abs(weights_base["standalone_date_time_penalty"])

    for match in regex_matches:
        level_key = match["level"]
        confidence = match["confidence"]
        level_scores[level_key] += confidence * weights_base["regex_match_boost"]

    # H1 Scoring
    score_h1 = base_prominence * weights_base["font_size_ratio_H1_boost"]
    if font_size >= dynamic_th.get("H1", float('inf')) * 0.95: 
        score_h1 += 18.0 
    if is_bold: score_h1 += weights_base["is_bold"] * 3.0
    if is_centered: score_h1 += weights_base["is_centered"] * 3.5 
    if is_preceded_by_larger_gap: score_h1 += weights_base["is_preceded_by_larger_gap"] * 3.0
    if is_first_on_page: score_h1 += weights_base["is_first_on_page"] * 4.0
    if is_all_caps: score_h1 += weights_base["is_all_caps"] * 2.5
    if is_short_line and num_words < 10: score_h1 += weights_base["is_short_line"] * 3.0
    if abs(relative_x0_to_common) < 15: score_h1 += 3.5 
    
    level_scores["H1"] += score_h1 - length_penalty


    # H2 Scoring
    score_h2 = base_prominence * weights_base["font_size_ratio_H2_boost"]
    if font_size >= dynamic_th.get("H2", float('inf')) * 0.95:
        score_h2 += 12.0 
    if is_bold: score_h2 += weights_base["is_bold"] * 2.5
    if is_preceded_by_larger_gap: score_h2 += weights_base["is_preceded_by_larger_gap"] * 2.0
    if is_followed_by_smaller_text: score_h2 += weights_base["is_followed_by_smaller_text"] * 2.5
    if starts_with_number_or_bullet: score_h2 += weights_base["starts_with_number_or_bullet"] * 5.0 
    if is_all_caps: score_h2 += weights_base["is_all_caps"] * 2.0
    if is_short_line and num_words < 15: score_h2 += weights_base["is_short_line"] * 2.5
    if is_centered: score_h2 += weights_base["is_centered"] * 1.8
    if is_smaller_than_predecessor_and_not_body: score_h2 += weights_base["is_smaller_than_predecessor_and_not_body"] * 2.5
    
    if relative_x0_to_common > 25 and not starts_with_number_or_bullet:
        score_h2 += weights_base["x0_indent_penalty"] * 1.8

    level_scores["H2"] += score_h2 - length_penalty

    # H3 Scoring
    score_h3 = base_prominence * weights_base["font_size_ratio_H3_boost"]
    if font_size >= dynamic_th.get("H3", float('inf')) * 0.95:
        score_h3 += 10.0 
    if is_bold: score_h3 += weights_base["is_bold"] * 2.0
    if is_preceded_by_larger_gap: score_h3 += weights_base["is_preceded_by_larger_gap"] * 1.8
    if starts_with_number_or_bullet: score_h3 += weights_base["starts_with_number_or_bullet"] * 5.5 
    if is_followed_by_smaller_text: score_h3 += weights_base["is_followed_by_smaller_text"] * 2.0
    if is_short_line and num_words < 20: score_h3 += weights_base["is_short_line"] * 1.8
    if is_smaller_than_predecessor_and_not_body: score_h3 += weights_base["is_smaller_than_predecessor_and_not_body"] * 1.5
    
    if relative_x0_to_common > 35 and not starts_with_number_or_bullet:
        score_h3 += weights_base["x0_indent_penalty"] * 2.5 
    
    level_scores["H3"] += score_h3 - length_penalty

    # H4 Scoring
    score_h4 = base_prominence * weights_base["font_size_ratio_H4_boost"]
    if font_size >= dynamic_th.get("H4", float('inf')) * 0.95:
        score_h4 += 8.0 
    if is_bold: score_h4 += weights_base["is_bold"] * 1.5
    if is_preceded_by_larger_gap: score_h4 += weights_base["is_preceded_by_larger_gap"] * 1.2
    if starts_with_number_or_bullet: score_h4 += weights_base["starts_with_number_or_bullet"] * 6.0 
    if is_short_line and num_words < 25: score_h4 += weights_base["is_short_line"] * 2.5
    if is_smaller_than_predecessor_and_not_body: score_h4 += weights_base["is_smaller_than_predecessor_and_not_body"] * 1.5
    
    if relative_x0_to_common > 45 and not starts_with_number_or_bullet:
        score_h4 += weights_base["x0_indent_penalty"] * 3.0 

    level_scores["H4"] += score_h4 - length_penalty

    min_confidence = {
        "H1": 30.0, 
        "H2": 25.0,
        "H3": 20.0,
        "H4": 15.0 
    }

    best_level = None
    max_score = -1.0
    
    for level_key in ["H1", "H2", "H3", "H4"]:
        current_score = level_scores[level_key]
        if current_score >= min_confidence.get(level_key, 0.0) and current_score > max_score:
            best_level = level_key
            max_score = current_score

    # Final filtering based on specific request:
    # Blocks explicitly marked to be excluded from outline classification (e.g., long body text, general paragraphs)
    if _exclude_from_outline_classification: 
        return None 
    
    # Also explicitly exclude if it's a standalone date/time combo that didn't get a strong heading score
    if is_standalone_date_time_combo and best_level is None:
        return None

    # NEW: Final check for "blunders" like "WWW.TOPJUMP.COM" or "HOPE SEE HERE" (very specific patterns of unwanted text)
    # This also handles URL patterns in the text
    if re.match(r'^(www\.|http[s]?://|ftp://)', cleaned_text, re.IGNORECASE) or \
       (len(cleaned_text.split()) <= 4 and re.fullmatch(r'[\w\d\.]+', cleaned_text) and not is_bold and font_size_ratio_to_common < 1.2) or \
       (len(cleaned_text.split()) > 1 and all(len(word) <= 4 and len(word) > 0 for word in cleaned_text.split()) and not is_bold and font_size_ratio_to_common < 1.2): 
        if best_level == "H1" and max_score > 60.0: # Only allow if extremely strong H1
            pass
        else:
            return None # Otherwise, reject this pattern from being a heading

    return best_level


def smooth_heading_levels(blocks):
    """
    Applies post-classification smoothing to correct common hierarchical issues.
    Ensures a logical flow of headings (e.g., H1 -> H2 -> H3, no H1 -> H3 directly).
    Also ensures every page has at least one H-n text in the outline.
    """
    if not blocks:
        return []

    all_processed_and_smoothed = [] 
    
    max_page = max(b["page"] for b in blocks) if blocks else 0
    
    blocks_by_page = collections.defaultdict(list)
    for block in blocks:
        blocks_by_page[block["page"]].append(block)
    
    for page_num in blocks_by_page:
        blocks_by_page[page_num].sort(key=itemgetter("top", "x0"))

    # Initialize here for final smoothed list
    final_output_blocks_before_final_pruning = [] 

    for page_num in range(max_page + 1):
        current_page_blocks = blocks_by_page[page_num]
        
        # Temp stack for current page processing within this loop (resets per page)
        current_page_level_stack_for_smoothing = [None, None, None, None] 
        
        # Keep track of headings encountered on current page *before* placeholders*
        headings_on_page_for_placeholder_check = [] 

        # Process existing blocks on the page, apply smoothing logic
        for block in current_page_blocks:
            if block.get("is_header_footer", False):
                all_processed_and_smoothed.append(block) # Still add to this global list for full blocks
                continue
            
            original_level = block.get("level")
            
            if original_level:
                level_num = int(original_level[1:]) - 1 
                
                effective_parent_level_idx = -1
                # To correctly find the parent from already processed blocks across pages:
                # Build a temporary stack from `all_processed_and_smoothed` (global) AND current_page_level_stack_for_smoothing.
                temp_combined_stack_blocks = []
                # Add headings from previous pages first
                for s_block in all_processed_and_smoothed:
                    if s_block.get("level") is not None and s_block["page"] < block["page"]:
                         temp_combined_stack_blocks.append(s_block)
                # Then add headings processed so far on the current page
                for s_block in current_page_level_stack_for_smoothing:
                    if s_block is not None:
                        temp_combined_stack_blocks.append(s_block)
                
                temp_combined_stack_blocks.sort(key=lambda x: (x["page"], x["top"])) # Sort by position for strict order

                temp_hierarchy_path = [] # Build a valid path from temp_combined_stack_blocks
                for s_block in temp_combined_stack_blocks:
                    s_level_num_int = int(s_block["level"][1:]) - 1
                    # Ensure strict level progression when building the temporary path
                    while temp_hierarchy_path and (int(temp_hierarchy_path[-1]["level"][1:]) - 1 >= s_level_num_int):
                        temp_hierarchy_path.pop()
                    # Only add if it's a valid next level
                    if not temp_hierarchy_path or s_level_num_int <= int(temp_hierarchy_path[-1]["level"][1:]): # Allow same level
                        temp_hierarchy_path.append(s_block)

                # Now, use temp_hierarchy_path to find parent for the current block
                for l_idx in range(level_num - 1, -1, -1):
                    found_parent = next((s_b for s_b in reversed(temp_hierarchy_path) if int(s_b["level"][1:]) - 1 == l_idx), None)
                    if found_parent:
                        effective_parent_level_idx = l_idx
                        break
                
                # Enforce strict hierarchy (e.g., H1 -> H3 becomes H1 -> H2)
                if effective_parent_level_idx != -1:
                    if level_num > effective_parent_level_idx + 1:
                        block["level"] = f"H{effective_parent_level_idx + 2}" 
                        level_num = effective_parent_level_idx + 1
                elif level_num > 0: # If H2, H3, H4 but no higher parent found globally/on stack
                    # Promote to H1 only if it's very visually prominent and first significant content on page.
                    if block.get("is_first_on_page", False) and block.get("font_size_ratio_to_common", 0) > 1.8 and block.get("is_bold", False) and block.get("is_centered", False):
                        block["level"] = "H1"
                        level_num = 0
                    else: # Otherwise demote it.
                        block["level"] = None 
                        level_num = -1 
                
                # Update the current_page_level_stack_for_smoothing for subsequent blocks on *this page*
                if block.get("level") is not None: # If it's still a heading
                    new_level_num_for_stack = int(block["level"][1:]) - 1
                    for l_idx_clear in range(new_level_num_for_stack + 1, 4):
                        current_page_level_stack_for_smoothing[l_idx_clear] = None
                    current_page_level_stack_for_smoothing[new_level_num_for_stack] = block
                    headings_on_page_for_placeholder_check.append(block) # Mark as having a heading
            else: 
                block["level"] = None 

            all_processed_and_smoothed.append(block) # Add block to global list

        # --- Add placeholder heading if page has no classified headings AFTER its blocks have been processed and smoothed ---
        if not headings_on_page_for_placeholder_check:
            meaningful_content_on_page = [b for b in current_page_blocks if not b.get("is_header_footer", False) and b.get("is_meaningful_fragment", True) and b["text"].strip()]
            
            placeholder_block_data = None
            if meaningful_content_on_page:
                meaningful_content_on_page.sort(key=itemgetter("top", "x0"))
                for pb in meaningful_content_on_page:
                    if pb.get("is_bold", False) and len(pb["text"].split()) < 15 and pb.get("font_size_ratio_to_common", 0) >= 0.9:
                        placeholder_block_data = pb
                        break
                
                if placeholder_block_data is None: 
                    for pb in meaningful_content_on_page:
                        if len(pb["text"].split()) > 3 and len(pb["text"]) < 100:
                            placeholder_block_data = pb
                            break
            
            if placeholder_block_data:
                placeholder_heading = placeholder_block_data.copy()
                placeholder_heading["level"] = "H4" # Placeholder is usually lowest level
                # Ensure placeholder has all necessary keys with default numerical values to prevent errors
                placeholder_heading.setdefault("page", page_num)
                placeholder_heading.setdefault("top", float(placeholder_block_data.get("top", 0.0))) 
                placeholder_heading.setdefault("x0", float(placeholder_block_data.get("x0", 0.0))) 
                placeholder_heading.setdefault("bottom", float(placeholder_block_data.get("bottom", 0.0)))
                placeholder_heading.setdefault("width", float(placeholder_block_data.get("width", 0.0)))
                placeholder_heading.setdefault("height", float(placeholder_block_data.get("height", 0.0)))
                placeholder_heading.setdefault("font_size", float(placeholder_block_data.get("font_size", 12.0))) 
                placeholder_heading.setdefault("font_name", placeholder_block_data.get("font_name", "placeholder_font"))
                placeholder_heading.setdefault("is_bold", placeholder_block_data.get("is_bold", False)) 
                placeholder_heading.setdefault("is_italic", placeholder_block_data.get("is_italic", False)) 
                placeholder_heading.setdefault("line_height", float(placeholder_block_data.get("line_height", 12.0))) 
                placeholder_heading.setdefault("lang", placeholder_block_data.get("lang", "en"))
                placeholder_heading.setdefault("is_all_caps", False)
                placeholder_heading.setdefault("line_length", len(placeholder_heading["text"]))
                placeholder_heading.setdefault("num_words", len(placeholder_heading["text"].split()))
                placeholder_heading.setdefault("starts_with_number_or_bullet", False)
                placeholder_heading.setdefault("is_short_line", True)
                placeholder_heading.setdefault("is_header_footer", False)
                placeholder_heading.setdefault("is_smaller_than_predecessor_and_not_body", False)
                placeholder_heading.setdefault("x0_normalized", 0.0)
                placeholder_heading.setdefault("relative_x0_to_common", 0.0)
                placeholder_heading.setdefault("is_meaningful_fragment", True)
                placeholder_heading.setdefault("_exclude_from_outline_classification", False)
                placeholder_heading.setdefault("is_body_paragraph_candidate", False)
                placeholder_heading.setdefault("is_standalone_date_time_combo", False)

                # Truncate placeholder text if needed
                placeholder_heading_text_cleaned = placeholder_heading['text'][:70].replace(':', '').strip()
                placeholder_heading["text"] = f"Page {page_num+1} Section: {placeholder_heading_text_cleaned}..." if len(placeholder_heading_text_cleaned) > 50 else f"Page {page_num+1} Section: {placeholder_heading_text_cleaned}"
                
                is_duplicate_text_in_outline = False
                for existing_block in all_processed_and_smoothed:
                    if existing_block.get("level") and existing_block["text"].lower() == placeholder_heading["text"].lower():
                       is_duplicate_text_in_outline = True
                       break

                if not is_duplicate_text_in_outline:
                    all_processed_and_smoothed.append(placeholder_heading)
            else: 
                generic_placeholder = {
                    "level": "H4",
                    "text": f"Page {page_num+1} - No Obvious Section",
                    "page": page_num,
                    "top": 0.0, "x0": 0.0, "bottom": 0.0, "width": 0.0, "height": 0.0, 
                    "font_size": 12.0, "font_name": "placeholder_font",
                    "is_bold": False, "is_italic": False, "line_height": 12.0, "lang": "en",
                    "is_all_caps": False, "line_length": len(f"Page {page_num+1} - No Obvious Section"),
                    "num_words": len(f"Page {page_num+1} - No Obvious Section".split()),
                    "starts_with_number_or_bullet": False, "is_short_line": True,
                    "is_header_footer": False, "is_smaller_than_predecessor_and_not_body": False,
                    "x0_normalized": 0.0, "relative_x0_to_common": 0.0,
                    "is_meaningful_fragment": True, "_exclude_from_outline_classification": False,
                    "is_body_paragraph_candidate": False,
                    "is_standalone_date_time_combo": False 
                }
                all_processed_and_smoothed.append(generic_placeholder)
                    
    # Final sort and re-hierarchy enforcement across ALL blocks after insertions
    # This pass is critical to fix the levels after placeholders are inserted.
    final_sorted_blocks = sorted(all_processed_and_smoothed, key=lambda b: (b["page"], b["top"], b["x0"]))
    
    # Initialize re_re_smoothed_final_blocks here, at the top level of this scope
    re_re_smoothed_final_blocks = [] 
    re_re_page_level_stack = [None, None, None, None] 

    for block in final_sorted_blocks:
        if block.get("level") is not None: 
            level_num = int(block["level"][1:]) - 1
            
            re_re_effective_parent_level_idx = -1
            temp_stack_for_re_re = [] 
            for s_block in re_re_smoothed_final_blocks:
                if s_block.get("level") is not None and s_block["page"] <= block["page"]:
                    s_level_num_int = int(s_block["level"][1:]) - 1
                    while temp_stack_for_re_re and int(temp_stack_for_re_re[-1]["level"][1:]) - 1 >= s_level_num_int:
                        temp_stack_for_re_re.pop()
                    temp_stack_for_re_re.append(s_block)

            for l_idx in range(level_num - 1, -1, -1):
                found_parent = next((s_b for s_b in reversed(temp_stack_for_re_re) if int(s_b["level"][1:]) - 1 == l_idx), None)
                if found_parent:
                    re_re_effective_parent_level_idx = l_idx
                    break
            
            if re_re_effective_parent_level_idx != -1:
                if level_num > re_re_effective_parent_level_idx + 1:
                    block["level"] = f"H{re_re_effective_parent_level_idx + 2}"
                    level_num = re_re_effective_parent_level_idx + 1
            elif level_num > 0: 
                if block.get("font_size_ratio_to_common", 0) > 1.8 and block.get("is_bold", False) and block.get("is_centered", False):
                    block["level"] = "H1"
                    level_num = 0
                else: 
                    block["level"] = None 
                    level_num = -1
            
            if level_num != -1:
                for l in range(level_num + 1, 4):
                    re_re_page_level_stack[l] = None
                re_re_page_level_stack[level_num] = block
            else: 
                for l in range(0, 4):
                    if re_re_page_level_stack[l] == block:
                        re_re_page_level_stack[l] = None
                        break
        
        re_re_smoothed_final_blocks.append(block)

    final_outline_candidates = []
    for block in re_re_smoothed_final_blocks:
        if block.get("is_header_footer", False):
            continue
        if block.get("is_standalone_date_time_combo", False) and block.get("level") is None:
            continue 

        if block.get("level") is not None: 
            final_outline_candidates.append(block)

    return final_outline_candidates


def run_with_custom_logic(raw_extracted_blocks, page_dimensions, detected_lang="und", nlp_model_for_quality_checks=None):
    """
    Main function to run the custom classification logic:
    1. Calculate initial features (including spatial) on raw blocks.
    2. Analyze line changes and perform merges based on dynamic thresholds.
    3. Apply strict pruning rules (hard prune for noise, soft prune for outline exclusion).
    4. Classify headings.
    5. Smooth hierarchy and ensure every page is covered.
    """
    if not raw_extracted_blocks:
        print("No blocks to classify.")
        return []

    print("      Sub-stage 3.1: Calculating initial block features..")
    blocks_with_initial_features, most_common_font_size_from_raw = calculate_all_features(raw_extracted_blocks, page_dimensions, detected_lang=detected_lang)

    print("      Sub-stage 3.2: Analyzing line changes and intelligent merging..")
    logical_blocks_with_merge_info = analyze_line_changes_and_merge(blocks_with_initial_features) 

    print("      Sub-stage 3.3: Applying strict pruning rules for outline vs. summary..")
    pruned_and_filtered_blocks = filter_blocks_for_classification(
        logical_blocks_with_merge_info, nlp_model_for_quality_checks, detected_lang
    )

    recalculated_all_font_sizes = [b["font_size"] for b in pruned_and_filtered_blocks if b["font_size"] is not None and b["font_size"] > 0]
    if not recalculated_all_font_sizes:
        recalculated_most_common_font_size = most_common_font_size_from_raw 
    else:
        try:
            recalculated_most_common_font_size = statistics.median(recalculated_all_font_sizes)
        except statistics.StatisticsError:
            recalculated_most_common_font_size = recalculated_all_font_sizes[0]
        if recalculated_most_common_font_size == 0:
            recalculated_most_common_font_size = most_common_font_size_from_raw

    dynamic_thresholds_map = dynamic_thresholds(
        recalculated_all_font_sizes, recalculated_most_common_font_size
    )
    print(f"      Sub-stage 3.4: Dynamically determined heading thresholds: {dynamic_thresholds_map}") 


    print("      Sub-stage 3.5: Classifying blocks into headings..")
    classified_blocks_output = []
    for block in pruned_and_filtered_blocks: 
        level = classify_block_hybrid_score(block, dynamic_thresholds_map, recalculated_most_common_font_size) 
        block["level"] = level 
        classified_blocks_output.append(block)

    print("      Sub-stage 3.6: Smoothing heading hierarchy and ensuring page coverage..")
    final_classified_blocks = smooth_heading_levels(classified_blocks_output)

    return final_classified_blocks