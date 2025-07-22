# pdf_utils/structure_outline.py

import json
import statistics
import re
import collections
from operator import itemgetter

def run(classified_blocks, page_dimensions, pdf_filename_base="Untitled Document"):
    """
    Reads classified blocks (in-memory), extracts the title using improved heuristics,
    and structures the flat outline.
    Returns a dictionary containing the title and the structured outline.
    """
    blocks = classified_blocks # Use the passed in-memory blocks

    # --- Title Extraction Logic ---
    document_title = "Untitled Document"
    cleaned_filename_title = re.sub(r'[\s_-]+', ' ', pdf_filename_base).strip()
    strong_filename_candidate = cleaned_filename_title if 5 < len(cleaned_filename_title) < 100 and len(cleaned_filename_title.split()) >= 2 else None

    # Filter out header/footer blocks for title consideration
    content_blocks = [b for b in blocks if not b.get("is_header_footer", False) and b["text"].strip()]

    if content_blocks:
        # Sort content blocks to find candidates from the beginning of the document
        content_blocks.sort(key=itemgetter("page", "top"))

        title_candidates = []
        # Consider blocks on the first few pages (e.g., up to page 3)
        for block in content_blocks:
            if block["page"] > 2:
                break
            
            # Consider blocks that are H1, or large/bold/centered, or first block on page
            if block.get("level") == "H1" or \
               (block.get("font_size_ratio_to_common", 0) > 1.8 and block.get("is_bold", False)) or \
               (block.get("is_first_on_page", False) and block.get("is_centered", False)):
                title_candidates.append({
                    "text": block["text"].strip(),
                    "font_size": block["font_size"],
                    "is_bold": block["is_bold"],
                    "is_centered": block["is_centered"],
                    "page": block["page"],
                    "score": 0 # Placeholder for scoring
                })

        # Score candidates
        # A more robust scoring: combine font size, bold, centered, page position, and length
        for candidate in title_candidates:
            score = candidate["font_size"] * 2.5 # Higher font size, higher score
            if candidate["is_bold"]: score += 6.0
            if candidate["is_centered"]: score += 10.0 # Strong indicator for titles
            
            # Penalize for later pages, but not too harshly for covers/title pages
            if candidate["page"] == 0: score += 12.0 # First page is strongest
            elif candidate["page"] == 1: score += 7.0
            elif candidate["page"] == 2: score += 3.0
            
            # Penalize for very short or very long titles
            num_words = len(candidate["text"].split())
            if num_words < 3 or num_words > 20: # Heuristic for reasonable title length
                score -= 5.0
            if len(candidate["text"]) > 150: # Too long for a title
                score -= 8.0

            candidate["score"] = score
        
        # Select the best title candidate
        if title_candidates:
            best_candidate = max(title_candidates, key=lambda x: x["score"])
            # A higher confidence threshold for accepting a title
            if best_candidate["score"] > 25.0: # Refined heuristic threshold for strong title
                document_title = best_candidate["text"]
            elif strong_filename_candidate: # If no strong title, fallback to filename
                document_title = strong_filename_candidate
            else:
                # Last resort: first non-empty block, clipped
                first_content_block_text = ""
                for b in content_blocks:
                    if b["text"].strip():
                        first_content_block_text = b["text"].strip()
                        break
                if first_content_block_text:
                    document_title = first_content_block_text[:100] + "..." if len(first_content_block_text) > 100 else first_content_block_text
                    if document_title.endswith("..."):
                        # Try to cut at a sentence end if possible for snippet-like titles
                        match = re.search(r'[.?!]\s', document_title[:-3])
                        if match:
                            document_title = document_title[:match.end()].strip()
                        elif ',' in document_title[:-3]:
                            document_title = document_title[:document_title.rfind(',') + 1].strip()

        elif strong_filename_candidate:
            document_title = strong_filename_candidate
    
    document_title = document_title.replace('\n', ' ').strip() # Clean newlines from title

    # --- Outline Structuring ---
    # Only consider blocks that have been classified as headings
    headings = [b for b in blocks if b.get("level") and b["level"].startswith("H")]
    headings.sort(key=itemgetter("page", "top")) # Already sorted, but re-confirm

    root = {"level": 0, "children": []}
    path = [root]

    for heading in headings:
        level = int(heading["level"][1:])
        node = {
            "level": level,
            "text": heading["text"].strip(), # Ensure text is stripped
            "page": heading["page"],
            "children": []
        }
        
        # Pop off levels that are at or deeper than the current heading
        while path and path[-1]["level"] >= level:
            path.pop()
        
        # If the path becomes empty (shouldn't happen with `root`), or if the level
        # is too deep compared to the current parent, attach to the highest available parent.
        # The `smooth_heading_levels` in classify_headings.py should already handle
        # most of the problematic level jumps, so this is mainly for robustness.
        if not path:
            path.append(root)
        elif level > path[-1]["level"] + 1:
            # If we jump from H1 directly to H3 (i.e., path[-1] is H1, level is 3)
            # We want to create dummy intermediate levels if `smooth_heading_levels` missed it.
            # This is a fallback and can create 'dummy' headings if the source PDF is poorly structured.
            # A more robust approach would be to refine `smooth_heading_levels` to *always* fix this.
            # For strict hierarchy, this means effectively promoting the H3 to an H2 if H2 is missing.
            node["level"] = path[-1]["level"] + 1
            print(f"Outline Warning: Adjusted level of '{node['text']}' from H{level} to H{node['level']} for hierarchical consistency.")
            level = node["level"] # Update current level for path.append

        path[-1]["children"].append(node)
        path.append(node)

    # --- Final Outline Cleaning (optional, but good for robustness) ---
    def clean_outline_recursive(nodes):
        cleaned = []
        for node in nodes:
            if not node["text"].strip(): # Remove empty text nodes
                continue
            
            # Ensure children are also cleaned and recursively processed
            node["children"] = clean_outline_recursive(node["children"])
            
            # Re-verify levels to ensure strict incremental hierarchy (H1 > H2 > H3)
            # This is a final safety net for levels, mainly if previous stages miss something
            if cleaned and node["level"] > cleaned[-1]["level"] + 1:
                node["level"] = cleaned[-1]["level"] + 1
                # print(f"Final outline adjustment: Level of '{node['text']}' promoted to H{node['level']} to maintain strict hierarchy.")
            
            cleaned.append(node)
        return cleaned
    
    final_outline = clean_outline_recursive(root["children"])

    # --- Final Output Generation ---
    final_output = {
        "title": document_title,
        "outline": final_outline
    }
    
    return final_output
