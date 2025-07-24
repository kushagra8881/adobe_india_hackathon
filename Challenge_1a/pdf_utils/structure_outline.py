import json
import statistics
import re
import collections
from operator import itemgetter

# Removed check_meaningful_fragment from this file as it's part of classify_headings
# and we're passing nlp_model directly to title derivation now.

def derive_title_from_sampled_text_and_filename(sampled_raw_blocks, pdf_filename_base, nlp_model=None):
    """
    Derives a meaningful document title based on text from early pages (with font size priority)
    and relatability to the PDF filename.
    The title must be short (shorter than 7 words) and meaningfully complete.
    Does NOT use summary text directly for title.
    """
    cleaned_filename_base = re.sub(r'[\s_-]+', ' ', pdf_filename_base).strip().lower()

    if not sampled_raw_blocks or not nlp_model:
        return re.sub(r'[\s_-]+', ' ', pdf_filename_base).strip() # Fallback to filename

    # Calculate common font size from sampled blocks for title scoring
    all_sampled_font_sizes = [b.get("font_size", 0.0) for b in sampled_raw_blocks if b.get("font_size") > 0]
    if not all_sampled_font_sizes:
        most_common_sampled_font_size = 12.0
    else:
        try:
            most_common_sampled_font_size = statistics.median(all_sampled_font_sizes)
        except statistics.StatisticsError:
            most_common_sampled_font_size = all_sampled_font_sizes[0]
        if most_common_sampled_font_size == 0:
            most_common_sampled_font_size = 12.0

    title_candidates = []
    
    for block_idx, block in enumerate(sampled_raw_blocks):
        sent_text = block["text"].strip()
        num_words_sent = len(sent_text.split())

        if not sent_text:
            continue
        
        # 1. Title must be short: shorter than 7 words.
        if num_words_sent >= 7 or num_words_sent < 2: # Min 2 words for a meaningful title
            continue
        
        # 2. Meaningful and complete (NLP based check, filter repetitive/gibberish)
        doc_sent = nlp_model(sent_text)
        is_cjk = nlp_model.lang_ in ["zh", "ja", "ko"] # Check if NLP model is CJK for language-specific sentence rules

        # Basic sentence structure check for non-CJK
        if not is_cjk:
            if not list(doc_sent.sents) or len(list(doc_sent.sents)[0].text.strip().split()) < num_words_sent * 0.8: # Fragmented sentence structure
                continue # Prune fragmented sentences
        
        # Filter patterns that are definitely NOT titles (URLs, common headers/footers, very short non-descriptive, repetitions)
        if re.match(r'^(www\.|http[s]?://|ftp://)', sent_text, re.IGNORECASE) or \
           re.fullmatch(r'[\d\W_]+', sent_text) or \
           re.match(r'^\s*(Page|Table|Figure)\s+\d+(\.\d+)?', sent_text, re.IGNORECASE) or \
           re.match(r'^\s*([A-Z]\.?){2,}', sent_text) or \
           (num_words_sent > 1 and all(len(word) <= 4 for word in sent_text.split()) and not re.match(r'^[A-Z][A-Z\s]+$', sent_text)): # "HOPE SEE HERE" type blunder
            continue
        
        # If the text is very repetitive (e.g., "RFP RFP RFP")
        if re.search(r'(\b\w+\b\s*){2,}\1', sent_text, re.IGNORECASE): # Detect repeated words/phrases
             continue

        # Check for unclosed parentheses/brackets (strong indicator of fragmentation)
        stack = []
        mapping = {")": "(", "]": "[", "}": "{"}
        unclosed = False
        for char in sent_text:
            if char in mapping.values():
                stack.append(char)
            elif char in mapping:
                if not stack or stack.pop() != mapping[char]:
                    unclosed = True; break
        if len(stack) > 0 or unclosed: # Unclosed or mismatched
            continue
        
        score = 0
        
        # Font size weight: larger fonts get more score
        font_size = block.get("font_size", most_common_sampled_font_size)
        font_size_ratio = font_size / most_common_sampled_font_size
        score += font_size_ratio * 10 # Strong weight for font size

        if block.get("is_bold", False):
            score += 5
        
        # Position weight: earlier blocks get more score (scaled by index)
        # Assuming sampled_raw_blocks is ordered
        position_score = (len(sampled_raw_blocks) - block_idx) / len(sampled_raw_blocks)
        score += position_score * 5 

        # Relatability score with PDF filename
        if cleaned_filename_base and nlp_model:
            sent_doc = nlp_model(sent_text.lower())
            filename_doc = nlp_model(cleaned_filename_base)
            
            # Using spaCy's vector similarity if available, else keyword overlap
            if sent_doc.has_vector and filename_doc.has_vector:
                similarity = sent_doc.similarity(filename_doc)
                score += similarity * 10 # Strong boost for semantic similarity
            else: # Fallback to keyword overlap if vectors not available (e.g., xx_ent_wiki_sm might not have vectors)
                sent_lemmas = {token.lemma_ for token in sent_doc if token.is_alpha and not token.is_stop}
                filename_lemmas = {token.lemma_ for token in filename_doc if token.is_alpha and not token.is_stop}
                if sent_lemmas and filename_lemmas:
                    overlap = len(sent_lemmas.intersection(filename_lemmas)) / min(len(sent_lemmas), len(filename_lemmas))
                    score += overlap * 5
        
        title_candidates.append({"text": sent_text, "score": score, "font_size": font_size})

    best_title_candidate = None
    if title_candidates:
        # Prioritize by score, then by font size (larger font if scores are equal)
        title_candidates.sort(key=lambda x: (x["score"], x["font_size"]), reverse=True)
        best_title_candidate = title_candidates[0]

    final_title = ""
    if best_title_candidate and best_title_candidate["score"] > 3: # Minimum score to consider a candidate
        final_title = best_title_candidate["text"]
    else:
        final_title = re.sub(r'[\s_-]+', ' ', pdf_filename_base).strip() # Fallback to cleaned filename


    # Final cleaning of the determined title
    final_title = re.sub(r'^(the\s*|an\s*|a\s*|this\s*document\s*|this\s*report\s*|overview\s*of\s*|request\s*for\s*proposal\s*)\s*', '', final_title, flags=re.IGNORECASE).strip()
    final_title = re.sub(r'[\u201c\u201d"\'`]', '', final_title).strip()
    final_title = re.sub(r'\s+', ' ', final_title).strip()
    
    # Final check for quality: if it's too short or looks like a generic fragment after all processing
    if len(final_title.split()) < 3 or len(final_title) < 20 or re.fullmatch(r'[\s\d\W_]+', final_title) or len(final_title.split()) >= 7: 
        final_title = re.sub(r'[\s_-]+', ' ', pdf_filename_base).strip()

    return final_title


def _prune_outline_for_length_and_page_coverage(flat_headings, num_pages_total):
    """
    Prunes the flattened list of headings to meet length constraints and ensure page coverage.
    Removes H4s first, then H3s, etc. Keeps at least 1-2 headings per page.
    The flat_headings are assumed to be sorted by page, then level, then text for initial passes.
    """
    if not flat_headings:
        return []

    # Map page number to list of headings on that page
    headings_by_page = collections.defaultdict(list)
    for heading in flat_headings:
        headings_by_page[heading["page"]].append(heading) # Page numbers are already 0-indexed here

    # Determine the target number of headings based on 1-2 per page and max 3*pages
    target_max_total_headings = int(num_pages_total * 3) # Max allowed total headings
    
    # Pass 1: Ensure minimum headings per page (1 to 2) and initially collect all unique headings
    
    # Use a set to track which headings (by their content) are already selected
    selected_heading_texts = set() 
    initial_selection_for_coverage = []

    for page_num_0_indexed in range(num_pages_total): # Iterate through 0-indexed page numbers
        page_headings = sorted(headings_by_page.get(page_num_0_indexed, []), key=lambda x: (int(x["level"][1:]), x["text"])) # Sort by level then text
        
        kept_on_page_count = 0
        
        # Prioritize keeping higher-level headings (H1-H3) for minimum coverage
        for heading in page_headings:
            if kept_on_page_count < 1: # Ensure at least 1 heading per page
                # Add to selection if not already added (e.g., from an earlier page's selection)
                if heading["text"] not in selected_heading_texts:
                    initial_selection_for_coverage.append(heading)
                    selected_heading_texts.add(heading["text"])
                    kept_on_page_count += 1
            # Add a second heading if possible, favoring H1-H3 or most prominent H4
            elif kept_on_page_count < 2 and int(heading["level"][1:]) <= 3: # Try to get up to 2, prioritize H1-H3
                if heading["text"] not in selected_heading_texts:
                    initial_selection_for_coverage.append(heading)
                    selected_heading_texts.add(heading["text"])
                    kept_on_page_count += 1
            elif kept_on_page_count < 2 and int(heading["level"][1:]) == 4 and len(heading["text"].split()) > 1: # If H4, ensure it's not too short
                 if heading["text"] not in selected_heading_texts:
                    initial_selection_for_coverage.append(heading)
                    selected_heading_texts.add(heading["text"])
                    kept_on_page_count += 1

        # If after checking all actual headings, the page still doesn't have at least one heading, add a generic placeholder
        if kept_on_page_count == 0:
            placeholder = {
                "level": "H4",
                "text": f"Page {page_num_0_indexed+1} Overview", # Display 1-indexed page number
                "page": page_num_0_indexed # Store 0-indexed page number
            }
            if placeholder["text"] not in selected_heading_texts:
                initial_selection_for_coverage.append(placeholder)
                selected_heading_texts.add(placeholder["text"])
                
    # Now, `initial_selection_for_coverage` contains unique headings ensuring page coverage.
    # We need to add back any other remaining headings that were classified (not just 1-2 per page)
    # up to the `target_max_total_headings` limit.

    all_unique_classified_headings = {} # Map text to heading object for uniqueness and latest info
    for heading in flat_headings: 
        all_unique_classified_headings[heading["text"]] = heading # Overwrite with last seen if duplicates

    # Ensure all headings from `initial_selection_for_coverage` are in the `final_pruned_list` first
    final_pruned_list = []
    for heading in initial_selection_for_coverage:
        final_pruned_list.append(heading)

    # Add remaining original classified headings (that were not selected in initial coverage pass)
    # Prioritize them by level (H1-H4), then page, then text.
    remaining_headings = []
    for heading in all_unique_classified_headings.values():
        if heading["text"] not in selected_heading_texts: 
            remaining_headings.append(heading)
    
    remaining_headings.sort(key=lambda x: (int(x["level"][1:]), x["page"], x["text"]))
    
    # Add these remaining headings until `target_max_total_headings` is reached
    for heading in remaining_headings:
        if len(final_pruned_list) < target_max_total_headings:
            final_pruned_list.append(heading)
        else:
            break # Stop if we hit the max limit

    # Final pruning pass: If we still exceed the `target_max_total_headings`, remove lowest priority
    while len(final_pruned_list) > target_max_total_headings:
        # Sort by level (H4 highest priority for removal), then page (later pages first)
        final_pruned_list.sort(key=lambda x: (int(x["level"][1:]), -x["page"]), reverse=True)
        
        # Remove the lowest priority heading (which is now at the end of the list)
        removed_one = False
        for idx in range(len(final_pruned_list) -1, -1, -1):
            heading_to_consider = final_pruned_list[idx]
            
            # Count headings on this page that are of HIGHER priority or are protected H1/H2/H3
            current_page_headings_count = 0
            for h in final_pruned_list:
                if h["page"] == heading_to_consider["page"] and h != heading_to_consider:
                    current_page_headings_count += 1

            # Only remove if its page still has more than the minimum allowed headings (e.g., 1 or 2)
            # This logic needs to be careful to ensure 1-2 per page minimums are met for the final output.
            # Here, `target_ideal_per_page` is 2. We'll ensure at least 1 heading per page after removal.
            if current_page_headings_count >= 1: # If other headings remain on page, can remove
                final_pruned_list.pop(idx)
                removed_one = True
                break
        
        if not removed_one: # If unable to remove more without violating min_per_page
            break

    # Final sort for output: by page, then by level, then by text
    final_pruned_list.sort(key=lambda x: (x["page"], int(x["level"][1:]), x["text"]))

    return final_pruned_list


def run(classified_blocks, num_pages_total, pdf_filename_base="Untitled Document"):
    """
    Reads classified blocks, structures the outline into a flat list,
    applies heading text truncation, and prunes to meet length constraints.
    """
    # Filter only blocks that were classified as headings
    headings = [b for b in classified_blocks if b.get("level") and b["level"].startswith("H")]
    
    # Prepare outline nodes for pruning (flat list).
    prepared_outline_nodes = []
    for heading in headings:
        node_text = heading["text"].strip()
        
        # Apply "no text above 5 words into the outline text" constraint (truncation for display)
        if len(node_text.split()) > 5:
            node_text = " ".join(node_text.split()[:5]) + "..."
        
        prepared_outline_nodes.append({
            "level": heading["level"], 
            "text": node_text, 
            "page": heading["page"] -1 # NEW: Adjust page number to be 0-indexed
        })
    
    # Apply outline pruning based on page coverage and level priority
    final_pruned_outline = _prune_outline_for_length_and_page_coverage(prepared_outline_nodes, num_pages_total)

    return {
        "outline": final_pruned_outline
    }