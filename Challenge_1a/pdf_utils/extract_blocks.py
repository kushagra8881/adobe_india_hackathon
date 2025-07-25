import json
import os
import collections
import re
from operator import itemgetter
import numpy as np
import fitz # PyMuPDF
from typing import List, Dict, Any, Tuple, Optional

# --- Constants and Configuration ---
# General Tolerances
FONT_SIZE_TOLERANCE_MERGE = 0.5 # points for font size comparison during tight merges
X_ALIGN_TOLERANCE_MERGE = 15.0 # pixels for horizontal alignment during merges
VERTICAL_GAP_TOLERANCE_MERGE_NEGATIVE = 5.0 # Max negative gap for vertical merges
PAGE_MARGIN_HEADER_FOOTER_PERCENT = 0.15 # % of page height for header/footer detection

# Regex for common patterns that are likely noise when standalone
URL_REGEX = re.compile(r'^(https?://|www\.)\S+\.\S+(\/\S*)?$', re.IGNORECASE)
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
DATE_REGEX = re.compile(r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$|^\d{4}[/-]\d{1,2}[/-]\d{1,2}$|^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2},?\s+\d{2,4}$', re.IGNORECASE)
TIME_REGEX = re.compile(r'^\d{1,2}:\d{2}(:\d{2})?(?:\s*(?:am|pm))?$', re.IGNORECASE)
NUMBER_REGEX = re.compile(r'^-?\d+(?:,\d{3})*(?:\.\d+)?$') # Covers integers, decimals, thousands separators
SYMBOL_ONLY_REGEX = re.compile(r'^[\W_]+$') # Matches strings purely of non-alphanumeric/underscore characters

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
        "D", "了", "在", "是", "我", "有", "和", "不", "就", "人", "都", "一", "一个",
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



def _has_unclosed_brackets(text: str) -> bool:
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


def _is_uninformative_text(text: str, is_header_footer: bool = False, detected_lang: str = "en") -> bool:
    """
    Determines if a given text string is likely uninformative noise.
    Considers standalone dates, times, links, mail IDs, numbers, symbols,
    and common single words. Includes language-aware filtering.
    """
    text_stripped = text.strip()
    if not text_stripped:
        return True # Empty string is always uninformative

    # Map detected_lang code to the full name used in COMMON_SINGLE_WORDS_EXTENDED
    lang_name = LANG_CODE_TO_NAME_MAP.get(detected_lang, "english")
    common_words_for_lang = set(COMMON_SINGLE_WORDS_EXTENDED.get(lang_name, []))

    predominant_script = _get_predominant_script_type(text_stripped)
    is_non_alphanumeric_script = (predominant_script in ['cjk', 'cyrillic', 'arabic', 'devanagari'])


    # Don't filter out potential header/footers unless they are extremely generic
    if is_header_footer:
        if re.match(r'^\s*\d{1,5}\s*$', text_stripped) or len(text_stripped) > 5: # Page numbers or longer text
            return False
        # Filter purely symbolic H/F, or single stop words for Latin scripts
        if SYMBOL_ONLY_REGEX.fullmatch(text_stripped) or \
           (predominant_script == 'latin' and text_stripped.lower() in common_words_for_lang):
            return True
        return False # Generally keep H/F text as it's been identified as repetitive

    # General filtering for main content blocks

    # Determine "word_count" based on script for more accurate length checks
    word_count = len(text_stripped.split())
    if predominant_script == 'cjk': # For CJK, word count is character count
        word_count = len(text_stripped)
    
    # 1. Very short, purely symbolic text
    if SYMBOL_ONLY_REGEX.fullmatch(text_stripped):
        return True
    
    # 1.5. Filter out very short fragmented text that's likely incomplete
    # LOOSENED: Be more permissive to ensure we have enough candidates for minimum headings
    if len(text_stripped) < 2:  # Only filter extremely short text (was 3)
        return True
    
    # For single words, be more permissive - only filter if very short AND not formatted like a heading
    if word_count == 1 and len(text_stripped) <= 3:  # Was 5, now 3
        # Keep single words that might be headings (uppercase, mixed case, etc.)
        if not (text_stripped.isupper() or text_stripped.istitle() or re.match(r'^\d+[A-Z]*$', text_stripped)):
            return True
    
    # 1.6. Filter out sentence fragments (text that doesn't end properly and seems incomplete)
    # This is especially important for Japanese and other languages
    if not is_header_footer:
        # Check for repeated prefix patterns (like "RFP: R RFP: Re")
        words = text_stripped.split()
        if len(words) >= 2 and len(text_stripped) <= 40:  # Apply to reasonably short text
            # Check for exact word repetitions (like "RFP: R RFP:")
            word_counts = {}
            for word in words:
                clean_word = re.sub(r'[^\w]', '', word.lower())  # Remove punctuation for comparison
                if len(clean_word) >= 2:  # Only count meaningful word parts
                    word_counts[clean_word] = word_counts.get(clean_word, 0) + 1
            
            # If any word appears multiple times in short text, likely fragmented
            max_word_count = max(word_counts.values()) if word_counts else 0
            if max_word_count >= 2 and len(words) <= 6:
                return True
                
            # Check for repeated word prefixes
            word_prefixes = []
            for word in words:
                if len(word) >= 3:
                    prefix = word[:3].lower()  # Use first 3 chars as prefix
                    word_prefixes.append(prefix)
            
            # If we have repeated prefixes in a short text, it's likely fragmented
            if len(word_prefixes) >= 2:
                prefix_counts = {}
                for prefix in word_prefixes:
                    prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
                
                # If any prefix appears multiple times in short text, likely fragmented
                max_count = max(prefix_counts.values()) if prefix_counts else 0
                if max_count >= 2 and len(words) <= 5:
                    return True
        
        # Check for very short incomplete fragments (like "or Pr")
        # LOOSENED: Only filter extremely obvious fragments
        if len(text_stripped) <= 5:  # Was 8, now 5
            # Single words that are likely cut off
            if word_count == 1 or (word_count == 2 and len(text_stripped) <= 5):  # Was 8, now 5
                # Common incomplete word patterns - be more specific
                incomplete_patterns = [
                    r'^(or|and|the|for|to|in|on|at|of)\s*$',  # Removed some patterns to be less aggressive
                    r'^[a-zA-Z]{1}\s+[a-zA-Z]{1}\s*$',  # Single letter "words" only
                    r'^[A-Z]{1,2}:\s*[A-Z]\s*$',  # Pattern like "R: R" but allow "RFP: R"
                ]
                for pattern in incomplete_patterns:
                    if re.match(pattern, text_stripped, re.IGNORECASE):
                        return True
        
        # Check for incomplete sentence patterns
        if predominant_script == 'latin':
            # For Latin scripts, check for fragments that start mid-sentence
            if text_stripped[0].islower() and not re.match(r'^(and|or|but|the|a|an|of|in|on|at|to|for)\b', text_stripped, re.IGNORECASE):
                return True
            # Filter out fragments that end mid-sentence without proper punctuation
            if len(text_stripped) > 10 and not re.search(r'[.!?:;]$', text_stripped) and re.search(r'\b(of|the|a|an|and|or|in|on|at|to|for|with|by|from)\s*$', text_stripped, re.IGNORECASE):
                return True
        elif predominant_script == 'cjk':
            # For CJK scripts (Japanese, Chinese, Korean)
            # Filter out fragments that start with particles or don't end properly
            if re.match(r'^[のはがをにでとから]', text_stripped):  # Common Japanese particles at start
                return True
            # Filter out fragments that end mid-sentence
            if len(text_stripped) > 5 and not re.search(r'[。！？：；]$', text_stripped) and re.search(r'[のはがをにでとから]\s*$', text_stripped):
                return True
    
    # 2. Single common stop words (language-aware and script-aware)
    if word_count == 1 and text_stripped.lower() in common_words_for_lang:
        # If it's a non-alphanumeric script and just a single "word" (char for CJK),
        # it's usually meaningful even if it's a common particle/preposition.
        # So, be lenient and pass it unless it's purely symbolic.
        if is_non_alphanumeric_script and not _has_script_chars(text_stripped, LATIN_CHARS_REGEX) and not re.search(r'\d', text_stripped): # Check it doesn't contain Latin or numbers
            return False # Be lenient: pass non-alphanumeric single words if not numeric/Latin
        return True # Filter if it's a common stop word (for Latin) or purely symbolic (for non-Latin)

    # 3. Standalone URLs, Email IDs, Dates, Times, Numbers (universal patterns)
    # Apply length limit carefully: be more lenient for non-alphanumeric scripts
    length_limit_for_patterns_words = 5
    if is_non_alphanumeric_script:
        if predominant_script == 'cjk': length_limit_for_patterns_words = 20 # For CJK, allow up to 20 chars
        else: length_limit_for_patterns_words = 10 # For other non-latin, allow up to 10 words

    if word_count <= length_limit_for_patterns_words:
        if URL_REGEX.fullmatch(text_stripped) or \
           EMAIL_REGEX.fullmatch(text_stripped) or \
           DATE_REGEX.fullmatch(text_stripped) or \
           TIME_REGEX.fullmatch(text_stripped) or \
           NUMBER_REGEX.fullmatch(text_stripped):
            return True
    
    # 4. Text that appears to be just a bullet or short list marker
    # Apply word_count condition carefully based on script.
    # Added common CJK bullet/numbering patterns
    if (re.match(r'^[•\->–—*+]\s*$', text_stripped)) or \
       (re.match(r'^\d+\.?$', text_stripped) and word_count <= (1 if predominant_script == 'latin' else 5)) or \
       (_has_script_chars(text_stripped, LATIN_CHARS_REGEX) and word_count == 1 and re.match(r'^[a-zA-Z]\.?$', text_stripped)) or \
       (_has_script_chars(text_stripped, CJK_CHARS_REGEX) and re.fullmatch(r'^[一二三四五六七八九十百千万億兆甲乙丙丁あいうえおかきくけこ]\s*[\.．、，]?$', text_stripped)):
        return True

    # 5. Check for absence of any meaningful script characters or numbers
    has_any_script_or_digit = False
    if re.search(r'[a-zA-Z0-9]', text_stripped) or \
       _has_script_chars(text_stripped, CJK_CHARS_REGEX) or \
       _has_script_chars(text_stripped, CYRILLIC_CHARS_REGEX) or \
       _has_script_chars(text_stripped, ARABIC_CHARS_REGEX) or \
       _has_script_chars(text_stripped, DEVANAGARI_CHARS_REGEX):
        has_any_script_or_digit = True
    
    # If no meaningful script characters AND no numbers, then it's likely noise
    if not has_any_script_or_digit and len(text_stripped) > 0:
        return True # Filter out if no meaningful chars at all

    # Final leniency: If it has actual script characters, but none of the above rules caught it,
    # then assume it's potentially meaningful and pass it forward.
    # This aligns with "be lenient and pass the txt block forward as long as it is not..."
    if has_any_script_or_digit:
        return False

    return False # Default to not uninformative if none of the explicit rules hit


def _is_standalone_fragment(text: str) -> bool:
    """
    Determines if a text block is a standalone fragment (date, time, number, symbol)
    that should be merged with nearby text regardless of distance.
    """
    text_stripped = text.strip()
    
    if not text_stripped or len(text_stripped) > 20:  # Too long to be a fragment
        return False
    
    # Check for common standalone fragments
    if (DATE_REGEX.fullmatch(text_stripped) or 
        TIME_REGEX.fullmatch(text_stripped) or 
        NUMBER_REGEX.fullmatch(text_stripped) or
        SYMBOL_ONLY_REGEX.fullmatch(text_stripped)):
        return True
    
    # Check for very short text that's likely a fragment
    if len(text_stripped) <= 3:
        return True
    
    # Check for standalone symbols/punctuation
    if re.match(r'^[^\w\s]*$', text_stripped, re.UNICODE):
        return True
    
    # Check for single characters or short abbreviations
    if len(text_stripped.split()) == 1 and len(text_stripped) <= 5:
        return True
    
    return False

def _is_meaningful_text(text: str) -> bool:
    """
    Determines if a text block contains meaningful content worth merging fragments to.
    """
    text_stripped = text.strip()
    
    if not text_stripped or len(text_stripped) < 3:
        return False
    
    # Has actual words (not just symbols/numbers)
    words = re.findall(r'\b\w+\b', text_stripped, re.UNICODE)
    if len(words) >= 2:  # At least 2 words
        return True
    
    # Single meaningful word that's reasonably long
    if len(words) == 1 and len(words[0]) >= 4:
        return True
    
    return False

def _pre_merge_horizontal_fragments(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Enhanced horizontal merging that:
    1. Performs aggressive merge of blocks that are extremely close horizontally
    2. Merges standalone fragments (dates, times, numbers, symbols) with nearby meaningful text
    This fixes issues like "RFP: R RFP: Re" and "March 21, 2003" split across blocks.
    """
    if not blocks:
        return []

    blocks.sort(key=itemgetter("top", "x0"))
    merged_output = []
    i = 0
    
    while i < len(blocks):
        current = blocks[i]
        current.setdefault("x1", current["x0"] + current.get("width", 0.0))
        current["x1"] = float(current["x1"])

        temp_merged = current.copy()
        j = i + 1
        
        while j < len(blocks):
            next_block = blocks[j]
            next_block.setdefault("x0", 0.0)
            next_block.setdefault("x1", next_block["x0"] + next_block.get("width", 0.0))
            next_block.setdefault("top", 0.0)
            next_block.setdefault("bottom", next_block["top"] + next_block.get("height", 0.0))
            
            if next_block["page"] != temp_merged["page"]:
                break
            
            horizontal_gap = next_block["x0"] - temp_merged["x1"]
            vertical_overlap = min(temp_merged["bottom"], next_block["bottom"]) - max(temp_merged["top"], next_block["top"])
            
            # Standard tight horizontal merging conditions
            is_tightly_horizontal_aligned = abs(horizontal_gap) < 10.0
            has_significant_vertical_overlap = vertical_overlap > min(temp_merged.get("height", 0.0), next_block.get("height", 0.0)) * 0.5
            is_similar_font_size = abs(next_block.get("font_size", 0.0) - temp_merged.get("font_size", 0.0)) < FONT_SIZE_TOLERANCE_MERGE
            
            font_name_current_base = temp_merged.get("font_name", "").split('+')[-1] if temp_merged.get("font_name") else ""
            font_name_next_base = next_block.get("font_name", "").split('+')[-1] if next_block.get("font_name") else ""
            is_similar_font_name = font_name_next_base == font_name_current_base
            
            # Enhanced fragment merging conditions
            current_text = temp_merged.get("text", "").strip()
            next_text = next_block.get("text", "").strip()
            
            is_current_fragment = _is_standalone_fragment(current_text)
            is_next_fragment = _is_standalone_fragment(next_text)
            is_current_meaningful = _is_meaningful_text(current_text)
            is_next_meaningful = _is_meaningful_text(next_text)
            
            # Standard tight merging
            should_merge_standard = (is_tightly_horizontal_aligned and has_significant_vertical_overlap and 
                                   is_similar_font_size and is_similar_font_name)
            
            # Fragment-specific merging (more lenient distance requirements)
            should_merge_fragment = False
            if (is_similar_font_size and is_similar_font_name and 
                vertical_overlap > 0 and horizontal_gap < 100.0):  # Much more lenient horizontal gap
                
                # Case 1: Current is fragment, next is meaningful text
                if is_current_fragment and is_next_meaningful:
                    should_merge_fragment = True
                
                # Case 2: Current is meaningful, next is fragment
                elif is_current_meaningful and is_next_fragment:
                    should_merge_fragment = True
                
                # Case 3: Both are fragments that should be combined
                elif is_current_fragment and is_next_fragment:
                    should_merge_fragment = True
                
                # Case 4: Special patterns for common document elements
                elif (re.match(r'^(page|p\.?)\s*$', current_text, re.IGNORECASE) and 
                      re.match(r'^\d+$', next_text)):  # "Page" + "123"
                    should_merge_fragment = True
                
                elif (DATE_REGEX.match(current_text) and 
                      TIME_REGEX.match(next_text)):  # Date followed by time
                    should_merge_fragment = True
                
                elif (re.match(r'^[\$€£¥]$', current_text) and 
                      NUMBER_REGEX.match(next_text)):  # Currency symbol + number
                    should_merge_fragment = True
                
                elif (re.match(r'^\d+$', current_text) and 
                      re.match(r'^[%°]$', next_text)):  # Number + percent/degree
                    should_merge_fragment = True
            
            if should_merge_standard or should_merge_fragment:
                # Determine appropriate spacing
                space_to_add = ""
                if should_merge_fragment:
                    # Smart spacing for fragments
                    if (re.match(r'^[\$€£¥]$', current_text) or  # Currency symbols
                        re.match(r'^[%°]$', next_text) or         # Percentage/degree symbols
                        current_text.endswith('-') or            # Hyphenated words
                        next_text.startswith('.')):              # Decimal continuation
                        space_to_add = ""  # No space needed
                    elif (re.match(r'^\d+$', current_text) and 
                          re.match(r'^[A-Za-z]', next_text)):    # Number followed by letter
                        space_to_add = " "
                    elif (DATE_REGEX.match(current_text) and 
                          TIME_REGEX.match(next_text)):          # Date + time
                        space_to_add = " "
                    elif horizontal_gap > 5.0:                   # Significant gap suggests space
                        space_to_add = " "
                else:
                    # Standard merging - minimal spacing
                    space_to_add = "" if horizontal_gap < 3.0 else " "
                
                # Perform the merge
                temp_merged["text"] = temp_merged["text"] + space_to_add + next_block["text"]
                temp_merged["x1"] = next_block["x1"] 
                temp_merged["width"] = temp_merged["x1"] - temp_merged["x0"]
                temp_merged["bottom"] = max(temp_merged["bottom"], next_block["bottom"])
                temp_merged["height"] = temp_merged["bottom"] - temp_merged["top"]
                temp_merged["is_bold"] = temp_merged.get("is_bold", False) or next_block.get("is_bold", False)
                temp_merged["is_italic"] = temp_merged.get("is_italic", False) or next_block.get("is_italic", False)
                temp_merged["font_size"] = max(temp_merged.get("font_size", 0.0), next_block.get("font_size", 0.0))
                
                j += 1
            else:
                break
        
        merged_output.append(temp_merged)
        i = j

    return merged_output


def detect_columns(blocks_on_page: List[Dict[str, Any]], page_width: float, x_tolerance: float = 10.0, min_column_width_ratio: float = 0.05) -> List[Tuple[float, float]]:
    """
    Detects text columns on a page based on x0 coordinates.
    Returns a list of column ranges (x_min, x_max).
    """
    if not blocks_on_page:
        return [(0, page_width)] 

    relevant_blocks_x0 = [b["x0"] for b in blocks_on_page if b.get("width", 0) > 5 and b.get("width", 0) < page_width * 0.9]
    x0_coords = np.array(relevant_blocks_x0)
    
    if len(x0_coords) < 2:
        return [(0, page_width)] 

    sorted_unique_x0s = np.sort(np.unique(x0_coords))
    gaps = sorted_unique_x0s[1:] - sorted_unique_x0s[:-1]
    column_break_indices = np.where(gaps > x_tolerance)[0]

    columns = []
    current_column_start_x = sorted_unique_x0s[0]

    for i, break_idx in enumerate(column_break_indices):
        column_end_x = sorted_unique_x0s[break_idx]
        if (column_end_x - current_column_start_x) > page_width * min_column_width_ratio:
            columns.append((current_column_start_x, column_end_x + x_tolerance)) 
        current_column_start_x = sorted_unique_x0s[break_idx + 1]

    if (page_width - current_column_start_x) > page_width * min_column_width_ratio:
        columns.append((current_column_start_x, page_width)) 

    if not columns: 
        return [(0, page_width)] 
    
    columns.sort(key=itemgetter(0))

    merged_columns = []
    if columns:
        current_merged_start, current_merged_end = columns[0]
        for i in range(1, len(columns)):
            next_start, next_end = columns[i]
            if next_start <= current_merged_end + x_tolerance: 
                current_merged_end = max(current_merged_end, next_end)
            else:
                merged_columns.append((current_merged_start, current_merged_end))
                current_merged_start, current_merged_end = next_start, next_end
        merged_columns.append((current_merged_start, current_merged_end))
    
    if len(merged_columns) == 1 and (merged_columns[0][1] - merged_columns[0][0]) < page_width * 0.9:
        return [(0, page_width)] 
    
    merged_columns = [col for col in merged_columns if (col[1] - col[0]) > page_width * 0.01]
    
    if not merged_columns: 
        return [(0, page_width)]

    return merged_columns

def merge_nearby_blocks_simple(blocks_in_column: List[Dict[str, Any]], 
                                 y_tolerance_factor: float, 
                                 x_tolerance: float,
                                 detected_lang: str = "en") -> List[Dict[str, Any]]: 
    """
    Performs a basic post-extraction merge of blocks that are vertically very close,
    horizontally aligned, and share similar font properties, likely representing 
    single logical lines or phrases split by PDF rendering, or paragraph continuations.
    Includes language-aware adjustments.
    """
    if not blocks_in_column:
        return []

    blocks_in_column.sort(key=itemgetter("top", "x0"))

    merged_output = []
    is_cjk = detected_lang in ["zh", "ja", "ko"] # Define is_cjk here
    i = 0
    while i < len(blocks_in_column):
        current = blocks_in_column[i]
        merged_current = current.copy()

        j = i + 1
        while j < len(blocks_in_column):
            next_block = blocks_in_column[j]

            if next_block["page"] != merged_current["page"]:
                break
            
            # Skip exact or near-duplicates
            is_near_duplicate = (next_block["text"].strip().lower() == merged_current["text"].strip().lower() and
                                 abs(next_block["x0"] - merged_current["x0"]) < 5 and
                                 abs(next_block["top"] - merged_current["top"]) < 5)
            if is_near_duplicate:
                j += 1 
                continue

            avg_line_height_current = merged_current.get("line_height", merged_current["height"])
            vertical_gap = next_block["top"] - merged_current["bottom"]
            
            is_very_close_vertically = abs(vertical_gap) < (avg_line_height_current * y_tolerance_factor) and vertical_gap >= -5.0 
            is_aligned_horizontally = abs(next_block["x0"] - merged_current["x0"]) < x_tolerance
            is_similar_font_size = abs(next_block["font_size"] - merged_current["font_size"]) < 0.5
            
            font_name_current_base = merged_current.get("font_name", "").split('+')[-1] if merged_current.get("font_name") else ""
            font_name_next_base = next_block.get("font_name", "").split('+')[-1] if next_block.get("font_name") else ""
            is_similar_font_name = font_name_next_base == font_name_current_base

            should_merge = False
            if is_very_close_vertically and is_aligned_horizontally and is_similar_font_size and is_similar_font_name:
                current_text_stripped = merged_current["text"].strip()
                next_text_stripped = next_block["text"].strip()

                # Rule 1: Hyphenated word continuation
                if current_text_stripped.endswith('-'):
                    should_merge = True
                # Rule 2: Sentence/paragraph continuation (language-aware)
                elif not (CJK_SENTENCE_END_PUNCTUATION.search(current_text_stripped) if is_cjk else re.search(r'[.?!]$', current_text_stripped)) and len(next_text_stripped) > 0:
                    if is_cjk: # For CJK, any non-empty text is a continuation if other conditions met
                        should_merge = True
                    else: # For non-CJK, check for lowercase start or digit
                        if next_text_stripped[0].islower() or next_text_stripped[0].isdigit() or next_text_stripped[0] in ['(', '[', '{']:
                            should_merge = True
                # Rule 3: Current text is very short and next text is very close, and they likely form a single word
                elif len(current_text_stripped) <= 3 and len(next_text_stripped) > 0 and \
                     abs(vertical_gap) < (avg_line_height_current * 0.2) and \
                     (current_text_stripped[-1].isalnum() and next_text_stripped[0].isalnum()):
                    should_merge = True
                # Rule 4: If previous block ends with common punctuation and next block starts with no space
                elif current_text_stripped.endswith(',') and not re.match(r'^\s*([A-Z]|\d)', next_text_stripped):
                    should_merge = True
                # Rule 5: Unclosed parentheses/brackets (language-aware)
                elif _has_unclosed_brackets(current_text_stripped) and \
                     re.search(r'[\)\]\}\)\]｝]', next_text_stripped): # Including CJK closing brackets
                    should_merge = True

            if should_merge:
                merged_text = merged_current["text"]
                if merged_text.strip().endswith('-'):
                    merged_text = merged_text.strip()[:-1] 
                else:
                    # Smart space insertion (language-aware punctuation)
                    # No space needed before punctuation (handle CJK too)
                    if re.match(r'^[\s]*(?:\,|\.|\!|\?|\:|\;|\)|\\]|\]|\}|\uff0c|\u3002|\uff1a|\uff1b|\uff01|\uff1f)$', next_text_stripped): # common Western + CJK commas/periods/exclamation/question/colon/semicolon/brackets
                        pass 
                    # No space needed after opening bracket (handle CJK too)
                    elif re.match(r'[\( \[ \{ （ 【 「 『]$', current_text_stripped):
                        pass
                    else:
                        merged_text += " " 

                merged_current["text"] = (merged_text + next_block["text"]).strip()
                merged_current["bottom"] = max(merged_current["bottom"], next_block["bottom"])
                merged_current["height"] = merged_current["bottom"] - merged_current["top"]
                merged_current["x0"] = min(merged_current["x0"], next_block["x0"]) 
                merged_current["x1"] = max(merged_current.get("x1", merged_current["x0"] + merged_current["width"]), next_block.get("x1", next_block["x0"] + next_block["width"]))
                merged_current["width"] = merged_current["x1"] - merged_current["x0"]
                merged_current["font_size"] = max(merged_current["font_size"], next_block.get("font_size", 0.0)) 
                merged_current["is_bold"] = merged_current.get("is_bold", False) or next_block.get("is_bold", False)
                merged_current["is_italic"] = merged_current.get("is_italic", False) or next_block.get("is_italic", False)
                merged_current["line_height"] = max(merged_current.get("line_height", 0), next_block.get("line_height", 0), merged_current["height"])
                
                j += 1
            else:
                break

        # Filter out "gibberish" or very short, uninformative merged blocks
        # Pass detected_lang to the uninformative text filter
        if not _is_uninformative_text(merged_current["text"], is_header_footer=merged_current.get("is_header_footer", False), detected_lang=detected_lang):
             merged_output.append(merged_current)
        
        i = j

    return merged_output


def detect_and_mark_headers_footers(blocks: List[Dict[str, Any]], page_dimensions_map: Dict[int, Dict[str, float]], min_pages_threshold: float = 0.3, y_margin_percent: float = 0.15) -> List[Dict[str, Any]]:
    """
    Identifies and marks likely headers/footers by looking for repeating text
    at consistent vertical positions across a significant number of pages.
    page_dimensions_map: Map of page_num to {"width", "height"}
    """
    if not blocks:
        return []

    position_text_counts = collections.defaultdict(lambda: collections.defaultdict(int))
    page_presence = collections.defaultdict(bool)

    for block in blocks:
        page_presence[block["page"]] = True
        page_height_for_block = page_dimensions_map.get(block["page"], {}).get("height", 792) # Default A4 height

        # Normalize Y position to group similar vertical positions
        norm_y_pos_top = round(block["top"] / 5) * 5 
        norm_y_pos_bottom = round(block["bottom"] / 5) * 5
        text_hash = block["text"].strip().lower()

        # Only consider blocks within the header/footer margins
        if norm_y_pos_top < page_height_for_block * y_margin_percent:
            position_text_counts["header"][(norm_y_pos_top, text_hash)] += 1
        elif norm_y_pos_bottom > page_height_for_block * (1 - y_margin_percent):
            position_text_counts["footer"][(norm_y_pos_bottom, text_hash)] += 1

    total_unique_pages = len(page_presence)
    # If there's only one page or no pages, no recurring headers/footers
    if total_unique_pages <= 1:
        for block in blocks:
            block["is_header_footer"] = False
        return blocks

    header_footer_candidates = set()
    for category in ["header", "footer"]:
        for (pos, text_hash), count in position_text_counts[category].items():
            # Criteria for a header/footer candidate:
            # 1. Appears on a significant number of pages
            # 2. Text length is reasonable (not too short, not too long)
            if count >= total_unique_pages * min_pages_threshold and \
               2 < len(text_hash) < 100: # Typical length for actual content
                header_footer_candidates.add((pos, text_hash))
            # Special rule for page numbers (digits only, very short, high frequency)
            if len(text_hash) <= 5 and text_hash.isdigit() and count >= total_unique_pages * 0.5:
                header_footer_candidates.add((pos, text_hash))

    for block in blocks:
        norm_y_pos_top = round(block["top"] / 5) * 5
        norm_y_pos_bottom = round(block["bottom"] / 5) * 5
        text_hash = block["text"].strip().lower()
        page_height_for_block = page_dimensions_map.get(block["page"], {}).get("height", 792)

        is_hf = False

        # Mark if block matches a general header/footer candidate
        if ((norm_y_pos_top, text_hash) in header_footer_candidates and norm_y_pos_top < page_height_for_block * y_margin_percent) or \
           ((norm_y_pos_bottom, text_hash) in header_footer_candidates and norm_y_pos_bottom > page_height_for_block * (1 - y_margin_percent)):
            is_hf = True
        
        # Mark if it's a page number and appears frequently in header/footer zones
        if not is_hf and (len(text_hash) <= 5 and text_hash.isdigit()):
            if (norm_y_pos_top < page_height_for_block * 0.10 and position_text_counts["header"][(norm_y_pos_top, text_hash)] >= total_unique_pages * 0.5) or \
               (norm_y_pos_bottom > page_height_for_block * 0.90 and position_text_counts["footer"][(norm_y_pos_bottom, text_hash)] >= total_unique_pages * 0.5):
                is_hf = True
        
        # Mark if it's a short phrase (like a running title) appearing frequently
        if not is_hf and (1 < len(text_hash.split()) <= 10 and len(text_hash) > 5) :
            if position_text_counts["header"][(norm_y_pos_top, text_hash)] >= total_unique_pages * 0.5 and norm_y_pos_top < page_height_for_block * 0.15:
                 is_hf = True
            if position_text_counts["footer"][(norm_y_pos_bottom, text_hash)] >= total_unique_pages * 0.5 and norm_y_pos_bottom > page_height_for_block * 0.85:
                 is_hf = True

        block["is_header_footer"] = is_hf

    return blocks


def extract_text_blocks_pymu(pdf_path: str, detected_lang: str = "en") -> Tuple[List[Dict[str, Any]], Dict[int, Dict[str, float]]]:
    """
    Extracts text blocks with detailed metadata using PyMuPDF (Fitz).
    Returns the list of blocks and a dictionary of page dimensions (mediabox).
    Blocks are raw spans, with a very simple initial merge.
    Passes detected_lang for language-aware filtering.
    """
    doc = fitz.open(pdf_path)
    all_raw_spans_with_metadata = [] 

    page_dimensions = {}

    for page_num in range(doc.page_count):
        page = doc[page_num]
        
        page_width = page.rect.width
        page_height = page.rect.height
        page_dimensions[page_num] = {"width": page_width, "height": page_height}

        page_content = page.get_text("dict")  

        page_spans_raw = [] 
        for b_dict in page_content['blocks']:
            if b_dict['type'] == 0: # This is a text block
                for l_dict in b_dict['lines']:
                    # Calculate line height based on actual line bbox to be more accurate
                    line_x0, line_y0, line_x1, line_y1 = l_dict['bbox']
                    line_height = line_y1 - line_y0

                    for s_dict in l_dict['spans']:
                        line_text = s_dict['text']
                        if not line_text.strip(): continue # Skip empty spans

                        font_name_lower = s_dict['font'].lower()
                        is_bold = "bold" in font_name_lower or "bd" in font_name_lower or "heavy" in font_name_lower or "black" in font_name_lower
                        is_italic = "italic" in font_name_lower or "it" in font_name_lower or "oblique" in font_name_lower

                        x0, y0, x1, y1 = s_dict['bbox']
                        # Ensure coordinates are valid
                        if not all(isinstance(val, (int, float)) for val in [x0, y0, x1, y1]):
                            continue 

                        page_spans_raw.append({
                            "text": line_text,
                            "font_size": s_dict['size'],
                            "font_name": s_dict['font'],
                            "x0": x0,
                            "x1": x1, # Store x1 directly for convenience
                            "top": y0,
                            "bottom": y1,
                            "width": x1 - x0,
                            "height": y1 - y0,
                            "page": page_num,
                            "is_bold": is_bold,
                            "is_italic": is_italic,
                            "line_height": line_height # Use actual line height
                        })
        
        # Ensure page_spans_raw is a list before sorting
        if not isinstance(page_spans_raw, list):
            print(f"Warning: page_spans_raw became {type(page_spans_raw)} on page {page_num}. Resetting to empty list.")
            page_spans_raw = []
        page_spans_raw.sort(key=itemgetter("top", "x0"))

        # NEW: Apply aggressive horizontal fragment pre-merging here
        # Explicitly cast to list() to ensure type consistency
        page_spans_pre_merged = list(_pre_merge_horizontal_fragments(page_spans_raw)) 
        
        columns = detect_columns(page_spans_pre_merged, page_width) # Use pre_merged blocks for column detect
        
        blocks_in_columns = collections.defaultdict(list)
        unassigned_blocks = [] 

        for block in page_spans_pre_merged: # Use pre_merged blocks for column assignment
            assigned_to_column = False
            for col_idx, (col_x_min, col_x_max) in enumerate(columns):
                block_center_x = block["x0"] + block["width"] / 2
                
                # Assign if block's center is within column, or if it's a wide block in a single column layout
                if (col_x_min <= block_center_x <= col_x_max) or \
                   (len(columns) == 1 and block["width"] > page_width * 0.7): 
                    blocks_in_columns[col_idx].append(block)
                    assigned_to_column = True
                    break
            if not assigned_to_column:
                unassigned_blocks.append(block)

        columnar_merged_blocks = []
        for col_idx in sorted(blocks_in_columns.keys()):
            column_blocks = blocks_in_columns[col_idx]
            # Pass detected_lang to merge_nearby_blocks_simple
            # Explicitly cast to list() to ensure type consistency
            merged_column_blocks = list(merge_nearby_blocks_simple(column_blocks, y_tolerance_factor=0.6, x_tolerance=5.0, detected_lang=detected_lang)) 
            columnar_merged_blocks.extend(merged_column_blocks)
        
        # Ensure unassigned_blocks is a list before sorting
        if not isinstance(unassigned_blocks, list):
            print(f"Warning: unassigned_blocks became {type(unassigned_blocks)} on page {page_num}. Resetting to empty list.")
            unassigned_blocks = []
        unassigned_blocks.sort(key=itemgetter("top", "x0"))
        
        # Explicitly cast to list() to ensure type consistency
        merged_unassigned_blocks = list(merge_nearby_blocks_simple(unassigned_blocks, y_tolerance_factor=0.8, x_tolerance=20.0, detected_lang=detected_lang)) 

        all_raw_spans_with_metadata.extend(columnar_merged_blocks)
        all_raw_spans_with_metadata.extend(merged_unassigned_blocks) 
            
    doc.close()

    # Apply header/footer detection to the initial set of blocks
    # Explicitly cast to list() to ensure type consistency
    final_blocks_with_hf_marked = list(detect_and_mark_headers_footers(all_raw_spans_with_metadata, page_dimensions))

    # Ensure final_blocks_with_hf_marked is a list before sorting
    if not isinstance(final_blocks_with_hf_marked, list):
        print(f"Warning: final_blocks_with_hf_marked became {type(final_blocks_with_hf_marked)}. Resetting to empty list for final sort.")
        final_blocks_with_hf_marked = []
    final_blocks_with_hf_marked.sort(key=itemgetter("page", "top", "x0"))

    # NEW: Final filter for any remaining uninformative blocks after all merges
    filtered_blocks = []
    for block in final_blocks_with_hf_marked:
        if not _is_uninformative_text(block.get("text", ""), block.get("is_header_footer", False), detected_lang=detected_lang):
            filtered_blocks.append(block)

    return filtered_blocks, page_dimensions

def run(pdf_path: str, output_path: Optional[str] = None, detected_lang: str = "en") -> Tuple[List[Dict[str, Any]], Dict[int, Dict[str, float]]]:
    """
    Main function to run the block extraction process using PyMuPDF.
    Returns the list of blocks and page dimensions.
    If output_path is provided, it also writes the blocks to that path.
    Accepts detected_lang for language-aware filtering.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at: {pdf_path}")

    try:
        # Pass detected_lang to extract_text_blocks_pymu
        all_blocks, page_dimensions = extract_text_blocks_pymu(pdf_path, detected_lang=detected_lang)
    except Exception as e:
        raise RuntimeError(f"Error during PyMuPDF extraction from {pdf_path}: {e}")

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(all_blocks, f, indent=2)
        except IOError as e:
            print(f"Warning: Error writing intermediate blocks to {output_path}: {e}")
    
    return all_blocks, page_dimensions