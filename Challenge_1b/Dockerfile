# Enhanced Document Intelligence System - Dockerfile
# Optimized for Python 3.10 with enhanced models under 700MB
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Set enhanced environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV MODELS_DIR=/app/models
ENV TOKENIZERS_PARALLELISM=false
ENV TRANSFORMERS_CACHE=/app/models/.cache

# Install enhanced system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    git \
    build-essential \
    tesseract-ocr \
    libtesseract-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with enhanced caching
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create enhanced directories
RUN mkdir -p models/.cache && \
    chmod 755 models

# Run enhanced setup script
RUN python setup.py --full-setup

# Expose port for future web interface
EXPOSE 8000

# Enhanced health check
HEALTHCHECK --interval=30s --timeout=60s --start-period=120s --retries=3 \
    CMD python -c "from model_manager import ModelManager; mm=ModelManager(); info=mm.get_system_info(); exit(0 if info.get('available_models') else 1)" || exit 1

# Default command - enhanced verification
CMD ["python", "setup.py", "--verify-only"]