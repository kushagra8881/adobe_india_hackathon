import json
from .advanced_heading_detector import AdvancedHeadingDetector

def run(input_path, output_path, page_dimensions):
    """
    Reads classified blocks and uses advanced heading detection to create final outline
    """
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            blocks = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Error reading or parsing classified blocks from {input_path}: {e}")

    # Initialize advanced detector
    detector = AdvancedHeadingDetector()
    
    # Process with advanced detector to get final outline
    result = detector.process_document(blocks, page_dimensions)
    
    # Extract title and outline
    document_title = result.get("title", "Untitled Document")
    outline = result.get("outline", [])
    
    print(f"Document title: {document_title}")
    print(f"Found {len(outline)} headings")
    
    # Create final output structure
    output_json = {
        "title": document_title,
        "outline": outline
    }

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_json, f, indent=2, ensure_ascii=False)
    except IOError as e:
        raise RuntimeError(f"Error writing final outline to {output_path}: {e}")
