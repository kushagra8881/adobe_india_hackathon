import spacy
from spacy.language import Language
from spacy_langdetect import LanguageDetector
import os

try:
    # Check if factory is already registered to avoid errors on multiple imports
    if not Language.has_factory("language_detector"):
        @Language.factory("language_detector")
        def create_lang_detector(nlp, name):
            return LanguageDetector()
except Exception as e:
    # Pass silently if already registered, or if there's an unexpected error during registration
    pass


def detect_language(text):
    if not text.strip():
        return 'en' # Default to English if no text

    try:
        # Load with minimal components, but ensuring tokenizer works.
        # 'tok2vec' and 'parser' are often heavy but not needed for basic detection.
        # 'sentencizer' is crucial for spacy-langdetect.
        # Loading 'xx_ent_wiki_sm' explicitly, then selectively removing pipes is safer than `disable`.
        nlp_for_detection = spacy.load("xx_ent_wiki_sm")
        
        # Remove components not strictly necessary for language detection.
        # Keep 'tokenizer' and ensure 'sentencizer' and 'language_detector' are present.
        components_to_remove = ['transformer', 'tagger', 'parser', 'ner', 'attribute_ruler', 'lemmatizer']
        for component in components_to_remove:
            if nlp_for_detection.has_pipe(component):
                nlp_for_detection.remove_pipe(component)

        if "sentencizer" not in nlp_for_detection.pipe_names:
            nlp_for_detection.add_pipe("sentencizer")
        
        if "language_detector" not in nlp_for_detection.pipe_names:
            nlp_for_detection.add_pipe('language_detector', last=True)

        doc = nlp_for_detection(text[:5000]) # Limit text length for faster detection
        
        detected_lang = 'un'
        if hasattr(doc, '_') and hasattr(doc._, 'language') and 'language' in doc._.language:
            detected_lang = doc._.language['language']
        else:
            # Fallback if spacy-langdetect extension isn't found for some reason
            if hasattr(doc, 'lang_'):
                detected_lang = doc.lang_

        # Return 'en' if confidence is low or detection fails.
        if detected_lang == 'un' or (hasattr(doc, '_') and hasattr(doc._, 'language') and hasattr(doc._.language, 'score') and doc._.language['score'] < 0.6): # Relaxed confidence slightly
            return 'en' 
        return detected_lang
    except OSError as e: 
        print(f"ERROR: SpaCy 'xx_ent_wiki_sm' model not found. Cannot perform language detection accurately. Please ensure it's downloaded ('python -m spacy download xx_ent_wiki_sm'). Falling back to 'en'. Error: {e}")
        return 'en'
    except Exception as e:
        print(f"ERROR: An unexpected error occurred during language detection process: {type(e).__name__}: {e}. Returning 'en'.")
        return 'en'


def get_multilingual_nlp(lang):
    """
    Loads a spaCy model for the detected language, strictly using xx_ent_wiki_sm.
    Ensures tokenizer is loaded.
    """
    model_name = "xx_ent_wiki_sm" 

    try:
        nlp_model = spacy.load(model_name) 
        
        # Remove components not needed for summarization or meaningful fragment check.
        # Keep 'sentencizer' and 'lemmatizer' if they exist, as they are useful.
        components_to_remove = ['transformer', 'tagger', 'parser', 'ner', 'attribute_ruler'] # Keep lemmatizer for summarization
        for component in components_to_remove:
            if nlp_model.has_pipe(component):
                nlp_model.remove_pipe(component)

        if "sentencizer" not in nlp_model.pipe_names:
            nlp_model.add_pipe("sentencizer")

        # Fallback for tokenizer: Crucial if the loaded model still somehow lacks one.
        if not hasattr(nlp_model, 'tokenizer') or nlp_model.tokenizer is None:
            from spacy.lang.en import English
            nlp_model.tokenizer = English().tokenizer # Fallback to a basic English tokenizer for tokenization

        return nlp_model
    except OSError as e:
        print(f"ERROR: SpaCy model '{model_name}' not found locally. Please ensure it is downloaded manually ('python -m spacy download {model_name}') before running in an offline environment. Error: {e}")
        raise RuntimeError(f"An unexpected error occurred while loading spaCy model '{model_name}': {e}. Please check your spaCy installation.")
    except Exception as e:
        print(f"ERROR: An unexpected error occurred while loading spaCy model in get_multilingual_nlp: {type(e).__name__}: {e}.")
        raise RuntimeError(f"An unexpected error occurred while loading spaCy model '{model_name}': {e}. Please check your spaCy installation.")