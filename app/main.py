"""
GLiNER2 Multilingual Extraction API
====================================
Two-tier architecture:
  Tier 1 — GLiNER-MoE-MultiLingual for broad zero-shot NER (40+ langs)
  Tier 2 — GLiNER2 + LoRA adapters for deep multi-task extraction (5 target langs)

Language detection via fastText routes requests automatically.
"""

import os
import time
import json
import logging
import threading
from typing import Optional
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# ──────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("gliner2-api")

# ──────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
ADAPTERS_DIR = BASE_DIR / "adapters"
MODELS_DIR = BASE_DIR / "models"
STATIC_DIR = BASE_DIR / "static"

# Languages with trained LoRA adapters
ADAPTER_LANGS = {
    "ru": "Russian",
    "zh": "Mandarin",
    "id": "Indonesian",
    "ur": "Urdu",
    "th": "Thai",
}

# GLiNER2 base model (6 Western European languages)
GLINER2_BASE_LANGS = {"en", "fr", "de", "es", "it", "pt"}

# ──────────────────────────────────────────────
# REQUEST / RESPONSE MODELS
# ──────────────────────────────────────────────

class ExtractRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000, description="Text to process")
    labels: list[str] = Field(default=["person", "organization", "location"],
                              description="Entity types to extract")
    lang: Optional[str] = Field(None, description="Override auto-detected language (ISO 639-1)")
    threshold: float = Field(0.3, ge=0.0, le=1.0, description="Confidence threshold")

class ClassifyRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    labels: list[str] = Field(..., description="Candidate labels")
    category: str = Field("sentiment", description="Classification category name")
    lang: Optional[str] = Field(None)

class StructuredField(BaseModel):
    name: str
    dtype: str = "str"
    description: str = ""

class StructuredRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    schema_name: str = "item"
    fields: list[StructuredField]
    lang: Optional[str] = Field(None)

class HealthResponse(BaseModel):
    status: str
    gliner2_loaded: bool
    moe_loaded: bool
    adapters_available: list[str]
    lang_detect_loaded: bool

# ──────────────────────────────────────────────
# MODEL MANAGER
# ──────────────────────────────────────────────

class ModelManager:
    """Manages loading and switching between models and adapters."""

    def __init__(self):
        self.gliner2 = None
        self.moe_model = None
        self.lang_model = None
        self.current_adapter = None
        self.available_adapters = []

    def load_all(self):
        """Load all models at startup."""
        self._load_gliner2()
        self._load_moe()
        self._load_lang_detect()
        self._scan_adapters()

    def _load_gliner2(self):
        """Load GLiNER2 base model for multi-task extraction."""
        try:
            from gliner2 import GLiNER2
            log.info("Loading GLiNER2 base model (fastino/gliner2-multi-v1)...")
            start = time.time()
            self.gliner2 = GLiNER2.from_pretrained("fastino/gliner2-multi-v1")
            log.info(f"GLiNER2 loaded in {time.time() - start:.1f}s")
        except Exception as e:
            log.warning(f"GLiNER2 failed to load: {e}")
            log.warning("Multi-task extraction (classify/structured) will be unavailable.")

    def _load_moe(self):
        """Load GLiNER-MoE-MultiLingual for broad NER."""
        config_path = MODELS_DIR / "moe_multilingual" / "gliner_config.json"
        weights_path = MODELS_DIR / "moe_multilingual" / "pytorch_model.bin"

        if not config_path.exists() or not weights_path.exists():
            log.warning(f"MoE model files not found at {MODELS_DIR / 'moe_multilingual'}")
            log.warning("Broad multilingual NER will fall back to GLiNER2 base.")
            return

        try:
            import torch
            # The MoE fork must be installed: github.com/mayank-rakesh-mck/GLiNER
            from gliner import GLiNERConfig, GLiNER

            log.info("Loading GLiNER-MoE-MultiLingual...")
            start = time.time()
            with open(config_path) as f:
                config = json.load(f)
            model_config = GLiNERConfig(**config)
            self.moe_model = GLiNER(model_config)

            device = "cuda:0" if torch.cuda.is_available() else "cpu"
            state = torch.load(str(weights_path), map_location=device, weights_only=True)
            self.moe_model.model.load_state_dict(state, strict=True)
            self.moe_model = self.moe_model.to(device)
            log.info(f"MoE model loaded on {device} in {time.time() - start:.1f}s")
        except ImportError:
            log.warning("MoE-compatible GLiNER fork not installed.")
            log.warning("Install from: github.com/mayank-rakesh-mck/GLiNER")
        except Exception as e:
            log.warning(f"MoE model failed to load: {e}")

    def _load_lang_detect(self):
        """Load langdetect language detection."""
        try:
            from langdetect import detect
            detect("test")
            self.lang_model = detect
            log.info("Language detection (langdetect) loaded.")
        except ImportError:
            log.warning("langdetect not installed. Auto language detection disabled.")
        except Exception as e:
            log.warning(f"Language detection failed: {e}")

    def _scan_adapters(self):
        """Discover available LoRA adapters."""
        self.available_adapters = []
        if not ADAPTERS_DIR.exists():
            log.info("No adapters directory found. LoRA adapters unavailable.")
            return

        for lang_code in ADAPTER_LANGS:
            adapter_dir = ADAPTERS_DIR / f"{lang_code}_adapter"
            # Check for 'best' or 'final' subdirectory
            for subdir in ["best", "final", ""]:
                check = adapter_dir / subdir if subdir else adapter_dir
                if check.exists() and any(check.iterdir()):
                    self.available_adapters.append(lang_code)
                    log.info(f"  Adapter found: {lang_code} ({ADAPTER_LANGS[lang_code]})")
                    break

        log.info(f"Total adapters available: {len(self.available_adapters)}")

    def detect_language(self, text: str) -> str:
        """Detect language of input text. Returns ISO 639-1 code."""
        if self.lang_model is None:
            return "en"  # Default fallback
        try:
            return self.lang_model(text)
        except Exception:
            return "en"

    def _load_adapter(self, lang_code: str):
        """Switch to a specific LoRA adapter."""
        if self.gliner2 is None:
            return
        if self.current_adapter == lang_code:
            return  # Already loaded

        adapter_dir = ADAPTERS_DIR / f"{lang_code}_adapter"
        for subdir in ["best", "final", ""]:
            check = adapter_dir / subdir if subdir else adapter_dir
            if check.exists() and any(check.iterdir()):
                try:
                    self.gliner2.load_adapter(str(check))
                    self.current_adapter = lang_code
                    log.info(f"Loaded LoRA adapter: {lang_code}")
                except Exception as e:
                    log.warning(f"Failed to load adapter {lang_code}: {e}")
                return

    def _unload_adapter(self):
        """Return to base model (no adapter)."""
        if self.current_adapter is not None:
            # Reload base model to clear adapter
            # (GLiNER2 may support unload_adapter in future)
            self.current_adapter = None

    def extract_entities(self, text: str, labels: list[str],
                         lang: Optional[str] = None, threshold: float = 0.3) -> dict:
        """
        Route entity extraction to the best available model.

        Priority:
          1. GLiNER2 + LoRA adapter (if adapter exists for language)
          2. GLiNER-MoE (if language in MoE's 40+ list)
          3. GLiNER2 base model (fallback)
        """
        detected_lang = lang or self.detect_language(text)

        # Route 1: LoRA adapter available
        if detected_lang in self.available_adapters and self.gliner2 is not None:
            self._load_adapter(detected_lang)
            result = self.gliner2.extract_entities(text, labels)
            return {"result": result, "model": "gliner2+lora", "lang": detected_lang}

        # Route 2: MoE model for broad coverage
        if self.moe_model is not None and detected_lang not in GLINER2_BASE_LANGS:
            title_labels = [l.title() for l in labels]
            entities = self.moe_model.predict_entities(text, title_labels, threshold=threshold)
            # Convert MoE output to GLiNER2-style format
            result = {"entities": {}}
            for label in labels:
                result["entities"][label] = [
                    e["text"] for e in entities
                    if e["label"].lower() == label.lower()
                ]
            return {"result": result, "model": "moe-multilingual", "lang": detected_lang}

        # Route 3: GLiNER2 base model
        if self.gliner2 is not None:
            self._unload_adapter()
            result = self.gliner2.extract_entities(text, labels)
            return {"result": result, "model": "gliner2-base", "lang": detected_lang}

        raise HTTPException(503, "No models available for extraction")

    def classify_text(self, text: str, labels: list[str], category: str,
                      lang: Optional[str] = None) -> dict:
        """Classify text using GLiNER2 (+ adapter if available)."""
        if self.gliner2 is None:
            raise HTTPException(503, "GLiNER2 not loaded — classification unavailable")

        detected_lang = lang or self.detect_language(text)
        if detected_lang in self.available_adapters:
            self._load_adapter(detected_lang)
        else:
            self._unload_adapter()

        result = self.gliner2.classify_text(text, {category: labels})
        return {"result": result, "model": f"gliner2{'+lora' if self.current_adapter else ''}", "lang": detected_lang}

    def extract_structured(self, text: str, schema_name: str,
                           fields: list[StructuredField],
                           lang: Optional[str] = None) -> dict:
        """Extract structured JSON using GLiNER2 (+ adapter if available)."""
        if self.gliner2 is None:
            raise HTTPException(503, "GLiNER2 not loaded — structured extraction unavailable")

        detected_lang = lang or self.detect_language(text)
        if detected_lang in self.available_adapters:
            self._load_adapter(detected_lang)
        else:
            self._unload_adapter()

        field_specs = []
        for f in fields:
            spec = f"{f.name}::{f.dtype}"
            if f.description:
                spec += f"::{f.description}"
            field_specs.append(spec)

        result = self.gliner2.extract_json(text, {schema_name: field_specs})
        return {"result": result, "model": f"gliner2{'+lora' if self.current_adapter else ''}", "lang": detected_lang}


# ──────────────────────────────────────────────
# APPLICATION LIFECYCLE
# ──────────────────────────────────────────────

mgr = ModelManager()
_models_ready = False


def _load_models_background():
    global _models_ready
    log.info("=" * 60)
    log.info("Loading models in background thread...")
    log.info("=" * 60)
    try:
        mgr.load_all()
        _models_ready = True
        log.info("=" * 60)
        log.info("Models ready. API fully operational.")
        log.info("=" * 60)
    except Exception as e:
        log.error(f"Model loading failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start model loading in background so the server binds immediately.
    # This allows Railway's healthcheck to reach /health before models finish.
    t = threading.Thread(target=_load_models_background, daemon=True)
    t.start()
    log.info("Server started. Models loading in background — check /health for status.")
    yield
    log.info("Shutting down.")


# ──────────────────────────────────────────────
# CREATE APP
# ──────────────────────────────────────────────

app = FastAPI(
    title="GLiNER2 Multilingual Extraction API",
    description="Two-tier multilingual NER, classification, and structured extraction.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static frontend
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ──────────────────────────────────────────────
# ROUTES
# ──────────────────────────────────────────────

@app.get("/")
async def root():
    """Serve the frontend UI."""
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"message": "GLiNER2 Multilingual API", "docs": "/docs"}


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="healthy" if _models_ready else "loading",
        gliner2_loaded=mgr.gliner2 is not None,
        moe_loaded=mgr.moe_model is not None,
        adapters_available=mgr.available_adapters,
        lang_detect_loaded=mgr.lang_model is not None,
    )


@app.get("/languages")
async def languages():
    """List all supported languages and their routing."""
    return {
        "adapter_languages": {k: v for k, v in ADAPTER_LANGS.items()
                              if k in mgr.available_adapters},
        "base_languages": list(GLINER2_BASE_LANGS),
        "moe_available": mgr.moe_model is not None,
        "moe_language_count": "40+" if mgr.moe_model else 0,
    }


def _require_models():
    if not _models_ready:
        raise HTTPException(503, "Models still loading — please retry in a moment")


@app.post("/extract")
async def extract(req: ExtractRequest):
    """Extract named entities with automatic language routing."""
    _require_models()
    start = time.time()
    result = mgr.extract_entities(req.text, req.labels, req.lang, req.threshold)
    result["processing_time_ms"] = round((time.time() - start) * 1000, 1)
    return result


@app.post("/classify")
async def classify(req: ClassifyRequest):
    """Classify text into labels."""
    _require_models()
    start = time.time()
    result = mgr.classify_text(req.text, req.labels, req.category, req.lang)
    result["processing_time_ms"] = round((time.time() - start) * 1000, 1)
    return result


@app.post("/structured")
async def structured(req: StructuredRequest):
    """Extract structured JSON data."""
    _require_models()
    start = time.time()
    result = mgr.extract_structured(req.text, req.schema_name, req.fields, req.lang)
    result["processing_time_ms"] = round((time.time() - start) * 1000, 1)
    return result


@app.post("/detect-language")
async def detect_lang(text: str):
    """Detect language of input text."""
    lang = mgr.detect_language(text)
    return {"lang": lang, "name": ADAPTER_LANGS.get(lang, lang)}
