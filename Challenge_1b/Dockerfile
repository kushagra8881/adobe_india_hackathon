# switch to python:3.10 or python:3.10-slim is build breaks
FROM --platform=linux/amd64 python:3.10-slim-buster

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MODELS_DIR=/app/models \
    TOKENIZERS_PARALLELISM=false \
    TRANSFORMERS_CACHE=/app/models/.cache

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    poppler-utils \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
# installed seprately for unique args(cpu-only)
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

COPY *.py /app/

RUN mkdir -p models/.cache && \
    chmod 755 models

RUN python setup.py

CMD ["python", "run.py"]
