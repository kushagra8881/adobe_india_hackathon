import os
import sys

script_dir = os.path.dirname(__file__)
if script_dir not in sys.path:
    sys.path.append(script_dir)

from pdf_utils import extract_blocks, classify_headings, structure_outline, generate_outline

INPUT_DIR = "/app/input"
OUTPUT_DIR = "/app/output"

def process_pdf(pdf_path, output_dir):
    """
    Processes a single PDF file to extract its outline.
    """
    base_filename = os.path.basename(pdf_path)
    name_without_ext = os.path.splitext(base_filename)[0]

    intermediate_path = os.path.join(output_dir, f"{name_without_ext}_intermediate_blocks.json")
    final_output_path = os.path.join(output_dir, f"{name_without_ext}.json")

    print(f"Starting processing for: {base_filename}")
    try:
        print(f"  Stage 1: Extracting blocks from {base_filename} using pdfminer.six...")
        # extract_blocks.run now returns blocks and page_dimensions
        extracted_blocks, page_dimensions = extract_blocks.run(pdf_path, intermediate_path)

        print(f"  Stage 2: Classifying headings for {base_filename} (enhanced heuristics + contextual features)...")
        # Pass page_dimensions to classify_headings for accurate centering
        classify_headings.run(intermediate_path, page_dimensions)

        print(f"  Stage 3: Structuring outline for {base_filename}...")
        # Pass page_dimensions for potentially better title extraction
        structure_outline.run(intermediate_path, final_output_path, page_dimensions)

        print(f"  Stage 4: Finalizing output for {base_filename}...")
        generate_outline.run(final_output_path)
        print(f"Successfully generated outline for {base_filename} to {final_output_path}")
    except Exception as e:
        print(f"ERROR: Failed to process {base_filename}. Reason: {e}")
        if os.path.exists(intermediate_path):
            try:
                os.remove(intermediate_path)
            except OSError as cleanup_e:
                print(f"Warning: Could not remove intermediate file {intermediate_path}: {cleanup_e}")


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    pdf_files_found = False
    if not os.path.exists(INPUT_DIR):
        print(f"Input directory '{INPUT_DIR}' not found. Please ensure it's mounted correctly.")
    else:
        for filename in os.listdir(INPUT_DIR):
            if filename.lower().endswith(".pdf"):
                pdf_path = os.path.join(INPUT_DIR, filename)
                process_pdf(pdf_path, OUTPUT_DIR)
                pdf_files_found = True

    if not pdf_files_found:
        print(f"No PDF files found in {INPUT_DIR}. Please mount your PDFs to this directory inside the container.")
    print("All processing complete.")