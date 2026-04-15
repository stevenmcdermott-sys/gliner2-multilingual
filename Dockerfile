# ═══════════════════════════════════════════════════════════
# GLiNER2 Multilingual Extraction System — Dockerfile
# ═══════════════════════════════════════════════════════════
#
# This Dockerfile builds a COMPLETE, self-contained image:
#   - Python 3.12 runtime
#   - All ML dependencies (PyTorch CPU, GLiNER2, etc.)
#   - MoE-compatible GLiNER fork
#   - FastAPI backend with language routing
#   - Static HTML frontend
#   - Pre-downloaded GLiNER2 base model
#   - Language detection model (fastText)
#   - Slots for LoRA adapters + MoE weights
#
# BUILD:
#   docker build -t gliner2-multilingual .
#
# RUN:
#   docker run -p 8000:8000 gliner2-multilingual
#
# RUN WITH GPU (NVIDIA):
#   docker run --gpus all -p 8000:8000 gliner2-multilingual
#
# MOUNT ADAPTERS (trained separately):
#   docker run -p 8000:8000 \
#     -v /path/to/adapters:/app/adapters \
#     -v /path/to/moe_weights:/app/models/moe_multilingual \
#     gliner2-multilingual
#
# ═══════════════════════════════════════════════════════════

# ---------- Stage 1: Base image ----------
FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        curl \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app


# ---------- Stage 2: Install Python dependencies ----------
FROM base AS deps

COPY requirements.txt .

# Install PyTorch CPU (much smaller than GPU version)
# For GPU: replace with the CUDA version from pytorch.org
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
RUN pip install -r requirements.txt

# Install the MoE-compatible GLiNER fork
# This is needed for the Tier 1 (broad NER) model
RUN git clone --depth 1 https://github.com/mayank-rakesh-mck/GLiNER.git /tmp/GLiNER \
    && cd /tmp/GLiNER \
    && pip install -r requirements.txt \
    && cd / && rm -rf /tmp/GLiNER/.git


# ---------- Stage 3: Pre-download models ----------
FROM deps AS models

# Pre-download GLiNER2 base model so it's baked into the image
# (avoids downloading at runtime — makes first startup fast)
RUN python -c "\
from gliner2 import GLiNER2; \
print('Downloading GLiNER2 base model...'); \
GLiNER2.from_pretrained('fastino/gliner2-multi-v1'); \
print('Model cached successfully.')"

# Warm up langdetect (pure Python, no model download needed)
RUN python -c "from langdetect import detect; detect('test'); print('langdetect ready.')"


# ---------- Stage 4: Final image ----------
FROM models AS final

# Copy application code
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY static/ ./static/

# Create directories for adapters and MoE model
# These can be populated via volume mounts at runtime
RUN mkdir -p adapters models/moe_multilingual data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Default command: start the API server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]


# ═══════════════════════════════════════════════════════════
# BUILD NOTES
# ═══════════════════════════════════════════════════════════
#
# Expected image size: ~3-4GB (CPU PyTorch + models)
#
# To build a GPU-enabled image, change the PyTorch install:
#   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
# And use NVIDIA base image:
#   FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04
#
# To add MoE weights at build time:
#   1. Download from huggingface.co/Mayank6255/GLiNER-MoE-MultiLingual
#   2. Place pytorch_model.bin + gliner_config.json in models/moe_multilingual/
#   3. Rebuild the image
#
# To add trained adapters at build time:
#   1. Run: python scripts/train_all.py
#   2. Adapters will be in adapters/
#   3. Rebuild the image
#
# ═══════════════════════════════════════════════════════════
