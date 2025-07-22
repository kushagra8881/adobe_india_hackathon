import sys

# Check required packages
required_packages = [
    "pymupdf", "sentence_transformers", "nltk", "torch", "huggingface_hub", "numpy"
]

missing_packages = []
for package in required_packages:
    try:
        __import__(package.replace("-", "_"))
    except ImportError:
        missing_packages.append(package)

if missing_packages:
    print("❌ Error: Missing required Python packages. Please install them using:")
    print(f"pip install {' '.join(missing_packages)}")
    print("\n📦 You may also need to install system packages:")
    print("- For Ubuntu/Debian: sudo apt-get install tesseract-ocr libtesseract-dev poppler-utils")
    print("- For macOS: brew install tesseract poppler")
    print("- For Windows: Install poppler and tesseract manually")
    sys.exit(1)


try:
    from model_manager import ModelManager
except ImportError as e:
    print(f"❌ Error importing project modules: {e}")
    print("Make sure all required files are in the same directory as run.py")
    sys.exit(1)

if __name__ == "__main__":
    model_manager = ModelManager()
    model_manager.setup_enhanced_models()
