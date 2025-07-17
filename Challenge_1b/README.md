# Enhanced Document Intelligence System

An advanced document intelligence system that extracts and prioritizes the most relevant sections from multiple documents based on a specific persona and their job-to-be-done. This enhanced version includes local model caching, improved processing, and better performance across various scenarios.

## 🚀 New Features

- **Local Model Management**: Downloads and caches AI models locally for better performance and offline usage
- **Enhanced Text Processing**: Improved section detection, OCR support, and text refinement
- **Advanced Relevance Ranking**: Multi-query matching with content-based scoring for better accuracy
- **Robust Error Handling**: Better error recovery and fallback mechanisms
- **Comprehensive Testing**: Enhanced test suite with multiple scenarios
- **Performance Monitoring**: Detailed timing and system information tracking

## 📋 Requirements

### System Requirements
- Python 3.7 or higher (64-bit recommended)
- 2GB+ free disk space for models
- 4GB+ RAM recommended

### Dependencies
- PyMuPDF for PDF processing
- Sentence Transformers for semantic similarity
- NLTK for text processing
- PyTorch for ML models
- Tesseract OCR (optional, for image-based text extraction)

## 🛠️ Installation & Setup

### Option 1: Automated Setup (Recommended)
```bash
# Install dependencies and download models
python setup.py

# For larger, more accurate models (requires more memory)
python setup.py --large-models

# Verify setup
python setup.py --verify-only
```

### Option 2: Manual Setup
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install system dependencies (Ubuntu/Debian)
sudo apt-get install tesseract-ocr libtesseract-dev poppler-utils

# Download models manually
python -c "from model_manager import ModelManager; ModelManager().setup_all_models()"
```

### Option 3: Docker
```bash
# Build the Docker image
docker build -t doc-intelligence .

# Run with Docker
docker run -v $(pwd):/app doc-intelligence \
    --input-dir "/app/Collection 1/PDFs" \
    --persona "Travel Planner" \
    --job "Plan a trip of 4 days for a group of 10 college friends"
```

## 🎯 Usage

### Basic Usage
```bash
python run.py \
    --input-dir "./Collection 1/PDFs" \
    --persona "Travel Planner" \
    --job "Plan a trip of 4 days for a group of 10 college friends" \
    --output-file "output.json"
```

### Advanced Usage
```bash
python run.py \
    --input-dir "./documents" \
    --persona "Software Trainer" \
    --job "Create a comprehensive training program" \
    --output-file "training_analysis.json" \
    --top-sections 10 \
    --top-subsections 8 \
    --use-large-models \
    --use-ocr \
    --verbose
```

### Command Line Options
- `--input-dir`: Directory containing PDF files (required)
- `--persona`: Description of the user persona (required)
- `--job`: Job to be done by the persona (required)
- `--output-file`: Path to output JSON file (default: challenge1b_output.json)
- `--top-sections`: Number of top sections to extract (default: 5)
- `--top-subsections`: Number of top subsections to analyze (default: 5)
- `--models-dir`: Directory to store downloaded models (default: ./models)
- `--use-large-models`: Use larger, more accurate models
- `--use-ocr`: Enable OCR for image-based text extraction
- `--verbose`: Enable verbose logging

## 🧪 Testing

### Run Comprehensive Tests
```bash
# Run all tests
python enhanced_test.py

# Run original basic test
python test.py
```

### Test Individual Components
```bash
# Test model manager
python -c "from enhanced_test import test_model_manager; test_model_manager()"

# Test document processor
python -c "from enhanced_test import test_document_processor; test_document_processor()"
```

## 📁 Project Structure

```
Challenge_1b/
├── model_manager.py          # Local model management
├── document_processor.py     # Enhanced PDF processing
├── relevance_ranker.py       # Improved section ranking
├── subsection_analyzer.py    # Advanced text analysis
├── run.py                    # Main execution script
├── setup.py                  # Automated setup script
├── enhanced_test.py          # Comprehensive test suite
├── requirements.txt          # Python dependencies
├── Dockerfile               # Container configuration
├── README.md                # This file
├── models/                  # Local model cache (created automatically)
├── Collection 1/            # Example document collection
├── Collection 2/            # Example document collection
└── Collection 3/            # Example document collection
```

## 🎯 Example Scenarios

### Travel Planning
```bash
python run.py \
    --input-dir "./Collection 1/PDFs" \
    --persona "Travel Planner" \
    --job "Plan a trip of 4 days for a group of 10 college friends" \
    --output-file "./travel_analysis.json"
```

### Training Development
```bash
python run.py \
    --input-dir "./Collection 2/PDFs" \
    --persona "Corporate Trainer" \
    --job "Develop Adobe Acrobat training for new employees" \
    --output-file "./training_analysis.json" \
    --use-large-models
```

### Research Analysis
```bash
python run.py \
    --input-dir "./documents" \
    --persona "Research Analyst" \
    --job "Extract key insights for executive summary" \
    --output-file "./research_summary.json" \
    --top-sections 10 \
    --top-subsections 10
```

## 📊 Output Format

The system generates a JSON file with the following structure:

```json
{
    "metadata": {
        "input_documents": ["doc1.pdf", "doc2.pdf"],
        "persona": "Travel Planner",
        "job_to_be_done": "Plan a trip...",
        "processing_timestamp": "2025-01-01T12:00:00",
        "processing_time_seconds": 45.67,
        "system_info": {
            "models_used": {"sentence_transformer": "locally_cached"},
            "documents_processed": 7,
            "total_sections_found": 42
        }
    },
    "extracted_sections": [
        {
            "document": "doc1.pdf",
            "section_title": "Budget Travel Tips",
            "importance_rank": 1,
            "page_number": 3,
            "relevance_score": 0.89,
            "similarity_score": 0.82,
            "content_bonus": 0.07
        }
    ],
    "subsection_analysis": [
        {
            "document": "doc1.pdf",
            "refined_text": "Extracted and refined text...",
            "page_number": 3,
            "original_section_title": "Budget Travel Tips",
            "text_length": 245
        }
    ]
}
```

## 🚀 Performance Improvements

- **Local Model Caching**: Models are downloaded once and reused, reducing startup time
- **Batch Processing**: Documents and sections are processed in batches for efficiency
- **Smart Text Extraction**: Combines standard extraction with OCR fallback
- **Advanced Scoring**: Multi-factor relevance scoring for better accuracy
- **Memory Management**: Optimized for processing large document collections
- **Error Recovery**: Robust error handling with fallback mechanisms

## 🐛 Troubleshooting

### Common Issues

1. **Models not downloading**: Check internet connection and disk space
2. **OCR errors**: Install tesseract-ocr system package
3. **Memory errors**: Use `--top-sections 3 --top-subsections 3` for smaller outputs
4. **No PDFs found**: Ensure PDF files are in the specified input directory

### Getting Help
```bash
# Check system info
python -c "from model_manager import ModelManager; print(ModelManager().get_system_info())"

# Verify installation
python setup.py --verify-only

# Run diagnostics
python enhanced_test.py
```

## 📝 License

This project is part of the Adobe India Hackathon 2025.

## 🤝 Contributing

The system is designed to be extensible. Key areas for enhancement:
- Additional document formats (Word, PowerPoint)
- More sophisticated NLP models
- Custom persona templates
- Integration with external APIs