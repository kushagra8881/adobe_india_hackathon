# 🧠 Enhanced Document Intelligence System v2.0

A cutting-edge document intelligence system that extracts and prioritizes the most relevant sections from multiple documents using advanced semantic analysis. The system leverages a sophisticated 4-model ensemble approach optimized for different task types while maintaining efficiency under 700MB total model size.

## 🚀 Enhanced Features v2.0

### 🎯 **Multi-Model Intelligence**
- **4-Model Ensemble**: Specialized transformers for different tasks (480MB total)
  - `sentence_transformer_best` (120MB): Best accuracy-to-size ratio with all-MiniLM-L12-v2
  - `sentence_transformer_qa` (90MB): Optimized for question-answering with multi-qa-MiniLM-L6-cos-v1
  - `sentence_transformer_domain` (90MB): Document retrieval specialist with msmarco-MiniLM-L6-cos-v5
  - `sentence_transformer_fast` (90MB): Lightning-fast processing with all-MiniLM-L6-v2

### � **Advanced Semantic Analysis**
- **Hybrid Scoring**: 70% semantic similarity + 30% keyword matching
- **Context-Aware Processing**: Intelligent model selection based on task requirements
- **Real-time Progress Tracking**: Live performance monitoring (120-190 it/s processing speeds)

### 🛠️ **Enhanced System Architecture**
- **Python 3.10 Optimized**: Enhanced setup with modern dependency management
- **Docker Ready**: Complete containerization with Python 3.10-slim base
- **CUDA Acceleration**: Automatic GPU detection and utilization
- **Robust Error Handling**: Comprehensive fallback mechanisms and validation

### 📊 **Performance Intelligence**
- **Smart Caching**: Local model management with automatic optimization
- **Memory Efficient**: Optimized model loading and batched processing
- **Comprehensive Metrics**: Detailed timing, system info, and performance analytics

## 📋 System Requirements

### Minimum Requirements
- **Python**: 3.10+ (64-bit) - optimized for enhanced features
- **Memory**: 8GB RAM (4GB minimum, 16GB+ recommended for large documents)
- **Storage**: 3GB free space (models + cache)
- **GPU**: Optional CUDA-compatible GPU for acceleration

### Enhanced Requirements (Recommended)
- **Python**: 3.10 or 3.11
- **Memory**: 16GB+ RAM for optimal performance
- **Storage**: 5GB+ free space
- **GPU**: NVIDIA GPU with 4GB+ VRAM for maximum speed

## 🛠️ Installation & Setup

### Option 1: Enhanced Automated Setup (Recommended)
```bash
# Complete system setup with verification
python setup.py

# Enhanced mode with all optimizations
python setup.py --enhanced

# Fast setup for quick testing
python setup.py --fast

# Comprehensive verification
python setup.py --verify-enhanced
```

### Option 2: Docker Deployment
```bash
# Build enhanced container
docker-compose build

# Run with volume mounting
docker-compose up

# Or manual Docker run
docker build -t enhanced-doc-intel .
docker run -v ./documents:/app/documents enhanced-doc-intel
```

### Option 3: Manual Installation
```bash
# Install enhanced dependencies
pip install -r requirements.txt

# System dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install tesseract-ocr libtesseract-dev poppler-utils

# Optional: Enhanced OCR support
pip install easyocr

# Verify installation
python check_setup.py
```
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

### Enhanced Basic Usage
```bash
# Enhanced processing with semantic analysis
python run.py \
    --input-dir "./Collection 1/PDFs" \
    --persona "Travel Planner" \
    --job "Plan a trip of 4 days for a group of 10 college friends" \
    --enhanced

# Fast processing mode
python run.py \
    --input-dir "./documents" \
    --persona "Software Trainer" \
    --job "Create a comprehensive training program" \
    --fast
```

### Advanced Enhanced Usage
```bash
# Full enhanced mode with all optimizations
python run.py \
    --input-dir "./documents" \
    --persona "Corporate Learning Specialist" \
    --job "Design comprehensive Adobe Acrobat curriculum" \
    --output-file "enhanced_analysis.json" \
    --top-sections 10 \
    --top-subsections 8 \
    --enhanced \
    --use-ocr \
    --verbose

# Model information and diagnostics
python run.py --model-info
```

### Enhanced Command Line Options
- `--input-dir`: Directory containing PDF files (required)
- `--persona`: Description of the user persona (required)
- `--job`: Job to be done by the persona (required)
- `--output-file`: Path to output JSON file (default: challenge1b_output.json)
- `--top-sections`: Number of top sections to extract (default: 5)
- `--top-subsections`: Number of top subsections to analyze (default: 5)
- `--models-dir`: Directory to store downloaded models (default: ./models)
- `--enhanced`: Enable enhanced multi-model processing
- `--fast`: Use fast processing mode
- `--use-ocr`: Enable OCR for image-based text extraction
- `--verbose`: Enable verbose logging
- `--model-info`: Display enhanced model information

## 🧪 Enhanced Testing

### Run Comprehensive Test Suite
```bash
# Full enhanced test suite
python enhanced_test.py

# Original compatibility test
python test.py

# Setup verification
python check_setup.py
```

### Test Individual Enhanced Components
```bash
# Test enhanced model manager
python -c "from enhanced_test import test_model_manager; test_model_manager()"

# Test document processor with semantic analysis
python -c "from enhanced_test import test_document_processor; test_document_processor()"

# Test relevance ranker with multi-model support
python -c "from enhanced_test import test_relevance_ranker; test_relevance_ranker()"

# Test subsection analyzer with semantic refinement
python -c "from enhanced_test import test_subsection_analyzer; test_subsection_analyzer()"

# Full end-to-end test
python -c "from enhanced_test import test_end_to_end; test_end_to_end()"
```

## 📁 Enhanced Project Structure

```
Challenge_1b/
├── 🧠 Core Enhanced Components
│   ├── model_manager.py          # Multi-model management (4 models)
│   ├── document_processor.py     # Enhanced PDF processing with OCR
│   ├── relevance_ranker.py       # Semantic ranking with task selection
│   ├── subsection_analyzer.py    # Advanced semantic text analysis
│   └── run.py                    # Enhanced CLI with model info
├── 🛠️ Setup & Configuration
│   ├── setup.py                  # Enhanced Python 3.10 setup
│   ├── check_setup.py           # System verification
│   ├── requirements.txt          # Enhanced dependencies
│   ├── Dockerfile               # Python 3.10-slim container
│   └── docker-compose.yml       # Enhanced deployment
├── 🧪 Testing & Validation
│   ├── enhanced_test.py          # Comprehensive test suite
│   ├── test.py                   # Original compatibility test
│   └── analysis.json            # System analysis results
├── 📁 Data & Models
│   ├── models/                   # Local model cache (480MB)
│   │   ├── all-MiniLM-L12-v2/   # Best accuracy model (120MB)
│   │   ├── multi-qa-MiniLM-L6-cos-v1/  # QA model (90MB)
│   │   ├── msmarco-MiniLM-L6-cos-v5/   # Domain model (90MB)
│   │   ├── all-MiniLM-L6-v2/    # Fast model (90MB)
│   │   └── nltk_data/           # NLTK resources
│   ├── Collection 1/            # South of France travel docs
│   ├── Collection 2/            # Adobe Acrobat training docs
│   └── Collection 3/            # Additional test collections
└── 📄 Documentation
    ├── README.md                # This enhanced guide
    ├── approach_explanation.md  # Technical methodology
    ├── SYSTEM_ENHANCEMENT_SUMMARY.md  # Enhancement details
    └── COMPLETE_RESTORATION_SUMMARY.md # Restoration log
```

## 🎯 Enhanced Example Scenarios

### Travel Planning with Semantic Analysis
```bash
python run.py \
    --input-dir "./Collection 1/PDFs" \
    --persona "Travel Planner" \
    --job "Plan a trip of 4 days for a group of 10 college friends" \
    --output-file "./travel_analysis.json" \
    --enhanced
```

### Corporate Training Development
```bash
python run.py \
    --input-dir "./Collection 2/PDFs" \
    --persona "Corporate Learning Specialist" \
    --job "Develop comprehensive Adobe Acrobat training curriculum" \
    --output-file "./training_analysis.json" \
    --enhanced \
    --top-sections 15 \
    --verbose
```

### Fast Processing for Quick Analysis
```bash
python run.py \
    --input-dir "./documents" \
    --persona "Content Curator" \
    --job "Extract key insights for executive summary" \
    --fast \
    --top-sections 3
```

## 📊 Enhanced Output Format

The enhanced system generates a comprehensive JSON file with the following structure:

```json
{
    "metadata": {
        "input_documents": ["South of France - Cities.pdf", "..."],
        "persona": "travel planner",
        "job_to_be_done": "plan trip",
        "processing_timestamp": "2025-07-19T21:22:40.190777",
        "processing_time_seconds": 14.56,
        "system_info": {
            "models_used": {
                "sentence_transformer": "locally_cached",
                "enhanced_mode": true,
                "fast_mode": false,
                "use_ocr": true
            },
            "documents_processed": 7,
            "total_sections_found": 14
        }
    },
    "extracted_sections": [
        {
            "document": "South of France - Tips and Tricks.pdf",
            "section_title": "Page 1",
            "importance_rank": 1,
            "page_number": 1,
            "relevance_score": 0.7228298254182166,
            "similarity_score": 0.5228298254182167,
            "content_bonus": 0.2
        }
    ],
    "subsection_analysis": [
        {
            "document": "South of France - Tips and Tricks.pdf",
            "refined_text": "The Ultimate South of France Travel Companion...",
            "page_number": 1,
            "original_section_title": "Page 1",
            "text_length": 582
        }
    ]
}
```

## 🔧 Enhanced Performance Features

### Multi-Model Intelligence
- **Task-Specific Selection**: Automatically chooses optimal model for each operation
- **Parallel Processing**: Batched operations with progress tracking
- **Memory Optimization**: Efficient model loading and caching

### Semantic Analysis Enhancements
- **Hybrid Scoring**: Combines semantic similarity with keyword matching
- **Context Preservation**: Maintains document structure and relationships
- **Quality Metrics**: Detailed relevance and similarity scoring

### System Monitoring
- **Real-time Progress**: Live updates during processing (120-190 it/s)
- **Performance Metrics**: Detailed timing breakdown by component
- **Resource Tracking**: Memory usage and model size monitoring

## 🐛 Troubleshooting

### Common Issues & Solutions

#### Model Download Issues
```bash
# Clear model cache and re-download
rm -rf ./models
python setup.py --enhanced

# Check internet connectivity and space
python check_setup.py
```

#### Memory Issues
```bash
# Use fast mode for low-memory systems
python run.py --fast --input-dir "./documents" --persona "..." --job "..."

# Monitor memory usage
python -c "from model_manager import ModelManager; print(ModelManager().get_system_info())"
```

#### CUDA Issues
```bash
# Check CUDA availability
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"

# Force CPU processing if needed
export CUDA_VISIBLE_DEVICES=""
python run.py --input-dir "./documents" --persona "..." --job "..."
```

## 🚀 Performance Benchmarks

### Processing Speed (7 documents)
- **Document Processing**: ~0.15 seconds
- **Section Ranking**: ~0.95 seconds  
- **Subsection Analysis**: ~9.59 seconds
- **Total Processing**: ~14.56 seconds

### Model Performance
- **Semantic Analysis**: 120-190 iterations/second
- **Model Loading**: Sub-second for cached models
- **Memory Usage**: 480MB for complete model suite

### Accuracy Improvements
- **Enhanced Relevance**: 70% semantic + 30% keyword scoring
- **Context Preservation**: Maintained through semantic analysis
- **Task Specialization**: Model selection based on use case

## 🤝 Contributing

### Development Setup
```bash
# Clone and setup development environment
git clone <repository>
cd Challenge_1b
python setup.py --enhanced

# Run development tests
python enhanced_test.py
```

### Testing New Features
```bash
# Test individual components
python -c "from enhanced_test import test_<component>; test_<component>()"

# Full integration test
python enhanced_test.py
```

## 📄 License & Credits

### Enhanced System Credits
- **Multi-Model Architecture**: Optimized ensemble approach
- **Semantic Analysis**: Advanced transformer implementations
- **Performance Optimization**: Efficient batching and caching
- **Docker Integration**: Containerized deployment ready

### Dependencies & Licenses
- Sentence Transformers: Apache 2.0
- PyMuPDF: AGPL-3.0
- PyTorch: BSD-3-Clause
- NLTK: Apache 2.0

---

*Enhanced Document Intelligence System v2.0 - Powered by Multi-Model Semantic Analysis* 🧠✨
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