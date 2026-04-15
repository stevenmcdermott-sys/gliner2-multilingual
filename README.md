# GLiNER2 Multilingual Extraction System

Two-tier multilingual information extraction covering **40+ languages** with deep multi-task support for Russian, Mandarin, Indonesian, Urdu, and Thai.

## Architecture

```
Request → Language Detection (fastText) → Router
                                            ├── Tier 1: GLiNER-MoE (40+ langs, NER only)
                                            └── Tier 2: GLiNER2 + LoRA (5 langs, NER + classify + structured)
```

**Tier 1** — GLiNER-MoE-MultiLingual provides zero-shot NER across 40+ languages  
**Tier 2** — GLiNER2 with per-language LoRA adapters (~5MB each) for full multi-task extraction

## Quick Start

### Docker (recommended)

```bash
docker-compose up --build
# API at http://localhost:8000
# UI at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### Manual

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Training Pipeline

```bash
# 1. Download WikiANN data for target languages
python scripts/download_wikiann.py

# 2. Train all LoRA adapters (one command)
python scripts/train_all.py

# Or train individual languages
python scripts/train_lora_adapter.py --lang ru --epochs 10
python scripts/train_lora_adapter.py --lang zh --epochs 10
python scripts/train_lora_adapter.py --lang id --epochs 10
python scripts/train_lora_adapter.py --lang ur --epochs 20 --lora-r 4
python scripts/train_lora_adapter.py --lang th --epochs 15

# 3. Evaluate
python scripts/evaluate.py --mode all --lang ru zh id ur th
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/` | Web UI |
| `GET`  | `/health` | System status |
| `GET`  | `/languages` | Supported languages |
| `POST` | `/extract` | Named entity extraction |
| `POST` | `/classify` | Text classification |
| `POST` | `/structured` | Structured JSON extraction |
| `POST` | `/detect-language` | Language detection |

## Adding MoE Model

Download from [HuggingFace](https://huggingface.co/Mayank6255/GLiNER-MoE-MultiLingual):

```bash
# Place these files in models/moe_multilingual/
#   pytorch_model.bin
#   gliner_config.json
```

## Hardware Requirements

| Use | GPU | RAM | Disk |
|-----|-----|-----|------|
| Inference (CPU) | None | 8GB | 5GB |
| Inference (GPU) | 8GB VRAM | 16GB | 5GB |
| Training (LoRA) | 8GB+ VRAM | 16GB | 20GB |

## Licence

Apache 2.0. Model weights are subject to their respective licences.
