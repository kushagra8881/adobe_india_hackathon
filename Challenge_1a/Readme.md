
✅ Python 3.10 Compatibility
This project is verified to run smoothly on Python 3.10 with the following library versions:

pdfminer.six==20221105: Compatible with Python ≥3.6.

spaCy==3.7.2: Supports Python ≥3.7 and <3.13 — fully compatible with 3.10.

scikit-learn==1.4.2: Requires Python ≥3.9 — compatible with 3.10.

pandas==2.2.2: Requires Python ≥3.9 — compatible with 3.10.

joblib==1.4.0: Requires Python ≥3.9 — compatible with 3.10.

✅ All dependencies are fully compatible with Python 3.10, ensuring stable performance. 

# PDF Outline Extraction Pipeline

## Project Overview

This project delivers a robust solution for extracting structured outlines from PDF documents. Its core function is to accurately identify the document's main title and various levels of headings (H1, H2, H3, H4), outputting them in a clean, machine-readable JSON format. This structured data is fundamental for applications requiring automated document navigation, semantic search, and content analysis.

**Key Requirements & Constraints:**

  * **Input:** Processes PDF files efficiently, designed for documents up to 50 pages.
  * **Output:** Generates a JSON file strictly adhering to the specified format, including the document's `title` and a flat `outline` list of heading objects (each with `level`, `text`, and `page`).
  * **Execution Environment:** Optimized for CPU-only (AMD64 architecture) systems, operating entirely offline (no internet access). Performance targets strict limits (e.g., ≤ 10 seconds for a 50-page PDF, custom model size ≤ 200MB if used).
  * **Scalability:** Automatically processes all PDF files found within a mounted `/app/input` directory, producing a corresponding JSON outline for each in the `/app/output` directory.

The pipeline is built on a modular architecture, progressing through four distinct and independent stages:

1.  **Block Extraction:** Parses PDF content into rich text blocks, including page-level dimensions.
2.  **Heading Classification:** Identifies and labels headings (H1-H4) using advanced, weighted heuristics and comprehensive contextual analysis, with optional multilingual awareness via `spaCy`.
3.  **Outline Structuring:** Filters classified blocks to form the final flat outline and intelligently extracts the document's main title.
4.  **Outline Generation:** A final step for output confirmation.

-----

## Project Structure

```
pdf_outline_project/
├── pdf_utils/
│   ├── extract_blocks.py        # Stage 1: Extracts text blocks + metadata (pdfminer.six)
│   ├── classify_headings.py     # Stage 2: Classifies H1–H4 (enhanced heuristics, weighted scoring, multilingual)
│   ├── structure_outline.py     # Stage 3: Structures outline & extracts title
│   ├── generate_outline.py      # Stage 4: Output final JSON (placeholder)
│
├── models/
│   ├── heading_classifier.pkl   # Optional ML model (not used by default)
│   └── xx_ent_wiki_sm           # Directory for optional spaCy multilingual model
│
├── outputs/
│   ├── intermediate_blocks.json # Intermediate data
│   ├── outline_final.json       # Final outline
│
├── main.py                      # Entrypoint script
├── requirements.txt             # Project dependencies
```

-----

## Detailed Processing Pipeline

The `main.py` script orchestrates the execution flow, managing each PDF's progression through the pipeline.

### 1\. Stage 1: Block Extraction (`pdf_utils/extract_blocks.py`)

  * **Purpose:** The foundational step; it parses raw PDF visual content and converts it into a structured list of text blocks. Each block is enriched with its precise location, font characteristics, and other properties.
  * **Method:** Utilizes `pdfminer.six` for its robust and granular control over PDF text extraction. It processes content page by page, line by line, and even character by character.
  * **Key Operations:**
      * **Text & Geometry:** Extracts the textual content of each line, along with its bounding box coordinates (`x0`, `top`, `bottom`, `width`, `height`).
      * **Font Properties:** Captures `font_size`, `font_name`, and infers `is_bold` and `is_italic` from the font's name (e.g., detecting "Bold", "Bd", "Italic").
      * **Page Dimensions:** Crucially, it extracts the actual `width` and `height` of each page's `mediabox`. This precise page-level dimension data is passed down the pipeline for accurate calculations like text centering.
      * **Sorting:** All extracted blocks within each page are rigorously sorted first by their vertical position (`top`), then by their horizontal position (`x0`), ensuring the `all_blocks` list accurately reflects the natural reading flow of the document. This meticulous sorting is vital for accurate contextual feature calculation in subsequent stages.
  * **Output:** Generates a JSON file (`[filename]_intermediate_blocks.json`) containing all extracted text blocks with their rich metadata. This file serves as the input for the next stage. Additionally, it returns a dictionary of `page_dimensions` to the calling `main.py` script for further use.

### 2\. Stage 2: Heading Classification (`pdf_utils/classify_headings.py`)

  * **Purpose:** This is the core intelligence component of the pipeline. It takes the detailed text blocks (and page dimensions) from Stage 1 and applies advanced analytical techniques to determine which blocks represent structural headings (H1, H2, H3, H4) and their respective hierarchical levels.
  * **Method:** Employs an enhanced heuristic system. This system incorporates **dynamic font size thresholds**, extracts **comprehensive contextual features**, and utilizes a **weighted scoring mechanism** to assign heading levels. Optional multilingual awareness is integrated via `spaCy`.
  * **Key Operations & Parameters:**
      * **Language Detection (Optional):** If the `xx_ent_wiki_sm` `spaCy` model is successfully loaded (requires offline installation), each text block is processed to detect its language (`lang` attribute). This enables more nuanced processing for specific scripts.
      * **Feature Calculation:** This function enriches each block with numerous intrinsic and contextual features:
          * **Intrinsic Features:** `text`, `font_size`, `is_bold`, `is_italic`, `x0`, `top`, `bottom`, `width`, `height`, `line_height`, `lang` (new), `font_size_ratio_to_common` (normalized font size), `font_size_deviation_from_common`. It also includes `is_all_caps` (adjusted for non-casing languages like Japanese), `line_length`, `num_words` (adjusted for non-space-delimited languages like Japanese to use character count), `starts_with_number_or_bullet` (using regex for common patterns), and `is_short_line` (adjusted based on `num_words`).
          * **Contextual Features:** `is_first_on_page`, `is_last_on_page`, `prev_font_size`, `next_font_size`, `prev_y_gap`, `next_y_gap`, `is_preceded_by_larger_gap`, `is_followed_by_larger_gap` (based on multiples of line height), `prev_x_diff`, `next_x_diff`, `is_followed_by_smaller_text`, and `is_centered` (accurately calculated using page dimensions from Stage 1).
      * **Dynamic Thresholding:** Automatically calculates and establishes specific font size cutoffs for H1-H4. This process analyzes the unique font size distribution within *the current PDF*, identifies the most common font size (likely body text), and then derives relative thresholds. This adaptability is crucial for handling diverse document designs where absolute font sizes for headings can vary widely.
      * **Weighted Heuristic Scoring (`classify_block_heuristic`):** This is the core decision-making logic.
          * It defines a set of **weights** for each individual feature (e.g., `is_bold` carries more weight than `is_all_caps`).
          * For each potential H-tag level (H1-H4), it calculates a composite "score" by summing the weights of all features present in the block that are indicative of that level. Higher-level headings (H1) demand higher scores and stricter feature combinations.
          * The block is classified into the H-tag level for which it achieves the highest score, *provided* that score also surpasses a predefined minimum confidence threshold for that specific level.
          * This weighted approach allows for **robustness to subtle design variations** and partial matches to heading patterns, as multiple contributing factors can collectively determine a classification, rather than relying on rigid, absolute boolean logic.
  * **Output:** Updates the `[filename]_intermediate_blocks.json` file in-place by adding a `"level"` attribute to all identified headings.

### 3\. Stage 3: Outline Structuring (`pdf_utils/structure_outline.py`)

  * **Purpose:** To extract the document's main title and construct the final flat outline in the specified JSON format.
  * **Method:** Filters the classified blocks from Stage 2 and applies advanced, multi-criteria heuristics for accurate title identification.
  * **Key Operations:**
      * **Title Extraction (`document_title`):** This function focuses exclusively on blocks from the *first page*. It implements a robust heuristic by:
          * Filtering for blocks with a `font_size_ratio_to_common` of at least `1.3` (30% larger than common text) and appropriate text length (not too short or too long).
          * Excluding blocks already classified as lower-level headings (H3, H4) unless no other strong candidates exist.
          * Sorting remaining candidates using multiple weighted criteria: `font_size` (descending, highest priority), `is_bold`, `is_centered` (leveraging page dimensions for accuracy), `top` position (ascending), and `is_preceded_by_larger_gap`. The text of the top-ranked block becomes the document title.
          * A fallback mechanism ensures a title is always provided, even if no strong candidates are found.
      * **Outline Filtering:** Initializes an empty `outline` list. It then iterates through all blocks (including non-headings), selecting only those with an assigned `level` of H1, H2, H3, or H4.
      * **Format Adherence:** For each selected heading, it constructs a dictionary containing only the `level`, `text`, and `page` number, precisely matching the required output JSON format. These are appended to the `outline` list.
  * **Output:** Generates the final JSON file (`[filename].json`) containing the document's title and its structured outline, saved to the `outputs` directory.

### 4\. Stage 4: Outline Generation (`pdf_utils/generate_outline.py`)

  * **Purpose:** Serves as a final confirmation point for the pipeline's successful execution.
  * **Method:** Currently a minimalist placeholder function.
  * **Potential Enhancements:** This stage can be extended in future iterations for advanced logging, integrating with notification systems, or triggering subsequent automated processes like converting the JSON output to other formats (e.g., Markdown, HTML) or pushing it to a database.

-----

### Analysis of Constraints Compliance

The solution has been rigorously designed to adhere to all defined project constraints:

1.  **Execution Time ($\\le$ 10 seconds for a 50-page PDF):**

      * The pipeline's performance is optimized through efficient `pdfminer.six` extraction and a CPU-friendly, heuristic-based classification approach that avoids computationally intensive large Machine Learning models.
      * JSON parsing and file I/O operations are inherently fast.
      * **Expected Performance:** For a 50-page PDF, typical processing time is estimated to be **3-7 seconds** on the specified hardware (8 CPUs, 16 GB RAM).
      * **Compliance Status:** **Compliant.**

2.  **Model Size ($\\le$ 200MB if used):**

      * The core heuristic logic itself has a **\~0MB** custom model footprint.
      * The optional `scikit-learn` ML model (if trained and integrated via `heading_classifier.pkl` and a `TfidfVectorizer.pkl`) is estimated to have a combined file size of **15-25MB**, comfortably within the 200MB limit.
      * The `spaCy` `xx_ent_wiki_sm` model, integrated for multilingual support, is approximately **10MB**.
      * **Total Library Size:** The full Python environment, including all required libraries (`scikit-learn`, `numpy`, `scipy`, `pandas`, `pdfminer.six`, `spaCy`), is estimated to be around **300-400MB** when installed. This figure represents the collective size of the installed external libraries, not the custom trained models specifically referenced by the constraint.
      * **Compliance Status:** **Fully compliant** regarding the specific "Model size" constraint for custom models.

3.  **Network (No internet access allowed):**

      * All dependencies are managed offline. The `spaCy` model, if used, is expected to be pre-installed within the Docker image from a local `.whl` file.
      * The code makes no external API calls or network requests during execution.
      * **Compliance Status:** **Fully compliant.**

4.  **Runtime (CPU: amd64 (x86\_64), 8 CPUs, 16 GB RAM, No GPU dependencies):**

      * The entire codebase is implemented in pure Python, optimized for CPU-bound operations, and is fully compatible with AMD64 architecture.
      * No GPU-specific libraries or dependencies are utilized.
      * The provided system resources (8 CPUs, 16 GB RAM) are highly sufficient for the computational demands of the pipeline.
      * **Expected Memory Usage:** Peak memory usage is estimated to be **\<500MB** for a 50-page PDF.
      * **Compliance Status:** **Fully compliant.**

-----
