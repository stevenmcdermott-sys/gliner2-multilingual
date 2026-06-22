# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Run the API server locally:**
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Docker (recommended for full stack):**
```bash
docker-compose up --build
# API + UI at http://localhost:8000, docs at http://localhost:8000/docs
```

**Training pipeline:**
```bash
# Download WikiANN data (ru zh id ur th by default)
python scripts/download_wikiann.py

# Train a single language adapter
python scripts/train_lora_adapter.py --lang ru --epochs 10

# Train all adapters in sequence
python scripts/train_all.py

# Skip steps as needed
python scripts/train_all.py --skip-download --langs ru zh
```

**Evaluate models:**
```bash
python scripts/evaluate.py --mode all --lang ru zh id ur th
python scripts/evaluate.py --mode gliner2-lora --lang ru   # single mode
```

**Build frontend for Netlify:**
```bash
RAILWAY_BACKEND_URL=https://your-app.railway.app node build.js
```

## Architecture

### Two-tier model routing

All inference is handled by `ModelManager` in `app/main.py`. When a `/extract` request arrives, it routes to one of three models in priority order:

1. **GLiNER2 + LoRA adapter** — if a trained adapter exists for the detected language (ru, zh, id, ur, th). Adapters are ~5MB, loaded on demand and cached as `current_adapter`.
2. **GLiNER-MoE-MultiLingual** — for languages outside the six GLiNER2 base languages when the MoE model is present. This requires a separate fork installation (`github.com/mayank-rakesh-mck/GLiNER`).
3. **GLiNER2 base model** — fallback for the six natively supported languages (en, fr, de, es, it, pt).

Only `/extract` uses this three-way routing. `/classify` and `/structured` always use GLiNER2 (+ adapter if available) since the MoE model only supports NER.

Language detection uses `langdetect` and can be overridden per-request with the `lang` field.

### Directory layout for models and adapters

- `models/moe_multilingual/` — MoE model weights (`pytorch_model.bin` + `gliner_config.json`). Not included in the repo; must be downloaded from HuggingFace and placed here manually.
- `adapters/{lang}_adapter/` — LoRA adapters produced by the training scripts. The app checks for `best/`, `final/`, or the root of each language directory on startup.
- `data/` — WikiANN JSONL files (`wikiann_{lang}_{split}.jsonl`) produced by `download_wikiann.py`.

### Deployment split

The project is designed for a split deployment:
- **Railway** runs the FastAPI backend via the `Dockerfile`. Entry point is `uvicorn app.main:app`. Models load in a background thread so the `/health` healthcheck responds before loading is complete (`status: "loading"` vs `status: "healthy"`).
- **Netlify** hosts the static frontend. `build.js` substitutes `%%RAILWAY_URL%%` in `frontend/index.html` with the `RAILWAY_BACKEND_URL` environment variable, writing the result to `dist/index.html`.
- For local/Docker development, both are served from the same FastAPI process: `static/` is mounted at `/static` and `GET /` returns `static/index.html`.

### Training data format

WikiANN IOB2 tags are converted to GLiNER2's entity dict format by `download_wikiann.py`:
```json
{"text": "Tim Cook visited Paris", "entities": {"person": ["Tim Cook"], "location": ["Paris"]}}
```
This JSONL format is consumed directly by `train_lora_adapter.py` and `evaluate.py`.

### LoRA adapter hyperparameters

Language-specific defaults in `scripts/train_all.py`:
- Urdu (`ur`): `lora_r=4`, 20 epochs — less training data requires lower rank and more epochs.
- Thai (`th`): 15 epochs — non-Latin script needs extra passes.
- All others: `lora_r=8`, 10 epochs.

`save_adapter_only=True` in `TrainingConfig` ensures checkpoints are ~5MB rather than ~450MB.
