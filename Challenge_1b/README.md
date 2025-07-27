# 🧠 Challenge 1B: Persona-Driven Document Intelligence

**AI-### 📚 For Students/Developers document analysis that understands what YOU need!** 

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



### 1️⃣ Setup (One Time)
```bash
git clone https://github.com/kushagra8881/adobe_india_hackathon.git

# Navigate to Challenge 1B
cd adobe_india_hackathon/Challenge_1b

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
# 🧠 Challenge 1B: Persona-Driven Document Intelligence (Docker Quickstart)

**AI-powered document analysis that understands what YOU need!**

Extract the most relevant content from document collections based on your specific persona and job requirements. Perfect for travel planners, researchers, trainers, and more!

## 🚀 Quick Docker Start

### 1️⃣ Prepare Your Environment

- Open a terminal.
- Create a new directory for this challenge (e.g., `Challenge_1b`):

```bash
mkdir -p Challenge_ba/input Challenge_1b/output
cd Challenge_1b
```

### 2️⃣ Build the Docker Image

Replace `<GHP token>` with your actual GitHub Personal Access Token.

```bash
sudo docker build --platform=linux/amd64 -t docdoc1b https://github.com/kushagra8881/adobe_india_hackathon.git#main:Challenge_1b
```

### 3️⃣ Run the Analysis

- Place your PDF files inside the `input/` directory.
- The results will be saved to the `output/` directory.

```bash
sudo docker run --rm --network none -v $(pwd)/input/:/app/input/ -v $(pwd)/output/:/app/output/ docdoc1b python run.py --persona "student" --job "build method"
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
## 📊 What You Get

The system creates `challenge1b_output.json` with:

```json
{
    "metadata": {
        "input_documents": [
            "South of France - Cities.pdf",
            "South of France - Cuisine.pdf",
            "South of France - History.pdf",
            "South of France - Restaurants and Hotels.pdf",
            "South of France - Things to Do.pdf",
            "South of France - Tips and Tricks.pdf",
            "South of France - Traditions and Culture.pdf"
        ],
        "persona": "travel planner",
        "job_to_be_done": "plan budget-friendly 5-day European trip",
        "processing_timestamp": "2025-07-25T13:56:45.550025"
    },
    "extracted_sections": [
        {
            "document": "South of France - Tips and Tricks.pdf",
            "section_title": "Page 1",
            "importance_rank": 1,
            "page_number": 1
        },
        {
            "document": "South of France - Restaurants and Hotels.pdf",
            "section_title": "Page 1",
            "importance_rank": 2,
            "page_number": 1
        },
        {
            "document": "South of France - Things to Do.pdf",
            "section_title": "Page 1",
            "importance_rank": 3,
            "page_number": 1
        },
        {
            "document": "South of France - Cities.pdf",
            "section_title": "Nice: The Jewel of the French Riviera History Nice, located on the French Riviera, has been a popular destination for centuries. Its history dates back to the ancient Greeks, who founded the city around 350 BC. Nice later became a Roman colony and has since evolved into a glamorous resort town. In the 19th century, Nice became a favorite winter retreat for European aristocrats, which contributed to its development as a luxurious destination. Key Attractions • Promenade des Anglais: This famous seaside promenade, built in the 19th century, is perfect for a leisurely stroll along the coast. It oﬀers stunning views of the Mediterranean and is lined with cafes and hotels. • Castle Hill (Colline du Château): This hilltop park oﬀers panoramic views of Nice and the Mediterranean. It was once the site of a medieval castle, which was destroyed in the 18th century. • Old Town (Vieux Nice): The historic center of Nice is a labyrinth of narrow streets, baroque churches, and bustling markets. Don't miss the Cours Saleya market, where you can find fresh produce, flowers, and local delicacies. • Matisse Museum: Dedicated to the works of Henri Matisse, who spent much of his life in Nice, this museum features a comprehensive collection of his paintings, sculptures, and drawings. Hidden Gems • Russian Orthodox Cathedral: Visit the stunning Russian Orthodox Cathedral, a unique architectural gem in Nice. • Marc Chagall National Museum: Explore the works of Marc Chagall at this dedicated museum. • Parc Phoenix: Discover the botanical wonders at Parc Phoenix, a beautiful garden and park. Cultural Highlights Nice is renowned for its vibrant cultural scene, with numerous museums, galleries, and theaters. The city hosts the Nice Carnival in February, one of the largest and oldest carnivals in the world. The Nice Jazz Festival, held in July, is another major event that attracts music",
            "importance_rank": 4,
            "page_number": 5
        },
        {
            "document": "South of France - Cities.pdf",
            "section_title": "Marseille: The Oldest City in France History Marseille, founded by Greek sailors around 600 BC, is the oldest city in France. Its strategic location on the Mediterranean coast made it a vital trading port throughout history. The city's rich cultural heritage is reflected in its diverse architecture and vibrant atmosphere. Over the centuries, Marseille has been influenced by various cultures, including Greek, Roman, and North African, making it a melting pot of traditions and customs. Key Attractions • Old Port (Vieux-Port): The heart of Marseille, the Old Port has been a bustling harbor for over 2,600 years. Today, it is a lively area filled with cafes, restaurants, and markets. • Basilica of Notre-Dame de la Garde: This iconic basilica, perched on a hill overlooking the city, oﬀers panoramic views of Marseille and the Mediterranean Sea. Built in the 19th century, it is a symbol of the city's maritime heritage. • MuCEM (Museum of European and Mediterranean Civilizations): This modern museum explores the cultural history of the Mediterranean region through a variety of exhibits and interactive displays. • Le Panier: The oldest district in Marseille, Le Panier is a maze of narrow streets, colorful buildings, and historic landmarks. It's a great place to explore the city's past and enjoy its vibrant culture. Local Experiences • Boat Trip to the Calanques: Take a boat trip to the Calanques, a series of stunning limestone cliﬀs and coves along the coast. • Fish Market at the Old Port: Visit the fish market at the Old Port to experience the local seafood culture. • Street Art in Cours Julien: Explore the vibrant street art scene in the Cours Julien district. Cultural Highlights Marseille is known for its vibrant arts scene, with numerous galleries, theaters, and music venues. The city hosts several festivals throughout the year, including the Festival de Marseille, which celebrates contemporary dance, theater, and music. Marseille's cuisine is",
            "importance_rank": 5,
            "page_number": 3
        }
    ],
    "subsection_analysis": [
        {
            "document": "South of France - Tips and Tricks.pdf",
            "refined_text": "The Ultimate South of France Travel Companion: Your Comprehensive Guide to Packing, Planning, and Exploring Introduction Planning a trip to the South of France requires thoughtful preparation to ensure a comfortable and enjoyable experience. Whether you're traveling solo, with kids, or in a group, this guide will help you make the most of your trip. • Additional Tips: Consider packing a travel-sized perfume or cologne to freshen up on the go. Conclusion Packing for a trip to the South of France involves considering the season, planned activities, and the needs of both adults and children.",
            "page_number": 1
        },
        {
            "document": "South of France - Restaurants and Hotels.pdf",
            "refined_text": "Whether you're looking for budget-friendly options, family-friendly spots, upscale dining, or luxurious experiences, this guide will help you find the perfect restaurants and hotels for your trip. The modern amenities and convenient location make it a great choice for budget-conscious travelers. The modern amenities and convenient location make it a great choice for budget-conscious travelers. Whether you're looking for budget-friendly eateries, family-friendly spots, upscale dining, or luxurious experiences, this guide will help you find the perfect places to eat and stay during your trip.",
            "page_number": 1
        },
        {
            "document": "South of France - Things to Do.pdf",
            "refined_text": "This guide will take you through a variety of activities and must-see attractions to help you plan an unforgettable trip. • Dordogne River: Enjoy a leisurely canoe trip, passing by medieval castles and charming villages. • Bordeaux: Take a day trip to the world-renowned wine region and visit its prestigious châteaux. • Fréjus: Cool oﬀ at Aqualand water park. Conclusion The South of France is a diverse and enchanting region that oﬀers a wide range of activities and experiences for travelers. Use this guide to plan your trip and make the most of everything this beautiful region has to oﬀer.",
            "page_number": 1
        },
        {
            "document": "South of France - Cities.pdf",
            "refined_text": "lovers from around the globe. Nice's cuisine is also a highlight, with dishes like salade niçoise and socca (a chickpea flour pancake) being local specialties.",
            "page_number": 5
        },
        {
            "document": "South of France - Cities.pdf",
            "refined_text": "also a highlight, with dishes like bouillabaisse (a traditional fish stew) and pastis (an anise- flavored aperitif) being local favorites.",
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




---

*🧠 Challenge 1B: Making document analysis as smart as you are!* ✨
