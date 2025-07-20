import json
import os
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTTextBox, LTTextLine, LTChar, LTFigure

def extract_text_blocks_pdfminer(pdf_path):
    """
    Extracts text blocks with detailed metadata using pdfminer.six.
    Groups LTChar objects into logical text lines/blocks.
    Returns the list of blocks and a dictionary of page dimensions (mediabox).
    """
    rsrcmgr = PDFResourceManager()
    laparams = LAParams(line_overlap=0.5, char_margin=2.0, word_margin=0.1, line_margin=0.5, boxes_flow=0.5, detect_vertical=False, all_texts=True)
    device = PDFPageAggregator(rsrcmgr, laparams=laparams)
    interpreter = PDFPageInterpreter(rsrcmgr, device)

    all_blocks = []
    page_dimensions = {} # Stores {page_num: (width, height)}

    with open(pdf_path, 'rb') as fp:
        for page_num, page in enumerate(PDFPage.get_pages(fp), start=1):
            interpreter.process_page(page)
            layout = device.get_result()

            # Store page dimensions (mediabox gives the physical size)
            # mediabox is (x0, y0, x1, y1)
            page_width = page.mediabox[2] - page.mediabox[0]
            page_height = page.mediabox[3] - page.mediabox[1]
            page_dimensions[page_num] = {"width": page_width, "height": page_height}


            page_blocks = [] # To store blocks for the current page

            def parse_obj(lt_obj):
                """Recursively parses layout objects."""
                if isinstance(lt_obj, LTTextLine):
                    line_chars = []
                    x0_min = float('inf')
                    y0_min = float('inf')
                    x1_max = float('-inf')
                    y1_max = float('-inf')
                    font_sizes = []
                    font_names = []
                    is_bold_flags = []
                    is_italic_flags = []

                    for char in lt_obj:
                        if isinstance(char, LTChar):
                            line_chars.append(char.get_text())
                            x0_min = min(x0_min, char.bbox[0])
                            y0_min = min(y0_min, char.bbox[1])
                            x1_max = max(x1_max, char.bbox[2])
                            y1_max = max(y1_max, char.bbox[3])
                            font_sizes.append(char.size)
                            font_names.append(char.fontname)

                            font_name_lower = char.fontname.lower()
                            is_bold_flags.append("bold" in font_name_lower or "bd" in font_name_lower or "heavy" in font_name_lower)
                            is_italic_flags.append("italic" in font_name_lower or "it" in font_name_lower)

                    text = "".join(line_chars).strip()
                    if not text:
                        return

                    avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 0
                    most_common_font_name = max(set(font_names), key=font_names.count) if font_names else "Unknown"

                    is_bold_line = any(is_bold_flags)
                    is_italic_line = any(is_italic_flags)

                    page_blocks.append({
                        "text": text,
                        "font_size": avg_font_size,
                        "font_name": most_common_font_name,
                        "x0": x0_min,
                        "top": page_height - y1_max, # Convert to top-down for consistency
                        "bottom": page_height - y0_min, # Convert to top-down
                        "width": x1_max - x0_min,
                        "height": y1_max - y0_min, # Line height
                        "page": page_num,
                        "is_bold": is_bold_line,
                        "is_italic": is_italic_line,
                        "line_height": y1_max - y0_min
                    })
                elif isinstance(lt_obj, (LTTextBox, LTFigure)):
                    for obj in lt_obj:
                        parse_obj(obj) # Recursively parse children

            for obj in layout:
                parse_obj(obj)

            page_blocks.sort(key=lambda b: (b["top"], b["x0"]))
            all_blocks.extend(page_blocks)

    return all_blocks, page_dimensions

def run(pdf_path, output_path):
    """
    Main function to run the block extraction process using pdfminer.six.
    Returns the list of blocks and page dimensions.
    """
    try:
        all_blocks, page_dimensions = extract_text_blocks_pdfminer(pdf_path)
    except Exception as e:
        raise RuntimeError(f"Error during PDFMiner.six extraction from {pdf_path}: {e}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_blocks, f, indent=2)
    except IOError as e:
        raise RuntimeError(f"Error writing intermediate blocks to {output_path}: {e}")
    
    return all_blocks, page_dimensions