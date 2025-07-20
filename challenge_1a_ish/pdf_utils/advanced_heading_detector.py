"""
Advanced Heading Detection System for Challenge 1A
Implements sophisticated heading detection with proper hierarchy and title extraction
"""
import json
import statistics
import re
from collections import Counter, defaultdict
import math

class AdvancedHeadingDetector:
    def __init__(self):
        self.font_size_clusters = {}
        self.document_title = ""
        self.heading_patterns = [
            # Numbered sections (various formats)
            r'^(\d+\.?\s+)',                    # 1. or 1
            r'^(\d+\.\d+\.?\s+)',              # 1.1. or 1.1
            r'^(\d+\.\d+\.\d+\.?\s+)',         # 1.1.1. or 1.1.1
            r'^(\d+\.\d+\.\d+\.\d+\.?\s+)',    # 1.1.1.1
            # Roman numerals
            r'^([IVX]+\.?\s+)',                # I. II. III.
            r'^([ivx]+\.?\s+)',                # i. ii. iii.
            # Letter sections
            r'^([A-Z]\.?\s+)',                 # A. B. C.
            r'^([a-z]\.?\s+)',                 # a. b. c.
            r'^\(([A-Z])\)\s+',                # (A) (B) (C)
            r'^\(([a-z])\)\s+',                # (a) (b) (c)
            r'^\((\d+)\)\s+',                  # (1) (2) (3)
            # Special markers and formats
            r'^(第\d+章|Chapter\s+\d+|Section\s+\d+)',  # Japanese/English chapters
            r'^(Kapitel\s+\d+|Abschnitt\s+\d+)',       # German
            r'^(Chapitre\s+\d+|Section\s+\d+)',        # French
            r'^(Capítulo\s+\d+|Sección\s+\d+)',        # Spanish
            r'^(Capitolo\s+\d+|Sezione\s+\d+)',        # Italian
            r'^(Глава\s+\d+|Раздел\s+\d+)',            # Russian
            r'^(제\d+장|제\d+절)',                       # Korean
            r'^(الفصل\s+\d+|القسم\s+\d+)',              # Arabic
            # Bullet points and special characters
            r'^([•◦▪▫■□●○◆◇▲△▼▽★☆]\s+)',
            r'^([-–—]\s+)',
            # Step/Part indicators
            r'^(Step\s+\d+|Part\s+\d+|Phase\s+\d+)',
            r'^(Étape\s+\d+|Partie\s+\d+)',            # French
            r'^(Schritt\s+\d+|Teil\s+\d+)',            # German
            r'^(Paso\s+\d+|Parte\s+\d+)',              # Spanish
            r'^(단계\s+\d+|부분\s+\d+)',                 # Korean
        ]
    
    def analyze_font_distribution(self, blocks):
        """Analyze font size distribution to understand document structure"""
        font_sizes = [block['font_size'] for block in blocks if block.get('font_size', 0) > 0]
        
        if not font_sizes:
            return {}
            
        # Group similar font sizes (within 1pt tolerance)
        size_groups = defaultdict(list)
        for size in font_sizes:
            rounded_size = round(size)
            size_groups[rounded_size].append(size)
        
        # Find the most common font size (body text)
        body_font_size = max(size_groups.keys(), key=lambda k: len(size_groups[k]))
        
        # Calculate size thresholds
        unique_sizes = sorted(set(font_sizes), reverse=True)
        
        # Define heading levels based on font size hierarchy
        thresholds = {}
        body_index = next((i for i, size in enumerate(unique_sizes) if abs(size - body_font_size) < 1), len(unique_sizes) - 1)
        
        # Sizes above body text are potential headings
        heading_sizes = unique_sizes[:body_index]
        
        if len(heading_sizes) >= 1:
            thresholds['H1'] = heading_sizes[0]
        if len(heading_sizes) >= 2:
            thresholds['H2'] = heading_sizes[1]
        if len(heading_sizes) >= 3:
            thresholds['H3'] = heading_sizes[2]
        
        # Fallback thresholds
        if 'H1' not in thresholds:
            thresholds['H1'] = body_font_size * 1.5
        if 'H2' not in thresholds:
            thresholds['H2'] = body_font_size * 1.3
        if 'H3' not in thresholds:
            thresholds['H3'] = body_font_size * 1.1
            
        return {
            'body_font_size': body_font_size,
            'thresholds': thresholds,
            'font_distribution': dict(size_groups)
        }
    
    def extract_document_title(self, blocks):
        """Extract the document title using multiple strategies"""
        title_candidates = []
        
        # Strategy 1: Largest font on first 2 pages
        first_page_blocks = [b for b in blocks if b.get('page', 1) <= 2]
        if first_page_blocks:
            max_font_size = max(b.get('font_size', 0) for b in first_page_blocks)
            large_font_blocks = [b for b in first_page_blocks 
                               if b.get('font_size', 0) >= max_font_size * 0.95]
            
            for block in large_font_blocks:
                text = block.get('text', '').strip()
                if self.is_valid_title(text):
                    title_candidates.append((text, 'font_size', block.get('font_size', 0)))
        
        # Strategy 2: Centered text on first page
        first_page_only = [b for b in blocks if b.get('page', 1) == 1]
        for block in first_page_only:
            if block.get('is_centered', False):
                text = block.get('text', '').strip()
                if self.is_valid_title(text):
                    title_candidates.append((text, 'centered', block.get('font_size', 0)))
        
        # Strategy 3: First meaningful text that looks like a title
        for block in first_page_blocks[:10]:  # Check first 10 blocks
            text = block.get('text', '').strip()
            if self.is_valid_title(text) and len(text) > 10:
                title_candidates.append((text, 'first_meaningful', block.get('font_size', 0)))
                break
        
        # Select best title candidate
        if title_candidates:
            # Prefer font_size strategy, then centered, then first_meaningful
            strategy_priority = {'font_size': 3, 'centered': 2, 'first_meaningful': 1}
            best_candidate = max(title_candidates, 
                               key=lambda x: (strategy_priority.get(x[1], 0), x[2], len(x[0])))
            return best_candidate[0]
        
        return "Untitled Document"
    
    def is_valid_title(self, text):
        """Check if text could be a valid document title"""
        if not text or len(text.strip()) < 3:
            return False
            
        # Remove common non-title patterns
        invalid_patterns = [
            r'^\d+$',  # Just numbers
            r'^Page\s+\d+',  # Page numbers
            r'^www\.',  # URLs
            r'^\s*[•◯▪▫■□●○]\s*$',  # Just bullets
            r'^\s*[-–—]\s*$',  # Just dashes
            r'^\(\d+\)$',  # Just parenthetical numbers
        ]
        
        for pattern in invalid_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return False
        
        # Check for title-like characteristics
        words = text.split()
        if len(words) == 0:
            return False
            
        # Too short or too long
        if len(text) < 5 or len(text) > 200:
            return False
            
        # Mostly punctuation
        alpha_chars = sum(1 for c in text if c.isalnum())
        if alpha_chars / len(text) < 0.3:
            return False
            
        return True
    
    def calculate_heading_score(self, block, font_analysis):
        """Calculate a score for how likely a block is to be a heading"""
        text = block.get('text', '').strip()
        
        # Early filtering - reject obvious non-headings
        if not self.is_potential_heading(text):
            return 0, None
        
        score = 0
        level_scores = {'H1': 0, 'H2': 0, 'H3': 0}
        
        font_size = block.get('font_size', 0)
        body_font = font_analysis['body_font_size']
        thresholds = font_analysis['thresholds']
        
        # Font size scoring
        font_ratio = font_size / body_font if body_font > 0 else 1
        
        # Base font size score
        if font_size >= thresholds.get('H1', float('inf')):
            level_scores['H1'] += 6 * font_ratio
        elif font_size >= thresholds.get('H2', float('inf')):
            level_scores['H2'] += 5 * font_ratio
        elif font_size >= thresholds.get('H3', float('inf')):
            level_scores['H3'] += 4 * font_ratio
        elif font_ratio > 1.2:  # Add fallback for any text larger than body
            level_scores['H3'] += 2 * font_ratio
        
        # Formatting features
        if block.get('is_bold', False):
            for level in level_scores:
                level_scores[level] += 3
        
        if block.get('is_centered', False):
            level_scores['H1'] += 4
            level_scores['H2'] += 2
        
        # Position features
        if block.get('is_first_on_page', False):
            level_scores['H1'] += 2
            level_scores['H2'] += 1
        
        if block.get('is_preceded_by_larger_gap', False):
            for level in level_scores:
                level_scores[level] += 2
        
        # Text pattern analysis
        pattern_bonus = self.analyze_text_patterns(text)
        for level in level_scores:
            level_scores[level] += pattern_bonus
        
        # Length and structure bonus
        if self.is_good_heading_length(text):
            for level in level_scores:
                level_scores[level] += 1
        
        # Determine best level and score
        best_level = max(level_scores.keys(), key=lambda k: level_scores[k])
        best_score = level_scores[best_level]
        
        # Apply minimum thresholds - increased for better precision
        min_thresholds = {'H1': 8, 'H2': 6, 'H3': 5}
        
        # Additional quality checks for better precision
        # Penalize very long text (likely paragraphs)
        if len(text.split()) > 12:
            best_score -= 2
        
        # Penalize text ending with periods (likely sentences)
        if text.strip().endswith('.') and len(text.split()) > 6:
            best_score -= 2
        
        # Bonus for text that looks like proper headings
        if text.strip().endswith(':') or text.isupper():
            best_score += 1
        
        if best_score < min_thresholds.get(best_level, 0):
            return 0, None
            
        return best_score, best_level
    
    def is_potential_heading(self, text):
        """Enhanced filtering to check if text could potentially be a heading"""
        if not text or len(text.strip()) < 2:
            return False
        
        text_clean = text.strip()
        
        # Filter out obvious non-headings with comprehensive patterns
        non_heading_patterns = [
            r'^\s*[•◯▪▫■□●○◆◇▲△▼▽★☆]\s*$',  # Just bullets
            r'^\s*[-–—]\s*$',  # Just dashes
            r'^\s*\d+\s*$',  # Just numbers
            r'^\s*\(\d+\)\s*$',  # Just parenthetical numbers
            r'^www\.',  # URLs
            r'^\s*[,;:]\s*$',  # Just punctuation
            r'^\s*[(){}[\]]\s*$',  # Just brackets/parentheses
            r'^\s*\.{2,}\s*$',  # Dots/ellipsis
            r'^\s*_{2,}\s*$',  # Underscores
            r'^\s*={2,}\s*$',  # Equal signs
            r'^\s*\*{2,}\s*$',  # Asterisks
            r'^\s*#{2,}\s*$',  # Hash marks
            r'^\s*Page\s+\d+\s*$',  # Page numbers
            r'^\s*\d+\s+of\s+\d+\s*$',  # Page x of y
            r'^\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s*$',  # Dates
            r'^\s*\d{1,2}:\d{2}(:\d{2})?\s*(AM|PM)?\s*$',  # Times
            r'^\s*\$\d+(\.\d{2})?\s*$',  # Currency
            r'^\s*\d+%\s*$',  # Percentages
            r'^\s*[A-Z]{2,}\s+\d+\s*$',  # Codes like "ISO 9001"
        ]
        
        for pattern in non_heading_patterns:
            if re.match(pattern, text_clean, re.IGNORECASE):
                return False
        
        # Filter out common document noise
        noise_keywords = [
            'copyright', '©', 'all rights reserved', 'confidential',
            'draft', 'preliminary', 'internal use only', 'proprietary',
            'page', 'printed', 'generated', 'created', 'modified',
            'document id', 'version', 'revision', 'template',
            'footer', 'header', 'watermark', 'logo', 'trademark',
            'continued on next page', 'see page', 'refer to',
            'note:', 'warning:', 'caution:', 'tip:', 'info:',
            'figure', 'table', 'chart', 'graph', 'diagram',
            'appendix', 'attachment', 'exhibit', 'schedule',
        ]
        
        text_lower = text_clean.lower()
        for keyword in noise_keywords:
            if keyword in text_lower and len(text_clean) < 50:
                return False
        
        # Filter out repetitive characters (like "........")
        if len(set(text_clean.replace(' ', ''))) <= 2 and len(text_clean) > 5:
            return False
        
        # Check character composition - must have reasonable alphanumeric content
        alpha_chars = sum(1 for c in text_clean if c.isalnum())
        if len(text_clean) > 0 and alpha_chars / len(text_clean) < 0.3:
            return False
        
        # Filter out very long text (likely paragraphs)
        if len(text_clean) > 150:
            return False
        
        # Filter out single words that are too short unless they're common headings
        words = text_clean.split()
        if len(words) == 1 and len(text_clean) < 3:
            return False
        
        # Filter out text that's mostly numbers and punctuation
        non_alpha = sum(1 for c in text_clean if not c.isalpha() and c != ' ')
        if len(text_clean) > 5 and non_alpha / len(text_clean) > 0.7:
            return False
        
        # Check for common sentence endings that indicate this is body text
        sentence_endings = ['.', '!', '?']
        if any(text_clean.endswith(ending) for ending in sentence_endings):
            # Allow if it's a question (could be a heading)
            if not text_clean.endswith('?'):
                # Allow short sentences that might be headings
                if len(words) > 8:
                    return False
        
        # Filter out URLs and email patterns
        if re.search(r'https?://', text_clean) or re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text_clean):
            return False
        
        return True
    
    def analyze_text_patterns(self, text):
        """Analyze text patterns that indicate headings with weighted scoring"""
        bonus = 0
        text_clean = text.strip()
        
        # Numbered sections (highest priority patterns)
        if re.match(r'^\d+\.?\s+', text_clean):
            bonus += 4  # Strong indicator for main sections
        elif re.match(r'^\d+\.\d+\.?\s+', text_clean):
            bonus += 3  # Strong subsection indicator
        elif re.match(r'^\d+\.\d+\.\d+\.?\s+', text_clean):
            bonus += 2  # Sub-subsection
        elif re.match(r'^\d+\.\d+\.\d+\.\d+\.?\s+', text_clean):
            bonus += 1  # Deep nesting
        
        # Roman numerals (academic style)
        if re.match(r'^[IVX]+\.?\s+', text_clean):
            bonus += 3  # Strong academic indicator
        elif re.match(r'^[ivx]+\.?\s+', text_clean):
            bonus += 2  # Lower case roman
        
        # Letter sections
        if re.match(r'^[A-Z]\.?\s+', text_clean) and len(text_clean.split()) > 1:
            bonus += 2  # Section indicator
        elif re.match(r'^[a-z]\.?\s+', text_clean) and len(text_clean.split()) > 1:
            bonus += 1  # Subsection indicator
        elif re.match(r'^\([A-Za-z0-9]\)\s+', text_clean):
            bonus += 1  # Parenthetical numbering
        
        # Chapter/Section keywords (language-aware, highest value)
        chapter_patterns = [
            r'^(Chapter\s+\d+|Section\s+\d+)',           # English
            r'^(第\d+章|第\d+節)',                        # Japanese
            r'^(Kapitel\s+\d+|Abschnitt\s+\d+)',        # German
            r'^(Chapitre\s+\d+|Section\s+\d+)',         # French
            r'^(Capítulo\s+\d+|Sección\s+\d+)',         # Spanish
            r'^(Capitolo\s+\d+|Sezione\s+\d+)',         # Italian
            r'^(Глава\s+\d+|Раздел\s+\d+)',             # Russian
            r'^(제\d+장|제\d+절)',                        # Korean
            r'^(الفصل\s+\d+|القسم\s+\d+)',               # Arabic
        ]
        
        for pattern in chapter_patterns:
            if re.match(pattern, text_clean, re.IGNORECASE):
                bonus += 5  # Very strong indicator
                break
        
        # Step/Part indicators
        step_patterns = [
            r'^(Step\s+\d+|Part\s+\d+|Phase\s+\d+)',     # English
            r'^(Étape\s+\d+|Partie\s+\d+)',             # French
            r'^(Schritt\s+\d+|Teil\s+\d+)',             # German
            r'^(Paso\s+\d+|Parte\s+\d+)',               # Spanish
            r'^(단계\s+\d+|부분\s+\d+)',                  # Korean
        ]
        
        for pattern in step_patterns:
            if re.match(pattern, text_clean, re.IGNORECASE):
                bonus += 3
                break
        
        # Special heading keywords (comprehensive multilingual)
        heading_keywords = [
            # English - High priority academic terms
            'introduction', 'conclusion', 'summary', 'abstract', 'overview', 'preface',
            'methodology', 'methods', 'results', 'discussion', 'background', 'objective',
            'chapter', 'section', 'subsection', 'appendix', 'bibliography', 'references',
            'acknowledgments', 'table of contents', 'index', 'glossary', 'foreword',
            'problem statement', 'literature review', 'data analysis', 'findings',
            'recommendations', 'future work', 'limitations', 'scope', 'definitions',
            'objectives', 'goals', 'aims', 'purpose', 'rationale', 'hypothesis',
            'theory', 'framework', 'model', 'approach', 'solution', 'implementation',
            'evaluation', 'validation', 'testing', 'experiments', 'case study',
            'related work', 'prior art', 'state of the art', 'survey', 'review',
            
            # Japanese
            '章', '節', 'まとめ', '概要', '序論', '結論', '要約', '抄録', '目次',
            '背景', '目的', '方法', '手法', '結果', '考察', '討論', '文献',
            '参考文献', '謝辞', '付録', '索引', '用語集', '前書き', '序文',
            '問題設定', '先行研究', 'データ分析', '知見', '提案', '実装',
            '評価', '検証', '実験', '事例研究', '関連研究', '今後の課題',
            
            # Chinese (Simplified & Traditional)
            '章', '节', '总结', '摘要', '引言', '结论', '概述', '目录',
            '总结', '摘要', '引言', '结论', '概述', '目录', '背景', '目标',
            '總結', '摘要', '引言', '結論', '概述', '目錄', '背景', '目標',
            
            # French
            'introduction', 'conclusion', 'résumé', 'aperçu', 'préface', 'méthodologie',
            'méthodes', 'résultats', 'discussion', 'contexte', 'objectif', 'chapitre',
            
            # German
            'einleitung', 'zusammenfassung', 'fazit', 'übersicht', 'vorwort', 'methodik',
            'methoden', 'ergebnisse', 'diskussion', 'hintergrund', 'ziel', 'kapitel',
            
            # Spanish
            'introducción', 'conclusión', 'resumen', 'metodología', 'resultados',
            'discusión', 'antecedentes', 'objetivo', 'capítulo',
            
            # Russian
            'введение', 'заключение', 'резюме', 'аннотация', 'обзор', 'методология',
            'результаты', 'обсуждение', 'цель', 'глава',
            
            # Korean
            '서론', '결론', '요약', '초록', '개요', '방법론', '결과', '토론', '목적', '장',
            
            # Arabic
            'مقدمة', 'خاتمة', 'ملخص', 'منهجية', 'نتائج', 'مناقشة', 'هدف', 'فصل'
        ]
        
        # Check for keyword matches (case-insensitive, word boundary matching)
        text_lower = text_clean.lower()
        for keyword in heading_keywords:
            # Full word match gets higher score
            if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', text_lower):
                bonus += 2
                break
            # Partial match for longer keywords gets lower score
            elif keyword.lower() in text_lower and len(keyword) > 3:
                bonus += 1
                break
        
        # Special formatting indicators
        if text_clean.isupper() and len(text_clean) > 2 and len(text_clean.split()) <= 8:
            bonus += 1  # ALL CAPS often indicates headings (but not too long)
        
        if text_clean.endswith(':') and len(text_clean) > 3:
            bonus += 1  # Colon endings often indicate section headers
        
        # Check for question format (often used in academic papers)
        if text_clean.endswith('?') and len(text_clean.split()) >= 2:
            bonus += 1
        
        # Bullet point penalty (reduce false positives)
        if re.match(r'^[•·▪▫◦‣⁃]\s+', text_clean):
            bonus -= 2  # Penalize bullet points
        
        return bonus
    
    def is_good_heading_length(self, text):
        """Check if text length is appropriate for a heading"""
        words = text.split()
        word_count = len(words)
        char_count = len(text.strip())
        
        # Good heading length: 1-15 words, 5-100 characters
        return 1 <= word_count <= 15 and 5 <= char_count <= 100
    
    def process_document(self, blocks, page_dimensions=None):
        """Main processing function"""
        if not blocks:
            return {"title": "Untitled Document", "outline": []}
        
        # Analyze font distribution
        font_analysis = self.analyze_font_distribution(blocks)
        
        # Extract title
        title = self.extract_document_title(blocks)
        
        # Classify headings
        headings = []
        for block in blocks:
            score, level = self.calculate_heading_score(block, font_analysis)
            if score > 0 and level:
                headings.append({
                    'level': level,
                    'text': block.get('text', '').strip(),
                    'page': block.get('page', 1),
                    'score': score,
                    'font_size': block.get('font_size', 0)
                })
        
        # Sort by page, then by position
        headings.sort(key=lambda x: (x['page'], -x['score']))
        
        # Post-process to ensure proper hierarchy
        final_headings = self.enforce_hierarchy(headings)
        
        # Remove title text from headings if it appears
        final_headings = [h for h in final_headings if h['text'] != title]
        
        return {
            "title": title,
            "outline": [{'level': h['level'], 'text': h['text'], 'page': h['page']} 
                       for h in final_headings]
        }
    
    def enforce_hierarchy(self, headings):
        """Ensure proper hierarchical structure H1 -> H2 -> H3"""
        if not headings:
            return []
        
        # Group headings by page
        pages = defaultdict(list)
        for h in headings:
            pages[h['page']].append(h)
        
        result = []
        current_h1_count = 0
        current_h2_count = 0
        
        for page_num in sorted(pages.keys()):
            page_headings = pages[page_num]
            
            # Sort by score (highest first)
            page_headings.sort(key=lambda x: -x['score'])
            
            for heading in page_headings:
                level = heading['level']
                
                # Hierarchy enforcement rules
                if level == 'H1':
                    current_h1_count += 1
                    current_h2_count = 0
                    result.append(heading)
                elif level == 'H2':
                    if current_h1_count > 0:  # Must have H1 before H2
                        current_h2_count += 1
                        result.append(heading)
                    else:
                        # Promote to H1 if no H1 exists
                        heading['level'] = 'H1'
                        current_h1_count += 1
                        result.append(heading)
                elif level == 'H3':
                    if current_h2_count > 0 or current_h1_count > 0:  # Must have H1 or H2
                        result.append(heading)
                    else:
                        # Promote to appropriate level
                        if current_h1_count == 0:
                            heading['level'] = 'H1'
                            current_h1_count += 1
                        else:
                            heading['level'] = 'H2'
                            current_h2_count += 1
                        result.append(heading)
        
        return result
