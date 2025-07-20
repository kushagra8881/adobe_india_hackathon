import json
import statistics
import re
import os
import joblib # For potential ML model loading
import spacy # NEW: Import spacy
from .advanced_heading_detector import AdvancedHeadingDetector

# Placeholder for ML model. If you train a model, save it as heading_classifier.pkl
# in the models/ directory.
HEADING_CLASSIFIER_MODEL_PATH = "models/heading_classifier.pkl"

# NEW: spaCy model for multilingual support
SPACY_MODEL_NAME = "xx_ent_wiki_sm"  # Multilingual model
nlp = None

try:
    nlp = spacy.load(SPACY_MODEL_NAME)
except IOError:
    print(f"SpaCy model '{SPACY_MODEL_NAME}' not found. Multilingual features will be limited.")
    nlp = None
except Exception as e:
    print(f"Error loading spaCy model: {e}. Multilingual features will be limited.")
    nlp = None

def run(input_path, page_dimensions):
    """
    Main entry point for heading classification using advanced detection
    """
    print(f"Loading blocks from {input_path}...")
    
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            blocks = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Error reading {input_path}: {e}")
    
    if not blocks:
        print("No blocks found. Writing empty classification result...")
        with open(input_path, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2, ensure_ascii=False)
        return
    
    print(f"Processing {len(blocks)} blocks with advanced heading detection...")
    
    # Initialize advanced detector
    detector = AdvancedHeadingDetector()
    
    # Add contextual features to blocks
    enhanced_blocks = calculate_all_features(blocks, page_dimensions)
    
    # Process with advanced detector
    result = detector.process_document(enhanced_blocks, page_dimensions)
    
    # Convert result back to block format for compatibility
    classified_blocks = []
    outline = result.get('outline', [])
    
    # Create a lookup for headings
    heading_lookup = {}
    for heading in outline:
        key = f"{heading['text']}_{heading['page']}"
        heading_lookup[key] = heading['level']
    
    # Mark blocks as headings or body text
    for block in enhanced_blocks:
        block_key = f"{block.get('text', '').strip()}_{block.get('page', 1)}"
        if block_key in heading_lookup:
            block['classification'] = heading_lookup[block_key]
        else:
            block['classification'] = 'body'
        classified_blocks.append(block)
    
    print(f"Advanced classification complete. Found {len(outline)} headings.")
    
    # Save results
    try:
        with open(input_path, "w", encoding="utf-8") as f:
            json.dump(classified_blocks, f, indent=2, ensure_ascii=False)
    except IOError as e:
        raise RuntimeError(f"Error writing classification results to {input_path}: {e}")

def calculate_all_features(blocks, page_dimensions):
    """Enhanced feature calculation with better contextual analysis"""
    if not blocks:
        return []

    all_font_sizes = [block["font_size"] for block in blocks if block.get("font_size", 0) > 0]
    try:
        most_common_font_size = statistics.mode(all_font_sizes) if all_font_sizes else 12
    except statistics.StatisticsError:
        most_common_font_size = statistics.median(all_font_sizes) if all_font_sizes else 12

    # Calculate page layout information
    page_layout_info = {}
    blocks_by_page = {}
    for block in blocks:
        page_num = block.get("page", 1)
        blocks_by_page.setdefault(page_num, []).append(block)
        
        if page_num not in page_layout_info and page_dimensions and page_num in page_dimensions:
            page_layout_info[page_num] = page_dimensions[page_num]

    processed_blocks = []
    for i, block in enumerate(blocks):
        # Language detection using spaCy if available
        block_lang = "en"  # Default
        if nlp:
            try:
                doc = nlp(block["text"][:100])  # First 100 chars for efficiency
                if hasattr(doc, "lang_") and doc.lang_ != "un": # 'un' for undefined
                    block_lang = doc.lang_
            except Exception:
                pass
        
        # Check for CJK (Chinese, Japanese, Korean) languages
        is_cjk = block_lang in ["zh", "ja", "ko"]

        # Calculate num_words first for use in other features
        num_words = len(block["text"]) if is_cjk else len(block["text"].split())

        # Intrinsic features
        features = {
            "text": block["text"],
            "font_size": block["font_size"],
            "is_bold": block.get("is_bold", False),
            "is_italic": block.get("is_italic", False),
            "x0": block["x0"],
            "top": block["top"],
            "bottom": block["bottom"],
            "width": block["width"],
            "height": block["height"],
            "page": block["page"],
            "line_height": block.get("line_height", block["height"]),
            "lang": block_lang,
            
            # Adjust is_all_caps for CJK languages (they don't use casing)
            "is_all_caps": False if is_cjk else (block["text"].isupper() and 2 < len(block["text"]) < 50),
            
            "line_length": len(block["text"]),
            "num_words": num_words,

            "starts_with_number_or_bullet": bool(
                re.match(r"^\s*(\d+(\.\d+)*|[A-Za-z]\.|[IVXLCDM]+\.|[\u2022\u25CF\u25FE\u25A0-])", block["text"].strip())
            ),
            "is_short_line": (len(block["text"]) < 50) and ((num_words < 10) or (is_cjk and num_words < 20)),
            "font_size_ratio_to_common": block["font_size"] / most_common_font_size if most_common_font_size > 0 else 1.0,
            "font_size_deviation_from_common": block["font_size"] - most_common_font_size
        }

        # Contextual Features
        prev_block = blocks[i-1] if i > 0 and blocks[i-1]["page"] == block["page"] else None
        next_block = blocks[i+1] if i < len(blocks) - 1 and blocks[i+1]["page"] == block["page"] else None

        features["is_first_on_page"] = (prev_block is None) or (prev_block["page"] != block["page"])
        features["is_last_on_page"] = (next_block is None) or (next_block["page"] != block["page"])

        if prev_block:
            features["prev_font_size"] = prev_block["font_size"]
            features["prev_y_gap"] = abs(block["top"] - prev_block["bottom"])
            features["prev_x_diff"] = block["x0"] - prev_block["x0"]
            features["is_preceded_by_larger_gap"] = features["prev_y_gap"] > block["line_height"] * 1.5
        else:
            features["prev_font_size"] = 0
            features["prev_y_gap"] = 0
            features["prev_x_diff"] = 0
            features["is_preceded_by_larger_gap"] = True

        if next_block:
            features["next_font_size"] = next_block["font_size"]
            features["next_y_gap"] = abs(next_block["top"] - block["bottom"])
            features["next_x_diff"] = next_block["x0"] - block["x0"]
            features["is_followed_by_smaller_text"] = next_block["font_size"] < block["font_size"] * 0.9
            features["is_followed_by_larger_gap"] = features["next_y_gap"] > block["line_height"] * 1.5
        else:
            features["next_font_size"] = 0
            features["next_y_gap"] = 0
            features["next_x_diff"] = 0
            features["is_followed_by_smaller_text"] = False
            features["is_followed_by_larger_gap"] = True

        # Check if text is centered
        page_info = page_layout_info.get(block["page"])
        if page_info and page_info.get("page_width", 0) > 0:
            page_width = page_info["page_width"]
            block_center_x = block["x0"] + block["width"] / 2
            page_center_x = page_width / 2
            features["is_centered"] = abs(block_center_x - page_center_x) < (page_width * 0.10)
        else:
            features["is_centered"] = False

        block.update(features)
        processed_blocks.append(block)
    
    return processed_blocks
