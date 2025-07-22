# pdf_utils/language.py

import spacy
from spacy.language import Language
from spacy_langdetect import LanguageDetector
import os

# To make spacy_langdetect work without relying on an internet connection for downloading
# language data, you often need to ensure the underlying 'langdetect' package
# has its data available. For most cases, `pip install langdetect` is enough.

def get_lang_detector(nlp, name):
    # This factory function is needed by spaCy's pipe system
    return LanguageDetector()

def detect_language(text):
    """
    Detects the language of a given text using spaCy and spacy-langdetect.
    Designed for offline use.
    """
    try:
        # We need a spaCy model that can handle tokenization for LanguageDetector.
        # 'xx_ent_wiki_sm' is a small multilingual model, good for this purpose.
        # Disable components not needed for just language detection to save memory and speed.
        nlp_for_detection = spacy.load("xx_ent_wiki_sm", disable=['parser', 'ner', 'textcat'])
        
        # Register the language detector if not already registered
        if "language_detector" not in nlp_for_detection.pipe_names:
            Language.factory("language_detector", func=get_lang_detector)
            nlp_for_detection.add_pipe('language_detector', last=True)
        
        # Analyze first 5000 characters for speed. This is usually sufficient for lang detection.
        doc = nlp_for_detection(text[:5000])
        
        detected_lang = doc._.language['language']
        # If confidence is low or language is undetermined, fallback to English
        if detected_lang == 'un' or (hasattr(doc._.language, 'score') and doc._.language['score'] < 0.7):
            return 'en' # Fallback to English
        return detected_lang
    except OSError: # Catch if the xx_ent_wiki_sm model is not found
        print("SpaCy 'xx_ent_wiki_sm' model not found. Cannot perform language detection accurately. Please ensure it's downloaded for offline use ('python -m spacy download xx_ent_wiki_sm'). Falling back to 'en'.")
        return 'en'
    except Exception as e:
        print(f"An unexpected error occurred during language detection: {e}. Falling back to 'en'.")
        return 'en'


def get_multilingual_nlp(lang):
    """
    Loads a spaCy model based on the detected language.
    Prioritizes 'xx_ent_wiki_sm' for offline constraints and model size.
    """
    # For strict <= 200MB, no internet, and CPU, 'xx_ent_wiki_sm' is the most sensible choice.
    # We explicitly do NOT try to download larger language-specific models here.
    model_name = "xx_ent_wiki_sm" # Only use this model for the whole pipeline

    try:
        # Load with disabled components to further reduce memory footprint and speed up loading
        return spacy.load(model_name, disable=['parser', 'ner', 'textcat'])
    except OSError:
        # This means the model is not found locally.
        # Since no internet is allowed, we cannot download it here.
        raise RuntimeError(f"SpaCy model '{model_name}' not found locally. Please ensure it is downloaded manually ('python -m spacy download {model_name}') before running in an offline environment.")
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred while loading spaCy model '{model_name}': {e}. Please check your spaCy installation.")