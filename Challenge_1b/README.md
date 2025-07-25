# 🧠 Challenge 1B: Persona-Driven Document Intelligence

**AI-### 📚 For Students/Developersowered document analysis that understands what YOU need!** 

Extract the most relevant content fro## 📈 Performance Tips document collections based on your specific persona and job requirements. Perfect for travel planners, researchers, trainers, and more!

## ✨ What Makes This Special?

🎯 **Persona-Aware**: Understands different user types and their specific needs  
🧠 **AI-Powered**: Uses advanced language models for semantic understanding  
⚡ **Lightning Fast**: Processes document collections in under 60 seconds  
🔍 **Smart Extraction**: Finds exactly what matters for your job  
📄 **Multi-Format**: Handles PDFs, OCR, and complex document layouts  

## 🏆 Competition Optimized

- ✅ **CPU-Only**: Runs without GPU requirements
- ✅ **Model Size**: Lightweight models under 1GB total
- ✅ **Speed**: Processes 3-5 documents in <60 seconds
- ✅ **Offline**: Works without internet after setup
- ✅ **Memory Efficient**: Runs on standard hardware

## 🚀 Quick Start

## � Quick Start

### 1️⃣ Setup (One Time)
```bash
# Navigate to Challenge 1B
cd Challenge_1b

# Install dependencies and download AI models
python setup.py
```

### 2️⃣ Run Analysis
```bash
# Basic usage - just put PDFs in input/ folder
python run.py --persona "software developer" --job "learn data structures"

# With sample collections
python run.py --persona "travel planner" --job "plan 4-day trip for college friends"
```

### 3️⃣ Check Results
```bash
# Output saved as challenge1b_output.json
cat challenge1b_output.json
```

## 📁 Where to Put Your Documents

```
Challenge_1b/
├── input/              ← Put your PDFs here!
├── Collection 1/       ← Sample: South France travel guides
├── Collection 2/       ← Sample: Adobe Acrobat tutorials  
└── Collection 3/       ← Sample: More documents
```

## 🎯 Real Examples

### � For Students/Developers
```bash
python run.py \
    --persona "computer science student" \
    --job "understand machine learning algorithms"
```

### ✈️ For Travel Planning
```bash
python run.py \
    --persona "travel planner" \
    --job "plan budget-friendly 5-day European trip"
```

### 🏢 For Corporate Training
```bash
python run.py \
    --persona "corporate trainer" \
    --job "create Adobe Acrobat training materials"
```

## 📊 What You Get

The system creates `challenge1b_output.json` with:

```json
{
    "metadata": {
        "persona": "travel planner",
        "job_to_be_done": "plan 4-day trip...",
        "input_documents": ["guide1.pdf", "guide2.pdf"]
    },
    "extracted_sections": [
        {
            "document": "guide1.pdf",
            "section_title": "Budget Travel Tips",
            "importance_rank": 1,
            "page_number": 3
        }
    ],
    "subsection_analysis": [
        {
            "document": "guide1.pdf", 
            "refined_text": "Key insights for budget travel...",
            "page_number": 3
        }
    ]
}
```

## ⚙️ Advanced Options

```bash
python run.py \
    --persona "data scientist" \
    --job "extract ML insights from research papers" \
    --top-sections 8 \
    --top-subsections 10 \
    --use-ocr \
    --verbose
```

### All Parameters
- `--persona` (required): Who you are (e.g., "student", "researcher", "manager")
- `--job` (required): What you need to do (e.g., "study for exam", "plan trip")
- `--top-sections`: How many sections to extract (default: 5)
- `--top-subsections`: How many detailed analyses (default: 5)
- `--use-ocr`: Enable OCR for image-heavy PDFs
- `--verbose`: Show detailed processing logs

## 🧪 Testing & Validation

```bash
# Test system works
python test.py



## 🔧 System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   PDF Input     │───▶│  Document        │───▶│  AI Analysis    │
│   (Your docs)   │    │  Processor       │    │  (Persona-aware)│
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   JSON Output   │◀───│  Section         │◀───│  Relevance      │
│   (Results)     │    │  Analyzer        │    │  Ranker         │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🚨 Troubleshooting

### ❓ Common Issues

**🔴 "No PDFs found"**
```bash
# Make sure PDFs are in input/ folder
ls input/*.pdf
```

**🔴 "Model download failed"**
```bash
# Check internet and run setup again
python setup.py
```

**🔴 "Out of memory"**
```bash
# Use fewer documents or restart
# Process 3-5 PDFs at a time
```

**🔴 "Permission denied"**
```bash
# Fix file permissions
chmod 644 input/*.pdf
```

## � Performance Tips

### 🚀 Speed Optimization
- Put 3-5 PDFs in `input/` folder (optimal)
- Use clear, specific persona and job descriptions
- Disable OCR unless needed: remove `--use-ocr`
- Use SSD storage for faster model loading

### 🎯 Better Results
- **Good personas**: "medical student", "travel blogger", "software engineer"
- **Good jobs**: "study cardiology", "write Paris guide", "learn Python"
- **Avoid vague**: "person", "do stuff", "general analysis"

## 🏆 Competition Ready Features

✅ **CPU-Only**: No GPU required  
✅ **Fast**: <60 seconds processing  
✅ **Lightweight**: <1GB model size  
✅ **Offline**: Works without internet  
✅ **Robust**: Handles various PDF formats  

## 🎨 Sample Output Preview

For persona="travel planner" + job="plan Paris trip":

```
🎯 Found 5 relevant sections:
  1. "Budget Hotels in Paris" (page 12)
  2. "Metro Transportation Guide" (page 8) 
  3. "Top 10 Free Attractions" (page 15)
  4. "Restaurant Recommendations" (page 22)
  5. "Safety Tips for Tourists" (page 3)

🔍 Generated 5 detailed analyses:
  ▪ Budget accommodation options near city center...
  ▪ Complete metro map with tourist-friendly routes...
  ▪ Free museums and attractions with visiting hours...
```

## 🛠️ For Developers

### Project Structure
```
Challenge_1b/
├── 🧠 Core AI Components
│   ├── model_manager.py          # Manages AI models
│   ├── document_processor.py     # PDF → Text
│   ├── relevance_ranker.py       # Ranks by persona
│   └── subsection_analyzer.py    # Deep analysis
├── 🚀 Execution
│   ├── run.py                    # Main script  
│   ├── setup.py                  # One-time setup
│                 # Validation
└── 📚 Sample Data
    ├── input/                    # Your PDFs here
    ├── Collection 1/             # Travel guides
    └── Collection 2/             # Tech tutorials
```

### Dependencies
- **AI**: sentence-transformers, torch
- **PDF**: PyMuPDF, OCR support  
- **Utils**: numpy, logging, json

---

## 🎉 Ready to Start?

1. **Setup**: `python setup.py` (downloads AI models)
2. **Add PDFs**: Put your documents in `input/` folder  
3. **Run**: `python run.py --persona "your role" --job "what you need"`
4. **Results**: Check `challenge1b_output.json`

**Need help?** Check the examples above or run `python run.py --help`
# 🧠 Challenge 1A: Persona-Driven Document Intelligence (Docker Quickstart)

**AI-powered document analysis that understands what YOU need!**

Extract the most relevant content from document collections based on your specific persona and job requirements. Perfect for travel planners, researchers, trainers, and more!

## 🚀 Quick Docker Start

### 1️⃣ Prepare Your Environment

- Open a terminal.
- Create a new directory for this challenge (e.g., `Challenge_1b`):

```bash
mkdir -p Challenge_ba/input Challenge_1b/output
cd Challenge_1a
```

### 2️⃣ Build the Docker Image

Replace `<GHP token>` with your actual GitHub Personal Access Token.

```bash
sudo docker build --platform=linux/amd64 -t docdoc1a https://<GHP token>@github.com/kushagra8881/adobe_india_hackathon.git#main:Challenge_1a
```

### 3️⃣ Run the Analysis

- Place your PDF files inside the `input/` directory.
- The results will be saved to the `output/` directory.

```bash
sudo docker run --rm -v $(pwd)/input:/app/input:ro -v $(pwd)/output:/app/output --network none docdoc1a
```

### 4️⃣ Check Results

- Output files will appear in `output/`.

---

## 📁 Directory Structure

```
Challenge_1b/
├── input/      # ← Put your PDFs here!
└── output/     # ← Results will be saved here!
```

---

## ⚡ Performance Tips

- Put 3-5 PDFs in the `input/` folder for best speed.
- Use clear, specific persona and job descriptions (see Challenge 1B for examples).
- Disable OCR unless needed (if that feature is available).
- Use SSD storage for faster model/data loading.

---

## 🛠️ Troubleshooting

- **"No PDFs found"**: Ensure your input PDFs are in the `input/` folder.
- **"Permission denied"**: Fix permissions: `chmod 644 input/*.pdf`
- **Model download/network error**: Ensure you have a working internet connection for the build step.

---

## 🎉 Need More?

For advanced options, customization, and feature explanations, see the README in **Challenge_1b**.

---

*🧠 Challenge 1A: Fast, persona-driven document analysis, ready in seconds with Docker!*

---

*🧠 Challenge 1B: Making document analysis as smart as you are!* ✨
