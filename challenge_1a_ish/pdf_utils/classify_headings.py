import json
import statistics
import re
import os
import joblib # For potential ML model loading
import spacy # NEW: Import spacy

# Placeholder for ML model. If you train a model, save it as heading_classifier.pkl
# in the models/ directory.
HEADING_CLASSIFIER_MODEL_PATH = "models/heading_classifier.pkl"
heading_classifier_model = None
try:
    if os.path.exists(HEADING_CLASSIFIER_MODEL_PATH):
        heading_classifier_model = joblib.load(HEADING_CLASSIFIER_MODEL_PATH)
        print(f"Loaded ML heading classifier from {HEADING_CLASSIFIER_MODEL_PATH}")
    else:
        print(f"ML model not found at {HEADING_CLASSIFIER_MODEL_PATH}. Using enhanced heuristics.")
except Exception as e:
    print(f"Could not load ML model: {e}. Using enhanced heuristics.")
    heading_classifier_model = None

# NEW: SpaCy model for language detection
# Model name should be "xx_ent_wiki_sm" if installed via pip directly or from .whl
SPACY_MODEL_NAME = "xx_ent_wiki_sm" 
nlp = None
try:
    # Attempt to load the spaCy model. This will only succeed if the model is installed locally.
    nlp = spacy.load(SPACY_MODEL_NAME)
    print(f"Loaded spaCy model: {SPACY_MODEL_NAME} for multilingual analysis.")
except OSError:
    print(f"SpaCy model '{SPACY_MODEL_NAME}' not found. Multilingual features will be limited.")
except Exception as e:
    print(f"Error loading spaCy model: {e}. Multilingual features will be limited.")


def calculate_all_features(blocks, page_dimensions):
    """
    Calculates intrinsic and contextual features for all blocks.
    Assumes blocks are already sorted by page, then top, then x0.
    page_dimensions: A dictionary {page_num: {"width": float, "height": float}}
    """
    if not blocks:
        return []

    all_font_sizes = [block["font_size"] for block in blocks]
    try:
        most_common_font_size = statistics.mode(all_font_sizes) if all_font_sizes else 0
    except statistics.StatisticsError:
        most_common_font_size = statistics.median(all_font_sizes) if all_font_sizes else 0

    blocks_by_page = {}
    for block in blocks:
        blocks_by_page.setdefault(block["page"], []).append(block)
    
    page_layout_info = {}
    for page_num, page_blocks_list in blocks_by_page.items():
        min_x0_page = min(b["x0"] for b in page_blocks_list)
        max_x1_page = max(b["x0"] + b["width"] for b in page_blocks_list)
        page_layout_info[page_num] = {
            "min_x0": min_x0_page,
            "max_x1": max_x1_page,
        }
        # Add actual page width if available from page_dimensions
        if page_num in page_dimensions:
            page_layout_info[page_num]["page_width"] = page_dimensions[page_num]["width"]
        else:
            page_layout_info[page_num]["page_width"] = 595.0 # Fallback to A4 width if not passed

    processed_blocks = []
    for i, block in enumerate(blocks):
        # NEW: Language detection for the block
        block_lang = "und" # Undetermined
        if nlp:
            try:
                doc = nlp(block["text"])
                # The language attribute is usually doc.lang_
                if hasattr(doc, "lang_") and doc.lang_ != "un": # 'un' for undefined
                    block_lang = doc.lang_
            except Exception as e:
                # Handle cases where spaCy might fail on some texts (e.g., malformed)
                # print(f"SpaCy processing error for text '{block['text']}': {e}")
                pass
        
        # Check for CJK (Chinese, Japanese, Korean) languages
        is_cjk = block_lang in ["zh", "ja", "ko"]

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
            "lang": block_lang, # NEW: Add detected language
            
            # Adjust is_all_caps for CJK languages (they don't use casing)
            "is_all_caps": False if is_cjk else (block["text"].isupper() and 2 < len(block["text"]) < 50),
            
            "line_length": len(block["text"]),
            # Adjust num_words for CJK languages (no space delimiters, so char count is a better proxy)
            "num_words": len(block["text"]) if is_cjk else len(block["text"].split()),

            "starts_with_number_or_bullet": bool(
                re.match(r"^\s*(\d+(\.\d+)*|[A-Za-z]\.|[IVXLCDM]+\.|[\u2022\u25CF\u25FE\u25A0-])", block["text"].strip())
            ),
            # is_short_line: Use adjusted num_words
            "is_short_line": (len(block["text"]) < 50) and ((features["num_words"] < 10) or is_cjk and (features["num_words"] < 20)), # Longer for CJK characters
            "font_size_ratio_to_common": block["font_size"] / most_common_font_size if most_common_font_size > 0 else 1.0,
            "font_size_deviation_from_common": block["font_size"] - most_common_font_size
        }

        # Contextual Features (rest of this section is largely unchanged, using updated features)
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

        page_info = page_layout_info.get(block["page"])
        if page_info and page_info["page_width"] > 0:
            page_width = page_info["page_width"]
            block_center_x = block["x0"] + block["width"] / 2
            page_center_x = page_width / 2
            features["is_centered"] = abs(block_center_x - page_center_x) < (page_width * 0.10)
        else:
            features["is_centered"] = False

        block.update(features)
        processed_blocks.append(block)
    return processed_blocks, most_common_font_size

def dynamic_thresholds(all_font_sizes, most_common_font_size):
    """
    Calculates dynamic font size thresholds based on the distribution of font sizes in the document.
    """
    if not all_font_sizes or most_common_font_size == 0:
        return {"H1": 16, "H2": 14, "H3": 12, "H4": 10} # Fallback to default

    unique_sizes = sorted(list(set(all_font_sizes)), reverse=True)
    
    candidate_heading_sizes = [s for s in unique_sizes if s > most_common_font_size * 1.15]

    thresholds = {}
    current_level = 1
    
    for size in candidate_heading_sizes:
        if current_level <= 4:
            thresholds[f"H{current_level}"] = size
            current_level += 1
        else:
            break
            
    h_keys = ["H1", "H2", "H3", "H4"]
    final_thresholds = {}

    if "H1" in thresholds:
        final_thresholds["H1"] = thresholds["H1"]
    elif candidate_heading_sizes:
        final_thresholds["H1"] = candidate_heading_sizes[0]
    else:
        final_thresholds["H1"] = most_common_font_size + 8

    for i in range(1, len(h_keys)):
        current_key = h_keys[i]
        prev_key = h_keys[i-1]
        
        if current_key in thresholds:
            final_thresholds[current_key] = min(thresholds[current_key], final_thresholds[prev_key] - 0.5)
        else:
            final_thresholds[current_key] = final_thresholds[prev_key] - 1.5

        min_level_size = most_common_font_size * 1.05 if current_key == "H4" else most_common_font_size * 1.10
        if final_thresholds[current_key] < min_level_size:
            final_thresholds[current_key] = min_level_size
        
        if final_thresholds[current_key] >= final_thresholds[prev_key]:
            final_thresholds[current_key] = final_thresholds[prev_key] - 0.5


    return final_thresholds


def classify_block_heuristic(block, dynamic_th, common_font_size):
    """
    Classifies a single block using a weighted heuristic scoring approach,
    leveraging intrinsic and contextual features.
    """
    # Define weights for different features for each level
    weights_base = {
        "font_size_prominence": 3.0,
        "is_bold": 2.5,
        "is_centered": 2.0,
        "is_preceded_by_larger_gap": 1.5,
        "is_followed_by_smaller_text": 1.5,
        "starts_with_number_or_bullet": 1.5,
        "is_first_on_page": 1.0,
        "is_all_caps": 0.8,
        "is_short_line": 0.7,
        "x_alignment_relevance": 0.5
    }

    level_scores = {"H1": 0.0, "H2": 0.0, "H3": 0.0, "H4": 0.0}
    
    base_prominence = (block["font_size_ratio_to_common"] - 1.0) * weights_base["font_size_prominence"]
    if base_prominence < 0: base_prominence = 0

    # H1 Scoring
    # Adjusted conditions for H1 to be quite strict for core features
    if (block["font_size"] >= dynamic_th.get("H1", float('inf')) and block["is_bold"]) or \
       (block["font_size_ratio_to_common"] > 1.5 and (block["is_centered"] or block["is_first_on_page"])):
        score = base_prominence
        if block["is_bold"]: score += weights_base["is_bold"] * 1.5
        if block["is_centered"]: score += weights_base["is_centered"] * 1.5
        if block["is_preceded_by_larger_gap"]: score += weights_base["is_preceded_by_larger_gap"]
        if block["is_first_on_page"]: score += weights_base["is_first_on_page"] * 1.2
        if block["is_all_caps"]: score += weights_base["is_all_caps"] * 1.2 # All caps stronger for H1
        if block["is_short_line"]: score += weights_base["is_short_line"] * 1.2
        level_scores["H1"] = score
    
    # H2 Scoring
    if (block["font_size"] >= dynamic_th.get("H2", float('inf')) and block["is_bold"]) or \
       (block["font_size_ratio_to_common"] > 1.25 and (block["is_preceded_by_larger_gap"] or block["starts_with_number_or_bullet"])):
        score = base_prominence
        if block["is_bold"]: score += weights_base["is_bold"]
        if block["is_preceded_by_larger_gap"]: score += weights_base["is_preceded_by_larger_gap"]
        if block["is_followed_by_smaller_text"]: score += weights_base["is_followed_by_smaller_text"]
        if block["starts_with_number_or_bullet"]: score += weights_base["starts_with_number_or_bullet"] * 1.2
        if block["is_all_caps"]: score += weights_base["is_all_caps"] * 0.8
        if block["is_short_line"]: score += weights_base["is_short_line"]
        if block["is_centered"]: score += weights_base["is_centered"] * 0.8
        level_scores["H2"] = score

    # H3 Scoring
    if (block["font_size"] >= dynamic_th.get("H3", float('inf')) and block["is_bold"]) or \
       (block["font_size_ratio_to_common"] > 1.1 and block["starts_with_number_or_bullet"]):
        score = base_prominence
        if block["is_bold"]: score += weights_base["is_bold"] * 0.8
        if block["is_preceded_by_larger_gap"]: score += weights_base["is_preceded_by_larger_gap"] * 0.8
        if block["starts_with_number_or_bullet"]: score += weights_base["starts_with_number_or_bullet"] * 1.5
        if block["is_followed_by_smaller_text"]: score += weights_base["is_followed_by_smaller_text"] * 0.8
        if block["is_short_line"]: score += weights_base["is_short_line"]
        level_scores["H3"] = score
    
    # H4 Scoring
    if (block["font_size"] >= dynamic_th.get("H4", float('inf')) and block["starts_with_number_or_bullet"]) or \
       (block["font_size_ratio_to_common"] > 1.05 and block["is_bold"] and block["is_short_line"]):
        score = base_prominence * 0.5
        if block["is_bold"]: score += weights_base["is_bold"] * 0.5
        if block["is_preceded_by_larger_gap"]: score += weights_base["is_preceded_by_larger_gap"] * 0.5
        if block["starts_with_number_or_bullet"]: score += weights_base["starts_with_number_or_bullet"] * 1.8
        if block["is_short_line"]: score += weights_base["is_short_line"] * 0.8
        level_scores["H4"] = score

    min_confidence = {
        "H1": 4.5,
        "H2": 3.5,
        "H3": 2.5,
        "H4": 1.5
    }

    best_level = None
    max_score = -1.0 # Initialize with a value that any valid score will exceed

    # Iterate from H1 to H4 to find the highest scoring, valid level
    # Higher levels are implicitly preferred if scores are close
    for level_key in ["H1", "H2", "H3", "H4"]:
        current_score = level_scores[level_key]
        if current_score >= min_confidence.get(level_key, 0.0) and current_score > max_score:
            max_score = current_score
            best_level = level_key
    
    return best_level

def run(input_path, page_dimensions):
    """
    Classifies text blocks into heading levels H1-H4 using dynamic thresholds
    and contextual features, or an ML model if available.
    Updates the input JSON file in place.
    page_dimensions: A dictionary {page_num: {"width": float, "height": float}} from extract_blocks.
    """
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            blocks = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Error reading or parsing intermediate blocks from {input_path}: {e}")

    if not blocks:
        print("No blocks to classify.")
        try:
            with open(input_path, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)
        except IOError as e:
            raise RuntimeError(f"Error writing empty blocks to {input_path}: {e}")
        return

    blocks.sort(key=lambda b: (b["page"], b["top"], b["x0"]))

    # Pass page_dimensions to calculate_all_features
    blocks_with_features, most_common_font_size = calculate_all_features(blocks, page_dimensions)

    dynamic_thresholds_map = dynamic_thresholds(
        [b["font_size"] for b in blocks_with_features], most_common_font_size
    )
    print(f"Dynamically determined heading thresholds: {dynamic_thresholds_map}")

    classified_blocks_output = []
    for block in blocks_with_features:
        level = None
        if heading_classifier_model:
            # ML model prediction logic goes here.
            pass

        if not level: # If ML model not used or didn't classify, use heuristics
            level = classify_block_heuristic(block, dynamic_thresholds_map, most_common_font_size)

        if level:
            block["level"] = level
        classified_blocks_output.append(block)

    try:
        with open(input_path, "w", encoding="utf-8") as f:
            json.dump(classified_blocks_output, f, indent=2)
    except IOError as e:
        raise RuntimeError(f"Error writing classified blocks to {input_path}: {e}")