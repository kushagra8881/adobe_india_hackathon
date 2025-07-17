#!/usr/bin/env python3
"""
Model Manager for downloading and managing AI models locally.
This ensures models are cached locally for better performance and offline usage.
"""
import os
import sys
import json
import torch
from pathlib import Path
from typing import Optional, Dict, Any
import hashlib
import requests
from sentence_transformers import SentenceTransformer
import nltk
from huggingface_hub import snapshot_download
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ModelManager:
    """Manages local downloading and caching of AI models."""
    
    def __init__(self, models_dir: str = "./models"):
        """
        Initialize the model manager.
        
        Args:
            models_dir: Directory to store downloaded models
        """
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Model configurations
        self.model_configs = {
            "sentence_transformer": {
                "name": "all-MiniLM-L6-v2",
                "alternative": "sentence-transformers/paraphrase-MiniLM-L6-v2",
                "size_mb": 90,
                "description": "Lightweight sentence embedding model"
            },
            "sentence_transformer_large": {
                "name": "all-mpnet-base-v2", 
                "alternative": "sentence-transformers/all-MiniLM-L12-v2",
                "size_mb": 420,
                "description": "More accurate sentence embedding model"
            }
        }
        
        # Initialize model cache
        self.loaded_models = {}
        
    def get_model_path(self, model_key: str) -> Path:
        """Get the local path for a model."""
        config = self.model_configs.get(model_key)
        if not config:
            raise ValueError(f"Unknown model key: {model_key}")
        return self.models_dir / config["name"]
    
    def is_model_downloaded(self, model_key: str) -> bool:
        """Check if a model is already downloaded locally."""
        model_path = self.get_model_path(model_key)
        return model_path.exists() and any(model_path.iterdir())
    
    def download_sentence_transformer(self, model_key: str = "sentence_transformer") -> str:
        """
        Download sentence transformer model locally.
        
        Args:
            model_key: Key for the model configuration
            
        Returns:
            Path to the downloaded model
        """
        config = self.model_configs[model_key]
        model_path = self.get_model_path(model_key)
        
        if self.is_model_downloaded(model_key):
            logger.info(f"Model {config['name']} already exists locally at {model_path}")
            return str(model_path)
        
        logger.info(f"Downloading {config['name']} ({config['size_mb']}MB)...")
        
        try:
            # Try primary model
            model = SentenceTransformer(config["name"])
            model.save(str(model_path))
            logger.info(f"Successfully downloaded {config['name']} to {model_path}")
            
        except Exception as e:
            logger.warning(f"Failed to download {config['name']}: {e}")
            logger.info(f"Trying alternative model: {config['alternative']}")
            
            try:
                # Try alternative model
                model = SentenceTransformer(config["alternative"])
                model.save(str(model_path))
                logger.info(f"Successfully downloaded {config['alternative']} to {model_path}")
                
            except Exception as e2:
                logger.error(f"Failed to download alternative model: {e2}")
                raise RuntimeError(f"Could not download any sentence transformer model: {e2}")
        
        return str(model_path)
    
    def load_sentence_transformer(self, model_key: str = "sentence_transformer") -> SentenceTransformer:
        """
        Load sentence transformer model from local cache.
        
        Args:
            model_key: Key for the model configuration
            
        Returns:
            Loaded SentenceTransformer model
        """
        if model_key in self.loaded_models:
            return self.loaded_models[model_key]
        
        # Ensure model is downloaded
        model_path = self.download_sentence_transformer(model_key)
        
        # Load model
        try:
            model = SentenceTransformer(model_path)
            self.loaded_models[model_key] = model
            logger.info(f"Loaded sentence transformer from {model_path}")
            return model
            
        except Exception as e:
            logger.error(f"Failed to load model from {model_path}: {e}")
            # Fallback: try loading from HuggingFace directly
            config = self.model_configs[model_key]
            try:
                model = SentenceTransformer(config["name"])
                self.loaded_models[model_key] = model
                logger.info(f"Loaded {config['name']} directly from HuggingFace")
                return model
            except Exception as e2:
                raise RuntimeError(f"Could not load sentence transformer: {e2}")
    
    def download_nltk_data(self):
        """Download required NLTK data."""
        nltk_data_dir = self.models_dir / "nltk_data"
        nltk_data_dir.mkdir(exist_ok=True)
        
        # Set NLTK data path
        nltk.data.path.insert(0, str(nltk_data_dir))
        
        required_nltk_data = ['punkt', 'stopwords', 'wordnet', 'averaged_perceptron_tagger']
        
        for data_name in required_nltk_data:
            try:
                nltk.data.find(f'tokenizers/{data_name}')
                logger.info(f"NLTK {data_name} already available")
            except LookupError:
                try:
                    logger.info(f"Downloading NLTK {data_name}...")
                    nltk.download(data_name, download_dir=str(nltk_data_dir))
                    logger.info(f"Successfully downloaded NLTK {data_name}")
                except Exception as e:
                    logger.warning(f"Failed to download NLTK {data_name}: {e}")
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information for model selection."""
        return {
            "torch_available": torch.cuda.is_available() if hasattr(torch, 'cuda') else False,
            "torch_version": torch.__version__ if 'torch' in sys.modules else None,
            "python_version": sys.version,
            "platform": sys.platform,
            "models_dir": str(self.models_dir),
            "available_models": [k for k in self.model_configs.keys() if self.is_model_downloaded(k)]
        }
    
    def cleanup_old_models(self, keep_latest: int = 2):
        """Clean up old model versions to save disk space."""
        logger.info("Cleaning up old model versions...")
        # Implementation for cleaning up old models if needed
        pass
    
    def setup_all_models(self, use_large_models: bool = False):
        """
        Download and setup all required models.
        
        Args:
            use_large_models: Whether to download larger, more accurate models
        """
        logger.info("Setting up all required models...")
        
        # Download NLTK data
        self.download_nltk_data()
        
        # Download sentence transformer
        model_key = "sentence_transformer_large" if use_large_models else "sentence_transformer"
        self.download_sentence_transformer(model_key)
        
        logger.info("All models setup complete!")
        
        # Print system info
        info = self.get_system_info()
        logger.info(f"System info: {json.dumps(info, indent=2)}")

if __name__ == "__main__":
    """Test the model manager."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Model Manager")
    parser.add_argument("--setup", action="store_true", help="Setup all models")
    parser.add_argument("--large", action="store_true", help="Use larger models")
    parser.add_argument("--info", action="store_true", help="Show system info")
    parser.add_argument("--models-dir", type=str, default="./models", help="Models directory")
    
    args = parser.parse_args()
    
    manager = ModelManager(args.models_dir)
    
    if args.setup:
        manager.setup_all_models(use_large_models=args.large)
    elif args.info:
        info = manager.get_system_info()
        print(json.dumps(info, indent=2))
    else:
        print("Use --setup to download models or --info to show system information")
