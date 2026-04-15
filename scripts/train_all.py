#!/usr/bin/env python3
"""
train_all.py
============
Master script that orchestrates the full training pipeline:
    1. Download WikiANN data for all target languages
    2. Train LoRA adapters for each language
    3. Evaluate all adapters against test sets

Usage:
    python scripts/train_all.py
    python scripts/train_all.py --skip-download
    python scripts/train_all.py --langs ru zh  # Only specific languages
"""

import subprocess
import sys
import argparse

parser = argparse.ArgumentParser(description="Train all LoRA adapters")
parser.add_argument("--langs", nargs="+", default=["ru", "zh", "id", "ur", "th"])
parser.add_argument("--skip-download", action="store_true", help="Skip data download step")
parser.add_argument("--skip-eval", action="store_true", help="Skip evaluation step")
args = parser.parse_args()

# Language-specific training configs (tuned per data availability)
LANG_CONFIGS = {
    "ru": {"max_train": 1000, "epochs": 10, "lora_r": 8},
    "zh": {"max_train": 1000, "epochs": 10, "lora_r": 8},
    "id": {"max_train": 1000, "epochs": 10, "lora_r": 8},
    "ur": {"max_train": 500,  "epochs": 20, "lora_r": 4},  # Less data → more epochs, lower rank
    "th": {"max_train": 1000, "epochs": 15, "lora_r": 8},  # Extra epochs for non-Latin
}


def run(cmd: list[str], desc: str):
    """Run a subprocess with clear logging."""
    print(f"\n{'='*60}")
    print(f"  {desc}")
    print(f"  Command: {' '.join(cmd)}")
    print(f"{'='*60}\n")
    result = subprocess.run(cmd, text=True)
    if result.returncode != 0:
        print(f"\n  FAILED (exit code {result.returncode})")
        sys.exit(1)


def main():
    print("=" * 60)
    print("GLiNER2 Multilingual Training Pipeline")
    print(f"Languages: {', '.join(args.langs)}")
    print("=" * 60)

    # Step 1: Download data
    if not args.skip_download:
        run(
            [sys.executable, "scripts/download_wikiann.py", "--langs"] + args.langs,
            "Step 1: Downloading WikiANN data"
        )

    # Step 2: Train adapters
    for lang in args.langs:
        cfg = LANG_CONFIGS.get(lang, {"max_train": 1000, "epochs": 10, "lora_r": 8})
        run(
            [sys.executable, "scripts/train_lora_adapter.py",
             "--lang", lang,
             "--max-train", str(cfg["max_train"]),
             "--epochs", str(cfg["epochs"]),
             "--lora-r", str(cfg["lora_r"])],
            f"Step 2: Training LoRA adapter for {lang}"
        )

    # Step 3: Evaluate
    if not args.skip_eval:
        run(
            [sys.executable, "scripts/evaluate.py",
             "--mode", "all", "--lang"] + args.langs,
            "Step 3: Evaluating all models"
        )

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"\nAdapters saved in: adapters/")
    print(f"Benchmarks saved in: data/benchmark_results.json")
    print(f"\nTo start the API:")
    print(f"  uvicorn app.main:app --host 0.0.0.0 --port 8000")


if __name__ == "__main__":
    main()
