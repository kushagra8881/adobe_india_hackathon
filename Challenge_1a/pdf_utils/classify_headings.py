import json
import statistics
import re
import collections
from operator import itemgetter
import numpy as np
import math
from typing import List, Dict, Any, Tuple, Optional
import spacy # Import spacy for type hinting nlp_model

# --- Constants and Configuration ---
# General Tolerances
FONT_SIZE_TOLERANCE_MERGE = 0.5 # points for font size comparison during tight merges
X_ALIGN_TOLERANCE_MERGE = 15.0 # pixels for horizontal alignment during merges
VERTICAL_GAP_TOLERANCE_MERGE_NEGATIVE = 5.0 # Max negative gap for vertical merges
PAGE_MARGIN_HEADER_FOOTER_PERCENT = 0.15 # % of page height for header/footer detection

# Title Derivation (These are less relevant to current request but kept for context)
MIN_TITLE_WORDS = 2
MAX_TITLE_WORDS = 7
MIN_TITLE_SCORE_THRESHOLD = 3
FILENAME_SIMILARITY_BOOST = 10
FONT_SIZE_BOOST_TITLE = 10
POSITION_BOOST_TITLE = 5
KEYWORD_MATCH_BOOST_TITLE = 7
MIN_RELATABILITY_FOR_KEYWORD_BOOST = 0.4

# Outline Pruning (These are less relevant to current request but kept for context)
DEFAULT_MEDIAN_FONT_SIZE = 12.0
MIN_HEADINGS_PER_PAGE = 2  # INCREASED from 1 to 2 - ensure at least 2 headings per page
MAX_HEADINGS_PER_PAGE = 4  # Allow more headings per page
MAX_HEADINGS_FACTOR_SMALL_DOC = 5
MAX_HEADINGS_FACTOR_LARGE_DOC = 3.5
OUTLINE_TEXT_TRUNCATION_WORDS = 5

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

# CJK specific punctuation that might end a sentence for merging logic
CJK_SENTENCE_END_PUNCTUATION = re.compile(r'[。？！]') # Japanese/Chinese full stops

# --- HEADING PATTERN DETECTION ---
# Common heading patterns that indicate structured documents
HEADING_PATTERNS = {
    'numbered_sections': [
        r'^\d+\.\s+[A-Z][^.]*$',  # "1. Introduction" (starts with capital, no ending period)
        r'^\d+\.\s+[A-Z][^.]*[^.]$',  # "1. Main Section" (more specific)
        r'^\d+\.\d+\s+[A-Z][^.]*$',  # "1.1 Overview" (subsection)
        r'^\d+\.\d+\.\d+\s+[A-Z][^.]*$',  # "1.1.1 Details" (sub-subsection)
        r'^[A-Z]\.\s+[A-Z][^.]*$',  # "A. Section" (alphabetic)
        r'^[IVXLCDM]+\.\s+[A-Z][^.]*$',  # "I. Roman numerals"
    ],
    'bullet_structured': [
        r'^[•●○▪▫]\s+[A-Z][^.]*$',  # Bullet points with capital start
        r'^[-*+]\s+[A-Z][^.]*$',  # Dash/asterisk bullets
        r'^\([a-z]\)\s+[A-Z][^.]*$',  # "(a) subsection"
        r'^\([0-9]+\)\s+[A-Z][^.]*$',  # "(1) numbered"
    ],
    'formatted_headings': [
        r'^[A-Z][A-Z\s]{4,}$',  # ALL CAPS headings (min 5 chars)
        r'^[A-Z][a-z]+(\s+[A-Z][a-z]+)*:?\s*$',  # Title Case headings
        r'^\*{1,3}.+\*{1,3}$',  # *Bold* formatting
    ],
    'outline_style': [
        r'^\d+\)\s+[A-Z][^.]*$',  # "1) Item"
        r'^[a-z]\)\s+[A-Z][^.]*$',  # "a) subitem"
        r'^\([IVXLCDM]+\)\s+[A-Z][^.]*$',  # "(I) Roman"
    ]
}

def detect_document_heading_patterns(blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze document blocks to detect consistent heading patterns.
    MORE AGGRESSIVE - lower thresholds to find patterns even in sparse documents.
    """
    pattern_matches = {pattern_type: [] for pattern_type in HEADING_PATTERNS.keys()}
    total_blocks = len(blocks)
    
    if total_blocks == 0:
        return {'dominant_pattern': None, 'confidence': 0.0, 'matches': pattern_matches}
    
    # Test each block against all patterns
    for i, block in enumerate(blocks):
        text = block.get('text', '').strip()
        if not text:
            continue
            
        for pattern_type, patterns in HEADING_PATTERNS.items():
            for pattern in patterns:
                if re.match(pattern, text):
                    pattern_matches[pattern_type].append({
                        'block_index': i,
                        'text': text,
                        'pattern': pattern,
                        'font_size': block.get('font_size', 12.0),
                        'is_bold': block.get('is_bold', False)
                    })
                    break  # Only match first pattern per type per block
    
    # Calculate pattern strength - MORE LENIENT
    pattern_scores = {}
    for pattern_type, matches in pattern_matches.items():
        if not matches:
            pattern_scores[pattern_type] = 0.0
            continue
            
        # Score based on frequency and distribution - LOWERED THRESHOLDS
        match_count = len(matches)
        frequency_score = min(match_count / max(total_blocks * 0.05, 2), 1.0)  # Only need 5% or 2 matches (was 10% or 3)
        
        # Bonus for consistent formatting within pattern
        font_sizes = [m['font_size'] for m in matches]
        bold_count = sum(1 for m in matches if m['is_bold'])
        consistency_score = 0.3  # Lower base score
        
        if len(set(font_sizes)) <= 3:  # More lenient font consistency (was 2)
            consistency_score += 0.3
        if bold_count > match_count * 0.5:  # Lower threshold for bold (was 0.7)
            consistency_score += 0.2
            
        pattern_scores[pattern_type] = frequency_score * consistency_score
    
    # Find dominant pattern - LOWERED THRESHOLD
    if not pattern_scores or max(pattern_scores.values()) < 0.15:  # Was 0.3, now 0.15
        return {'dominant_pattern': None, 'confidence': 0.0, 'matches': pattern_matches}
    
    dominant_pattern = max(pattern_scores.keys(), key=lambda k: pattern_scores[k])
    confidence = pattern_scores[dominant_pattern]
    
    return {
        'dominant_pattern': dominant_pattern,
        'confidence': confidence,
        'matches': pattern_matches,
        'all_scores': pattern_scores
    }

def classify_block_by_pattern(block: Dict[str, Any], pattern_info: Dict[str, Any]) -> Optional[str]:
    """
    Classify a block based on detected document patterns.
    Returns heading level (H1-H4) if block matches pattern, None otherwise.
    """
    if not pattern_info or pattern_info['confidence'] < 0.5:
        return None
        
    text = block.get('text', '').strip()
    if not text:
        return None
    
    dominant_pattern = pattern_info['dominant_pattern']
    if not dominant_pattern:
        return None
    
    patterns = HEADING_PATTERNS[dominant_pattern]
    
    # Check if this block matches the dominant pattern
    matched_pattern = None
    for pattern in patterns:
        if re.match(pattern, text):
            matched_pattern = pattern
            break
    
    if not matched_pattern:
        return None
    
    # Determine heading level based on pattern specificity
    if dominant_pattern == 'numbered_sections':
        if re.match(r'^\d+\.\s+[A-Z][^.]*$', text):  # "1. Main section"
            return 'H1'
        elif re.match(r'^\d+\.\d+\s+[A-Z][^.]*$', text):  # "1.1 Subsection"
            return 'H2'
        elif re.match(r'^\d+\.\d+\.\d+\s+[A-Z][^.]*$', text):  # "1.1.1 Sub-subsection"
            return 'H3'
        elif re.match(r'^[A-Z]\.\s+[A-Z][^.]*$', text):  # "A. Appendix"
            return 'H2'
        elif re.match(r'^[IVXLCDM]+\.\s+[A-Z][^.]*$', text):  # "I. Roman"
            return 'H1'
    
    elif dominant_pattern == 'bullet_structured':
        if re.match(r'^[•●○▪▫]\s+[A-Z][^.]*$', text):  # Main bullets
            return 'H2'
        elif re.match(r'^[-*+]\s+[A-Z][^.]*$', text):  # Dash bullets
            return 'H3'
        elif re.match(r'^\([a-z]\)\s+[A-Z][^.]*$', text):  # "(a) subsection"
            return 'H4'
        elif re.match(r'^\([0-9]+\)\s+[A-Z][^.]*$', text):  # "(1) numbered"
            return 'H3'
    
    elif dominant_pattern == 'formatted_headings':
        if re.match(r'^[A-Z][A-Z\s]{4,}$', text):  # ALL CAPS
            return 'H1'
        elif re.match(r'^[A-Z][a-z]+(\s+[A-Z][a-z]+)*:?\s*$', text):  # Title Case
            # Determine level by length and font size
            word_count = len(text.split())
            font_size = block.get('font_size', 12.0)
            if word_count <= 3 and font_size > 14:
                return 'H1'
            elif word_count <= 5:
                return 'H2'
            else:
                return 'H3'
        elif re.match(r'^\*{1,3}.+\*{1,3}$', text):  # *Bold*
            return 'H3'
    
    elif dominant_pattern == 'outline_style':
        if re.match(r'^\d+\)\s+[A-Z][^.]*$', text):  # "1) Item"
            return 'H1'
        elif re.match(r'^[a-z]\)\s+[A-Z][^.]*$', text):  # "a) subitem"
            return 'H2'
        elif re.match(r'^\([IVXLCDM]+\)\s+[A-Z][^.]*$', text):  # "(I) Roman"
            return 'H1'
    
    # Default fallback
    return 'H2'

def identify_numbered_headings_with_separation(blocks: List[Dict[str, Any]], 
                                               page_dimensions: Dict[int, Dict[str, float]]) -> List[Dict[str, Any]]:
    """
    Identify blocks that match 'n. _______' pattern and have vertical separation.
    These are considered headings by default regardless of other formatting.
    """
    numbered_heading_pattern = re.compile(r'^\d+\.\s+.+')
    guaranteed_headings = []
    
    for i, block in enumerate(blocks):
        text = block.get('text', '').strip()
        if not text:
            continue
            
        # Check if it matches numbered pattern
        if not numbered_heading_pattern.match(text):
            continue
            
        # Check if it's in header/footer region
        page_num = block.get('page', 0)
        if page_num in page_dimensions:
            page_height = page_dimensions[page_num].get('height', 800)
            y_pos = block.get('top', 0)
            
            # Skip if in header/footer regions (top/bottom 15% of page)
            header_threshold = page_height * 0.15
            footer_threshold = page_height * 0.85
            if y_pos < header_threshold or y_pos > footer_threshold:
                continue
        
        # Check vertical separation from neighbors
        font_size = block.get('font_size', 12.0)
        min_separation = font_size * 0.5  # Minimum gap for heading consideration
        
        has_separation = False
        
        # Check gap before this block
        gap_before = block.get('gap_before_block', 0.0)
        gap_after = block.get('gap_after_block', 0.0)
        
        # If either gap before or after is significant, consider it separated
        if gap_before >= min_separation or gap_after >= min_separation:
            has_separation = True
        
        # Alternative: check distance to neighboring blocks manually
        if not has_separation and i > 0:
            prev_block = blocks[i-1]
            if (prev_block.get('page') == block.get('page') and 
                block.get('top', 0) - (prev_block.get('top', 0) + prev_block.get('height', 0)) >= min_separation):
                has_separation = True
        
        if not has_separation and i < len(blocks) - 1:
            next_block = blocks[i+1]
            if (next_block.get('page') == block.get('page') and 
                next_block.get('top', 0) - (block.get('top', 0) + block.get('height', 0)) >= min_separation):
                has_separation = True
        
        if has_separation:
            # Mark as guaranteed heading
            block_copy = block.copy()
            block_copy['is_guaranteed_heading'] = True
            block_copy['guaranteed_level'] = 'H1'  # Numbered sections are typically H1
            guaranteed_headings.append(block_copy)
    
    return guaranteed_headings


# NEW: Extended Common Single Words (Stop Words) by Language
COMMON_SINGLE_WORDS_EXTENDED = {
    "english": [
        "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
        "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
        "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
        "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
        "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
        "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
        "hers", "herself", "him", "himself", "his", "how", "i", "i'd", "i'll", "i'm",
        "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself",
        "let's", "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not",
        "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours",
        "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd", "she'll",
        "she's", "should", "shouldn't", "so", "some", "such", "than", "that", "that's",
        "the", "their", "theirs", "them", "themselves", "then", "there", "there's",
        "these", "they", "they'd", "they'll", "they're", "they've", "this", "those",
        "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we",
        "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when",
        "when's", "where", "where's", "which", "while", "who", "who's", "whom", "why",
        "why's", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll",
        "you're", "you've", "your", "yours", "yourself", "yourselves"
    ],
    "spanish": [
        "de", "la", "que", "el", "en", "y", "a", "los", "del", "se", "las", "por",
        "un", "para", "con", "no", "una", "su", "al", "lo", "como", "más", "pero",
        "sus", "le", "ya", "o", "este", "sí", "porque", "esta", "entre", "cuando",
        "muy", "sin", "sobre", "también", "me", "hasta", "hay", "donde", "quien",
        "desde", "todo", "nos", "durante", "todos", "uno", "les", "ni", "contra",
        "otros", "ese", "eso", "ante", "ellos", "e", "esto", "mí", "antes", "algunos"
    ],
    "french": [
        "alors", "au", "aucuns", "aussi", "autre", "avant", "avec", "avoir", "bon",
        "car", "ce", "cela", "ces", "ceux", "chaque", "ci", "comme", "comment", "dans",
        "des", "du", "dedans", "dehors", "depuis", "devrait", "doit", "donc", "dos",
        "droite", "début", "elle", "elles", "en", "encore", "essai", "est", "et", "eu",
        "fait", "faites", "fois", "font", "force", "haut", "hors", "ici", "il", "ils",
        "je", "juste", "la", "le", "les", "leur", "là", "ma", "maintenant", "mais",
        "mes", "mine", "moins", "mon", "mot", "même", "ni", "nommés", "notre", "nous",
        "nouveaux", "ou", "où", "par", "parce", "parole", "pas", "personnes", "peut",
        "peu", "pièce", "plupart", "pour", "pourquoi", "quand", "que", "quel", "quelle",
        "quelles", "quels", "qui", "sa", "sans", "ses", "seulement", "si", "sien",
        "son", "sont", "sous", "soyez", "sujet", "sur", "ta", "tandis", "tellement",
        "tels", "tes", "ton", "tous", "tout", "trop", "très", "tu", "voient", "vont",
        "votre", "vous", "vu", "ça", "étaient", "état", "étions", "été", "être"
    ],
    "german": [
        "aber", "als", "am", "an", "auch", "auf", "aus", "bei", "bin", "bis", "bist",
        "da", "dadurch", "daher", "darum", "das", "daß", "dass", "dein", "deine", "dem",
        "den", "der", "des", "dessen", "deshalb", "die", "dies", "dieser", "dieses",
        "doch", "dort", "du", "durch", "ein", "eine", "einem", "einen", "einer", "eines",
        "er", "es", "euer", "eure", "für", "hatte", "hatten", "hattest", "hattet", "hier",
        "hinter", "ich", "ihr", "ihre", "im", "in", "ist", "ja", "jede", "jedem", "jeden",
        "jeder", "jedes", "jener", "jenes", "jetzt", "kann", "kannst", "können", "könnt",
        "machen", "mein", "meine", "mit", "muß", "mußt", "musst", "müssen", "müßt", "nach",
        "nachdem", "nein", "nicht", "nun", "oder", "seid", "sein", "seine", "sich", "sie",
        "sind", "soll", "sollen", "sollst", "sollt", "sonst", "soweit", "sowie", "und",
        "unser", "unsere", "unter", "vom", "von", "vor", "wann", "warum", "was", "weiter",
        "weitere", "wenn", "wer", "werde", "werden", "werdet", "weshalb", "wie", "wieder",
        "wieso", "wir", "wird", "wirst", "wo", "woher", "wohin", "zu", "zum", "zur", "über"
    ],
    "russian": [
        "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то", "все",
        "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за", "бы", "по",
        "только", "ее", "мне", "было", "вот", "от", "меня", "еще", "нет", "о", "из",
        "ему", "теперь", "когда", "даже", "ну", "вдруг", "ли", "если", "уже", "или", "ни",
        "быть", "был", "него", "до", "вас", "нибудь", "опять", "уж", "вам", "ведь",
        "там", "потом", "себя", "ничего", "ей", "может", "они", "тут", "где", "есть"
    ],
    "dutch": [
        "de", "en", "van", "ik", "te", "dat", "die", "in", "een", "hij", "het", "niet",
        "zijn", "is", "was", "op", "aan", "met", "als", "voor", "had", "er", "maar",
        "om", "hem", "dan", "zou", "of", "wat", "mijn", "men", "dit", "zo", "door",
        "over", "ze", "zich", "bij", "ook", "tot", "je", "mij", "uit", "der", "daar",
        "haar", "naar", "heb", "hoe", "heeft", "hebben", "deze", "u", "want", "nog",
        "zal", "me", "zij", "nu", "ge", "geen", "omdat", "iets", "worden", "toch", "al"
    ],
    "hindi": [
        "के", "का", "है", "की", "को", "पर", "यह", "था", "और", "से", "में", "हैं", "एक",
        "लिए", "कि", "जो", "तक", "ने", "ही", "या", "तो", "था", "थे", "थे", "हो", "नहीं",
        "क्या", "जब", "तक", "जहाँ", "क्यों", "किस", "कौन", "कब", "अगर", "इसे", "उसे"
    ],
    "arabic": [
        "في", "من", "على", "و", "أن", "إلى", "عن", "هو", "هي", "هذا", "كان", "ل", "ما",
        "مع", "كل", "تم", "قد", "لا", "إن", "ذلك", "أو", "أي", "أين", "لم", "لن", "هنا",
        "هناك", "أنا", "نحن", "هم", "هن", "كما", "حتى", "إذا", "عند", "منذ"
    ],
    "chinese": [
        "的", "了", "在", "是", "我", "有", "和", "不", "就", "人", "都", "一", "一个",
        "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "我们", "来",
        "他们", "这", "那", "吗", "呢", "把", "被", "为", "什么", "怎么", "谁", "而", "与"
    ],
    "japanese": [
        "の", "に", "は", "を", "た", "が", "で", "て", "と", "し", "れ", "さ", "ある",
        "いる", "も", "する", "から", "な", "こと", "として", "い", "や", "また", "なっ",
        "それ", "この", "そして", "しかし", "られ", "ため", "その", "さらに"
    ],
    "korean": [
        "의", "가", "이", "은", "는", "을", "를", "에", "와", "과", "도", "으로", "해서",
        "에서", "이다", "하다", "그리고", "그", "하지만", "또는", "또", "한", "그러나",
        "그래서", "더", "보다", "않다", "있다", "없다", "같다", "되어", "된다"
    ]
}

# Mapping of detected language codes to the keys in COMMON_SINGLE_WORDS_EXTENDED
LANG_CODE_TO_NAME_MAP = {
    "en": "english",
    "es": "spanish",
    "fr": "french",
    "de": "german",
    "ru": "russian",
    "hi": "hindi",
    "ar": "arabic",
    "zh": "chinese",
    "ja": "japanese",
    "ko": "korean",
    "nl": "dutch"
}


# Regex for common patterns that are likely noise when standalone in a title context
_COMMON_NOISE_PATTERNS = [
    re.compile(r'^(https?://|www\.)\S+\.\S+(\/\S*)?$', re.IGNORECASE), # URLs
    re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'), # Email IDs
    re.compile(r'^\s*(Page|Table|Figure)\s+\d+(\.\d+)?', re.IGNORECASE), # Page/Table/Figure indicators
    re.compile(r'^\s*Page\s+\d+\s+of\s+\d+\s*$', re.IGNORECASE), # Page X of Y indicators
    re.compile(r'^\s*\$\d+(\.\d+)?[KMB]?\s*\(\d+%\)\s*$', re.IGNORECASE), # Monetary amounts with percentages like "$10M (20%)"
    re.compile(r'^\s*([A-Z]\.?){2,}', re.IGNORECASE), # All caps acronyms (e.g., "U.S.A.")
    re.compile(r'(\b\w+\b\s*){2,}\1', re.IGNORECASE), # Repetitive words (e.g., "RFP RFP RFP")
    re.compile(r'^[\d\W_]+$'), # Purely numbers/symbols
    re.compile(r'^\s*([•*○■●►▼►‣—+-]\s*){1,2}$'), # Common bullet points / very short separators
    re.compile(r'^\s*\d{1,5}\s*$'), # Short standalone numbers (e.g., page numbers, chapter numbers)
    re.compile(r'^\s*(I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII|XIV|XV|XVI|XVII|XVIII|XIX|XX)\s*$', re.IGNORECASE), # Standalone Roman numerals
    re.compile(r'^\s*(\d+(\.\d+)*)\s*$'), # Standalone numeric sequences (e.g., "1.2.3")
    re.compile(r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$|^\d{4}[/-]\d{1,2}[/-]\d{1,2}$|^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2},?\s+\d{2,4}$', re.IGNORECASE), # Dates
    re.compile(r'^\d{1,2}:\d{2}(:\d{2})?(?:\s*(?:am|pm))?$', re.IGNORECASE), # Times
]


# --- Helper Functions ---

def _has_unclosed_parentheses_brackets(text: str) -> bool:
    """
    Checks if a string has unclosed parentheses, brackets, or braces,
    including common CJK variants.
    Returns True if unclosed, False otherwise.
    """
    stack = []
    # Add common CJK bracket mappings
    mapping = {")": "(", "]": "[", "}": "{",
               "）": "（", "】": "【", "」": "「", "』": "『"}
    for char in text:
        if char in mapping.values(): # Opening bracket
            stack.append(char)
        elif char in mapping: # Closing bracket
            if not stack or stack.pop() != mapping[char]:
                return True # Mismatched or unclosed
    return len(stack) > 0 # Any left in stack means unclosed

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


def _is_uninformative_text_strict(text: str, detected_lang: str = "en") -> bool:
    """
    Strictly determines if a text string is uninformative noise, not meant for content extraction.
    This is a rule-based filter, designed to prune absolute garbage.
    Includes language-aware adjustments.
    """
    text_stripped = text.strip()
    if not text_stripped:
        return True # Empty string

    # Map detected_lang code to the full name used in COMMON_SINGLE_WORDS_EXTENDED
    lang_name = LANG_CODE_TO_NAME_MAP.get(detected_lang, "english")
    common_words_for_lang = set(COMMON_SINGLE_WORDS_EXTENDED.get(lang_name, []))

    predominant_script = _get_predominant_script_type(text_stripped)
    is_non_latin_script = (predominant_script in ['cjk', 'cyrillic', 'arabic', 'devanagari'])


    # 1. Purely whitespace or decorative lines
    if re.fullmatch(r'[\s\-—_•*●■]*', text_stripped) and len(set(text_stripped.replace(" ", ""))) < 3:
        return True

    # 2. Text matching common noise patterns (URLs, emails, etc.)
    for pattern in _COMMON_NOISE_PATTERNS:
        # Skip English-specific acronym pattern for non-Latin scripts
        if is_non_latin_script and pattern == _COMMON_NOISE_PATTERNS[5]: # All caps acronyms pattern (moved index again)
            continue
        # Skip repetitive words for non-Latin scripts (or adapt with complex tokenization if available)
        if is_non_latin_script and pattern == _COMMON_NOISE_PATTERNS[6]: # Repetitive words pattern (moved index again)
            continue

        if pattern.fullmatch(text_stripped):
            # Special allowance for single-word numeric headings that are bold and reasonably large
            # (handled by classifier, so allow them through this filter IF they match a number/roman/cjk list pattern)
            if (pattern == _COMMON_NOISE_PATTERNS[10] or pattern == _COMMON_NOISE_PATTERNS[11] or pattern == _COMMON_NOISE_PATTERNS[12]) and \
               re.fullmatch(r'^\s*(\d+(\.\d+)*|[IVXLCDM]+|[一二三四五六七八九十百千万億兆甲乙丙丁あいうえおかきくけこ]\s*[\.．、，]?)\s*$', text_stripped, re.IGNORECASE): # Numbers or Roman Num/CJK lists
                pass # Allow potential headings (single num/roman/cjk list item) to pass here
            elif pattern.fullmatch(text_stripped): # Re-check if it truly matches a general noise pattern
                return True
    
    # 3. Single common stop words (language-aware and script-aware)
    word_count_for_stop_word_check = len(text_stripped.split())
    if predominant_script == 'cjk':
        word_count_for_stop_word_check = len(text_stripped) # For CJK, word count is character count

    if word_count_for_stop_word_check == 1 and text_stripped.lower() in common_words_for_lang:
        # If it's a non-alphanumeric script and just a single "word" (char for CJK),
        # it's usually meaningful even if it's a common particle/preposition.
        # So, be lenient and pass it unless it's purely symbolic.
        if is_non_latin_script and not _has_script_chars(text_stripped, LATIN_CHARS_REGEX) and not re.search(r'\d', text_stripped): # Check it doesn't contain Latin or numbers
            return False # Be lenient: pass non-alphanumeric single words if not numeric/Latin
        return True # Filter if it's a common stop word (for Latin) or purely symbolic (for non-Latin)

    # 4. Very low meaningful script content suggests noise, especially for short blocks
    has_any_meaningful_script_or_digit = False
    if re.search(r'[a-zA-Z0-9]', text_stripped) or \
       _has_script_chars(text_stripped, CJK_CHARS_REGEX) or \
       _has_script_chars(text_stripped, CYRILLIC_CHARS_REGEX) or \
       _has_script_chars(text_stripped, ARABIC_CHARS_REGEX) or \
       _has_script_chars(text_stripped, DEVANAGARI_CHARS_REGEX):
        has_any_meaningful_script_or_digit = True
    
    if not has_any_meaningful_script_or_digit and len(text_stripped) > 0:
        return True # Filter out if no meaningful chars at all

    return False


def _merge_nearby_blocks_logical(blocks_in_column: List[Dict[str, Any]], 
                                 typical_line_spacing_threshold: float, 
                                 paragraph_break_threshold: float, 
                                 x_tolerance_alignment: float = 10.0,
                                 detected_lang: str = "en") -> List[Dict[str, Any]]:
    """
    Performs a logical merge of blocks to form "complete word bodies" or paragraphs.
    This version uses dynamic thresholds for gaps and enhanced linguistic/formatting rules,
    with language-aware adjustments.
    """
    if not blocks_in_column:
        return []

    blocks_in_column.sort(key=itemgetter("top", "x0"))
    final_logical_blocks = []
    is_cjk = detected_lang in ["zh", "ja", "ko"]
    i = 0
    while i < len(blocks_in_column):
        current_block = blocks_in_column[i]
        merged_block_candidate = current_block.copy()

        # Initialize flags that track the nature of the block
        merged_block_candidate["_is_line_wrapped"] = False
        merged_block_candidate["_is_intentional_newline"] = False
        merged_block_candidate["_is_paragraph_start"] = True # Assume true until proven otherwise
        merged_block_candidate["_is_descriptive_continuation_of_numbered_heading"] = False
        merged_block_candidate["_exclude_from_outline_classification"] = False
        merged_block_candidate["_is_body_paragraph_candidate"] = False

        j = i + 1
        while j < len(blocks_in_column):
            next_block = blocks_in_column[j]

            if next_block["page"] != merged_block_candidate["page"]:
                break

            vertical_gap = next_block["top"] - merged_block_candidate["bottom"]
            x_diff = next_block["x0"] - merged_block_candidate["x0"]
            
            # Conditions for merging:
            is_same_line_continuation = (vertical_gap <= typical_line_spacing_threshold + VERTICAL_GAP_TOLERANCE_MERGE_NEGATIVE) and \
                                         abs(x_diff) < X_ALIGN_TOLERANCE_MERGE and \
                                         abs(next_block.get("font_size", 0.0) - merged_block_candidate.get("font_size", 0.0)) < FONT_SIZE_TOLERANCE_MERGE and \
                                         next_block.get("font_name", "").split('+')[-1] == merged_block_candidate.get("font_name", "").split('+')[-1]

            is_potential_paragraph_continuation = False
            current_text_stripped = merged_block_candidate["text"].strip()
            next_text_stripped = next_block["text"].strip()

            # Sentence ending check: language-aware
            ends_sentence_prev = False
            if is_cjk:
                if CJK_SENTENCE_END_PUNCTUATION.search(current_text_stripped):
                    ends_sentence_prev = True
            else: # English/Latin script
                if re.search(r'[.?!]\s*$', current_text_stripped):
                    ends_sentence_prev = True

            # If current block doesn't end a sentence, and next block is aligned, similar font, and starts lowercase (for non-CJK) or any non-whitespace for CJK
            if not ends_sentence_prev and \
               (abs(x_diff) < x_tolerance_alignment or (next_block["x0"] > merged_block_candidate["x0"] and next_block["x0"] < merged_block_candidate["x0"] + x_tolerance_alignment * 2)) and \
               abs(next_block.get("font_size", 0.0) - merged_block_candidate.get("font_size", 0.0)) < FONT_SIZE_TOLERANCE_MERGE and \
               vertical_gap > VERTICAL_GAP_TOLERANCE_MERGE_NEGATIVE and vertical_gap < paragraph_break_threshold:
                
                if is_cjk: # For CJK, just check if it's not empty, doesn't rely on case
                    if next_text_stripped:
                        is_potential_paragraph_continuation = True
                else: # For non-CJK, check if it starts lowercase or is a digit/opening bracket
                    if next_text_stripped and (next_text_stripped[0].islower() or next_text_stripped[0].isdigit() or next_text_stripped[0] in ['(', '[', '{']):
                        is_potential_paragraph_continuation = True
            
            # Special case: Current block ends with hyphen
            ends_with_hyphen = current_text_stripped.endswith('-')

            # Special case: Unclosed parenthesis/bracket
            has_unclosed = _has_unclosed_parentheses_brackets(current_text_stripped)
            next_closes_bracket = has_unclosed and re.search(r'[\)\]\}\)\]｝]', next_text_stripped) # Including CJK closing brackets

            # Special case: Descriptive continuation of numbered/bulleted list item
            is_desc_continuation = False
            # Check if current starts with bullet/number AND isn't a long paragraph (by word count)
            # AND next block is slightly indented or same alignment AND similar font
            # AND previous block didn't end a sentence AND next doesn't start with new bullet/number
            # AND vertical gap is small (not a paragraph break)
            if merged_block_candidate.get("starts_with_number_or_bullet", False) and \
               (len(current_text_stripped.split()) < 20 if not is_cjk else len(current_text_stripped) < 40) and \
               (abs(x_diff) < x_tolerance_alignment or (next_block["x0"] > merged_block_candidate["x0"] + 5 and next_block["x0"] < merged_block_candidate["x0"] + x_tolerance_alignment * 3)) and \
               abs(next_block.get("font_size", 0.0) - merged_block_candidate.get("font_size", 0.0)) < FONT_SIZE_TOLERANCE_MERGE and \
               not ends_sentence_prev and \
               not re.match(r"^\s*(?:\d+(\.\d+)*[\s.)\]}]?|[A-Z][.)\]}]?\s*|[ivxlcdm]+\s*[.)\]]?\s*|[•*○■●►▼►‣—+・※々〄【\-/]|\s*[一二三四五六七八九十百千万億兆甲乙丙丁あいうえおかきくけこ]+)\s*$", next_text_stripped, re.IGNORECASE) and \
               vertical_gap < paragraph_break_threshold: # Must be within typical line spacing or slightly more
                is_desc_continuation = True
                merged_block_candidate["_is_descriptive_continuation_of_numbered_heading"] = True


            should_merge_this_iteration = False
            if is_same_line_continuation or ends_with_hyphen or next_closes_bracket or is_potential_paragraph_continuation or is_desc_continuation:
                should_merge_this_iteration = True
            
            if should_merge_this_iteration:
                if len(merged_block_candidate["text"]) + len(next_block["text"]) > 1000:
                    break # Avoid creating excessively long blocks, likely errors

                # Determine separator
                separator = " "
                if ends_with_hyphen:
                    merged_block_candidate["text"] = merged_block_candidate["text"].strip()[:-1] 
                    separator = ""
                # No space needed before punctuation (handle CJK too)
                elif re.match(r'^[\s]*(?:\,|\.|\!|\?|\:|\;|\)|\\]|\]|\}|\uff0c|\u3002|\uff1a|\uff1b|\uff01|\uff1f)$', next_text_stripped): 
                    separator = "" 
                # No space needed after opening bracket (handle CJK too)
                elif re.match(r'[\( \[ \{ （ 【 「 『]$', current_text_stripped):
                    separator = ""

                merged_block_candidate["text"] = (merged_block_candidate["text"] + separator + next_block["text"]).strip()
                merged_block_candidate["bottom"] = max(merged_block_candidate["bottom"], next_block["bottom"])
                merged_block_candidate["height"] = merged_block_candidate["bottom"] - merged_block_candidate["top"]
                merged_block_candidate["x0"] = min(merged_block_candidate["x0"], next_block["x0"]) 
                merged_block_candidate["x1"] = max(merged_block_candidate.get("x1", merged_block_candidate["x0"] + merged_block_candidate["width"]), next_block.get("x1", next_block["x0"] + next_block["width"]))
                merged_block_candidate["width"] = merged_block_candidate["x1"] - merged_block_candidate["x0"]
                merged_block_candidate["font_size"] = max(merged_block_candidate["font_size"], next_block.get("font_size", 0.0)) 
                merged_block_candidate["is_bold"] = merged_block_candidate.get("is_bold", False) or next_block.get("is_bold", False)
                merged_block_candidate["is_italic"] = merged_block_candidate.get("is_italic", False) or next_block.get("is_italic", False)
                merged_block_candidate["line_height"] = max(merged_block_candidate.get("line_height", 0), next_block.get("line_height", 0), merged_block_candidate["height"])
                
                # Update line feature flags based on the last merged block
                merged_block_candidate["_is_line_wrapped"] = next_block.get("_is_line_wrapped", False)
                merged_block_candidate["_is_intentional_newline"] = next_block.get("_is_intentional_newline", False)
                merged_block_candidate["_is_paragraph_start"] = next_block.get("_is_paragraph_start", False)
                
                j += 1
            else:
                # If we don't merge, determine the line change type for the next block
                vertical_gap_from_prev = next_block["top"] - merged_block_candidate["bottom"]
                x_diff_from_prev = next_block["x0"] - merged_block_candidate["x0"]

                # Determine if the *current* merged block is likely to end a paragraph.
                ends_sentence_current_merged = False
                if is_cjk:
                    if CJK_SENTENCE_END_PUNCTUATION.search(merged_block_candidate["text"].strip()):
                        ends_sentence_current_merged = True
                else:
                    if re.search(r'[.?!]\s*$', merged_block_candidate["text"].strip()):
                        ends_sentence_current_merged = True

                if ends_sentence_current_merged or \
                   vertical_gap_from_prev >= paragraph_break_threshold or \
                   abs(x_diff_from_prev) > x_tolerance_alignment * 2:
                    
                    next_block["_is_intentional_newline"] = True
                    next_block["_is_paragraph_start"] = True
                    next_block["_is_line_wrapped"] = False
                else: # It's a soft break within a paragraph
                    next_block["_is_intentional_newline"] = False 
                    next_block["_is_paragraph_start"] = False
                    next_block["_is_line_wrapped"] = True 
                
                break # Stop merging

        # Determine if this merged block is a "body paragraph candidate"
        num_words_merged_body = len(merged_block_candidate["text"].split()) 
        # Adjust thresholds for CJK
        min_words_for_body = 15
        if is_cjk:
            min_words_for_body = 30 

        if num_words_merged_body > min_words_for_body and \
           merged_block_candidate.get("font_size_ratio_to_common", 1.0) > 0.9 and \
           merged_block_candidate.get("font_size_ratio_to_common", 1.0) < 1.15 and \
           not merged_block_candidate.get("is_bold", False) and \
           abs(merged_block_candidate.get("relative_x0_to_common", 0)) < 20: 
            merged_block_candidate["_is_body_paragraph_candidate"] = True
            # If it's a long body paragraph, exclude it from outline classification
            if num_words_merged_body > min_words_for_body * 1.5: 
                merged_block_candidate["_exclude_from_outline_classification"] = True

        final_logical_blocks.append(merged_block_candidate)
        i = j
    
    return final_logical_blocks

def filter_blocks_for_classification(logical_blocks: List[Dict[str, Any]], detected_lang: str) -> List[Dict[str, Any]]:
    """
    PHASE 1: Very permissive filtering - let all meaningful blocks through initially.
    Only filter out absolute garbage (header/footers, empty, purely decorative content).
    Real selection happens later in the classification phase.
    """
    filtered_blocks = []
    for block in logical_blocks:
        cleaned_text = block["text"].strip()
        
        # --- Hard Prune (only absolute garbage) ---
        # 1. Drop header-footer 
        if block.get("is_header_footer", False):
            continue

        # 2. Drop empty blocks or blocks with very little content that's purely whitespace
        if not cleaned_text or len(cleaned_text) < 1:
            continue

        # 3. Only filter out purely symbolic content (be very permissive)
        if re.fullmatch(r'[\s\-—_•*●■]*', cleaned_text) and len(set(cleaned_text.replace(" ", ""))) < 2:
            continue
            
        # 4. Filter out pure punctuation/symbols only
        if re.fullmatch(r'[^\w\s]*', cleaned_text):
            continue

        # EVERYTHING ELSE PASSES - let classification phase decide
        filtered_blocks.append(block)
    return filtered_blocks


def calculate_all_features(blocks: List[Dict[str, Any]], page_dimensions: Dict[int, Dict[str, float]], 
                           detected_lang: str = "und", nlp_model: Optional[Any] = None) -> Tuple[List[Dict[str, Any]], float]:
    """
    Calculates intrinsic and contextual features for all blocks.
    Assumes blocks are already sorted by page, then top, then x0.
    Uses NLP model for more accurate word counting for non-CJK languages.
    """
    if not blocks:
        return [], DEFAULT_MEDIAN_FONT_SIZE

    all_font_sizes = [block_item["font_size"] for block_item in blocks if block_item.get("font_size") is not None and block_item["font_size"] > 0]
    
    try:
        most_common_font_size = statistics.median(all_font_sizes) if all_font_sizes else DEFAULT_MEDIAN_FONT_SIZE
    except statistics.StatisticsError:
        most_common_font_size = all_font_sizes[0] if all_font_sizes else DEFAULT_MEDIAN_FONT_SIZE
    if most_common_font_size == 0:
        most_common_font_size = DEFAULT_MEDIAN_FONT_SIZE

    blocks_by_page = collections.defaultdict(list) 
    for block_item in blocks:
        blocks_by_page.setdefault(block_item["page"], []).append(block_item)
    
    page_layout_info = {}
    for page_num, page_blocks_list in blocks_by_page.items():
        if not page_blocks_list: continue 
        min_x0_page = min(b["x0"] for b in page_blocks_list)
        # Using 95th percentile for max_x1 to be more robust against outliers
        all_x1s = [b["x0"] + b["width"] for b in page_blocks_list]
        max_x1_page = np.percentile(all_x1s, 95) if all_x1s else page_dimensions.get(page_num, {}).get("width", 595.0)

        # Using 25th percentile for avg_x0 of content blocks as left alignment is common
        content_x0s = [b["x0"] for b in page_blocks_list if not b.get("is_header_footer", False) and b["text"].strip()]
        avg_x0_page = np.percentile(content_x0s, 25) if content_x0s else min_x0_page 

        page_layout_info[page_num] = {
            "min_x0": min_x0_page,
            "max_x1": max_x1_page,
            "avg_x0": avg_x0_page,
        }
        if page_num in page_dimensions:
            page_layout_info[page_num]["page_width"] = page_dimensions[page_num]["width"]
            page_layout_info[page_num]["page_height"] = page_dimensions[page_num]["height"]
        else: # Default A4 dimensions if not provided
            page_layout_info[page_num]["page_width"] = 595.0 
            page_layout_info[page_num]["page_height"] = 842.0 

    processed_blocks = []
    unique_font_sizes_sorted = sorted(list(set(s for s in all_font_sizes if s > 0)), reverse=True) 
    font_size_rank_map = {size: rank for rank, size in enumerate(unique_font_sizes_sorted)}
    
    is_cjk = detected_lang in ["zh", "ja", "ko"]

    # Pre-process texts with NLP for word count if model is provided and not CJK
    nlp_docs = {}
    if nlp_model and not is_cjk and hasattr(nlp_model, 'pipe') and hasattr(nlp_model, 'tokenizer'):
        texts_to_process = [block["text"] for block in blocks]
        try:
            for i, doc in enumerate(nlp_model.pipe(texts_to_process)):
                nlp_docs[blocks[i]["text"]] = doc
        except Exception as e:
            print(f"Warning: NLP pipe failed during feature calculation: {e}. Falling back to split() for word count.")
            nlp_docs = {} # Clear nlp_docs to force fallback

    for i, block_orig in enumerate(blocks):
        features = block_orig.copy() 

        if features.get("font_size") is None or features["font_size"] <= 0:
            features["font_size"] = most_common_font_size

        features["font_size_ratio_to_common"] = features["font_size"] / most_common_font_size
        features["font_size_deviation_from_common"] = features["font_size"] - most_common_font_size
        features["font_size_rank"] = font_size_rank_map.get(block_orig.get("font_size"), len(unique_font_sizes_sorted))

        features["lang"] = detected_lang

        cleaned_text = features["text"].strip()
        
        # is_all_caps: Recalculate strictly for non-CJK (needs at least 2 words)
        features["is_all_caps"] = False
        if not is_cjk and len(cleaned_text.split()) >= 2 and cleaned_text.isupper() and any(c.isalpha() for c in cleaned_text):
            features["is_all_caps"] = True
        
        # num_words: Use NLP tokenizer for non-CJK, character count for CJK
        if is_cjk:
            features["num_words"] = len(cleaned_text) # For CJK, word count is often character count
        elif cleaned_text in nlp_docs:
            features["num_words"] = len(nlp_docs[cleaned_text]) # Use spaCy's token count
        else: # Fallback if no NLP model or text not processed by pipe
            features["num_words"] = len(cleaned_text.split()) # Basic split for other cases


        features["line_length"] = len(cleaned_text) 

        # starts_with_number_or_bullet: Language-aware regex for complex patterns
        features["starts_with_number_or_bullet"] = bool(
            re.match(r"^\s*(?:"
                     r"\d+(\.\d+)*[\s.)\]}]?|"          # Western numbers (1., 1.1)
                     r"[A-Z][.)\]}]?\s*|[ivxlcdm]+\s*[.)\]]?\s*|"         # Capital letters (A.) / Roman numerals (I.)
                     r"[•*○■●►▼►‣—+・※々〄【\-/]\s*|"    # Common Western/Japanese bullets/list markers
                     r"[一二三四五六七八九十百千万億兆甲乙丙丁]\s*[.)\]}]?|" # Japanese numbers/stems
                     r"[あいうえおかきくけこ]\s*[.)\]}]?" # Japanese hiragana lists
                     r")", cleaned_text, re.IGNORECASE)
        )
        
        # Check for short lines relative to page width, not just character count
        page_info = page_layout_info.get(features["page"])
        page_width = page_info.get("page_width", 595.0) if page_info else 595.0
        # Adjust num_words threshold for CJK for "short line"
        num_words_short_line_threshold = 15
        if is_cjk:
            num_words_short_line_threshold = 30 # CJK often has higher char counts for short lines

        features["is_short_line"] = (features["width"] / page_width < 0.5) and (features["num_words"] < num_words_short_line_threshold)

        prev_block = blocks[i-1] if i > 0 and blocks[i-1]["page"] == features["page"] else None
        next_block = blocks[i+1] if i < len(blocks) - 1 and blocks[i+1]["page"] == features["page"] else None

        features["is_first_on_page"] = (prev_block is None) or (prev_block["page"] != features["page"])
        features["is_last_on_page"] = (next_block is None) or (next_block["page"] != features["page"])

        # Calculate gaps and x-diffs
        features["prev_font_size"] = prev_block["font_size"] if prev_block else 0
        features["prev_y_gap"] = features["top"] - prev_block["bottom"] if prev_block else 0
        features["prev_x_diff"] = features["x0"] - prev_block["x0"] if prev_block else 0

        features["next_font_size"] = next_block["font_size"] if next_block else 0
        features["next_y_gap"] = next_block["top"] - features["bottom"] if next_block else 0
        features["next_x_diff"] = next_block["x0"] - features["x0"] if next_block else 0
        
        # Add gap features for vertical separation check
        features["gap_before_block"] = features["prev_y_gap"]
        features["gap_after_block"] = features["next_y_gap"]
        
        # Use line_height for dynamic gap analysis from merged blocks
        current_block_height_for_gap = features.get("line_height", features.get("height", most_common_font_size * 1.2))

        features["is_preceded_by_larger_gap"] = features["prev_y_gap"] > (current_block_height_for_gap * 1.5) and features["prev_y_gap"] < (current_block_height_for_gap * 4.0) 
        features["is_followed_by_larger_gap"] = features["next_y_gap"] > (current_block_height_for_gap * 1.5) and features["next_y_gap"] < (current_block_height_for_gap * 4.0)

        features["is_followed_by_smaller_text"] = features["next_font_size"] > 0 and features["next_font_size"] < features["font_size"] * 0.9

        # Redefine `is_smaller_than_predecessor_and_not_body` to be more focused on heading patterns
        features["is_smaller_than_predecessor_and_not_body"] = False
        if prev_block and features["font_size"] < prev_block["font_size"] * 0.9 and \
           features["font_size_ratio_to_common"] > 0.95 and \
           not prev_block.get("is_bold", False) and \
           len(prev_block["text"].strip()) > 10 and \
           not (CJK_SENTENCE_END_PUNCTUATION.search(prev_block["text"].strip()) if is_cjk else re.search(r'[.?!]$', prev_block["text"].strip())) and \
           abs(features["x0"] - prev_block["x0"]) < X_ALIGN_TOLERANCE_MERGE * 2: 
            features["is_smaller_than_predecessor_and_not_body"] = True

        # Layout features
        if page_info:
            block_center_x = features["x0"] + features["width"] / 2
            page_center_x = page_width / 2
            features["is_centered"] = abs(block_center_x - page_center_x) < (page_width * 0.05) 

            features["x0_normalized"] = features["x0"] / page_width
            features["relative_x0_to_common"] = features["x0"] - page_info["avg_x0"] if page_info.get("avg_x0") else 0
        else:
            features["is_centered"] = False
            features["x0_normalized"] = features["x0"] / 595.0 
            features["relative_x0_to_common"] = 0.0 
        
        processed_blocks.append(features)

    return processed_blocks, most_common_font_size


def dynamic_thresholds(all_font_sizes: List[float], most_common_font_size: float) -> Dict[str, float]:
    """
    Calculates dynamic font size thresholds based on the distribution of font sizes in the document.
    Prioritizes distinct large font sizes.
    """
    if not all_font_sizes or most_common_font_size == 0:
        return {"H1": 16.0, "H2": 14.0, "H3": 12.0, "H4": 11.0} 

    # Filter out extreme outliers, focus on sizes relevant for text/headings
    filtered_sizes = [s for s in all_font_sizes if most_common_font_size * 0.7 < s < most_common_font_size * 3.0]
    if not filtered_sizes:
        filtered_sizes = all_font_sizes 

    unique_sorted_sizes = sorted(list(set(filtered_sizes)), reverse=True) 
    if not unique_sorted_sizes:
        return {"H1": most_common_font_size + 5, "H2": most_common_font_size + 3, "H3": most_common_font_size + 1, "H4": most_common_font_size + 0.5}

    thresholds = {}
    
    # Identify distinct heading-like font sizes
    candidate_heading_sizes = [s for s in unique_sorted_sizes if s >= most_common_font_size * 1.05] 
    candidate_heading_sizes = sorted(list(set(candidate_heading_sizes)), reverse=True) # Ensure unique and sorted large fonts

    if len(candidate_heading_sizes) > 0:
        thresholds["H1"] = candidate_heading_sizes[0]
        current_h_level = 2
        for i in range(1, len(candidate_heading_sizes)):
            prev_size = candidate_heading_sizes[i-1]
            current_size = candidate_heading_sizes[i]
            # A significant drop in font size suggests a new level
            if (prev_size - current_size) >= 0.75 and current_size >= most_common_font_size * 1.05: 
                if current_h_level <= 4:
                    thresholds[f"H{current_h_level}"] = current_size
                    current_h_level += 1
                else:
                    break 

    # Fill in any missing thresholds with reasonable defaults relative to higher levels or common font size
    h_keys = ["H1", "H2", "H3", "H4"]
    for i in range(len(h_keys)):
        current_key = h_keys[i]
        if current_key not in thresholds:
            if i == 0: # H1 not found
                thresholds[current_key] = most_common_font_size + 6.0
            else: # Fill relative to previous heading level
                prev_key = h_keys[i-1]
                thresholds[current_key] = thresholds[prev_key] - (2.0 if current_key == "H2" else 1.5 if current_key == "H3" else 1.0)
        
        # Ensure thresholds don't go below certain multiples of common font size
        if current_key == "H2" and thresholds[current_key] < most_common_font_size * 1.15: thresholds[current_key] = most_common_font_size * 1.15
        if current_key == "H3" and thresholds[current_key] < most_common_font_size * 1.1: thresholds[current_key] = most_common_font_size * 1.1
        if current_key == "H4" and thresholds[current_key] < most_common_font_size * 1.05: thresholds[current_key] = most_common_font_size * 1.05

    # Final sanity check: ensure thresholds are strictly decreasing
    for i in range(1, len(h_keys)):
        if thresholds[h_keys[i]] >= thresholds[h_keys[i-1]]:
            thresholds[h_keys[i]] = thresholds[h_keys[i-1]] - 0.5 
        if thresholds[h_keys[i]] < most_common_font_size: # Ensure no heading is smaller than body text
            thresholds[h_keys[i]] = most_common_font_size + 0.5

    return thresholds


def classify_block_heuristic(block: Dict[str, Any], dynamic_th: Dict[str, float], common_font_size: float, 
                             last_classified_heading: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    PHASE 3: Strict heuristic classification - only select the most heading-like blocks.
    This function now filters more aggressively since Phase 1 was permissive.
    """
    cleaned_text = block["text"].strip()
    detected_lang = block.get("lang", "en")
    
    # PHASE 3: AGGRESSIVE FILTERING - Now be much more selective
    # Define these variables at the beginning
    predominant_script = _get_predominant_script_type(cleaned_text)
    is_cjk = (predominant_script == 'cjk')
    is_non_latin_script = (predominant_script in ['cjk', 'cyrillic', 'arabic', 'devanagari'])
    
    word_count = len(cleaned_text.split())
    char_count = len(cleaned_text)
    
    # 1. IMMEDIATE DISQUALIFIERS (aggressive filtering for Phase 3)
    if block.get("is_header_footer", False) or not cleaned_text:
        return None
        
    # 2. Filter out obvious fragments and noise
    if _is_uninformative_text_strict(cleaned_text, detected_lang=detected_lang):
        return None
    
    # 3. Length constraints for headings by level
    max_heading_lengths = {
        'words': {'H1': 15, 'H2': 20, 'H3': 25, 'H4': 30},
        'chars': {'H1': 80, 'H2': 120, 'H3': 150, 'H4': 200}
    }
    
    # Check if text is too long to be any heading
    if is_cjk:
        if char_count > max_heading_lengths['chars']['H4']:
            return None
    else:
        if word_count > max_heading_lengths['words']['H4'] or char_count > max_heading_lengths['chars']['H4']:
            return None
    
    # 4. Multiple sentences suggest body text
    sentence_endings = len(re.findall(r'[.!?。！？]+', cleaned_text))
    if sentence_endings > 2:
        return None
    
    # 5. PHASE 3: Enhanced fragment detection (more aggressive than Phase 1)
    # Check for repeated word patterns (like "RFP: R RFP: Re")
    words = cleaned_text.split()
    if len(words) >= 2 and len(cleaned_text) <= 40:
        # Check for exact word repetitions
        word_counts = {}
        for word in words:
            clean_word = re.sub(r'[^\w]', '', word.lower())
            if len(clean_word) >= 2:
                word_counts[clean_word] = word_counts.get(clean_word, 0) + 1
        
        # If any word appears multiple times in short text, likely fragmented
        max_word_count = max(word_counts.values()) if word_counts else 0
        if max_word_count >= 2 and len(words) <= 6:
            return None
    
    # 6. Filter out obvious incomplete fragments
    if len(cleaned_text) <= 6:
        incomplete_patterns = [
            r'^(or|and|the|for|to|in|on|at|of|a|an)\s*$',
            r'^[a-zA-Z]{1,2}\s*$',
            r'^(or|and|the|for|to|in|on|at|of)\s+[a-zA-Z]{1,2}\s*$',
        ]
        for pattern in incomplete_patterns:
            if re.match(pattern, cleaned_text, re.IGNORECASE):
                return None
        return None 
    
    if block.get("_exclude_from_outline_classification", False):
        return None

    # Re-check for very short, likely uninformative blocks that might have slipped through
    # Adjusted for CJK/non-Latin scripts - LOOSENED to ensure minimum headings
    min_chars_for_meaningful = 2  # Was more strict
    if is_cjk: min_chars_for_meaningful = 3  # Was 5, now 3
    elif is_non_latin_script: min_chars_for_meaningful = 2  # Was 3, now 2

    # Only filter extremely short text that clearly can't be a heading
    if len(cleaned_text) < min_chars_for_meaningful:
        return None
        
    # Additional filtering for sentence fragments (especially important for Japanese)
    # LOOSENED: Only filter obvious fragments, not potential headings
    if len(cleaned_text) > 3:  # Only apply to longer text
        # Check for repeated prefix patterns (like "RFP: R RFP: Re")
        # ENHANCED: More aggressive detection of fragmented repetitive text
        words = cleaned_text.split()
        if len(words) >= 2 and len(cleaned_text) <= 40:  # Apply to short text with 2+ words
            # Check for exact word repetitions (like "RFP: R RFP:")
            word_counts = {}
            for word in words:
                clean_word = re.sub(r'[^\w]', '', word.lower())  # Remove punctuation
                if len(clean_word) >= 2:  # Only count meaningful word parts
                    word_counts[clean_word] = word_counts.get(clean_word, 0) + 1
            
            # If any word appears multiple times in short text, likely fragmented
            max_word_count = max(word_counts.values()) if word_counts else 0
            if max_word_count >= 2 and len(words) <= 6:
                return None
                
            # Also check for repeated prefixes (like "RFP" appearing multiple times)
            word_prefixes = []
            for word in words:
                if len(word) >= 3:  # Increased from 2 to 3 to be less aggressive
                    prefix = word[:3].lower()  # Use first 3 chars as prefix
                    word_prefixes.append(prefix)
            
            # If we have repeated prefixes in a short text, it's likely fragmented
            if len(word_prefixes) >= 2:  # Only need 2+ for check
                prefix_counts = {}
                for prefix in word_prefixes:
                    prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
                
                # If any prefix appears multiple times in short text, likely fragmented
                max_count = max(prefix_counts.values()) if prefix_counts else 0
                if max_count >= 2 and len(words) <= 5:  # Tightened from 6 to 5 words
                    return None
        
        # Check for very short incomplete fragments (like "or Pr")
        # ENHANCED: More specific patterns
        if len(cleaned_text) <= 6:  # Tightened from 5 to 6
            words_count = len(words) if 'words' in locals() else len(cleaned_text.split())
            # Single words or very short phrases that are likely cut off
            if words_count <= 2 and len(cleaned_text) <= 6:
                # Common incomplete word patterns - more comprehensive
                incomplete_patterns = [
                    r'^(or|and|the|for|to|in|on|at|of|a|an)\s*$',  # Single function words
                    r'^[a-zA-Z]{1,2}\s*$',  # Very short single "words"
                    r'^(or|and|the|for|to|in|on|at|of)\s+[a-zA-Z]{1,2}\s*$',  # Function word + short fragment
                    r'^[a-zA-Z]{1,2}\s+(or|and|the|for|to|in|on|at|of)\s*$',  # Short fragment + function word
                ]
                for pattern in incomplete_patterns:
                    if re.match(pattern, cleaned_text, re.IGNORECASE):
                        return None
        
        # For CJK scripts (Japanese, Chinese, Korean)
        if is_cjk:
            # Filter out fragments that start with particles or don't end properly
            if re.match(r'^[のはがをにでとから]', cleaned_text):  # Common Japanese particles at start
                return None
            # Filter out fragments that end mid-sentence
            if len(cleaned_text) > 8 and not re.search(r'[。！？：；]$', cleaned_text) and re.search(r'[のはがをにでとから]\s*$', cleaned_text):
                return None
        # For Latin scripts
        elif predominant_script == 'latin':
            # Filter out fragments that start mid-sentence
            if cleaned_text[0].islower() and not re.match(r'^(and|or|but|the|a|an|of|in|on|at|to|for)\b', cleaned_text, re.IGNORECASE):
                return None
            # Filter out fragments that end mid-sentence without proper punctuation
            if len(cleaned_text) > 10 and not re.search(r'[.!?:;]$', cleaned_text) and re.search(r'\b(of|the|a|an|and|or|in|on|at|to|for|with|by|from)\s*$', cleaned_text, re.IGNORECASE):
                return None
    
    # If it's a "body paragraph candidate" based on _merge_nearby_blocks_logical logic, it's not a heading
    if block.get("_is_body_paragraph_candidate", False):
        return None
    
    # NEW: Check for vertical separation - headings should be separated from surrounding text
    # A block should have some vertical spacing before/after to be considered a heading
    min_gap_for_heading = block.get("font_size", 12.0) * 0.3  # Minimum gap relative to font size
    
    gap_before = block.get("gap_before_block", 0.0)
    gap_after = block.get("gap_after_block", 0.0)
    
    # If the block has very small gaps both before and after, it's likely inline text, not a heading
    if gap_before < min_gap_for_heading and gap_after < min_gap_for_heading:
        # Exception: if it's bold, larger font, or centered, it might still be a heading
        font_size_ratio = block.get("font_size", 12.0) / common_font_size
        if not (block.get("is_bold", False) or font_size_ratio > 1.2 or block.get("is_centered", False)):
            return None

    # --- Heuristic Weights (tuned for this specific approach) ---
    weights_base = {
        "font_size_prominence": 4.5,
        "is_bold": 5.0,
        "is_centered": 6.0,
        "is_preceded_by_larger_gap": 4.0,
        "is_followed_by_smaller_text": 4.0,
        "starts_with_number_or_bullet": 5.0,
        "is_first_on_page": 3.0,
        "is_all_caps": 1.5,
        "is_short_line": 1.2,
        "length_penalty_factor": -0.4,
        "is_smaller_than_predecessor_and_not_body": 2.0,
        "font_size_ratio_H_boost": 2.0, # Generic boost for font size ratio
        "x0_indent_penalty": -0.8,
        "parent_level_match_boost": 3.0,
        "densely_populated_penalty": -2.0,
        "standalone_line_boost": 3.0
    }

    # Extract features with safe defaults
    font_size = block.get("font_size", common_font_size)
    font_size_ratio = block.get("font_size_ratio_to_common", 1.0)
    is_bold = block.get("is_bold", False)
    is_centered = block.get("is_centered", False)
    is_preceded_by_larger_gap = block.get("is_preceded_by_larger_gap", False)
    is_followed_by_smaller_text = block.get("is_followed_by_smaller_text", False)
    starts_with_number_or_bullet = block.get("starts_with_number_or_bullet", False)
    is_first_on_page = block.get("is_first_on_page", False)
    is_all_caps = block.get("is_all_caps", False)
    is_short_line = block.get("is_short_line", False)
    num_words = block.get("num_words", 0)
    is_smaller_than_predecessor_and_not_body = block.get("is_smaller_than_predecessor_and_not_body", False)
    relative_x0_to_common = block.get("relative_x0_to_common", 0)

    # --- Length Penalty (Language-aware adjustment) ---
    length_penalty = 0
    max_words_for_heading_general = 10
    if is_cjk: 
        max_words_for_heading_general = 30 
    elif is_non_latin_script: 
        max_words_for_heading_general = 15

    if num_words > max_words_for_heading_general:
        length_penalty += (num_words - max_words_for_heading_general) * abs(weights_base["length_penalty_factor"]) * 1.5
    
    max_line_length_chars = 80
    if is_cjk:
        max_line_length_chars = 120 
    elif is_non_latin_script:
        max_line_length_chars = 100

    if block["line_length"] > max_line_length_chars:
        length_penalty += (block["line_length"] - max_line_length_chars) * abs(weights_base["length_penalty_factor"])
    
    # Very high penalty for extremely long blocks that aren't numeric/bulleted and are not large font
    if num_words > (max_words_for_heading_general * 3) and not starts_with_number_or_bullet and font_size_ratio < 1.5:
        length_penalty += 15.0

    # --- Density / Body Text Penalty ---
    densely_populated_penalty = 0
    # If font size is very close to common, and it's not separated by large gaps, and indentation is typical
    if font_size_ratio > 0.95 and font_size_ratio < 1.05 and \
       not is_preceded_by_larger_gap and not is_followed_by_smaller_text and \
       abs(relative_x0_to_common) < 10: 
        densely_populated_penalty = weights_base["densely_populated_penalty"]
    
    # If the block itself was flagged as a body paragraph candidate by the merger, severely penalize
    if block.get("_is_body_paragraph_candidate", False):
        return None 

    level_scores = {"H1": 0.0, "H2": 0.0, "H3": 0.0, "H4": 0.0}

    # Base prominence from font size ratio
    base_prominence_score = (font_size_ratio - 1.0) * weights_base["font_size_prominence"]
    if base_prominence_score < 0: base_prominence_score = 0 

    # --- Calculate scores for each potential heading level (H1-H4) ---

    for level_key in ["H1", "H2", "H3", "H4"]:
        current_level_num = int(level_key[1:])

        score = base_prominence_score * weights_base["font_size_ratio_H_boost"]

        # Strong boost if font size meets dynamic threshold for this level
        if font_size >= dynamic_th.get(level_key, float('inf')) * 0.95:
            score += 10.0 - (current_level_num - 1) * 2.0 

        if is_bold: score += weights_base["is_bold"]
        if is_preceded_by_larger_gap: score += weights_base["is_preceded_by_larger_gap"]
        
        # is_short_line boost (language-aware due to num_words calculation in features)
        if is_short_line: score += weights_base["is_short_line"]

        # H1 specific boosts
        if level_key == "H1":
            if is_centered: score += weights_base["is_centered"] * 2.0 
            if is_first_on_page: score += weights_base["is_first_on_page"] * 2.0
            if is_all_caps and not is_non_latin_script: score += weights_base["is_all_caps"] * 2.0 
            # A block that is truly standalone (large gaps before AND after) is highly likely an H1
            if is_preceded_by_larger_gap and block.get("is_followed_by_larger_gap", False):
                score += weights_base["standalone_line_boost"] * 2.0

        # H2-H4 specific boosts (numbered/bulleted items, smaller text following)
        elif level_key in ["H2", "H3", "H4"]:
            if starts_with_number_or_bullet: score += weights_base["starts_with_number_or_bullet"] * (1.0 + (current_level_num - 1) * 0.5) 
            if is_followed_by_smaller_text: score += weights_base["is_followed_by_smaller_text"] * 1.0
            if is_smaller_than_predecessor_and_not_body: score += weights_base["is_smaller_than_predecessor_and_not_body"] * 1.0

        # --- Contextual Comparison with Last Classified Heading (Parent-Child Logic) ---
        if last_classified_heading:
            last_level_num = int(last_classified_heading["level"][1:])
            # If current block is candidate for next level (e.g., H1 -> H2)
            if current_level_num == last_level_num + 1:
                # Check for relative font size (must be smaller than parent but larger than common)
                if font_size < last_classified_heading["font_size"] * 0.95 and \
                   font_size > common_font_size * 1.05:
                    score += weights_base["parent_level_match_boost"]

                # Check for relative indentation (should be same or slightly indented from parent)
                # Adjusted x0 tolerance for parent-child indentation
                if abs(block["x0"] - last_classified_heading["x0"]) < X_ALIGN_TOLERANCE_MERGE * 1.5 or \
                   (block["x0"] > last_classified_heading["x0"] and block["x0"] < last_classified_heading["x0"] + X_ALIGN_TOLERANCE_MERGE * 3): 
                    score += weights_base["parent_level_match_boost"] * 0.5

            # Penalty if skipping a level (e.g., H1 -> H3) - significant penalty
            if current_level_num > last_level_num + 1:
                score -= weights_base["parent_level_match_boost"] * (current_level_num - (last_level_num + 1)) * 1.5

            # Penalty if current candidate is same level as last, but properties don't match well (e.g., different font size/boldness)
            if current_level_num == last_level_num and \
               (abs(font_size - last_classified_heading["font_size"]) > FONT_SIZE_TOLERANCE_MERGE * 2 or \
                is_bold != last_classified_heading.get("is_bold", False)):
                score -= weights_base["parent_level_match_boost"] * 0.5

        # --- Penalties ---
        score -= length_penalty
        score += densely_populated_penalty # This is a negative weight, so adding it applies a penalty

        # Indentation penalty: if a higher-level heading (H1/H2) is very indented
        # Adjusted indentation thresholds based on page width/common_x0 for robustness
        page_info_current = block.get("page_layout_info", {}) 
        page_width_current = page_info_current.get("page_width", 595.0)
        
        # Penalize if far from left edge for H1/H2, or too far for H3/H4
        if current_level_num <= 2 and relative_x0_to_common > page_width_current * 0.07: 
            score += weights_base["x0_indent_penalty"] * 2.0
        elif current_level_num == 3 and relative_x0_to_common > page_width_current * 0.12: 
             score += weights_base["x0_indent_penalty"] * 1.5
        elif current_level_num == 4 and relative_x0_to_common > page_width_current * 0.2: 
            score += weights_base["x0_indent_penalty"] * 1.0


        level_scores[level_key] = score

    # --- Select Best Level based on Scores and Minimum Confidence ---
    min_confidence = {
        "H1": 15.0, # High confidence needed for H1
        "H2": 10.0,
        "H3": 8.0,
        "H4": 5.0
    }

    best_level = None
    max_score = -1.0
    
    # Iterate from H1 down to H4 to prioritize higher levels
    for level_key in ["H1", "H2", "H3", "H4"]:
        current_score = level_scores[level_key]
        
        # Consider this level only if its score meets its minimum confidence AND
        # it's higher than the best score found so far.
        if current_score >= min_confidence.get(level_key, 0.0) and current_score > max_score:
            best_level = level_key
            max_score = current_score
    
    # Final quality check: If a block is identified as heading but is visually very generic
    if best_level:
        # IMPORTANT: Check if text is too long for the assigned heading level
        if is_cjk:
            if char_count > max_heading_lengths['chars'][best_level]:
                # Try to assign a lower level (longer headings can be H4)
                if best_level == 'H1' and char_count <= max_heading_lengths['chars']['H2']:
                    best_level = 'H2'
                elif best_level in ['H1', 'H2'] and char_count <= max_heading_lengths['chars']['H3']:
                    best_level = 'H3'
                elif best_level in ['H1', 'H2', 'H3'] and char_count <= max_heading_lengths['chars']['H4']:
                    best_level = 'H4'
                else:
                    return None  # Too long for any heading level
        else:
            if word_count > max_heading_lengths['words'][best_level] or char_count > max_heading_lengths['chars'][best_level]:
                # Try to assign a lower level (longer headings can be H4)
                if best_level == 'H1' and (word_count <= max_heading_lengths['words']['H2'] and char_count <= max_heading_lengths['chars']['H2']):
                    best_level = 'H2'
                elif best_level in ['H1', 'H2'] and (word_count <= max_heading_lengths['words']['H3'] and char_count <= max_heading_lengths['chars']['H3']):
                    best_level = 'H3'
                elif best_level in ['H1', 'H2', 'H3'] and (word_count <= max_heading_lengths['words']['H4'] and char_count <= max_heading_lengths['chars']['H4']):
                    best_level = 'H4'
                else:
                    return None  # Too long for any heading level
        
        # Language-aware adjustment for very short headings
        min_words_for_valid_heading = 2
        min_chars_for_valid_heading = 5
        if is_cjk: 
            min_words_for_valid_heading = 5 
            min_chars_for_valid_heading = 10 

        # If it's short, not bold/large, and starts with a simple number/bullet, and it's classified as H1-H3,
        # it might be a false positive (e.g., a simple list item mistaken for a main heading).
        # Use num_words for check, which is language-aware
        if starts_with_number_or_bullet and num_words <= min_words_for_valid_heading and not is_bold and font_size_ratio < 1.15:
            if best_level in ["H1", "H2", "H3"]:
                return None 
        
        # If the determined heading is very short and not bold/large or centered, it's suspect.
        # Use num_words (language-aware) and character length.
        has_any_script_or_digit = False
        if re.search(r'[a-zA-Z0-9]', cleaned_text) or \
           _has_script_chars(cleaned_text, CJK_CHARS_REGEX) or \
           _has_script_chars(cleaned_text, CYRILLIC_CHARS_REGEX) or \
           _has_script_chars(cleaned_text, ARABIC_CHARS_REGEX) or \
           _has_script_chars(cleaned_text, DEVANAGARI_CHARS_REGEX):
            has_any_script_or_digit = True

        if num_words <= 2 and not is_bold and not is_centered and font_size_ratio < 1.2:
            if not has_any_script_or_digit: 
                return None
            if len(cleaned_text) < min_chars_for_valid_heading: 
                return None
        
        # If it has unclosed parentheses/brackets, it's likely a fragmented block, not a clean heading
        if _has_unclosed_parentheses_brackets(cleaned_text):
            return None

    return best_level


def smooth_heading_levels(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Applies post-classification smoothing to correct common hierarchical issues.
    Ensures a logical flow of headings (e.g., H1 -> H2 -> H3, no H1 -> H3 directly),
    and re-evaluates blocks that might have been misclassified or missed.
    """
    if not blocks:
        return []

    smoothed_blocks = []
    page_level_stack: List[Optional[Dict[str, Any]]] = [None, None, None, None]
    last_page = -1

    for block in blocks:
        if block["page"] != last_page:
            page_level_stack = [None, None, None, None]
            last_page = block["page"]

        if block.get("is_header_footer", False) or block.get("_exclude_from_outline_classification", False):
            smoothed_blocks.append(block)
            continue

        original_level = block.get("level")
        
        if original_level:
            level_num_idx = int(original_level[1:]) - 1 

            effective_parent_level_idx = -1
            for l_idx in range(level_num_idx - 1, -1, -1):
                if page_level_stack[l_idx] is not None:
                    effective_parent_level_idx = l_idx
                    break
            
            if effective_parent_level_idx != -1:
                if level_num_idx > effective_parent_level_idx + 1:
                    new_level_num_idx = effective_parent_level_idx + 1
                    block["level"] = f"H{new_level_num_idx + 1}"
                    level_num_idx = new_level_num_idx
            elif level_num_idx > 0: 
                prominence_threshold_ratio = 1.3
                num_words_prominence_threshold = 20
                if block.get("lang") in ["zh", "ja", "ko"]:
                    prominence_threshold_ratio = 1.2 
                    num_words_prominence_threshold = 40 

                if block.get("font_size_ratio_to_common", 1.0) > prominence_threshold_ratio and block.get("is_bold", False) and \
                   block.get("is_short_line", False) and block.get("num_words", 0) < num_words_prominence_threshold:
                    
                    is_first_content_on_page = True
                    for prev_s_block in reversed(smoothed_blocks):
                        if prev_s_block["page"] != block["page"]:
                            break 
                        if prev_s_block.get("level"): 
                            is_first_content_on_page = False
                            break
                        if prev_s_block["text"].strip(): 
                            is_first_content_on_page = False
                            break
                    
                    if is_first_content_on_page and level_num_idx <= 1: 
                         block["level"] = "H1"
                         level_num_idx = 0
                    else: 
                        block["level"] = None 
                        level_num_idx = -1 
                else: 
                    block["level"] = None 
                    level_num_idx = -1 

            if level_num_idx != -1:
                for l in range(level_num_idx + 1, 4):
                    page_level_stack[l] = None
                page_level_stack[level_num_idx] = block
            else:
                for l in range(0, 4):
                    if page_level_stack[l] == block: 
                        page_level_stack[l] = None
                        break
        else:
            block["level"] = None

        smoothed_blocks.append(block)

    return [b for b in smoothed_blocks if b.get("level") is not None]

def run(blocks: List[Dict[str, Any]], page_dimensions: Dict[int, Dict[str, float]], detected_lang: str = "und", nlp_model_for_all_nlp_tasks: Optional[Any] = None) -> List[Dict[str, Any]]:
    """
    Classifies text blocks into heading levels H1-H4 using dynamic thresholds
    and contextual features.
    Accepts blocks and page_dimensions directly (in-memory processing).
    Returns the classified blocks.
    detected_lang: Language code from main.py.
    nlp_model_for_all_nlp_tasks: A loaded spaCy model for text quality checks and tokenization.
    """
    if not blocks:
        print("No blocks to classify.")
        return []

    blocks.sort(key=itemgetter("page", "top", "x0"))

    all_font_sizes_pre = [b.get("font_size", 0.0) for b in blocks if b.get("font_size") > 0]
    mean_font_size_for_merger = statistics.median(all_font_sizes_pre) if all_font_sizes_pre else DEFAULT_MEDIAN_FONT_SIZE
    
    sampled_line_heights_for_merger = []
    for i, block in enumerate(blocks):
        sampled_line_heights_for_merger.append(block.get("line_height", block.get("height", mean_font_size_for_merger * 1.2)))
        if i >= min(200, len(blocks) - 1): 
            break
    
    if sampled_line_heights_for_merger:
        filtered_sampled_line_heights = [lh for lh in sampled_line_heights_for_merger if lh > mean_font_size_for_merger * 0.3 and lh < mean_font_size_for_merger * 3.0]
        if filtered_sampled_line_heights:
            typical_line_spacing = np.percentile(filtered_sampled_line_heights, 25)
            paragraph_spacing = np.percentile(filtered_sampled_line_heights, 75)
        else:
            typical_line_spacing = mean_font_size_for_merger * 0.6
            paragraph_spacing = mean_font_size_for_merger * 1.5
    else:
        typical_line_spacing = mean_font_size_for_merger * 0.6
        paragraph_spacing = mean_font_size_for_merger * 1.5


    print(f"  Merger: Typical Line Spacing: {typical_line_spacing:.2f}, Paragraph Spacing: {paragraph_spacing:.2f}")

    # Pass detected_lang to _merge_nearby_blocks_logical
    logical_blocks = _merge_nearby_blocks_logical(blocks, typical_line_spacing, paragraph_spacing, detected_lang=detected_lang)
    print(f"  After logical merging: {len(logical_blocks)} blocks.")

    # Pass 2: PHASE 1 - Very permissive filtering (let meaningful blocks through)
    phase1_blocks = filter_blocks_for_classification(logical_blocks, detected_lang=detected_lang)
    print(f"  Phase 1 - After permissive filtering: {len(phase1_blocks)} blocks.")

    # Pass 3: Calculate all features for classification. Pass NLP model for num_words.
    blocks_with_features, most_common_font_size = calculate_all_features(phase1_blocks, page_dimensions, detected_lang=detected_lang, nlp_model=nlp_model_for_all_nlp_tasks)
    print(f"  Most common font size: {most_common_font_size:.2f}")

    # NEW: PHASE 2 - Identify guaranteed numbered headings with vertical separation
    guaranteed_headings = identify_numbered_headings_with_separation(blocks_with_features, page_dimensions)
    print(f"  Phase 2 - Guaranteed numbered headings found: {len(guaranteed_headings)}")
    
    # Mark guaranteed headings in the main blocks list
    guaranteed_texts = {h['text'].strip() for h in guaranteed_headings}
    for block in blocks_with_features:
        if block['text'].strip() in guaranteed_texts:
            block['is_guaranteed_heading'] = True
            block['guaranteed_level'] = 'H1'

    # Pass 4: Determine dynamic font size thresholds for H1-H4
    dynamic_thresholds_map = dynamic_thresholds(
        [b["font_size"] for b in blocks_with_features if b["font_size"] is not None], most_common_font_size
    )
    print(f"  Dynamically determined heading thresholds: {dynamic_thresholds_map}")

    # NEW: Pass 4.5: Detect document heading patterns
    pattern_info = detect_document_heading_patterns(blocks_with_features)
    print(f"  Pattern detection: {pattern_info['dominant_pattern']} (confidence: {pattern_info['confidence']:.2f})")

    # Pass 5: PHASE 3 - Classify blocks with priority system
    classified_blocks_output = []
    last_classified_heading_on_page: Dict[int, Optional[Dict[str, Any]]] = collections.defaultdict(lambda: None)
    
    guaranteed_count = 0
    pattern_based_count = 0
    heuristic_based_count = 0

    for block in blocks_with_features:
        last_heading = last_classified_heading_on_page[block["page"]]
        
        level = None
        classification_method = "none"
        
        # PRIORITY 1: Guaranteed numbered headings with separation
        if block.get('is_guaranteed_heading', False):
            level = block.get('guaranteed_level', 'H1')
            classification_method = "guaranteed"
            guaranteed_count += 1
        
        # PRIORITY 2: Pattern-based classification if patterns are strong
        elif pattern_info['confidence'] >= 0.5:
            level = classify_block_by_pattern(block, pattern_info)
            if level:
                classification_method = "pattern"
                pattern_based_count += 1
        
        # PRIORITY 3: Heuristic classification (now with stricter filtering)
        if not level:
            level = classify_block_heuristic(block, dynamic_thresholds_map, most_common_font_size, last_heading)
            if level:
                classification_method = "heuristic"
                heuristic_based_count += 1

        if level:
            block["level"] = level
            block["classification_method"] = classification_method  # For debugging
            last_classified_heading_on_page[block["page"]] = block
        else:
            block["level"] = None
            block["classification_method"] = "none"
        
        classified_blocks_output.append(block)

    print(f"  Phase 3 - Classification: {guaranteed_count} guaranteed, {pattern_based_count} pattern-based, {heuristic_based_count} heuristic-based headings.")

    # Pass 6: Smooth heading levels for hierarchical consistency
    smoothed_blocks = smooth_heading_levels(classified_blocks_output)
    print(f"  After smoothing: {sum(1 for b in smoothed_blocks if b.get('level'))} headings.")

    # Pass 7: Ensure minimum headings per page (1-2 headings per page)
    # AGGRESSIVE: Check if we need to be more lenient overall
    total_pages = len(set(block.get('page', 0) for block in classified_blocks_output))
    total_headings = sum(1 for b in smoothed_blocks if b.get('level'))
    avg_headings_per_page = total_headings / max(total_pages, 1)
    
    if avg_headings_per_page < 1.5:  # If we're short on headings overall
        print(f"  WARNING: Only {avg_headings_per_page:.1f} headings per page. Being more lenient...")
        # Re-run classification with more lenient standards
        for block in classified_blocks_output:
            if not block.get('level'):  # For blocks that weren't classified
                # Try a much more lenient classification
                lenient_level = classify_block_lenient(block, dynamic_thresholds_map, most_common_font_size)
                if lenient_level:
                    block['level'] = lenient_level
                    block['classification_method'] = 'lenient_fallback'
        
        # Re-smooth with the new headings
        smoothed_blocks = smooth_heading_levels(classified_blocks_output)
    
    # NEW: Pass 8: NLP-based heading refinement and correction
    if nlp_model_for_all_nlp_tasks:
        print("  Applying NLP-based heading refinement...")
        nlp_refined_blocks = refine_headings_with_nlp(smoothed_blocks, nlp_model_for_all_nlp_tasks, detected_lang)
        print(f"  After NLP refinement: {sum(1 for b in nlp_refined_blocks if b.get('level'))} headings.")
    else:
        print("  Skipping NLP refinement (no model provided)")
        nlp_refined_blocks = smoothed_blocks
    
    final_blocks = ensure_minimum_headings_per_page(nlp_refined_blocks, classified_blocks_output)
    print(f"  After minimum headings enforcement: {sum(1 for b in final_blocks if b.get('level'))} final headings.")

    return final_blocks

def refine_headings_with_nlp(heading_blocks: List[Dict[str, Any]], 
                            nlp_model: Any, 
                            detected_lang: str) -> List[Dict[str, Any]]:
    """
    Use NLP to analyze and refine heading candidates:
    1. Fix text fragments and merge incomplete headings
    2. Improve heading quality through linguistic analysis
    3. Correct heading levels based on semantic structure
    4. Filter out non-heading content using NLP features
    """
    if not nlp_model or not heading_blocks:
        return heading_blocks
    
    refined_blocks = []
    is_cjk = detected_lang in ["zh", "ja", "ko"]
    
    # Group blocks by page for context-aware processing
    pages = {}
    for block in heading_blocks:
        page = block.get('page', 0)
        if page not in pages:
            pages[page] = []
        pages[page].append(block)
    
    for page_num, page_blocks in pages.items():
        print(f"    Processing page {page_num} with {len(page_blocks)} blocks...")
        
        # Separate headings from non-headings
        headings = [b for b in page_blocks if b.get('level')]
        non_headings = [b for b in page_blocks if not b.get('level')]
        
        # NLP analysis of heading candidates
        analyzed_headings = []
        for heading in headings:
            analysis = analyze_heading_with_nlp(heading, nlp_model, is_cjk)
            
            # Decide whether to keep, modify, or reject the heading
            if analysis['is_valid_heading']:
                # Apply NLP corrections
                corrected_heading = apply_nlp_corrections(heading, analysis)
                analyzed_headings.append(corrected_heading)
            else:
                # Convert invalid heading back to non-heading
                heading['level'] = None
                heading['classification_method'] = 'nlp_rejected'
                heading['nlp_rejection_reason'] = analysis['rejection_reason']
                non_headings.append(heading)
        
        # Try to merge fragmented headings
        merged_headings = merge_fragmented_headings_nlp(analyzed_headings, nlp_model, is_cjk)
        
        # Add refined headings and non-headings back
        refined_blocks.extend(merged_headings)
        refined_blocks.extend(non_headings)
    
    return refined_blocks

def analyze_heading_with_nlp(heading: Dict[str, Any], nlp_model: Any, is_cjk: bool) -> Dict[str, Any]:
    """
    Use NLP to analyze if a text block is truly a heading and provide corrections.
    """
    text = heading.get('text', '').strip()
    analysis = {
        'is_valid_heading': True,
        'rejection_reason': None,
        'corrections': {},
        'semantic_features': {},
        'suggested_level': heading.get('level')
    }
    
    if not text or len(text) < 2:
        analysis['is_valid_heading'] = False
        analysis['rejection_reason'] = 'empty_or_too_short'
        return analysis
    
    try:
        # Process text with NLP model
        doc = nlp_model(text)
        
        # Extract linguistic features
        tokens = [token for token in doc if not token.is_space]
        
        analysis['semantic_features'] = {
            'token_count': len(tokens),
            'has_verbs': any(token.pos_ == 'VERB' for token in tokens),
            'has_nouns': any(token.pos_ == 'NOUN' for token in tokens),
            'is_sentence': any(token.pos_ == 'VERB' and not token.dep_ == 'aux' for token in tokens),
            'entity_count': len(doc.ents),
            'entities': [ent.label_ for ent in doc.ents],
            'is_complete_sentence': text.rstrip().endswith('.') or text.rstrip().endswith('!') or text.rstrip().endswith('?'),
            'starts_with_capital': text[0].isupper() if text else False,
            'word_count': len([t for t in tokens if t.is_alpha])
        }
        
        # Heading validation rules based on NLP features
        features = analysis['semantic_features']
        
        # Rule 1: Complete sentences are usually body text, not headings
        if features['is_complete_sentence'] and features['has_verbs'] and features['word_count'] > 8:
            if not (heading.get('font_size', 12) / 12 > 1.3 or heading.get('is_bold', False)):
                analysis['is_valid_heading'] = False
                analysis['rejection_reason'] = 'complete_sentence_body_text'
                return analysis
        
        # Rule 2: Very short fragments without meaning
        if features['word_count'] <= 2 and not features['has_nouns'] and not features['entity_count']:
            # Check if it's just function words
            function_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with'}
            if all(token.text.lower() in function_words for token in tokens if token.is_alpha):
                analysis['is_valid_heading'] = False
                analysis['rejection_reason'] = 'only_function_words'
                return analysis
        
        # Rule 3: Text that's clearly mid-sentence
        if (features['word_count'] > 3 and 
            not features['starts_with_capital'] and 
            not any(token.text in ['and', 'or', 'but'] for token in tokens[:2])):
            analysis['is_valid_heading'] = False
            analysis['rejection_reason'] = 'mid_sentence_fragment'
            return analysis
        
        # Rule 4: Very long text without strong formatting
        if (features['word_count'] > 15 and 
            not (heading.get('font_size', 12) / 12 > 1.2) and 
            not heading.get('is_bold', False) and
            not heading.get('is_centered', False)):
            analysis['is_valid_heading'] = False
            analysis['rejection_reason'] = 'too_long_without_formatting'
            return analysis
        
        # Rule 5: Suggest better heading levels based on content
        if features['entity_count'] > 0 or features['has_nouns']:
            if features['word_count'] <= 5 and (heading.get('is_bold', False) or heading.get('font_size', 12) > 14):
                analysis['suggested_level'] = 'H1'
            elif features['word_count'] <= 10:
                analysis['suggested_level'] = 'H2'
            else:
                analysis['suggested_level'] = 'H3'
        
        # Rule 6: Look for common heading patterns
        text_lower = text.lower()
        heading_indicators = ['introduction', 'conclusion', 'overview', 'summary', 'background', 'methodology', 'results', 'discussion']
        if any(indicator in text_lower for indicator in heading_indicators):
            analysis['suggested_level'] = 'H1'  # These are typically major section headings
        
    except Exception as e:
        print(f"    NLP analysis failed for '{text[:50]}...': {e}")
        # On NLP failure, be conservative but don't reject
        pass
    
    return analysis

def apply_nlp_corrections(heading: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply NLP-suggested corrections to the heading.
    """
    corrected = heading.copy()
    
    # Apply level correction if suggested
    if analysis.get('suggested_level') and analysis['suggested_level'] != heading.get('level'):
        corrected['level'] = analysis['suggested_level']
        corrected['classification_method'] = 'nlp_corrected'
        corrected['original_level'] = heading.get('level')
    
    # Store NLP analysis for debugging
    corrected['nlp_analysis'] = analysis['semantic_features']
    
    return corrected

def merge_fragmented_headings_nlp(headings: List[Dict[str, Any]], nlp_model: Any, is_cjk: bool) -> List[Dict[str, Any]]:
    """
    Use NLP to identify and merge fragmented headings that should be combined.
    """
    if len(headings) < 2:
        return headings
    
    merged_headings = []
    i = 0
    
    while i < len(headings):
        current = headings[i]
        
        # Look ahead to see if next heading(s) should be merged
        merge_candidates = [current]
        j = i + 1
        
        while j < len(headings) and j < i + 3:  # Look at most 3 blocks ahead
            next_heading = headings[j]
            
            # Only merge if they're on the same page and close together
            if (next_heading.get('page') == current.get('page') and
                abs(next_heading.get('top', 0) - current.get('bottom', 0)) < 50):  # Within 50 pixels
                
                # Check if they should be merged using NLP
                if should_merge_headings_nlp(current, next_heading, nlp_model, is_cjk):
                    merge_candidates.append(next_heading)
                    j += 1
                else:
                    break
            else:
                break
        
        # If we found candidates to merge, merge them
        if len(merge_candidates) > 1:
            merged = merge_heading_blocks(merge_candidates)
            merged['classification_method'] = 'nlp_merged'
            merged_headings.append(merged)
            i = j  # Skip all merged blocks
        else:
            merged_headings.append(current)
            i += 1
    
    return merged_headings

def should_merge_headings_nlp(heading1: Dict[str, Any], heading2: Dict[str, Any], nlp_model: Any, is_cjk: bool) -> bool:
    """
    Use NLP to determine if two headings should be merged.
    """
    text1 = heading1.get('text', '').strip()
    text2 = heading2.get('text', '').strip()
    
    if not text1 or not text2:
        return False
    
    try:
        # Combine texts and analyze
        combined_text = f"{text1} {text2}"
        doc_combined = nlp_model(combined_text)
        doc1 = nlp_model(text1)
        doc2 = nlp_model(text2)
        
        # Merge if:
        # 1. First text ends abruptly (no proper noun/entity endings)
        # 2. Second text continues the thought (starts with lowercase or continuation)
        # 3. Combined text makes more semantic sense
        
        tokens1 = [t for t in doc1 if not t.is_space and t.is_alpha]
        tokens2 = [t for t in doc2 if not t.is_space and t.is_alpha]
        
        # Check for obvious continuation patterns
        if (len(tokens1) > 0 and len(tokens2) > 0):
            # If first ends without punctuation and second starts lowercase
            if (not text1.rstrip()[-1:] in '.!?:;' and 
                text2[0].islower()):
                return True
            
            # If first is very short and incomplete
            if (len(tokens1) <= 3 and 
                not any(token.pos_ in ['NOUN', 'PROPN'] for token in tokens1)):
                return True
            
            # If they have similar formatting (same level, similar font size)
            if (heading1.get('level') == heading2.get('level') and
                abs(heading1.get('font_size', 12) - heading2.get('font_size', 12)) < 2):
                return True
    
    except Exception as e:
        # On error, don't merge
        return False
    
    return False

def merge_heading_blocks(blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Physically merge multiple heading blocks into one.
    """
    if not blocks:
        return {}
    
    merged = blocks[0].copy()
    
    # Combine text
    combined_text = ' '.join(block.get('text', '').strip() for block in blocks if block.get('text', '').strip())
    merged['text'] = combined_text
    
    # Update coordinates to encompass all blocks
    merged['x0'] = min(block.get('x0', 0) for block in blocks)
    merged['x1'] = max(block.get('x1', block.get('x0', 0) + block.get('width', 0)) for block in blocks)
    merged['top'] = min(block.get('top', 0) for block in blocks)
    merged['bottom'] = max(block.get('bottom', block.get('top', 0) + block.get('height', 0)) for block in blocks)
    merged['width'] = merged['x1'] - merged['x0']
    merged['height'] = merged['bottom'] - merged['top']
    
    # Use the highest level (H1 > H2 > H3 > H4)
    levels = [block.get('level') for block in blocks if block.get('level')]
    if levels:
        level_priorities = {'H1': 1, 'H2': 2, 'H3': 3, 'H4': 4}
        best_level = min(levels, key=lambda x: level_priorities.get(x, 5))
        merged['level'] = best_level
    
    # Combine formatting features (use the strongest)
    merged['is_bold'] = any(block.get('is_bold', False) for block in blocks)
    merged['is_centered'] = any(block.get('is_centered', False) for block in blocks)
    merged['font_size'] = max(block.get('font_size', 12) for block in blocks)
    
    return merged

def classify_block_lenient(block: Dict[str, Any], dynamic_th: Dict[str, float], common_font_size: float) -> Optional[str]:
    """
    VERY lenient classification for when we're short on headings.
    Compromises on quality to ensure minimum headings per page.
    """
    cleaned_text = block["text"].strip()
    
    if not cleaned_text or len(cleaned_text) < 2:
        return None
        
    # Skip obvious header/footer
    if block.get("is_header_footer", False):
        return None
    
    # VERY lenient length limits
    word_count = len(cleaned_text.split())
    if word_count > 50:  # Only reject very long paragraphs
        return None
    
    # Only reject obvious noise patterns
    if re.fullmatch(r'[\s\-—_•*●■]*', cleaned_text):
        return None
    if re.fullmatch(r'[^\w\s]*', cleaned_text):
        return None
    
    # Very basic scoring
    score = 1.0  # Start with base score
    
    # Font size scoring (very lenient)
    font_size = block.get('font_size', 12.0)
    if font_size > common_font_size:
        score += 2.0
    
    # Formatting bonuses
    if block.get('is_bold', False):
        score += 2.0
    if block.get('is_centered', False):
        score += 1.5
    
    # Pattern bonuses
    if re.match(r'^\d+\.\s+', cleaned_text):
        score += 3.0
    elif cleaned_text.isupper() and len(cleaned_text) <= 50:
        score += 2.0
    elif cleaned_text.istitle():
        score += 1.0
    elif cleaned_text[0].isupper():
        score += 0.5
    
    # Length bonus (shorter is better)
    if word_count <= 5:
        score += 1.5
    elif word_count <= 10:
        score += 1.0
    
    # If score is decent, classify as heading
    if score >= 2.0:
        if font_size >= dynamic_th.get('H1', common_font_size + 4):
            return 'H1'
        elif font_size >= dynamic_th.get('H2', common_font_size + 2):
            return 'H2'
        elif font_size >= dynamic_th.get('H3', common_font_size + 1):
            return 'H3'
        else:
            return 'H4'  # Even small fonts can be H4 if other features are good
    
    return None

def ensure_minimum_headings_per_page(heading_blocks: List[Dict[str, Any]], 
                                     all_classified_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    AGGRESSIVELY ensures each page has at least 1-2 headings by promoting the best candidates.
    Compromises on quality to meet minimum requirements.
    """
    # Group blocks by page
    pages = {}
    all_blocks_by_page = {}
    
    for block in heading_blocks:
        page = block.get('page', 0)
        if page not in pages:
            pages[page] = []
        pages[page].append(block)
    
    for block in all_classified_blocks:
        page = block.get('page', 0)
        if page not in all_blocks_by_page:
            all_blocks_by_page[page] = []
        all_blocks_by_page[page].append(block)
    
    final_blocks = []
    
    for page, page_headings in pages.items():
        headings_count = len(page_headings)
        target_headings = 2  # Always try for 2 headings per page
        
        # If page has fewer than target, AGGRESSIVELY add more
        if headings_count < target_headings:
            needed = target_headings - headings_count
            
            # Get all blocks on this page that aren't already headings
            page_blocks = all_blocks_by_page.get(page, [])
            non_heading_blocks = [b for b in page_blocks 
                                if not b.get('level') 
                                and not b.get('is_header_footer', False)
                                and b.get('text', '').strip()]
            
            # RELAXED scoring - be much more permissive
            candidates = []
            for block in non_heading_blocks:
                score = calculate_heading_likeness_score_relaxed(block)
                # Accept ANY block with minimal score (even 0.5)
                if score >= 0.5:
                    candidates.append((score, block))
            
            # If still not enough candidates, accept even more blocks
            if len(candidates) < needed:
                for block in non_heading_blocks:
                    if (block, None) not in [(c[1], None) for c in candidates]:
                        text = block.get('text', '').strip()
                        # Accept any non-empty text that's not obviously garbage
                        if (len(text) >= 3 and 
                            not re.fullmatch(r'[\s\-—_•*●■]*', text) and
                            not re.fullmatch(r'[^\w\s]*', text)):
                            candidates.append((0.1, block))  # Very low score but acceptable
            
            # Sort by score and take the best available
            candidates.sort(key=lambda x: x[0], reverse=True)
            
            for i in range(min(needed, len(candidates))):
                score, candidate = candidates[i]
                # Assign level based on score - higher scores get H1, lower get H2
                if score >= 3.0:
                    candidate['level'] = 'H1'
                elif score >= 1.0:
                    candidate['level'] = 'H2'
                else:
                    candidate['level'] = 'H3'  # Even low-quality gets H3
                candidate['classification_method'] = 'minimum_enforced'
                page_headings.append(candidate)
                print(f"    Promoted heading on page {page}: '{candidate.get('text', '')[:50]}...' (score: {score:.1f})")
        
        final_blocks.extend(page_headings)
    
    return final_blocks

def calculate_heading_likeness_score_relaxed(block: Dict[str, Any]) -> float:
    """
    RELAXED scoring - much more permissive to ensure we find enough headings.
    """
    score = 1.0  # Start with base score instead of 0
    text = block.get('text', '').strip()
    
    if not text:
        return 0.0
    
    # Basic text quality (very lenient)
    if len(text) >= 3:
        score += 1.0
    
    # Font size bonus (more generous)
    font_size = block.get('font_size', 12.0)
    if font_size > 13:  # Lowered from 14
        score += 2.0
    elif font_size > 11:  # Even slightly larger than body text
        score += 1.0
    
    # Bold bonus
    if block.get('is_bold', False):
        score += 2.0
    
    # Centered bonus
    if block.get('is_centered', False):
        score += 1.5
    
    # Length scoring (more forgiving)
    word_count = len(text.split())
    if word_count <= 8:  # Increased from 5
        score += 1.5
    elif word_count <= 15:  # Increased from 10
        score += 0.5
    elif word_count > 30:  # Only penalize very long text
        score -= 1.0
    
    # Pattern bonuses
    if re.match(r'^\d+\.\s+', text):
        score += 3.0
    elif re.match(r'^[A-Z][A-Z\s]{2,}$', text):  # ALL CAPS
        score += 2.0
    elif text.istitle() and word_count <= 6:
        score += 1.5
    elif text[0].isupper():  # Starts with capital
        score += 0.5
    
    # Vertical separation bonus (more lenient)
    gap_before = block.get('gap_before_block', 0.0)
    gap_after = block.get('gap_after_block', 0.0)
    if gap_before > 3 or gap_after > 3:  # Lowered from 5
        score += 1.0
    
    # Position bonus - text at start/end of sections often headings
    if block.get('is_start_of_section', False):
        score += 1.0
    
    return score