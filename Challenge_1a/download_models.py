#!/usr/bin/env python3
"""
Script to download SpaCy model wheel files for offline Docker deployment.
Run this script to download the required .whl files to the models/ directory.
"""

import os
import subprocess
import sys
import urllib.request
import shutil

def download_file(url, destination):
    """Download a file from URL to destination."""
    print(f"Downloading {url}...")
    try:
        urllib.request.urlretrieve(url, destination)
        print(f"✓ Downloaded {destination}")
        return True
    except Exception as e:
        print(f"✗ Failed to download {url}: {e}")
        return False

def main():
    # Create models directory if it doesn't exist
    models_dir = "models"
    os.makedirs(models_dir, exist_ok=True)
    
    # SpaCy model URLs (adjust versions as needed)
    models = {
        "xx_ent_wiki_sm-3.7.0-py3-none-any.whl": 
            "https://github.com/explosion/spacy-models/releases/download/xx_ent_wiki_sm-3.7.0/xx_ent_wiki_sm-3.7.0-py3-none-any.whl",
        "en_core_web_sm-3.7.1-py3-none-any.whl": 
            "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl"
    }
    
    success_count = 0
    for filename, url in models.items():
        filepath = os.path.join(models_dir, filename)
        
        # Skip if file already exists
        if os.path.exists(filepath):
            print(f"⚠ {filename} already exists, skipping...")
            success_count += 1
            continue
            
        if download_file(url, filepath):
            success_count += 1
    
    print(f"\n{'='*50}")
    print(f"Downloaded {success_count}/{len(models)} model files")
    
    if success_count == len(models):
        print("✅ All models downloaded successfully!")
        print("\nNext steps:")
        print("1. Build your Docker image: docker build -t your-app .")
        print("2. The models will be installed directly from the .whl files")
    else:
        print("❌ Some downloads failed. Check the URLs and try again.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
