#!/usr/bin/env python3
import torch
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import numpy as np
import logging
from model_manager import ModelManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RelevanceRanker:
    """Ranks document sections by relevance to persona and job."""
    
    def __init__(self, model_manager: ModelManager = None, use_large_model: bool = False):
        """
        Initialize the relevance ranker.
        
        Args:
            model_manager: ModelManager instance for handling models
            use_large_model: Whether to use a larger, more accurate model
        """
        self.model_manager = model_manager or ModelManager()
        
        # Select model based on preference
        self.model_key = "sentence_transformer_large" if use_large_model else "sentence_transformer"
        
        # Load the model
        try:
            self.model = self.model_manager.load_sentence_transformer(self.model_key)
            logger.info(f"Successfully loaded model: {self.model_key}")
        except Exception as e:
            logger.error(f"Failed to load model {self.model_key}: {e}")
            # Fallback to basic model
            try:
                self.model = self.model_manager.load_sentence_transformer("sentence_transformer")
                logger.info("Fallback to basic sentence transformer model")
            except Exception as e2:
                raise RuntimeError(f"Could not load any sentence transformer model: {e2}")
        
    def rank_sections(self, documents: List[Dict[str, Any]], 
                      persona: str, job: str, top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Rank document sections by relevance.
        
        Args:
            documents: List of processed document dictionaries
            persona: Description of the user persona
            job: Job to be done by the persona
            top_n: Number of top sections to return
            
        Returns:
            List of ranked sections
        """
        if not documents:
            logger.warning("No documents provided for ranking")
            return []
        
        # Create multiple query variations for better matching
        queries = [
            f"As a {persona}, I need to {job}",
            f"{persona} {job}",
            f"Information for {persona} to {job}",
            job,
            persona
        ]
        
        # Get embeddings for all queries
        query_embeddings = self.model.encode(queries)
        
        # Extract all sections from documents
        all_sections = []
        for doc in documents:
            if "sections" not in doc or not doc["sections"]:
                logger.warning(f"Document {doc.get('filename', 'unknown')} has no sections")
                continue
                
            for section in doc["sections"]:
                if not section.get("content", "").strip():
                    continue  # Skip empty sections
                    
                all_sections.append({
                    "document": doc["filename"],
                    "section_title": section.get("title", "Untitled"),
                    "page_number": section.get("page_number", 1),
                    "content": section["content"]
                })
        
        if not all_sections:
            logger.warning("No valid sections found in documents")
            return []
        
        # Prepare section texts for embedding
        section_texts = []
        for section in all_sections:
            # Combine title and content for better context
            title = section['section_title']
            content = section['content'][:1000]  # Limit content length
            section_text = f"{title}: {content}" if title != "Untitled" else content
            section_texts.append(section_text)
        
        # Compute section embeddings in batches to handle memory better
        batch_size = 32
        section_embeddings = []
        
        for i in range(0, len(section_texts), batch_size):
            batch = section_texts[i:i + batch_size]
            try:
                batch_embeddings = self.model.encode(batch)
                section_embeddings.extend(batch_embeddings)
            except Exception as e:
                logger.error(f"Error encoding batch {i//batch_size}: {e}")
                # Fallback: encode one by one
                for text in batch:
                    try:
                        embedding = self.model.encode([text])[0]
                        section_embeddings.append(embedding)
                    except:
                        # Create zero embedding as fallback
                        section_embeddings.append(np.zeros(self.model.get_sentence_embedding_dimension()))
        
        # Calculate similarity scores
        similarity_scores = []
        for i, section_embedding in enumerate(section_embeddings):
            max_similarity = 0
            
            # Check similarity with all query variations
            for query_embedding in query_embeddings:
                try:
                    # Cosine similarity
                    similarity = np.dot(section_embedding, query_embedding) / (
                        np.linalg.norm(section_embedding) * np.linalg.norm(query_embedding) + 1e-8
                    )
                    max_similarity = max(max_similarity, similarity)
                except:
                    continue
            
            # Add content-based bonus scoring
            section = all_sections[i]
            content_bonus = self._calculate_content_bonus(section, persona, job)
            final_score = max_similarity + content_bonus
            
            similarity_scores.append({
                "index": i,
                "score": float(final_score),  # Ensure serializable
                "similarity": float(max_similarity),
                "content_bonus": float(content_bonus)
            })
        
        # Sort by score and take top_n
        similarity_scores.sort(key=lambda x: x["score"], reverse=True)
        top_indices = [item["index"] for item in similarity_scores[:top_n]]
        
        # Create ranked sections
        ranked_sections = []
        for i, idx in enumerate(top_indices):
            section = all_sections[idx]
            score_info = similarity_scores[i]
            
            ranked_sections.append({
                "document": section["document"],
                "section_title": section["section_title"],
                "importance_rank": i + 1,
                "page_number": section["page_number"],
                "relevance_score": score_info["score"],
                "similarity_score": score_info["similarity"],
                "content_bonus": score_info["content_bonus"]
            })
        
        logger.info(f"Ranked {len(all_sections)} sections, returning top {len(ranked_sections)}")
        return ranked_sections
    
    def _calculate_content_bonus(self, section: Dict[str, Any], persona: str, job: str) -> float:
        """
        Calculate content-based bonus for section relevance.
        
        Args:
            section: Section dictionary
            persona: User persona
            job: Job to be done
            
        Returns:
            Content bonus score
        """
        bonus = 0.0
        content = section["content"].lower()
        title = section["section_title"].lower()
        
        # Keyword matching bonus
        persona_words = set(persona.lower().split())
        job_words = set(job.lower().split())
        
        # Check for persona keywords
        for word in persona_words:
            if len(word) > 2:  # Skip short words
                if word in content:
                    bonus += 0.02
                if word in title:
                    bonus += 0.05
        
        # Check for job keywords
        for word in job_words:
            if len(word) > 2:  # Skip short words
                if word in content:
                    bonus += 0.02
                if word in title:
                    bonus += 0.05
        
        # General useful keywords for travel planning
        useful_keywords = [
            'recommend', 'important', 'essential', 'must', 'best', 'popular', 
            'guide', 'tip', 'advice', 'suggestion', 'experience', 'activity',
            'cost', 'price', 'budget', 'cheap', 'expensive', 'free',
            'group', 'friends', 'young', 'student', 'college',
            'plan', 'itinerary', 'schedule', 'time', 'day', 'visit',
            'location', 'place', 'area', 'region', 'city', 'town'
        ]
        
        for keyword in useful_keywords:
            if keyword in content:
                bonus += 0.01
            if keyword in title:
                bonus += 0.02
        
        # Length bonus (longer sections might have more information)
        content_length = len(section["content"])
        if content_length > 500:
            bonus += 0.01
        if content_length > 1000:
            bonus += 0.01
        
        # Title clarity bonus
        if len(section["section_title"]) > 10 and section["section_title"] != "Untitled":
            bonus += 0.01
        
        return min(bonus, 0.2)  # Cap bonus at 0.2