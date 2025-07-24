from spacy.lang.en.stop_words import STOP_WORDS
from string import punctuation
from heapq import nlargest
import collections
import re 

def get_stopwords_and_punctuation(nlp_model):
    """
    Retrieves language-specific stopwords and punctuation from the spaCy model.
    Falls back to English if not found.
    """
    # Use nlp_model.Defaults.stop_words if available, otherwise fallback to generic English
    stop_words = nlp_model.Defaults.stop_words if hasattr(nlp_model.Defaults, 'stop_words') else STOP_WORDS
    all_punctuation = set(punctuation)
    return stop_words, all_punctuation

def summarize_text(text, nlp_model, max_sentences=3):
    """
    Generates a simple extractive summary of the text using sentence scoring.
    Handles cases with empty text or no significant words.
    """
    if not text or not nlp_model:
        return ""

    doc = nlp_model(text)
    
    stop_words, all_punctuation = get_stopwords_and_punctuation(nlp_model)

    word_frequencies = collections.defaultdict(int)
    for word in doc:
        # Process lemma and check if it's alphanumeric and not a stop word/punctuation
        if word.is_alpha and word.text.lower() not in stop_words and word.text not in all_punctuation:
            word_frequencies[word.lemma_.lower()] += 1 

    if not word_frequencies:
        # Fallback for text with only stop words or punctuation, return first few sentences
        return " ".join([sent.text.strip() for sent in doc.sents][:max_sentences])

    max_frequency = max(word_frequencies.values())
    if max_frequency > 0:
        for word_lemma in word_frequencies.keys():
            word_frequencies[word_lemma] = (word_frequencies[word_lemma] / max_frequency)
    else: 
        # If all words have zero frequency (shouldn't happen if word_frequencies is not empty, but good defensive check)
        return " ".join([sent.text.strip() for sent in doc.sents][:max_sentences])

    sentence_tokens = list(doc.sents)
    sentence_scores = collections.defaultdict(float)
    
    for sent in sentence_tokens:
        for word in sent:
            if word.is_alpha and word.lemma_.lower() in word_frequencies:
                sentence_scores[sent] += word_frequencies[word.lemma_.lower()]
    
    if not sentence_scores:
        # If no sentences scored, return first few sentences as fallback
        return " ".join([sent.text.strip() for sent in sentence_tokens][:max_sentences])

    select_length = min(len(sentence_tokens), max_sentences)
    
    # Use nlargest to get top sentences by score, then sort them by their original order in the document
    summary_sents_heap = nlargest(select_length, sentence_scores, key=sentence_scores.get)
    summary_sents_ordered = sorted(summary_sents_heap, key=lambda sent: sent.start) 

    final_summary = [sent.text.strip() for sent in summary_sents_ordered]
    summary = " ".join(final_summary)
    
    # Clean up excessive whitespace
    summary = re.sub(r'\s+', ' ', summary).strip()
    return summary