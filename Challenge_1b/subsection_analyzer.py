#!/usr/bin/env python3
from typing import List, Dict, Any
import re
import nltk
from nltk.tokenize import sent_tokenize
import logging
from model_manager import ModelManager

# Set up logging  
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SubsectionAnalyzer:
    """Analyzes and refines subsections from extracted document sections."""
    
    def __init__(self, model_manager: ModelManager = None):
        """
        Initialize the subsection analyzer.
        
        Args:
            model_manager: ModelManager instance for handling NLTK data
        """
        self.model_manager = model_manager or ModelManager()
        
        # Download NLTK data if needed
        self.model_manager.download_nltk_data()
        
        # Verify NLTK data is available
        try:
            nltk.data.find('tokenizers/punkt')
            logger.info("NLTK punkt tokenizer is available")
        except LookupError:
            logger.warning("NLTK punkt tokenizer not found, using basic sentence splitting")
    
    def analyze_subsections(self, documents: List[Dict[str, Any]], 
                           ranked_sections: List[Dict[str, Any]],
                           persona: str, job: str, top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Analyze and refine subsections from ranked sections.
        
        Args:
            documents: List of processed document dictionaries
            ranked_sections: List of ranked sections
            persona: Description of the user persona
            job: Job to be done by the persona
            top_n: Number of top subsections to return
            
        Returns:
            List of subsection analysis dictionaries
        """
        if not documents or not ranked_sections:
            logger.warning("No documents or ranked sections provided")
            return []
            
        subsection_analyses = []
        
        # Map document filenames to document objects
        doc_map = {doc["filename"]: doc for doc in documents}
        
        # Process each ranked section
        for ranked_section in ranked_sections:
            try:
                doc_filename = ranked_section["document"]
                page_number = ranked_section["page_number"]
                section_title = ranked_section["section_title"]
                
                # Find the section in the document
                doc = doc_map.get(doc_filename)
                if not doc:
                    logger.warning(f"Document {doc_filename} not found in document map")
                    continue
                
                # Find the section content
                section_content = None
                for section in doc["sections"]:
                    if (section["title"] == section_title and 
                        section["page_number"] == page_number):
                        section_content = section["content"]
                        break
                
                if not section_content:
                    logger.warning(f"Section content not found for {section_title} on page {page_number}")
                    continue
                
                # Refine the section content with multiple strategies
                refined_text = self._refine_text_advanced(section_content, persona, job)
                
                # Fallback if advanced refinement fails
                if not self._is_valid_text(refined_text):
                    refined_text = self._refine_text(section_content, persona, job)
                
                # Second fallback for difficult cases
                if not self._is_valid_text(refined_text):
                    refined_text = self._extract_fallback_text(section_content)
                
                # Final check - if still invalid, skip this section
                if not self._is_valid_text(refined_text):
                    logger.warning(f"Could not extract valid text from section {section_title}")
                    continue
                
                subsection_analyses.append({
                    "document": doc_filename,
                    "refined_text": refined_text,
                    "page_number": page_number,
                    "original_section_title": section_title,
                    "text_length": len(refined_text)
                })
                
                # Stop when we have enough subsections
                if len(subsection_analyses) >= top_n:
                    break
                    
            except Exception as e:
                logger.error(f"Error processing ranked section: {e}")
                continue
        
        # If we don't have enough valid subsections, add more from other sections
        if len(subsection_analyses) < top_n:
            logger.info(f"Only found {len(subsection_analyses)} valid subsections, searching for more...")
            
            for doc in documents:
                if len(subsection_analyses) >= top_n:
                    break
                    
                for section in doc["sections"]:
                    if len(subsection_analyses) >= top_n:
                        break
                        
                    # Skip sections we've already processed
                    already_processed = any(
                        sa["document"] == doc["filename"] and sa["page_number"] == section["page_number"]
                        for sa in subsection_analyses
                    )
                    
                    if already_processed:
                        continue
                    
                    try:
                        refined_text = self._extract_fallback_text(section["content"])
                        if self._is_valid_text(refined_text):
                            subsection_analyses.append({
                                "document": doc["filename"],
                                "refined_text": refined_text,
                                "page_number": section["page_number"],
                                "original_section_title": section.get("title", "Additional Content"),
                                "text_length": len(refined_text)
                            })
                    except Exception as e:
                        logger.warning(f"Error processing additional section: {e}")
                        continue
        
        logger.info(f"Generated {len(subsection_analyses)} subsection analyses")
        return subsection_analyses
    
    def _is_valid_text(self, text: str) -> bool:
        """
        Check if text is valid (not too short, not just bullet points).
        
        Args:
            text: Text to check
            
        Returns:
            True if text is valid, False otherwise
        """
        if not text or len(text) < 30:
            return False
            
        # Check if text is just bullet points or other special characters
        text_without_special = re.sub(r'[\u2022\u2023\u2043\u204C\u204D\u2219\u25D8\u25E6\u2619\u2765\u2767\n\r\t•*-]', '', text)
        if len(text_without_special.strip()) < 20:
            return False
            
        # Check if text contains actual words (at least 5 words with 3+ letters)
        words = [w for w in text.split() if len(w) >= 3]
        if len(words) < 5:
            return False
            
        return True
    
    def _refine_text(self, text: str, persona: str, job: str) -> str:
        """
        Refine text by extracting key information.
        
        Args:
            text: Section content
            persona: Description of the user persona
            job: Job to be done by the persona
            
        Returns:
            Refined text
        """
        # Clean up the text
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Break text into sentences
        sentences = sent_tokenize(text)
        
        # Keep important sentences (improved heuristic)
        important_sentences = []
        persona_keywords = set(persona.lower().split())
        job_keywords = set(job.lower().split())
        
        # General keywords based on travel planning for groups
        general_keywords = {
            'recommend', 'important', 'essential', 'key', 'must', 'best', 
            'popular', 'famous', 'unique', 'experience', 'enjoy', 'visit',
            'group', 'friend', 'budget', 'affordable', 'itinerary', 'plan',
            'activity', 'accommodation', 'restaurant', 'transport', 'local',
            'authentic', 'cost', 'price', 'ticket', 'reservation', 'book'
        }
        
        for sentence in sentences:
            # Skip very short sentences
            if len(sentence.split()) < 3:
                continue
                
            sentence_lower = sentence.lower()
            
            # Check for keywords
            has_persona_keyword = any(kw in sentence_lower for kw in persona_keywords)
            has_job_keyword = any(kw in sentence_lower for kw in job_keywords)
            has_general_keyword = any(kw in sentence_lower for kw in general_keywords)
            
            # Score the sentence
            score = 0
            if has_persona_keyword: score += 2
            if has_job_keyword: score += 2
            if has_general_keyword: score += 1
            
            # Check for informative patterns
            if re.search(r'\d+(?:\.\d+)?', sentence):  # Contains numbers
                score += 1
            if re.search(r'(?:in|at|on|near)\s+\w+', sentence):  # Contains locations
                score += 1
            if ':' in sentence or '-' in sentence:  # Likely contains a list or description
                score += 1
            
            if score >= 2:  # Threshold for importance
                important_sentences.append(sentence)
                
        # If we have too few sentences, include more based on position
        if len(important_sentences) < 3:
            # Include first 2 sentences (often contain important context)
            for i in range(min(2, len(sentences))):
                if sentences[i] not in important_sentences:
                    important_sentences.append(sentences[i])
            
            # Include sentences with bullet points
            for sentence in sentences:
                if '•' in sentence or '\u2022' in sentence:
                    if sentence not in important_sentences and len(important_sentences) < 5:
                        important_sentences.append(sentence)
        
        # Reorder sentences to maintain the original flow
        important_sentences.sort(key=lambda s: sentences.index(s))
        
        # Join sentences back together
        refined_text = " ".join(important_sentences)
        
        # Ensure it's not too long (limit to ~500 chars if needed)
        if len(refined_text) > 800:
            words = refined_text.split()
            refined_text = " ".join(words[:100])
            if len(refined_text) < 800:
                refined_text = refined_text + "..."
            
        return refined_text
    
    def _extract_fallback_text(self, text: str) -> str:
        """
        Extract fallback text when regular refinement fails.
        
        Args:
            text: Section content
            
        Returns:
            Extracted text
        """
        # Clean up the text
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Simply take the first 600 characters of meaningful text
        bullet_free_text = re.sub(r'[\u2022\u2023\u2043\u204C\u204D\u2219\u25D8\u25E6\u2619\u2765\u2767]', '', text)
        cleaned_text = re.sub(r'\s+', ' ', bullet_free_text).strip()
        
        # Take the first paragraph if possible
        paragraphs = re.split(r'\n\s*\n', cleaned_text)
        if paragraphs and len(paragraphs[0]) >= 100:
            return paragraphs[0][:600]
        
        # Otherwise take the first 600 characters
        return cleaned_text[:600]
    
    def _refine_text_advanced(self, text: str, persona: str, job: str) -> str:
        """
        Advanced text refinement using multiple strategies.
        
        Args:
            text: Section content
            persona: Description of the user persona
            job: Job to be done by the persona
            
        Returns:
            Refined text
        """
        # Clean up the text first
        text = re.sub(r'\s+', ' ', text).strip()
        
        if len(text) < 100:
            return text  # Return as-is if too short to process
        
        # Try to use NLTK sentence tokenization
        try:
            sentences = sent_tokenize(text)
        except:
            # Fallback to simple sentence splitting
            sentences = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentences if s.strip()]
        
        # Create keyword sets for scoring
        persona_keywords = set(word.lower() for word in persona.split() if len(word) > 2)
        job_keywords = set(word.lower() for word in job.split() if len(word) > 2)
        
        # Enhanced keyword sets based on common scenarios
        scenario_keywords = {
            'travel': {'travel', 'trip', 'visit', 'destination', 'tourist', 'sightseeing', 'vacation', 'holiday'},
            'planning': {'plan', 'schedule', 'itinerary', 'organize', 'arrange', 'book', 'reserve'},
            'group': {'group', 'friends', 'party', 'team', 'together', 'collective'},
            'budget': {'budget', 'cost', 'price', 'cheap', 'expensive', 'afford', 'money', 'fee'},
            'activities': {'activity', 'attraction', 'entertainment', 'fun', 'experience', 'adventure'},
            'accommodation': {'hotel', 'hostel', 'accommodation', 'stay', 'lodge', 'room'},
            'food': {'restaurant', 'food', 'dining', 'cuisine', 'meal', 'eat', 'cafe'},
            'transport': {'transport', 'travel', 'bus', 'train', 'flight', 'car', 'taxi', 'metro'}
        }
        
        # Flatten all scenario keywords
        all_scenario_keywords = set()
        for keywords in scenario_keywords.values():
            all_scenario_keywords.update(keywords)
        
        # Score sentences
        scored_sentences = []
        for sentence in sentences:
            if len(sentence.split()) < 3:  # Skip very short sentences
                continue
                
            sentence_lower = sentence.lower()
            score = 0
            
            # Persona keyword matches
            persona_matches = sum(1 for kw in persona_keywords if kw in sentence_lower)
            score += persona_matches * 3
            
            # Job keyword matches
            job_matches = sum(1 for kw in job_keywords if kw in sentence_lower)
            score += job_matches * 3
            
            # Scenario keyword matches
            scenario_matches = sum(1 for kw in all_scenario_keywords if kw in sentence_lower)
            score += scenario_matches * 1
            
            # Informational content indicators
            if re.search(r'\d+', sentence):  # Contains numbers
                score += 2
            if re.search(r'(?:in|at|on|near|from|to)\s+[A-Z][a-z]+', sentence):  # Contains locations
                score += 2
            if any(word in sentence_lower for word in ['recommend', 'suggest', 'important', 'must', 'should']):
                score += 3
            if any(char in sentence for char in ['-', ':', '•']):  # Lists or structured content
                score += 1
            
            # Position bonus (first and last sentences often important)
            position = sentences.index(sentence)
            if position == 0:
                score += 2
            elif position == len(sentences) - 1:
                score += 1
            
            scored_sentences.append((sentence, score))
        
        # Sort by score and select best sentences
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        
        # Select sentences maintaining readability
        selected_sentences = []
        total_length = 0
        max_length = 800
        
        # Always include highest scoring sentences
        for sentence, score in scored_sentences:
            if score > 0 and total_length + len(sentence) <= max_length:
                selected_sentences.append(sentence)
                total_length += len(sentence)
            elif len(selected_sentences) >= 3:  # Minimum 3 sentences
                break
        
        # If we don't have enough content, add more sentences
        if total_length < 200 and len(selected_sentences) < 5:
            for sentence, score in scored_sentences:
                if sentence not in selected_sentences and total_length + len(sentence) <= max_length * 1.2:
                    selected_sentences.append(sentence)
                    total_length += len(sentence)
        
        # Reorder sentences to maintain original flow
        if selected_sentences:
            # Sort by original position
            selected_sentences.sort(key=lambda s: sentences.index(s))
            refined_text = " ".join(selected_sentences)
        else:
            # Fallback to original text truncated
            refined_text = text[:800]
        
        return refined_text.strip()
    
    def _safe_sentence_tokenize(self, text: str) -> List[str]:
        """
        Safely tokenize text into sentences with fallback methods.
        
        Args:
            text: Text to tokenize
            
        Returns:
            List of sentences
        """
        try:
            return sent_tokenize(text)
        except:
            # Fallback 1: Use regex
            sentences = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentences if s.strip()]
            if sentences:
                return sentences
            
            # Fallback 2: Split by newlines and filter
            lines = text.split('\n')
            lines = [line.strip() for line in lines if line.strip() and len(line.strip()) > 10]
            if lines:
                return lines
            
            # Fallback 3: Return as single sentence
            return [text.strip()] if text.strip() else []