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
    # print(f"Warning: LanguageDetector factory registration issue: {e}") # Uncomment for debugging
    pass

def detect_language(text: str) -> str:
    """
    Detects the language of a given text string using spacy-langdetect.
    """
    if not text.strip():
        return 'en' # Default to English if no text

    try:
        # Load with minimal components for speed, but ensuring sentencizer and tokenizer work.
        # 'xx_ent_wiki_sm' is a good universal starting point for detection.
        nlp_for_detection = spacy.load("xx_ent_wiki_sm")
        
        # Remove components not strictly necessary for language detection to save resources.
        components_to_remove = ['transformer', 'tagger', 'parser', 'ner', 'attribute_ruler', 'lemmatizer']
        for component in components_to_remove:
            if nlp_for_detection.has_pipe(component):
                nlp_for_detection.remove_pipe(component)

        # Ensure sentencizer is present; it's crucial for spacy-langdetect.
        if "sentencizer" not in nlp_for_detection.pipe_names:
            nlp_for_detection.add_pipe("sentencizer", first=True) # Add early for sentence processing
        
        # Add the language detector
        if "language_detector" not in nlp_for_detection.pipe_names:
            nlp_for_detection.add_pipe('language_detector', last=True)

        doc = nlp_for_detection(text[:5000]) # Limit text length for faster detection
        
        detected_lang = 'un'
        confidence_score = 0.0

        if hasattr(doc, '_') and hasattr(doc._, 'language'):
            lang_data = doc._.language
            detected_lang = lang_data.get('language', 'un')
            confidence_score = lang_data.get('score', 0.0)

        # Return 'en' if confidence is low or detection fails.
        if detected_lang == 'un' or confidence_score < 0.6: # Relaxed confidence slightly
            return 'en' 
        return detected_lang

    except OSError as e: 
        print(f"ERROR: SpaCy 'xx_ent_wiki_sm' model not found. Cannot perform language detection accurately. Please ensure it's downloaded ('python -m spacy download xx_ent_wiki_sm'). Falling back to 'en'. Error: {e}")
        return 'en'
    except Exception as e:
        print(f"ERROR: An unexpected error occurred during language detection process: {type(e).__name__}: {e}. Returning 'en'.")
        return 'en'


def get_multilingual_nlp(lang: str) -> spacy.language.Language:
    """
    Loads a spaCy model for the detected language, prioritizing language-specific
    models, then falling back to 'xx_ent_wiki_sm'.
    Ensures tokenizer and sentencizer are loaded.
    """
    # Mapping of common languages to recommended spaCy models (small versions for speed)
    model_map = {
        "en": "en_core_web_sm",
        "ja": "ja_core_news_sm", # Japanese model (requires download)
        "zh": "zh_core_web_sm", # Chinese model (requires download)
        "de": "de_core_news_sm", # German example
        "fr": "fr_core_news_sm", # French example
        "es": "es_core_news_sm", # Spanish example
        # Add more as needed
    }
    
    # Try to load language-specific model first
    model_name = model_map.get(lang)
    nlp_model = None

    if model_name:
        try:
            nlp_model = spacy.load(model_name)
            print(f"  Loaded spaCy model: {model_name}")
        except OSError:
            print(f"  Warning: Language-specific model '{model_name}' not found. Falling back to 'xx_ent_wiki_sm'.")
        except Exception as e:
            print(f"  Warning: Error loading '{model_name}': {e}. Falling back to 'xx_ent_wiki_sm'.")

    # Fallback to xx_ent_wiki_sm if language-specific model not found or failed
    if nlp_model is None:
        model_name = "xx_ent_wiki_sm"
        try:
            nlp_model = spacy.load(model_name)
            print(f"  Loaded spaCy model: {model_name}")
        except OSError as e:
            print(f"ERROR: SpaCy model '{model_name}' not found locally. Please ensure it is downloaded ('python -m spacy download {model_name}') before running in an offline environment. Error: {e}")
            raise RuntimeError(f"An unexpected error occurred while loading spaCy model '{model_name}': {e}. Please check your spaCy installation and ensure models are downloaded.")
        except Exception as e:
            print(f"ERROR: An unexpected error occurred while loading spaCy model in get_multilingual_nlp: {type(e).__name__}: {e}.")
            raise RuntimeError(f"An unexpected error occurred while loading spaCy model '{model_name}': {e}. Please check your spaCy installation.")

    # Remove components not strictly needed to reduce memory and processing time.
    # Keep 'tokenizer', 'sentencizer', 'lemmatizer' if available.
    components_to_remove = ['transformer', 'tagger', 'parser', 'ner', 'attribute_ruler'] # Keep lemmatizer for meaningfulness checks
    for component in components_to_remove:
        if nlp_model.has_pipe(component):
            try:
                nlp_model.remove_pipe(component)
            except ValueError: # Already removed or not present
                pass

    # Ensure sentencizer is always present and early in pipeline for sentence boundary detection
    if "sentencizer" not in nlp_model.pipe_names:
        nlp_model.add_pipe("sentencizer", first=True)

    # Fallback for tokenizer: Crucial if the loaded model still somehow lacks one (rare but good safeguard).
    if not hasattr(nlp_model, 'tokenizer') or nlp_model.tokenizer is None:
        try:
            # Attempt to use a basic English tokenizer as a last resort
            from spacy.lang.en import English
            nlp_model.tokenizer = English().tokenizer
            print("  Warning: Using fallback English tokenizer.")
        except Exception as e:
            print(f"  Error setting fallback tokenizer: {e}. Tokenization might fail for some text.")

    return nlp_model