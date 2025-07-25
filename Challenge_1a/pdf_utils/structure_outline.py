import json
import os
import statistics
import re
import collections
from operator import itemgetter
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import spacy # Import spacy for type hinting nlp_model

# --- Constants and Configuration ---
# Title Derivation
MIN_TITLE_WORDS = 2
MAX_TITLE_WORDS = 7 # General for English, will be interpreted as characters for CJK
MIN_TITLE_SCORE_THRESHOLD = 3
FILENAME_SIMILARITY_BOOST = 10 # Strong boost for semantic similarity with filename
FONT_SIZE_BOOST_TITLE = 10 # Strong weight for larger font sizes
POSITION_BOOST_TITLE = 5 # Moderate weight for earlier appearance
KEYWORD_MATCH_BOOST_TITLE = 7 # Boost for matching specific PDF title keywords
MIN_RELATABILITY_FOR_KEYWORD_BOOST = 0.4 # Minimum filename similarity for keyword boost

# Outline Pruning
DEFAULT_MEDIAN_FONT_SIZE = 12.0 # Fallback font size if none found
MIN_HEADINGS_PER_PAGE = 2
MAX_HEADINGS_PER_PAGE = 2
MAX_HEADINGS_FACTOR_SMALL_DOC = 5 # Up to 5x pages for small docs (<5 pages)
MAX_HEADINGS_FACTOR_LARGE_DOC = 3.5 # Up to 3.5x pages for large docs (>=5 pages)
OUTLINE_TEXT_TRUNCATION_WORDS = 5 # Words to keep for outline display (will be characters for CJK)


# --- Script-specific Regexes for Character Detection (Copied from classify_headings.py) ---
CJK_CHARS_REGEX = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\uFF00-\uFFEF]')
CYRILLIC_CHARS_REGEX = re.compile(r'[\u0400-\u04FF]')
ARABIC_CHARS_REGEX = re.compile(r'[\u0600-\u06FF]')
DEVANAGARI_CHARS_REGEX = re.compile(r'[\u0900-\u097F]')
LATIN_CHARS_REGEX = re.compile(r'[a-zA-Z]') # General Latin (for checking if a language is *not* primarily Latin)

# --- Script-specific Regexes for Character Detection ---
# CJK UNICODE RANGES (Hiragana, Katakana, CJK Unified Ideographs, Full-width ASCII/Punctuation)
CJK_CHARS_REGEX = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\uFF00-\uFFEF]')
# Cyrillic (Russian)
CYRILLIC_CHARS_REGEX = re.compile(r'[\u0400-\u04FF]')
# Arabic
ARABIC_CHARS_REGEX = re.compile(r'[\u0600-\u06FF]')
# Devanagari (Hindi)
DEVANAGARI_CHARS_REGEX = re.compile(r'[\u0900-\u097F]')
# General Latin (for checking if a language is *not* primarily Latin)
LATIN_CHARS_REGEX = re.compile(r'[a-zA-Z]')


# --- PDF Title Keywords Dictionary ---
# (As provided in your prompt. Note: these are primarily English keywords)
PDF_TITLE_KEYWORDS = {
    "document_types": [
        "report", "proposal", "plan", "policy", "manual", "agreement", "contract", "agenda",
        "summary", "presentation", "study", "research", "brochure", "flyer", "newsletter",
        "requirements", "tender", "rfp", "statement", "certificate", "form", "guide",
        "journal", "abstract", "review", "catalogue", "directory", "code", "statute",
        "notice", "thesis", "paper", "article", "analysis", "audit", "inspection",
        "appendix", "chapter", "section", "volume", "issue", "edition", "version",
        "update", "draft", "sample", "test", "faq", "help","Application"
    ],
    "common_terms": [
        "annual", "final", "draft", "version", "update", "review", "analysis", "strategy",
        "project", "solution", "system", "management", "business", "technical", "financial",
        "marketing", "sales", "development", "innovation", "technology", "security", "data",
        "cloud", "software", "hardware", "service", "product", "customer", "employee",
        "training", "education", "performance", "evaluation", "metrics", "dashboard",
        "compliance", "risk", "privacy", "summary", "plan", "implementation", "future",
        "vision", "mission", "objectives", "results", "impact", "challenge", "trend",
        "recommendation", "solution", "method", "practice", "faq", "issue", "problem",
        "resolution", "fix", "patch", "error", "status", "progress", "deadline", "schedule",
        "timeline", "phase", "process", "workflow", "policy", "law", "code", "document",
        "file", "archive", "system", "application", "api", "framework", "library",
        "module", "feature", "configuration", "input", "output", "feedback", "comment",
        "conclusion", "introduction", "background", "purpose", "scope", "definition",
        "references", "appendix", "table", "figure", "chart", "diagram", "image", "map",
        "plan", "model", "example", "sample", "test", "validation", "review", "pilot",
        "trial", "beta", "alpha"
    ],
    "legal_financial": [
        "terms", "statement", "invoice", "audit", "compliance", "regulation", "legal",
        "tax", "financial", "budget", "profit", "loss", "revenue", "cost", "asset",
        "liability", "equity", "debt", "capital", "shares", "stock", "bond", "security",
        "valuation", "assessment", "filing", "declaration", "credit", "debit",
        "transaction", "payment", "loan", "insurance", "claim", "benefit", "pension",
        "retirement", "estate", "litigation", "settlement", "judgment", "contract",
        "property", "trademark", "copyright", "patent", "licensing", "warranty",
        "liability", "jurisdiction", "confidentiality", "privacy policy"
    ],
    "academic_research": [
        "thesis", "dissertation", "paper", "journal", "abstract", "chapter", "appendix",
        "introduction", "conclusion", "results", "discussion", "bibliography", "citation",
        "experiment", "study", "research", "analysis", "findings", "theory", "model",
        "framework", "survey", "algorithm", "design", "evaluation", "validation",
        "proof", "definition", "problem", "solution", "example", "figure", "table",
        "chart", "diagram", "references", "review", "overview", "summary", "guide",
        "manual", "textbook"
    ],
    "marketing_sales": [
        "brochure", "flyer", "catalog", "campaign", "promotion", "advertisement", "marketing",
        "sales", "pitch", "presentation", "strategy", "plan", "branding", "conversion",
        "customer", "roi", "metrics", "dashboard", "performance", "report", "analysis",
        "trends", "opportunity", "threat", "strength", "marketing plan", "content strategy",
        "press release"
    ],
    "hr_corporate": [
        "onboarding", "employee handbook", "hr policy", "training", "development", "learning",
        "performance review", "feedback", "compensation", "benefits", "recruitment", "hiring",
        "interview", "job description", "career", "talent management", "employee engagement",
        "workplace culture", "health and safety", "security protocol", "crisis management",
        "meeting notes", "minutes", "board meeting", "annual report", "corporate governance",
        "csr", "sustainability report", "ethics policy"
    ],
    "technical_it": [
        "api", "sdk", "documentation", "user guide", "installation", "configuration",
        "troubleshooting", "release notes", "system design", "architecture", "security",
        "database", "code", "workflow", "specifications", "test plan", "test results",
        "qa report", "performance", "security audit", "incident response", "disaster recovery",
        "cloud", "devops", "automation"
    ]
}


# Regex for common patterns that are likely noise when standalone in a title context
_TITLE_REJECT_PATTERNS = [
    re.compile(r'^(https?://|www\.)\S+\.\S+(\/\S*)?$', re.IGNORECASE), # URLs
    re.compile(r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$|^\d{4}[/-]\d{1,2}[/-]\d{1,2}$|^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2},?\s+\d{2,4}$', re.IGNORECASE), # Dates
    re.compile(r'^\d{1,2}:\d{2}(:\d{2})?(?:\s*(?:am|pm))?$', re.IGNORECASE), # Times
    re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'), # Email IDs
    re.compile(r'^\s*(Page|Table|Figure)\s+\d+(\.\d+)?', re.IGNORECASE), # Page/Table/Figure indicators
    re.compile(r'^\s*([A-Z]\.?){2,}', re.IGNORECASE), # All caps acronyms (e.g., "U.S.A.")
    re.compile(r'(\b\w+\b\s*){2,}\1', re.IGNORECASE), # Repetitive words (e.g., "RFP RFP RFP")
    re.compile(r'^[\d\W_]+$'), # Purely numbers/symbols
]

# Helper for bracket matching (including CJK)
def _has_unclosed_brackets(text: str) -> bool:
    """Checks for unclosed parentheses/brackets, including CJK variants."""
    stack = []
    mapping = {")": "(", "]": "[", "}": "{",
               "）": "（", "】": "【", "」": "「", "』": "『"}
    for char in text:
        if char in mapping.values():
            stack.append(char)
        elif char in mapping:
            if not stack or stack.pop() != mapping[char]:
                return True # Mismatched closing bracket
    return len(stack) > 0 # Unclosed opening brackets


def _has_script_chars(text: str, script_regex: re.Pattern) -> bool:
    """Checks if the text contains characters from the given script regex."""
    return bool(script_regex.search(text))

def _get_predominant_script_type(text: str) -> str:
    """
    Determines the predominant script type of a text block based on character presence.
    This is a quick heuristic, not a full script detection.
    Returns 'latin', 'cjk', 'cyrillic', 'arabic', 'devanagari', or 'other'.
    """
    # Order matters here: CJK first because it might contain Latin digits/punctuation
    if _has_script_chars(text, CJK_CHARS_REGEX): return 'cjk'
    if _has_script_chars(text, LATIN_CHARS_REGEX): return 'latin'
    if _has_script_chars(text, CYRILLIC_CHARS_REGEX): return 'cyrillic'
    if _has_script_chars(text, ARABIC_CHARS_REGEX): return 'arabic'
    if _has_script_chars(text, DEVANAGARI_CHARS_REGEX): return 'devanagari'
    return 'other'


def _text_contains_title_keywords(text: str) -> bool:
    """Checks if the text contains any of the predefined PDF title keywords (currently English)."""
    lower_text = text.lower()
    for category_list in PDF_TITLE_KEYWORDS.values():
        for keyword in category_list:
            # Use word boundaries to avoid partial matches (e.g., "prop" in "property")
            # re.escape is critical for keywords like "q&a", "rfi"
            if re.search(r'\b' + re.escape(keyword) + r'\b', lower_text):
                return True
    return False

def _find_visual_title_candidates(blocks: List[Dict[str, Any]], detected_lang: str) -> List[Dict[str, Any]]:
    """
    Find candidate word bodies based on visual and positional parameters.
    """
    if not blocks:
        return []
    
    candidates = []
    
    # Calculate font statistics
    font_sizes = [b.get("font_size", 12) for b in blocks if b.get("font_size", 0) > 0]
    if not font_sizes:
        font_sizes = [12.0]
    
    max_font_size = max(font_sizes)
    avg_font_size = sum(font_sizes) / len(font_sizes)
    
    for block in blocks:
        text = block.get("text", "").strip()
        if not text or len(text) < 3:
            continue
        
        font_size = block.get("font_size", avg_font_size)
        page = block.get("page", 0)
        top = block.get("top", 0)
        is_bold = block.get("is_bold", False)
        
        # Visual/Positional scoring
        score = 0
        
        # Font size factor (most important visual cue)
        if font_size >= max_font_size * 0.9:  # Top 10% font sizes
            score += 50
        elif font_size >= avg_font_size * 1.3:  # 30% above average
            score += 30
        elif font_size >= avg_font_size * 1.1:  # 10% above average
            score += 15
        
        # Bold formatting bonus
        if is_bold:
            score += 20
        
        # Position bonus (earlier = better for titles)
        if page == 0:
            if top < 150:  # Top 20% of first page
                score += 40
            elif top < 300:  # Top 40% of first page  
                score += 25
            else:
                score += 10
        elif page == 1:
            score += 5  # Small bonus for second page
        
        # Length considerations (not too short, not too long)
        is_cjk = detected_lang in ["zh", "ja", "ko"]
        text_length = len(text) if is_cjk else len(text.split())
        
        if is_cjk:
            if 6 <= text_length <= 30:  # Good CJK title length
                score += 15
            elif text_length < 4:  # Too short
                score -= 20
        else:
            if 2 <= text_length <= 10:  # Good English title length
                score += 15
            elif text_length < 2:  # Too short
                score -= 20
        
        candidates.append({
            'text': text,
            'score': score,
            'font_size': font_size,
            'page': page,
            'position': top,
            'is_bold': is_bold,
            'block': block
        })
    
    # Return candidates sorted by score
    return sorted(candidates, key=lambda x: x['score'], reverse=True)

def _calculate_heading_relatability(title_text: str, heading_blocks: List[Dict[str, Any]], detected_lang: str) -> float:
    """
    Calculate how related the title text is to the document headings (English only).
    """
    if detected_lang not in ["en"] or not heading_blocks:
        return 0.0  # Skip for non-English documents
    
    title_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', title_text.lower()))
    if not title_words:
        return 0.0
    
    # Extract words from all headings
    all_heading_words = set()
    for heading in heading_blocks:
        heading_text = heading.get('text', '')
        heading_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', heading_text.lower()))
        all_heading_words.update(heading_words)
    
    if not all_heading_words:
        return 0.0
    
    # Calculate overlap
    common_words = title_words.intersection(all_heading_words)
    if not common_words:
        return 0.0
    
    # Relatability score (Jaccard similarity)
    union_words = title_words.union(all_heading_words)
    relatability = len(common_words) / len(union_words)
    
    return relatability

def _is_gibberish_text(text: str, detected_lang: str) -> bool:
    """
    Eliminate gibberish text bodies using language-aware criteria.
    """
    text = text.strip()
    
    if len(text) < 3:
        return True
    
    is_cjk = detected_lang in ["zh", "ja", "ko"]
    
    if is_cjk:
        # For CJK languages - simpler gibberish detection
        # Reject very short or obviously bad patterns
        if len(text) < 4:
            return True
        
        # Patterns that are clearly gibberish for CJK
        cjk_gibberish_patterns = [
            r'^\d+\s*[:：]\s*\d+$',  # "2: 5"
            r'^\d+\.\d+$',  # Decimal numbers
            r'^[^\w\s]*$',  # Only symbols
            r'^[a-zA-Z]{1,3}$',  # Very short Latin abbreviations
        ]
        
        for pattern in cjk_gibberish_patterns:
            if re.match(pattern, text):
                return True
        
        return False
    
    # For English and other Latin-based languages
    # Check for meaningful words
    words = re.findall(r'\b[a-zA-Z]{2,}\b', text)
    if len(words) == 0:
        return True
    
    # Check for addresses and location patterns
    address_patterns = [
        r'\b\d{5}(-\d{4})?\b',  # ZIP codes like "37863" or "12345-6789"
        r'\b[A-Z]{2}\s+\d{5}\b',  # State + ZIP like "TN 37863"
        r'\b\w+,\s*[A-Z]{2}\s+\d{5}\b',  # City, State ZIP like "PIGEON FORGE, TN 37863"
        r'^\d+\s+[A-Z\s]+\b(ST|STREET|AVE|AVENUE|RD|ROAD|BLVD|BOULEVARD|DR|DRIVE|LN|LANE|CT|COURT)\b',  # Street addresses
        r'^\b(PO|P\.O\.)\s+BOX\s+\d+\b',  # PO Box addresses
    ]
    
    for pattern in address_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    # Check if mostly numbers/symbols
    alpha_chars = len(re.findall(r'[a-zA-Z]', text))
    total_chars = len(text.replace(' ', ''))
    if alpha_chars / max(total_chars, 1) < 0.5:  # Less than 50% alphabetic
        return True
    
    # Check for repetitive patterns
    if re.search(r'(\b\w+\b)\s*[:\-]\s*\1', text, re.IGNORECASE):  # "RFP: RFP"
        return True
    
    # Check for very short fragments after colons/dashes (like "RFP: R")
    if re.search(r'\b\w+\s*[:]\s*\b\w{1,2}\b\s*$', text, re.IGNORECASE):  # "RFP: R" or "ABC: XY"
        return True
    
    # Check for incomplete text with ellipsis or truncation indicators
    if re.search(r'\.\.\.|…|\b\w+\s+or\s*\.\.\.?\s*$', text, re.IGNORECASE):  # "word or..."
        return True
    
    # Check average word length (gibberish often has very short "words")
    if words:
        avg_word_length = sum(len(word) for word in words) / len(words)
        if avg_word_length < 2.5:  # Very short average word length
            return True
    
    return False

def _select_optimal_title(candidates: List[Dict[str, Any]], filename: str, detected_lang: str) -> str:
    """
    Select the most optimal title considering keywords, font, relatability, etc.
    """
    if not candidates:
        return _extract_title_from_filename(filename, detected_lang)
    
    # Enhanced scoring for final selection
    for candidate in candidates:
        text = candidate['text']
        
        # Start with visual score
        final_score = candidate['score']
        
        # Keyword presence bonus (English only) - increased by 20%
        if detected_lang == "en":
            if _text_contains_title_keywords(text):
                final_score += 36
        
        # Heading relatability bonus (English only)
        relatability = candidate.get('heading_relatability', 0)
        final_score += relatability * 25  # Up to 25 point bonus
        
        # Font size bonus (already partially included, but emphasize)
        font_factor = candidate['font_size'] / 12.0  # Normalize to 12pt
        final_score += min(font_factor * 10, 20)  # Up to 20 point bonus
        
        # Position bonus (refined)
        if candidate['page'] == 0 and candidate['position'] < 100:
            final_score += 15  # Very top of first page
        
        # Completeness bonus
        if _looks_complete_title(text):
            final_score += 10
        
        candidate['final_score'] = final_score
    
    # Sort by final score and select best
    best_candidate = max(candidates, key=lambda x: x['final_score'])
    
    # Normalize and return the best title
    return _normalize_title_text(best_candidate['text'])

def derive_title_from_sampled_text_and_filename(sampled_raw_blocks: List[Dict[str, Any]], 
                                                 pdf_filename_base: str, 
                                                 nlp_model: Optional[Any] = None, 
                                                 detected_lang: str = "en") -> str:
    """
    Streamlined title derivation using visual/positional parameters, heading relatability, 
    and optimal selection criteria.
    """
    if not sampled_raw_blocks:
        return _extract_title_from_filename(pdf_filename_base, detected_lang)
    
    # Step 1: Define search scope (first 3 pages OR 20% of document - whichever is shorter)
    total_pages = max([b.get('page', 0) for b in sampled_raw_blocks]) + 1
    search_pages = min(3, max(1, int(total_pages * 0.2)))
    
    candidate_blocks = [b for b in sampled_raw_blocks if b.get('page', 0) < search_pages]
    
    print(f"    Title search: analyzing first {search_pages} pages ({len(candidate_blocks)} blocks)")
    
    # Step 2: Find candidate word bodies based on visual/positional parameters
    title_candidates = _find_visual_title_candidates(candidate_blocks, detected_lang)
    
    if not title_candidates:
        return _extract_title_from_filename(pdf_filename_base, detected_lang)
    
    # Step 3: Check relatability with headings (English only)
    heading_blocks = [b for b in sampled_raw_blocks if b.get("level") and b["level"].startswith("H")]
    for candidate in title_candidates:
        candidate['heading_relatability'] = _calculate_heading_relatability(
            candidate['text'], heading_blocks, detected_lang)
    
    # Step 4: Eliminate gibberish text bodies
    meaningful_candidates = []
    for candidate in title_candidates:
        if not _is_gibberish_text(candidate['text'], detected_lang):
            meaningful_candidates.append(candidate)
    
    print(f"    Found {len(meaningful_candidates)} meaningful title candidates")
    
    if not meaningful_candidates:
        return _extract_title_from_filename(pdf_filename_base, detected_lang)
    
    # Step 5: Select optimal title considering all factors
    best_title = _select_optimal_title(meaningful_candidates, pdf_filename_base, detected_lang)
    
    print(f"    Selected title: \"{best_title}\"")
    return best_title

def _extract_title_from_filename(filename: str, detected_lang: str = "en") -> str:
    """Extract a meaningful title from the PDF filename - enhanced to avoid gibberish and handle non-English."""
    # Remove file extension
    name = os.path.splitext(filename)[0] if '.' in filename else filename
    
    is_cjk = detected_lang in ["zh", "ja", "ko"]
    
    # Handle common filename patterns
    if re.match(r'^[A-Z0-9_-]+$', name):  # All caps/numbers like "E0H1CM114"
        # Try to break into meaningful parts
        parts = re.findall(r'[A-Z][a-z]*|\d+', name)
        if len(parts) > 1:
            title_candidate = ' '.join(parts)
            # Check if the result is meaningful
            if _is_meaningful_title_text(title_candidate, detected_lang):
                return title_candidate
        
        # If filename is just a code, return a generic but meaningful title
        if is_cjk:
            return "文書 " + name if len(name) < 15 else "文書"  # "Document" in Japanese
        else:
            return "Document " + name if len(name) < 15 else "Document"
    
    # Replace underscores and dashes with spaces
    name = re.sub(r'[_-]+', ' ', name)
    
    # Remove excessive whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    
    # Check if the processed name is meaningful
    if _is_meaningful_title_text(name, detected_lang):
        # For non-CJK, capitalize first letter of each word
        if not is_cjk:
            return ' '.join(word.capitalize() for word in name.split())
        else:
            return name  # Keep CJK text as-is
    
    # If filename doesn't contain meaningful words, return generic title
    if is_cjk:
        return "文書" if not name else "無題文書"  # "Document" or "Untitled Document" in Japanese
    else:
        return "Document" if not name else "Untitled Document"

def _is_obviously_not_title(text: str, detected_lang: str = "en") -> bool:
    """Check if text is obviously not a title - language-aware version."""
    text = text.strip()
    
    # Too short or too long
    if len(text) < 3 or len(text) > 200:
        return True
    
    is_cjk = detected_lang in ["zh", "ja", "ko"]
    
    if is_cjk:
        # For CJK languages, use different criteria
        # Reject very short fragments
        if len(text) < 4:
            return True
            
        # Reject obvious non-title patterns for CJK
        cjk_non_title_patterns = [
            r'^\d+$',  # Just numbers
            r'^\d+\s*[:：]\s*\d+$',  # Number patterns like "2: 5"
            r'^[^\w\s]*$',  # Only symbols
            r'^[a-zA-Z]{1,3}$',  # Very short Latin abbreviations
            r'^\d+\.\d+$',  # Decimal numbers
        ]
        
        for pattern in cjk_non_title_patterns:
            if re.match(pattern, text):
                return True
                
        return False
    
    # For English and other languages, use the enhanced logic
    # Check for meaningful word content
    words = re.findall(r'\b[a-zA-Z]{2,}\b', text)  # Find actual words (2+ letters)
    if len(words) == 0:
        return True  # No real words found
    
    # Reject if mostly numbers
    alpha_chars = len(re.findall(r'[a-zA-Z]', text))
    digit_chars = len(re.findall(r'\d', text))
    if digit_chars > alpha_chars:  # More digits than letters
        return True
    
    # Reject if mostly single characters or abbreviations
    total_word_length = sum(len(word) for word in words)
    if len(words) > 0 and total_word_length / len(words) < 2.5:  # Average word length too short
        return True
    
    # Common non-title patterns
    non_title_patterns = [
        r'^\d+$',  # Just numbers
        r'^[A-Z0-9\s\-_]+$',  # Only caps, numbers, and basic punctuation (like "RFP: R")
        r'^page\s+\d+',  # Page numbers
        r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$',  # Dates
        r'^\d{1,2}:\d{2}',  # Times
        r'^https?://',  # URLs
        r'@\w+\.',  # Email addresses
        r'^[^\w\s]*$',  # Only symbols
        r'^\w{1,2}$',  # Single characters or very short
        r'^[A-Z]\s*:\s*[A-Z]$',  # Pattern like "RFP: R"
        r'^[A-Z]+\s*:\s*[A-Z]*$',  # Patterns like "ABC: DEF" or "RFP:"
    ]
    
    for pattern in non_title_patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return True
    
    return False

def _is_meaningful_title_text(text: str, detected_lang: str = "en") -> bool:
    """
    Enhanced check for meaningful title content.
    For non-English documents, focus on structural completeness rather than English word meaning.
    """
    text = text.strip()
    
    # Must have minimum length
    if len(text) < 4:
        return False
    
    # For CJK languages (Chinese, Japanese, Korean), use different criteria
    is_cjk = detected_lang in ["zh", "ja", "ko"]
    
    if is_cjk:
        # For CJK: focus on length and structure, not English word meaning
        # Check for minimum meaningful length
        if len(text) < 6:  # At least 6 characters for CJK
            return False
            
        # Reject obvious fragments like single numbers or very short phrases
        if re.match(r'^\d+\s*[:：]\s*\d+$', text):  # Pattern like "2: 5"
            return False
            
        if re.match(r'^[^\w\s]*$', text):  # Only symbols/punctuation
            return False
            
        # Accept if it has reasonable length and mixed content
        return len(text.strip()) >= 6
    
    # For English and other Latin-based languages, use word-based analysis
    # Extract meaningful words (3+ characters, alphabetic)
    meaningful_words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
    
    # Must have at least 2 meaningful words, or 1 long word (6+ chars)
    if len(meaningful_words) >= 2:
        return True
    elif len(meaningful_words) == 1 and len(meaningful_words[0]) >= 6:
        return True
    
    # Check if it contains recognizable English words (from our keyword list)
    text_lower = text.lower()
    for category_list in PDF_TITLE_KEYWORDS.values():
        for keyword in category_list:
            if len(keyword) >= 4 and keyword in text_lower:
                return True
    
    # Check for common title words not in our keyword list
    common_title_words = [
        'document', 'report', 'proposal', 'manual', 'guide', 'handbook', 
        'overview', 'summary', 'introduction', 'conclusion', 'analysis',
        'system', 'service', 'application', 'project', 'program', 'plan',
        'policy', 'procedure', 'process', 'standard', 'specification',
        'requirements', 'design', 'development', 'implementation', 'strategy'
    ]
    
    for word in common_title_words:
        if word in text_lower:
            return True
    
    return False

def _looks_like_main_heading(text: str) -> bool:
    """Check if text looks like a main document heading."""
    text = text.strip()
    
    # Main heading patterns
    heading_patterns = [
        r'^(chapter|section|part)\s+\d+',  # "Chapter 1", "Section 2"
        r'^\d+\.\s*[A-Z]',  # "1. Introduction"
        r'^[IVX]+\.\s*[A-Z]',  # Roman numerals "I. Overview"
        r'^(introduction|overview|summary|conclusion|background)',  # Common section names
        r'^(abstract|executive\s+summary|table\s+of\s+contents)',
        r'^(methodology|results|discussion|recommendations)',
        r'^(appendix|references|bibliography|acknowledgments)',
    ]
    
    for pattern in heading_patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return True
    
    return False

def _has_meaningful_filename(filename: str) -> bool:
    """Check if filename contains meaningful words (not just codes)."""
    name = os.path.splitext(filename)[0] if '.' in filename else filename
    
    # Skip files that are just codes/numbers
    if re.match(r'^[A-Z0-9_-]+$', name) and len(name) < 15:
        return False
    
    # Count actual words
    words = re.findall(r'[a-zA-Z]{3,}', name)
    return len(words) >= 2

def _calculate_semantic_similarity(text1: str, text2: str, nlp_model: Any) -> float:
    """Calculate semantic similarity between two texts using NLP model."""
    try:
        doc1 = nlp_model(text1.lower())
        doc2 = nlp_model(text2.lower())
        
        if doc1.has_vector and doc2.has_vector and doc1.vector_norm and doc2.vector_norm:
            return doc1.similarity(doc2)
    except Exception:
        pass
    return 0.0

def _normalize_title_text(text: str) -> str:
    """Normalize title text by cleaning and formatting - enhanced to preserve meaning."""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Remove trailing punctuation that's not meaningful
    text = re.sub(r'[.,:;]+$', '', text)
    
    # Remove quotes
    text = re.sub(r'[\u201c\u201d"\'`""'']+', '', text)
    
    # NEW: Clean up common artifacts
    # Remove leading/trailing colons that don't add meaning
    text = re.sub(r'^:\s*|\s*:$', '', text)
    
    # Remove repetitive patterns like "RFP: R RFP: R..."
    text = re.sub(r'(\b\w+\b)\s*:\s*\1', r'\1', text)
    
    # Remove excessive ellipsis 
    text = re.sub(r'\.{3,}.*$', '', text)
    
    # Ensure proper capitalization for first word
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    
    return text

def _looks_complete_title(text: str) -> bool:
    """Check if text looks like a complete, well-formed title."""
    text = text.strip()
    
    # Should have actual words
    words = re.findall(r'\b\w+\b', text)
    if len(words) < 2:
        return False
    
    # Should not end mid-sentence
    if text.endswith((',', 'and', 'or', 'the', 'a', 'an')):
        return False
    
    # Should not start with articles/prepositions unless it's a proper title
    if re.match(r'^(the|a|an|in|on|at|for|with|by)\s+', text, re.IGNORECASE):
        return len(words) >= 4  # Allow if long enough
    
    return True

def _is_valid_final_title(text: str, detected_lang: str = "en") -> bool:
    """Enhanced final validation for selected title - language-aware and strict about meaningful content."""
    text = text.strip()
    
    if not text or len(text) < 3:
        return False
    
    is_cjk = detected_lang in ["zh", "ja", "ko"]
    
    if is_cjk:
        # For CJK languages: focus on completeness and structure
        if len(text) < 6:  # Minimum length for meaningful CJK title
            return False
            
        # Reject obvious fragments for CJK
        cjk_reject_patterns = [
            r'^\d+\s*[:：]\s*\d+$',  # "2: 5" pattern
            r'^[^\w\s]*$',  # Only symbols
            r'^\d+$',  # Just numbers
            r'^[a-zA-Z]{1,3}$',  # Very short Latin abbreviations
            r'\.{3,}$',  # Ends with ellipsis (truncated)
        ]
        
        for pattern in cjk_reject_patterns:
            if re.match(pattern, text):
                return False
                
        return True  # Accept if passes basic CJK checks
    
    # For English and other Latin-based languages
    # Should contain at least some letters
    if not re.search(r'[a-zA-Z]', text):
        return False
    
    # Use the enhanced meaningful text check
    if not _is_meaningful_title_text(text, detected_lang):
        return False
    
    # Reject patterns that look like codes or fragments
    reject_patterns = [
        r'^[A-Z]{1,3}\s*:\s*[A-Z]{0,3}$',  # "RFP: R", "ABC:", "X: Y"
        r'^[A-Z0-9\-_]{2,10}$',  # Short codes like "E0H1CM114"
        r'^\w{1,3}\s+\w{1,3}$',  # Very short fragments like "A B" 
        r'^(to\s+|for\s+|and\s+|or\s+|the\s+)',  # Starts with prepositions/articles only
        r'\.\.\.$',  # Ends with ellipsis (truncated)
    ]
    
    for pattern in reject_patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return False
    
    # Should not be just a fragment
    words = text.split()
    if len(words) == 1 and len(text) < 6:  # Single short word
        return False
    
    # Check for balanced content (not mostly symbols/numbers)
    alpha_count = len(re.findall(r'[a-zA-Z]', text))
    total_count = len(text.replace(' ', ''))
    if alpha_count / max(total_count, 1) < 0.6:  # Less than 60% alphabetic
        return False
    
    return True

def _cluster_font_sizes_for_heading_levels(blocks: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Use statistical analysis to dynamically identify font size thresholds for heading levels.
    This replaces fixed thresholds with data-driven percentile-based clustering.
    """
    try:
        # Extract font sizes from all text blocks
        font_sizes = []
        for block in blocks:
            font_size = block.get('font_size', 0)
            if font_size > 0:
                font_sizes.append(font_size)
        
        if len(font_sizes) < 4:  # Need at least 4 different sizes for H1-H4
            return _get_fallback_thresholds(font_sizes)
        
        # Remove duplicates and sort
        unique_sizes = sorted(list(set(font_sizes)), reverse=True)
        
        if len(unique_sizes) < 4:
            return _get_fallback_thresholds(font_sizes)
        
        # Use percentile-based "clustering" - simpler but effective
        # Calculate percentiles to identify natural breaks in font sizes
        sorted_sizes = sorted(font_sizes, reverse=True)
        total_count = len(sorted_sizes)
        
        # Use percentiles to identify clusters
        p90 = sorted_sizes[int(total_count * 0.1)]  # Top 10% - likely H1
        p75 = sorted_sizes[int(total_count * 0.25)] # Top 25% - likely H2  
        p50 = sorted_sizes[int(total_count * 0.5)]  # Median - likely H3
        p25 = sorted_sizes[int(total_count * 0.75)] # Bottom 25% - likely H4
        
        # Map to heading levels with some overlap tolerance
        thresholds = {
            'H1': max(p90, statistics.median(font_sizes) * 1.3),
            'H2': max(p75, statistics.median(font_sizes) * 1.2),
            'H3': max(p50, statistics.median(font_sizes) * 1.1),
            'H4': max(p25, statistics.median(font_sizes) * 1.05)
        }
            
        return thresholds
        
    except Exception:
        # Fallback to statistical approach if clustering fails
        return _get_fallback_thresholds(font_sizes if 'font_sizes' in locals() else [])

def _get_fallback_thresholds(font_sizes: List[float]) -> Dict[str, float]:
    """Fallback threshold calculation using percentiles."""
    if not font_sizes:
        return {'H1': 16.0, 'H2': 14.0, 'H3': 12.5, 'H4': 11.0}
    
    median_size = statistics.median(font_sizes)
    return {
        'H1': median_size * 1.4,
        'H2': median_size * 1.25, 
        'H3': median_size * 1.15,
        'H4': median_size * 1.05
    }

def _analyze_whitespace_patterns(blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze whitespace above and below text blocks to identify heading patterns.
    Headings typically have more whitespace above than below.
    """
    whitespace_analysis = {}
    
    for i, block in enumerate(blocks):
        if i == 0:
            continue  # Skip first block
            
        prev_block = blocks[i-1]
        
        # Calculate vertical gap (whitespace above current block)
        gap_above = block.get('top', 0) - prev_block.get('bottom', 0)
        
        # Calculate gap below (if not last block)
        gap_below = 0
        if i < len(blocks) - 1:
            next_block = blocks[i+1]
            gap_below = next_block.get('top', 0) - block.get('bottom', 0)
        
        # Store whitespace ratios
        whitespace_analysis[i] = {
            'gap_above': gap_above,
            'gap_below': gap_below,
            'ratio_above_below': gap_above / max(gap_below, 1),  # Avoid division by zero
            'is_heading_like': gap_above > gap_below * 1.5  # Heading-like if much more space above
        }
    
    return whitespace_analysis

def _detect_all_caps_and_formatting(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Enhance blocks with ALL CAPS, italic, and other formatting detection.
    """
    enhanced_blocks = []
    
    for block in blocks:
        enhanced_block = block.copy()
        text = block.get('text', '')
        
        # ALL CAPS detection
        if len(text) > 3:  # Only check longer text
            alpha_chars = ''.join(c for c in text if c.isalpha())
            if alpha_chars and alpha_chars.isupper() and len(alpha_chars) > 2:
                enhanced_block['is_all_caps'] = True
            else:
                enhanced_block['is_all_caps'] = False
        else:
            enhanced_block['is_all_caps'] = False
        
        # Text alignment analysis (basic)
        x_position = block.get('x0', 0)
        page_width = block.get('page_width', 612)  # Default PDF width
        
        # Determine alignment (rough estimation)
        if x_position < page_width * 0.2:
            enhanced_block['alignment'] = 'left'
        elif x_position > page_width * 0.4:
            enhanced_block['alignment'] = 'center_or_right'
        else:
            enhanced_block['alignment'] = 'left_indented'
        
        enhanced_blocks.append(enhanced_block)
    
    return enhanced_blocks

def _build_heading_hierarchy(headings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build parent-child relationships between headings based on font size, 
    indentation, and numbering patterns.
    """
    if not headings:
        return []
    
    # Sort by page and position for hierarchy building
    sorted_headings = sorted(headings, key=lambda x: (x.get('page', 0), x.get('top', 0)))
    
    # Add hierarchy information
    for i, heading in enumerate(sorted_headings):
        level = heading.get('level', 'H4')
        level_num = int(level[1:]) if level.startswith('H') else 4
        
        # Find parent (previous heading with higher level)
        parent_id = None
        for j in range(i-1, -1, -1):
            prev_heading = sorted_headings[j]
            prev_level = prev_heading.get('level', 'H4')
            prev_level_num = int(prev_level[1:]) if prev_level.startswith('H') else 4
            
            if prev_level_num < level_num:
                parent_id = j
                break
        
        # Add hierarchy metadata (but keep original structure for output)
        heading['_hierarchy_parent'] = parent_id
        heading['_hierarchy_children'] = []
        
        # Add to parent's children list
        if parent_id is not None:
            sorted_headings[parent_id]['_hierarchy_children'].append(i)
    
    return sorted_headings


def _prune_flattened_headings_with_page_distribution(flat_headings: List[Dict[str, Any]], 
                                                     num_pages_total: int, 
                                                     detected_lang: str = "en") -> List[Dict[str, Any]]:
    """
    Placeholder function - functionality moved elsewhere.
    """
    return flat_headings



    # Apply aggressive final cleaning to the determined title
    final_title = re.sub(r'^(the\s*|an\s*|a\s*|this\s*document\s*|this\s*report\s*|overview\s*of\s*|request\s*for\s*proposal\s*)\s*', '', final_title, flags=re.IGNORECASE).strip()
    final_title = re.sub(r'[\u201c\u201d"\'`“”‘’]', '', final_title).strip() 
    final_title = re.sub(r'\s+', ' ', final_title).strip()





    


def _prune_outline_for_length_and_page_coverage(flat_headings: List[Dict[str, Any]], 
                                                 num_pages_total: int,
                                                 detected_lang: str = "en") -> List[Dict[str, Any]]:
    """
    Prunes the flattened list of headings to meet length constraints and ensure page coverage.
    Removes lower-level headings first (H4s, then H3s etc.) to fit limits,
    while trying to keep at least 1-2 important headings per page.
    The flat_headings are assumed to be sorted by page, then level, then text for initial passes.
    Includes language-aware placeholder.
    """
    if not flat_headings:
        return []

    headings_by_page = collections.defaultdict(list)
    for heading in flat_headings:
        headings_by_page[heading["page"]].append(heading)

    # Determine target max total headings based on document size
    if num_pages_total < 5:
        target_max_total_headings = MAX_HEADINGS_FACTOR_SMALL_DOC * num_pages_total
    else:
        target_max_total_headings = int(MAX_HEADINGS_FACTOR_LARGE_DOC * num_pages_total)
    
    if target_max_total_headings > 150: 
        target_max_total_headings = 150

    selected_heading_texts = set() 
    final_pruned_list = []

    # Pass 1: Ensure minimum headings per page (1 to 2) and prioritize higher levels
    for page_num_0_indexed in range(num_pages_total):
        page_headings = sorted(headings_by_page.get(page_num_0_indexed, []), key=lambda x: (int(x["level"][1:]), x["text"]))
        
        kept_on_page_count = 0
        is_cjk = detected_lang in ["zh", "ja", "ko"]

        for heading in page_headings:
            if kept_on_page_count >= MAX_HEADINGS_PER_PAGE:
                break 

            heading_text_len_for_check = len(heading["text"].split()) if not is_cjk else len(heading["text"]) # Use chars for CJK

            if int(heading["level"][1:]) <= 3: 
                if heading["text"] not in selected_heading_texts:
                    final_pruned_list.append(heading)
                    selected_heading_texts.add(heading["text"])
                    kept_on_page_count += 1
            elif int(heading["level"][1:]) == 4 and kept_on_page_count < 1 and \
                 heading_text_len_for_check > (1 if not is_cjk else 3): # Language-aware word count for H4 min length
                if heading["text"] not in selected_heading_texts:
                    final_pruned_list.append(heading)
                    selected_heading_texts.add(heading["text"])
                    kept_on_page_count += 1

        # If a page still lacks MIN_HEADINGS_PER_PAGE after explicit selection, find any reasonable fallback
        while kept_on_page_count < MIN_HEADINGS_PER_PAGE:
            best_fallback_heading = None
            for heading in page_headings:
                if heading["text"] not in selected_heading_texts:
                    # Start with stricter criteria, then relax if needed
                    min_len_for_fallback = 5 if kept_on_page_count == 0 else 3  # Relax for second heading
                    if is_cjk:
                        min_len_for_fallback = 8 if kept_on_page_count == 0 else 5
                    
                    heading_text_len_for_fallback_check = len(heading["text"].split()) if not is_cjk else len(heading["text"])
                    min_words_needed = 2 if kept_on_page_count == 0 else 1  # Relax word count for second heading
                    
                    if heading_text_len_for_fallback_check >= (min_words_needed if not is_cjk else min_len_for_fallback) and len(heading["text"]) >= min_len_for_fallback:
                        best_fallback_heading = heading
                        break
            
            if best_fallback_heading:
                final_pruned_list.append(best_fallback_heading)
                selected_heading_texts.add(best_fallback_heading["text"])
                kept_on_page_count += 1
            else:
                break  # No more suitable headings found for this page
    
    # Pass 2: Add remaining unique classified headings (not selected in Pass 1) up to max limit
    all_unique_classified_headings_map = {h["text"]: h for h in flat_headings}

    remaining_headings_to_consider = []
    for heading_text, heading_obj in all_unique_classified_headings_map.items():
        if heading_text not in selected_heading_texts:
            remaining_headings_to_consider.append(heading_obj)

    remaining_headings_to_consider.sort(key=lambda x: (int(x["level"][1:]), x["page"], x["text"]))

    for heading in remaining_headings_to_consider:
        if len(final_pruned_list) < target_max_total_headings:
            final_pruned_list.append(heading)
            selected_heading_texts.add(heading["text"])
        else:
            break

    # Pass 3: Aggressive pruning if still over target_max_total_headings
    while len(final_pruned_list) > target_max_total_headings:
        final_pruned_list.sort(key=lambda x: (int(x["level"][1:]), -x["page"]), reverse=True)
        
        removed_one = False
        for idx in range(len(final_pruned_list) - 1, -1, -1):
            heading_to_remove = final_pruned_list[idx]
            
            headings_on_this_page = [h for h in final_pruned_list if h["page"] == heading_to_remove["page"] and h != heading_to_remove]
            
            if len(headings_on_this_page) >= MIN_HEADINGS_PER_PAGE:
                final_pruned_list.pop(idx)
                selected_heading_texts.remove(heading_to_remove["text"])
                removed_one = True
                break
        
        if not removed_one:
            break
    
    final_pruned_list.sort(key=lambda x: (x["page"], int(x["level"][1:]), x["text"]))

    return final_pruned_list

def run(classified_blocks: List[Dict[str, Any]], num_pages_total: int, 
        pdf_filename_base: str = "Untitled Document", 
        detected_lang: str = "en") -> Dict[str, Any]:
    """
    Reads classified blocks, structures the outline into a flat list,
    applies heading text truncation, and prunes to meet length constraints.
    ENHANCED with clustering, whitespace analysis, and hierarchy detection.
    """
    
    # Step 1: Enhance blocks with advanced formatting detection
    try:
        enhanced_blocks = _detect_all_caps_and_formatting(classified_blocks)
    except:
        enhanced_blocks = classified_blocks  # Fallback
    
    # Step 2: Apply font size clustering for better heading detection
    try:
        font_thresholds = _cluster_font_sizes_for_heading_levels(enhanced_blocks)
        print(f"    Dynamic font thresholds: {font_thresholds}")
    except:
        font_thresholds = None  # Will use existing logic
    
    # Step 3: Analyze whitespace patterns
    try:
        whitespace_patterns = _analyze_whitespace_patterns(enhanced_blocks)
    except:
        whitespace_patterns = {}
        
    # Step 4: Extract headings with enhanced criteria
    headings = []
    for i, block in enumerate(enhanced_blocks):
        if block.get("level") and block["level"].startswith("H"):
            # Apply additional scoring based on new analysis
            enhanced_score = 0
            
            # ALL CAPS bonus
            if block.get('is_all_caps', False):
                enhanced_score += 10
                
            # Whitespace pattern bonus
            whitespace_info = whitespace_patterns.get(i, {})
            if whitespace_info.get('is_heading_like', False):
                enhanced_score += 15
                
            # Font clustering bonus
            if font_thresholds:
                font_size = block.get('font_size', 12)
                level = block.get('level', 'H4')
                expected_threshold = font_thresholds.get(level, 12)
                if font_size >= expected_threshold * 0.9:  # Within 10% of cluster threshold
                    enhanced_score += 20
            
            # Store enhanced score for potential future use
            block['_enhanced_score'] = enhanced_score
            headings.append(block)
    
    # Step 5: Build hierarchy relationships (but maintain flat output)
    try:
        headings_with_hierarchy = _build_heading_hierarchy(headings)
    except:
        headings_with_hierarchy = headings
    
    # Step 6: Prepare outline nodes (same as original logic)
    prepared_outline_nodes = []
    is_cjk = detected_lang in ["zh", "ja", "ko"]

    for heading in headings_with_hierarchy:
        node_text = heading["text"].strip()
        
        truncation_words = OUTLINE_TEXT_TRUNCATION_WORDS
        if is_cjk:
            truncation_words = 15 

        if (len(node_text.split()) > truncation_words and not is_cjk) or \
           (len(node_text) > truncation_words and is_cjk):
            if is_cjk:
                node_text = node_text[:truncation_words] + "..."
            else:
                node_text = " ".join(node_text.split()[:truncation_words]) + "..."
        
        prepared_outline_nodes.append({
            "level": heading["level"], 
            "text": node_text, 
            "page": heading["page"]
        })
    
    # Step 7: Final pruning (same as original)
    final_pruned_outline = _prune_outline_for_length_and_page_coverage(
        prepared_outline_nodes, num_pages_total, detected_lang=detected_lang)

    return {
        "outline": final_pruned_outline
    }