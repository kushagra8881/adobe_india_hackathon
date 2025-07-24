import json
import statistics
import re
import collections
from operator import itemgetter

def derive_title_from_summary_and_outline(summary_text, outline_root_node_children, pdf_filename_base, nlp_model=None):
    """
    Derives a meaningful document title from the summary text,
    giving weight to its relevance to actual outline headings and the original filename.
    The title must be whole and meaningful, shorter than 7 words, and not just repetitions or points.
    """
    cleaned_filename_base = re.sub(r'[\s_-]+', ' ', pdf_filename_base).strip().lower()

    if not summary_text or not nlp_model:
        return re.sub(r'[\s_-]+', ' ', pdf_filename_base).strip() # Fallback to filename if no summary or NLP

    doc_sents = list(nlp_model(summary_text).sents)
    
    outline_heading_texts = []
    for node in outline_root_node_children:
        if node.get("level") == 1:
            outline_heading_texts.append(node["text"].strip())
        for child in node.get("children", []):
            if child.get("level") == 2:
                outline_heading_texts.append(child["text"].strip())

    title_candidates = []

    for sent_idx, sent in enumerate(doc_sents):
        sent_text = sent.text.strip()
        num_words_sent = len(sent_text.split())

        if not sent_text:
            continue

        # Filter out sentences that are too long for the title (new constraint: < 7 words)
        if num_words_sent >= 7:
            continue
        
        # Filter out very short, non-descriptive sentences, or those that are clearly just noise/URLs/repetitive
        if num_words_sent < 2 or len(sent_text) < 10 or re.fullmatch(r'[\d\W_]+', sent_text) or \
           re.match(r'^(www\.|http[s]?://|ftp://)', sent_text, re.IGNORECASE) or \
           (num_words_sent > 1 and all(len(word) <= 4 for word in sent_text.split()) and not re.match(r'^[A-Z][A-Z\s]+$', sent_text)): # "HOPE SEE HERE" type blunder
            continue

        # Filter out sentences that look like dates, page numbers, or simple list markers (common noise)
        if re.fullmatch(r'^\s*((\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})|(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})|((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s*\d{4})|(\d{4})|(\d+\.?)|([A-Z]\.?){2,})\s*$', sent_text, re.IGNORECASE):
            continue
        
        score = 0
        
        # Boost for appearing early in the summary
        if sent_idx == 0: 
            score += 10
        elif sent_idx == 1: 
            score += 5
            
        # Semantic/Keyword similarity with outline headings
        if nlp_model and outline_heading_texts:
            sent_doc_lower = nlp_model(sent_text.lower())
            sent_lemmas = {token.lemma_ for token in sent_doc_lower if token.is_alpha and not token.is_stop}
            
            heading_overlap_score = 0
            for heading_text in outline_heading_texts:
                heading_doc_lower = nlp_model(heading_text.lower())
                heading_lemmas = {token.lemma_ for token in heading_doc_lower if token.is_alpha and not token.is_stop}
                
                common_lemmas_count = len(sent_lemmas.intersection(heading_lemmas))
                if common_lemmas_count > 0:
                    heading_overlap_score += common_lemmas_count / len(sent_lemmas) if len(sent_lemmas) > 0 else 0
            
            score += heading_overlap_score * 8 
            
            if heading_overlap_score == 0 and len(sent_lemmas) > 5:
                score -= 8 
        
        # Clause to check doc name as well and give more weightage
        if cleaned_filename_base and nlp_model:
            filename_doc = nlp_model(cleaned_filename_base)
            filename_lemmas = {token.lemma_ for token in filename_doc if token.is_alpha and not token.is_stop}
            
            if filename_lemmas:
                filename_overlap_count = len(sent_lemmas.intersection(filename_lemmas))
                if filename_overlap_count > 0:
                    score += filename_overlap_count * 5 


        title_candidates.append({"text": sent_text, "score": score})

    best_candidate = None
    if title_candidates:
        best_candidate = max(title_candidates, key=itemgetter("score"))
    
    final_title = ""
    # Ensure a minimum score for a summary sentence to be considered a title, AND meet length constraint
    if best_candidate and best_candidate["score"] > 5 and len(best_candidate["text"].split()) < 7: 
        final_title = best_candidate["text"]
    else: # Fallback to cleaned filename if no good summary candidate
        final_title = re.sub(r'[\s_-]+', ' ', pdf_filename_base).strip()

    # Final cleaning: remove common prefixes, excessive spaces
    final_title = re.sub(r'^(the\s*|an\s*|a\s*|this\s*document\s*|this\s*report\s*|summary\s*of\s*|overview\s*of\s*|request\s*for\s*proposal\s*)\s*', '', final_title, flags=re.IGNORECASE).strip()
    final_title = re.sub(r'[\u201c\u201d"\'`]', '', final_title).strip()
    final_title = re.sub(r'\s+', ' ', final_title).strip()
    
    # If after all derivation and cleaning, the title is still too short or looks like a fragment/generic, revert to filename
    # Re-check length after cleaning
    if len(final_title.split()) < 3 or len(final_title) < 20 or re.fullmatch(r'[\s\d\W_]+', final_title) or len(final_title.split()) >= 7: # Re-enforce < 7 words
        final_title = re.sub(r'[\s_-]+', ' ', pdf_filename_base).strip()

    return final_title


def _count_headings_in_outline(outline_nodes):
    """Recursively counts total headings in a structured outline."""
    count = 0
    for node in outline_nodes:
        count += 1
        count += _count_headings_in_outline(node.get("children", []))
    return count

def _prune_outline_by_length_constraint(outline_nodes, max_headings_allowed):
    """
    Intelligently prunes the outline to meet a maximum heading count constraint.
    Prioritizes higher-level headings and more prominent ones.
    """
    flat_headings = []
    
    # Convert to a flat list with full path and score for pruning decisions
    def flatten_and_score(nodes, current_path=[]):
        for node in nodes:
            # Score: higher level = more important, earlier in document = more important
            # Add weight for font size, boldness if original block data were passed
            score = (5 - node["level"]) * 1000 + (1000 - node["page"]) # Level has higher weight
            
            flat_headings.append({
                "node": node,
                "score": score,
                "path_levels": [p.get("level",0) for p in current_path] + [node["level"]]
            })
            flatten_and_score(node.get("children", []), current_path + [node])

    flatten_and_score(outline_nodes)
    
    if len(flat_headings) <= max_headings_allowed:
        return outline_nodes # No pruning needed

    # Sort by score (most important first)
    flat_headings.sort(key=lambda x: x["score"], reverse=True)

    # Select top N headings.
    # To maintain hierarchy, we must ensure parents are kept if their children are selected.
    selected_nodes_ids = set() # Use IDs to keep track of selected nodes

    # First pass: select the top `max_headings_allowed` nodes and all their ancestors
    initial_selection = flat_headings[:max_headings_allowed]
    
    # Create a map from original node object (by its ID) to its path for easy ancestor finding
    all_nodes_map = {}
    def build_node_map(nodes, current_path=[]):
        for node in nodes:
            # Assign a unique ID if not already present (from classify_headings smoothing)
            if "_id" not in node:
                node["_id"] = id(node) 
            all_nodes_map[node["_id"]] = {"node": node, "path": current_path}
            build_node_map(node.get("children", []), current_path + [node])
    
    build_node_map(outline_nodes)

    for item in initial_selection:
        current_node_id = item["node"]["_id"]
        selected_nodes_ids.add(current_node_id)
        
        # Add all ancestors of the current node to selected_nodes_ids
        for ancestor_node in all_nodes_map[current_node_id]["path"]:
            selected_nodes_ids.add(ancestor_node["_id"])

    # Rebuild the outline based on selected nodes
    def rebuild_outline(nodes):
        rebuilt_children = []
        for node in nodes:
            if node["_id"] in selected_nodes_ids:
                rebuilt_node = node.copy()
                rebuilt_node["children"] = rebuild_outline(node.get("children", []))
                rebuilt_children.append(rebuilt_node)
        return rebuilt_children

    return rebuild_outline(outline_nodes)


def run(classified_blocks, num_pages_total, pdf_filename_base="Untitled Document"):
    """
    Reads classified blocks (in-memory), structures the outline, and prepares for title derivation.
    Applies heading text truncation and outline length constraint.
    num_pages_total: Total number of pages in the PDF, used for outline length constraint.
    """
    blocks = classified_blocks 

    # --- Outline Structuring ---
    headings = [b for b in blocks if b.get("level") and b["level"].startswith("H")]
    headings.sort(key=itemgetter("page", "top")) 

    root = {"level": 0, "children": []} 
    path = [root] 

    for heading in headings:
        level = int(heading["level"][1:]) 
        node_text = heading["text"].strip()

        # Apply "no text above 5 words into the outline text" constraint (truncation for display)
        if len(node_text.split()) > 5:
            node_text = " ".join(node_text.split()[:5]) + "..."
        
        node = {
            "level": level,
            "text": node_text, 
            "page": heading["page"],
            "children": [],
            "_id": id(heading) # Assign unique ID to node for pruning
        }
        
        while path and path[-1]["level"] >= level:
            path.pop()
        
        if not path:
            path.append(root)
        elif level > path[-1]["level"] + 1:
            node["level"] = path[-1]["level"] + 1
            level = node["level"] 

        path[-1]["children"].append(node)
        path.append(node)

    # --- Final Outline Cleaning (recursive to prune empty/fix nested levels) ---
    def clean_outline_recursive(nodes):
        cleaned = []
        for node in nodes:
            if not node["text"].strip(): 
                continue
            
            node["children"] = clean_outline_recursive(node["children"])
            
            if cleaned and node["level"] > cleaned[-1]["level"] + 1:
                node["level"] = cleaned[-1]["level"] + 1
            
            cleaned.append(node)
        return cleaned
    
    final_outline = clean_outline_recursive(root["children"])

    # --- Apply Outline Length Constraint (2-3 times number of pages) ---
    # Using a multiplier of 3 (can be adjusted)
    max_headings_allowed = 3 * num_pages_total
    current_heading_count = _count_headings_in_outline(final_outline)

    if current_heading_count > max_headings_allowed:
        print(f"DEBUG: Outline too long ({current_heading_count} headings for {num_pages_total} pages). Pruning to {max_headings_allowed}.")
        final_outline = _prune_outline_by_length_constraint(final_outline, max_headings_allowed)


    return {
        "outline": final_outline
    }