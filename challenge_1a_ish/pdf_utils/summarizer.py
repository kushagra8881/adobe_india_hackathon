# pdf_utils/summarizer.py

from spacy.lang.en.stop_words import STOP_WORDS
from string import punctuation
from heapq import nlargest
import collections

# It's better to get language-specific stop words from the loaded NLP model if available
def get_stopwords_and_punctuation(nlp_model):
    """
    Retrieves language-specific stopwords and punctuation from the spaCy model.
    Falls back to English if not found.
    """
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
    
    # Get language-specific stopwords and punctuation
    stop_words, all_punctuation = get_stopwords_and_punctuation(nlp_model)

    # 1. Word Frequency - consider lemma for better aggregation
    word_frequencies = collections.defaultdict(int)
    for word in doc:
        # Process lemma and check if it's alphanumeric and not a stop word/punctuation
        if word.is_alpha and word.text.lower() not in stop_words and word.text not in all_punctuation:
            word_frequencies[word.lemma_.lower()] += 1 # Use lemma for frequency count

    if not word_frequencies:
        # Fallback for text with only stop words or punctuation
        # Just take the first few sentences
        return " ".join([sent.text.strip() for sent in doc.sents][:max_sentences])

    max_frequency = max(word_frequencies.values())
    if max_frequency > 0:
        for word_lemma in word_frequencies.keys():
            word_frequencies[word_lemma] = (word_frequencies[word_lemma] / max_frequency)
    else: # Should not happen if word_frequencies is not empty, but safeguard
        return " ".join([sent.text.strip() for sent in doc.sents][:max_sentences])

    # 2. Sentence Scoring
    sentence_tokens = list(doc.sents)
    sentence_scores = collections.defaultdict(float)
    
    for sent in sentence_tokens:
        for word in sent:
            if word.is_alpha and word.lemma_.lower() in word_frequencies:
                sentence_scores[sent] += word_frequencies[word.lemma_.lower()]
    
    # 3. Select top sentences
    if not sentence_scores:
        return " ".join([sent.text.strip() for sent in sentence_tokens][:max_sentences])

    # Ensure we don't request more sentences than available
    select_length = min(len(sentence_tokens), max_sentences)
    
    # Use nlargest to get sentences with highest scores
    # Ensure to sort them back in original document order for coherence
    summary_sents_heap = nlargest(select_length, sentence_scores, key=sentence_scores.get)
    summary_sents_ordered = sorted(summary_sents_heap, key=lambda sent: sent.start) # Sort by original position

    final_summary = [sent.text.strip() for sent in summary_sents_ordered]
    summary = " ".join(final_summary)
    
    # Clean up multiple spaces and newlines that might result from joining
    summary = re.sub(r'\s+', ' ', summary).strip()
    return summary