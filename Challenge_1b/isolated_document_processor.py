#!/usr/bin/env python3
"""
Isolated Document Processor - handles PDF processing in isolated contexts
to avoid document closure issues.
"""
import fitz  # PyMuPDF
import pytesseract
from typing import List, Dict, Any, Tuple
import re
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IsolatedDocumentProcessor:
    """Processes PDF documents with isolated context handling."""
    
    def __init__(self, use_ocr: bool = True):
        """
        Initialize the isolated document processor.
        
        Args:
            use_ocr: Whether to use OCR for image-based text extraction
        """
        self.use_ocr = use_ocr
        
        # Define comprehensive regex patterns for section identification
        self.section_patterns = [
            r'^(?:\d+\.)+\s+(.+)$',  # Numbered sections like "1.2.3 Section Title"
            r'^(?:[A-Z][a-z]+\s*)+:',  # Title case followed by colon
            r'^[A-Z\s]{5,}$',         # All caps titles
            r'^Chapter\s+\d+',        # Chapter headings
            r'^Section\s+\d+',        # Section headings
            r'^Part\s+[IVX]+',        # Roman numeral parts
            r'^\d+\.\s+[A-Z]',        # Simple numbered sections
            r'^[A-Z][^.!?]*[A-Z]$',   # Multi-word titles ending with caps
        ]
        self.compiled_patterns = [re.compile(pattern, re.MULTILINE) for pattern in self.section_patterns]
        
        # Patterns for common document elements to skip
        self.skip_patterns = [
            r'^\s*page\s+\d+\s*$',    # Page numbers
            r'^\s*\d+\s*$',           # Standalone numbers
            r'^\s*©.*$',              # Copyright notices
            r'^\s*\.\.\.\s*$',        # Ellipsis
        ]
        self.skip_compiled = [re.compile(pattern, re.IGNORECASE) for pattern in self.skip_patterns]

    def process_single_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Process a single PDF in complete isolation.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary containing document structure and content
        """
        doc_name = Path(pdf_path).name
        
        try:
            # Open document in isolated context
            with fitz.open(pdf_path) as doc:
                logger.info(f"Processing {doc_name} with {doc.page_count} pages")
                
                sections = []
                current_section = None
                total_text_length = 0
                page_count = doc.page_count
                
                # Extract all content first
                for page_num in range(page_count):
                    try:
                        page = doc[page_num]
                        
                        # Try text extraction first
                        text = page.get_text()
                        
                        # If text is empty or very short, try OCR if enabled
                        if self.use_ocr and (not text.strip() or len(text.strip()) < 50):
                            try:
                                # Get page as image and apply OCR
                                pix = page.get_pixmap()
                                img_data = pix.tobytes("png")
                                ocr_text = pytesseract.image_to_string(img_data)
                                if len(ocr_text.strip()) > len(text.strip()):
                                    text = ocr_text
                                    logger.debug(f"Used OCR for page {page_num + 1} of {doc_name}")
                            except Exception as ocr_e:
                                logger.debug(f"OCR failed for page {page_num + 1} of {doc_name}: {ocr_e}")
                        
                        # Skip empty pages
                        if not text.strip():
                            continue
                        
                        total_text_length += len(text)
                        
                        # Clean the text
                        text = self._clean_text(text)
                        
                        # Extract sections from page
                        page_sections = self._extract_sections(text, page_num)
                        
                        if page_sections:
                            sections.extend(page_sections)
                            current_section = page_sections[-1]  # Update current section
                        elif current_section:
                            # Append text to the current section if no new sections found
                            current_section["content"] += "\n" + text
                        else:
                            # Create a default section if we haven't found any yet
                            current_section = {
                                "title": f"Page {page_num + 1}",
                                "page_number": page_num + 1,
                                "content": text
                            }
                            sections.append(current_section)
                    
                    except Exception as page_e:
                        logger.warning(f"Error processing page {page_num + 1} of {doc_name}: {page_e}")
                        continue
                
                # Post-process sections
                sections = self._post_process_sections(sections)
                
                # If no meaningful sections found, create one big section
                if not sections and total_text_length > 0:
                    # Extract all text as one section
                    all_text = ""
                    for page_num in range(min(page_count, 10)):  # Limit to first 10 pages
                        try:
                            page = doc[page_num]
                            text = page.get_text()
                            if text.strip():
                                all_text += text + "\n"
                        except:
                            continue
                    
                    if all_text.strip():
                        sections = [{
                            "title": f"Full Document: {doc_name}",
                            "page_number": 1,
                            "content": self._clean_text(all_text)
                        }]
                
                logger.info(f"Successfully processed {doc_name} with {len(sections)} sections")
                
                return {
                    "filename": doc_name,
                    "path": pdf_path,
                    "pages": page_count,
                    "sections": sections,
                    "total_text_length": total_text_length
                }
        
        except Exception as e:
            logger.error(f"Error processing {doc_name}: {e}")
            return self._fallback_processing(pdf_path)
    
    def _fallback_processing(self, pdf_path: str) -> Dict[str, Any]:
        """
        Fallback processing for difficult PDFs.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary containing basic document info
        """
        doc_name = Path(pdf_path).name
        
        try:
            logger.info(f"Trying fallback processing for {doc_name}")
            
            # Simple text extraction without complex processing
            doc = fitz.open(pdf_path)
            all_text = ""
            page_count = doc.page_count
            
            # Extract text from first few pages only
            for page_num in range(min(page_count, 5)):
                try:
                    page = doc[page_num]
                    text = page.get_text()
                    if text.strip():
                        all_text += f"Page {page_num + 1}:\n{text}\n\n"
                except:
                    continue
            
            doc.close()
            
            if all_text.strip():
                logger.info(f"Fallback processing successful for {doc_name}")
                return {
                    "filename": doc_name,
                    "path": pdf_path,
                    "pages": page_count,
                    "sections": [{
                        "title": f"Content from {doc_name}",
                        "page_number": 1,
                        "content": all_text[:3000]  # Limit content length
                    }],
                    "total_text_length": len(all_text)
                }
        
        except Exception as e:
            logger.error(f"Fallback processing failed for {doc_name}: {e}")
        
        return None
    
    def process_documents(self, pdf_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Process multiple PDF documents.
        
        Args:
            pdf_paths: List of paths to PDF files
            
        Returns:
            List of processed document dictionaries
        """
        processed_docs = []
        
        for pdf_path in pdf_paths:
            logger.info(f"Processing document: {Path(pdf_path).name}")
            
            # Process each document in isolation
            doc_dict = self.process_single_pdf(pdf_path)
            
            if doc_dict and doc_dict.get("sections"):
                processed_docs.append(doc_dict)
                logger.info(f"✅ Successfully processed {doc_dict['filename']} with {len(doc_dict['sections'])} sections")
            else:
                logger.warning(f"❌ No content extracted from {Path(pdf_path).name}")
        
        logger.info(f"📊 Processed {len(processed_docs)} documents successfully out of {len(pdf_paths)} total")
        return processed_docs
    
    def _clean_text(self, text: str) -> str:
        """
        Clean extracted text by removing unwanted elements.
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove page numbers and common footers/headers
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Skip lines that match skip patterns
            if any(pattern.match(line) for pattern in self.skip_compiled):
                continue
                
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()
    
    def _extract_sections(self, text: str, page_num: int) -> List[Dict[str, Any]]:
        """
        Extract sections from page text.
        
        Args:
            text: Page text content
            page_num: Page number (0-indexed)
            
        Returns:
            List of section dictionaries
        """
        sections = []
        lines = text.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Check if line matches any section pattern
            section_title = self._is_section_title(line)
            if section_title:
                # Start a new section
                section_content = []
                i += 1
                
                # Collect content until the next section or end
                while i < len(lines) and not self._is_section_title(lines[i].strip()):
                    section_content.append(lines[i])
                    i += 1
                
                sections.append({
                    "title": section_title,
                    "page_number": page_num + 1,
                    "content": "\n".join(section_content)
                })
                
                # Don't increment i here as we need to process the new line
            else:
                i += 1
        
        return sections
    
    def _is_section_title(self, line: str) -> str:
        """
        Check if a line is a section title.
        
        Args:
            line: Text line to check
            
        Returns:
            Section title if matched, else None
        """
        if not line:
            return None
            
        # Check if line matches any section pattern
        for pattern in self.compiled_patterns:
            match = pattern.search(line)
            if match:
                return line
                
        # Check for other section indicators
        if len(line) < 100 and line.strip() and any(c.isupper() for c in line):
            if line.endswith(':') or line.isupper() or line[0].isupper():
                return line
                
        return None
    
    def _post_process_sections(self, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Post-process sections to improve quality.
        
        Args:
            sections: List of section dictionaries
            
        Returns:
            Processed sections
        """
        processed_sections = []
        
        for section in sections:
            # Skip very short sections
            if len(section["content"].strip()) < 50:
                continue
            
            # Clean section title
            title = section["title"].strip()
            if not title or title == "Untitled":
                # Try to extract title from first line of content
                content_lines = section["content"].strip().split('\n')
                if content_lines:
                    first_line = content_lines[0].strip()
                    if len(first_line) < 100 and len(first_line) > 5:
                        title = first_line
                        # Remove first line from content
                        section["content"] = '\n'.join(content_lines[1:])
            
            section["title"] = title
            
            # Ensure content is not empty after processing
            if section["content"].strip():
                processed_sections.append(section)
        
        return processed_sections

if __name__ == "__main__":
    # Test the isolated processor
    processor = IsolatedDocumentProcessor()
    print("Isolated Document Processor ready for testing")
