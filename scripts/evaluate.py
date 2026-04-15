#!/usr/bin/env python3
"""
evaluate.py
===========
Evaluate models against WikiANN test sets and produce F1 benchmarks.

Usage:
    python scripts/evaluate.py --mode gliner2-base --lang ru
    python scripts/evaluate.py --mode gliner2-lora --lang ru
    python scripts/evaluate.py --mode moe --lang ru
    python scripts/evaluate.py --mode all --lang ru zh id ur th
"""

import json
import argparse
import time
from pathlib import Path
from collections import defaultdict

parser = argparse.ArgumentParser(description="Evaluate NER models on WikiANN")
parser.add_argument("--mode", required=True, choices=["gliner2-base", "gliner2-lora", "moe", "all"],
                    help="Which model to evaluate")
parser.add_argument("--lang", nargs="+", required=True, help="Language codes to evaluate")
parser.add_argument("--data-dir", default="data", help="Directory with JSONL test files")
parser.add_argument("--adapters-dir", default="adapters", help="Directory with LoRA adapters")
parser.add_argument("--threshold", type=float, default=0.3, help="Prediction threshold (MoE)")
parser.add_argument("--max-examples", type=int, default=500, help="Max test examples per lang")
args = parser.parse_args()


# ──────────────────────────────────────────────
# EVALUATION FUNCTION
# ──────────────────────────────────────────────

def compute_entity_f1(predictions: list[dict], gold: list[dict]) -> dict:
    """
    Compute entity-level precision, recall, F1.

    Compares predicted entity spans against gold spans.
    A prediction is correct (true positive) if the exact text AND label match.

    Returns: {"precision": float, "recall": float, "f1": float,
              "tp": int, "fp": int, "fn": int}
    """
    tp = fp = fn = 0

    for pred, gold_item in zip(predictions, gold):
        pred_spans = set()
        gold_spans = set()

        # Collect predicted spans
        if "entities" in pred:
            for label, values in pred["entities"].items():
                for v in values:
                    pred_spans.add((v.strip(), label.lower()))
        elif isinstance(pred, list):
            # MoE format: list of {"text": ..., "label": ...}
            for e in pred:
                pred_spans.add((e["text"].strip(), e["label"].lower()))

        # Collect gold spans
        for label, values in gold_item["entities"].items():
            for v in values:
                gold_spans.add((v.strip(), label.lower()))

        tp += len(pred_spans & gold_spans)
        fp += len(pred_spans - gold_spans)
        fn += len(gold_spans - pred_spans)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {"precision": precision, "recall": recall, "f1": f1,
            "tp": tp, "fp": fp, "fn": fn}


def load_test_data(lang: str, max_n: int = None) -> list[dict]:
    """Load JSONL test file."""
    path = Path(args.data_dir) / f"wikiann_{lang}_test.jsonl"
    if not path.exists():
        print(f"  ERROR: {path} not found. Run download_wikiann.py first.")
        return []

    examples = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if max_n and i >= max_n:
                break
            examples.append(json.loads(line))
    return examples


# ──────────────────────────────────────────────
# MODEL EVALUATORS
# ──────────────────────────────────────────────

def evaluate_gliner2_base(lang: str, test_data: list[dict]) -> dict:
    """Evaluate GLiNER2 base model (no adapter)."""
    from gliner2 import GLiNER2
    model = GLiNER2.from_pretrained("fastino/gliner2-multi-v1")
    labels = ["person", "organization", "location"]

    predictions = []
    for ex in test_data:
        result = model.extract_entities(ex["text"], labels)
        predictions.append(result)

    return compute_entity_f1(predictions, test_data)


def evaluate_gliner2_lora(lang: str, test_data: list[dict]) -> dict:
    """Evaluate GLiNER2 with LoRA adapter."""
    from gliner2 import GLiNER2
    model = GLiNER2.from_pretrained("fastino/gliner2-base-v1")

    adapter_path = Path(args.adapters_dir) / f"{lang}_adapter"
    for subdir in ["best", "final", ""]:
        check = adapter_path / subdir if subdir else adapter_path
        if check.exists() and any(check.iterdir()):
            model.load_adapter(str(check))
            break
    else:
        print(f"  No adapter found for {lang}")
        return {"precision": 0, "recall": 0, "f1": 0}

    labels = ["person", "organization", "location"]
    predictions = []
    for ex in test_data:
        result = model.extract_entities(ex["text"], labels)
        predictions.append(result)

    return compute_entity_f1(predictions, test_data)


def evaluate_moe(lang: str, test_data: list[dict]) -> dict:
    """Evaluate GLiNER-MoE-MultiLingual."""
    import torch
    from gliner import GLiNERConfig, GLiNER

    config_path = Path("models/moe_multilingual/gliner_config.json")
    weights_path = Path("models/moe_multilingual/pytorch_model.bin")

    if not config_path.exists():
        print("  MoE model not found. Skipping.")
        return {"precision": 0, "recall": 0, "f1": 0}

    with open(config_path) as f:
        config = json.load(f)
    model = GLiNER(GLiNERConfig(**config))
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    state = torch.load(str(weights_path), map_location=device, weights_only=True)
    model.model.load_state_dict(state, strict=True)
    model = model.to(device)

    labels = ["Person", "Organization", "Location"]
    label_lower = {"person": "person", "organization": "organization", "location": "location"}

    predictions = []
    for ex in test_data:
        entities = model.predict_entities(ex["text"], labels, threshold=args.threshold)
        # Convert to standard format
        result = {"entities": defaultdict(list)}
        for e in entities:
            result["entities"][e["label"].lower()].append(e["text"])
        predictions.append(dict(result))

    return compute_entity_f1(predictions, test_data)


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    modes = [args.mode] if args.mode != "all" else ["gliner2-base", "gliner2-lora", "moe"]
    results = {}

    for lang in args.lang:
        print(f"\n{'='*60}")
        print(f"Evaluating: {lang}")
        print(f"{'='*60}")

        test_data = load_test_data(lang, args.max_examples)
        if not test_data:
            continue
        print(f"  Test examples: {len(test_data)}")

        results[lang] = {}

        for mode in modes:
            print(f"\n  Model: {mode}")
            start = time.time()

            try:
                if mode == "gliner2-base":
                    metrics = evaluate_gliner2_base(lang, test_data)
                elif mode == "gliner2-lora":
                    metrics = evaluate_gliner2_lora(lang, test_data)
                elif mode == "moe":
                    metrics = evaluate_moe(lang, test_data)
            except Exception as e:
                print(f"  ERROR: {e}")
                metrics = {"precision": 0, "recall": 0, "f1": 0, "error": str(e)}

            elapsed = time.time() - start
            metrics["time_s"] = round(elapsed, 1)
            results[lang][mode] = metrics

            print(f"    Precision: {metrics['precision']:.3f}")
            print(f"    Recall:    {metrics['recall']:.3f}")
            print(f"    F1:        {metrics['f1']:.3f}")
            print(f"    Time:      {elapsed:.1f}s")

    # ── Summary Table ──
    print(f"\n{'='*60}")
    print("BENCHMARK SUMMARY")
    print(f"{'='*60}")
    print(f"{'Language':<12}", end="")
    for mode in modes:
        print(f"  {mode:<18}", end="")
    print()
    print("-" * (12 + 20 * len(modes)))

    for lang in args.lang:
        if lang not in results:
            continue
        print(f"{lang:<12}", end="")
        for mode in modes:
            if mode in results[lang]:
                f1 = results[lang][mode]["f1"]
                print(f"  F1={f1:.3f}          ", end="")
            else:
                print(f"  {'N/A':<18}", end="")
        print()

    # Save results
    out_path = Path(args.data_dir) / "benchmark_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()
