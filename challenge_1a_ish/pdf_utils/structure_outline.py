import json
import statistics

def run(input_path, output_path, page_dimensions):
    """
    Reads classified blocks, extracts the title using improved heuristics,
    and structures the flat outline as per the required format.
    page_dimensions: A dictionary {page_num: {"width": float, "height": float}} from extract_blocks.
    """
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            blocks = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Error reading or parsing classified blocks from {input_path}: {e}")

    # --- Title Extraction Improvement ---
    document_title = "Untitled Document"
    if blocks:
        first_page_blocks = [b for b in blocks if b["page"] == 1]
        
        if first_page_blocks:
            # Sort first page blocks to ensure consistent order for analysis
            first_page_blocks.sort(key=lambda b: (b["top"], b["x0"]))

            page1_font_sizes = [b["font_size"] for b in first_page_blocks]
            try:
                page1_most_common_font_size = statistics.mode(page1_font_sizes) if page1_font_sizes else 0
            except statistics.StatisticsError:
                page1_most_common_font_size = statistics.median(page1_font_sizes) if page1_font_sizes else 0

            candidate_titles = []
            for block in first_page_blocks:
                # Retrieve features calculated in classify_headings.py
                font_size_ratio = block.get("font_size_ratio_to_common", block["font_size"] / (page1_most_common_font_size if page1_most_common_font_size > 0 else block["font_size"]))
                text_len = len(block["text"].strip())
                num_words = block.get("num_words", len(block["text"].split()))
                
                # Use actual page width for centering if available from page_dimensions
                is_centered = False
                page_info = page_dimensions.get(block["page"])
                if page_info and page_info["width"] > 0:
                    page_width = page_info["width"]
                    block_center_x = block["x0"] + block["width"] / 2
                    page_center_x = page_width / 2
                    is_centered = abs(block_center_x - page_center_x) < (page_width * 0.10) # 10% tolerance

                # Criteria for a title candidate:
                # 1. Significantly larger font than common text (e.g., at least 30-40% larger).
                # 2. Not extremely short (like a page number/footer) or very long (paragraph).
                # 3. Preferably bold, or centered, or first prominent element.
                # 4. Not a low-level heading (H3/H4 are unlikely to be titles).

                if font_size_ratio < 1.3: # Must be at least 30% larger than common font
                    continue
                
                if text_len < 5 or num_words < 2 or text_len > 100: # Adjust length heuristics as needed
                    continue
                
                if block.get("level") in {"H3", "H4"}: # Exclude if already classified as lower-level heading
                    continue
                
                # Add 'is_centered' to the block temporarily for sorting
                block['is_centered_for_title_sort'] = is_centered 
                candidate_titles.append(block)

            if candidate_titles:
                # Sort candidates using multiple criteria to find the "best" title:
                # 1. By font size (descending) - most important indicator of prominence.
                # 2. By boldness (bold first) - strong visual cue.
                # 3. By 'is_centered_for_title_sort' (True first) - titles are often centered.
                # 4. By 'top' position (ascending) - higher on the page is better.
                # 5. By 'is_preceded_by_larger_gap' (True first) - clear visual separation.
                candidate_titles.sort(key=lambda x: (
                    -x["font_size"],
                    not x.get("is_bold", False),
                    not x.get("is_centered_for_title_sort", False), # Use the new temporary key
                    x["top"],
                    not x.get("is_preceded_by_larger_gap", False)
                ))
                
                document_title = candidate_titles[0]["text"]
            else:
                # Fallback to the very first block's text if no strong title candidate found
                document_title = blocks[0]["text"]
        else:
            document_title = "Untitled Document" # No blocks on first page, or no blocks at all
    
    # --- Outline Structuring (Flat as per requirement) ---
    outline = []
    # Levels to consider for the outline
    heading_levels = {"H1", "H2", "H3", "H4"}

    for block in blocks:
        if block.get("level") in heading_levels:
            outline.append({
                "level": block["level"],
                "text": block["text"],
                "page": block["page"]
            })

    output_json = {
        "title": document_title,
        "outline": outline
    }

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_json, f, indent=2)
    except IOError as e:
        raise RuntimeError(f"Error writing final outline to {output_path}: {e}")