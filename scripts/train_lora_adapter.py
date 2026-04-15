#!/usr/bin/env python3
"""
train_lora_adapter.py
=====================
Train a LoRA adapter for GLiNER2 on a specific language.

Usage:
    python scripts/train_lora_adapter.py --lang ru
    python scripts/train_lora_adapter.py --lang ur --max-train 500 --epochs 20 --lora-r 4
    python scripts/train_lora_adapter.py --lang zh --base-model fastino/gliner2-large-v1

What this script does (step by step):
    1. Loads WikiANN JSONL training data for the specified language
    2. Converts each example to GLiNER2's InputExample format
    3. Loads the GLiNER2 base model
    4. Configures LoRA training (freezes base model, trains small adapter)
    5. Trains for N epochs with early stopping
    6. Saves the adapter (~5MB) to adapters/{lang}_adapter/
"""

import json
import random
import argparse
import sys
from pathlib import Path

# ──────────────────────────────────────────────
# STEP 1: Parse arguments
# ──────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Train a LoRA adapter for GLiNER2")
parser.add_argument("--lang", required=True, help="Language code (ru, zh, id, ur, th)")
parser.add_argument("--base-model", default="fastino/gliner2-base-v1",
                    help="Base GLiNER2 model to adapt")
parser.add_argument("--data-dir", default="data", help="Directory containing JSONL files")
parser.add_argument("--output-dir", default="adapters", help="Output directory for adapters")
parser.add_argument("--max-train", type=int, default=1000, help="Max training examples")
parser.add_argument("--max-val", type=int, default=200, help="Max validation examples")
parser.add_argument("--epochs", type=int, default=10, help="Training epochs")
parser.add_argument("--batch-size", type=int, default=8, help="Batch size")
parser.add_argument("--lora-r", type=int, default=8,
                    help="LoRA rank (4=small data, 8=standard, 16=large data)")
parser.add_argument("--lora-alpha", type=float, default=None,
                    help="LoRA alpha (default: 2 * lora_r)")
parser.add_argument("--encoder-lr", type=float, default=1e-5, help="Encoder learning rate")
parser.add_argument("--task-lr", type=float, default=5e-4, help="Task head learning rate")
parser.add_argument("--seed", type=int, default=42, help="Random seed")
args = parser.parse_args()

if args.lora_alpha is None:
    args.lora_alpha = float(args.lora_r * 2)

random.seed(args.seed)


# ──────────────────────────────────────────────
# STEP 2: Load training data
# ──────────────────────────────────────────────
def load_jsonl_examples(path: str, max_n: int = None):
    """
    Load JSONL file and convert to GLiNER2 InputExample objects.

    Each line in the JSONL should look like:
        {"text": "...", "entities": {"person": ["Tim Cook"], "location": ["Paris"]}}

    GLiNER2's InputExample expects the same format.
    """
    from gliner2.training.data import InputExample

    examples = []
    path = Path(path)
    if not path.exists():
        print(f"ERROR: Data file not found: {path}")
        print(f"Run download_wikiann.py first: python scripts/download_wikiann.py --langs {args.lang}")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line.strip())
            examples.append(InputExample(
                text=d["text"],
                entities=d["entities"]
            ))

    if max_n and len(examples) > max_n:
        random.shuffle(examples)
        examples = examples[:max_n]

    return examples


print(f"{'='*60}")
print(f"Training LoRA Adapter: {args.lang}")
print(f"{'='*60}")

data_dir = Path(args.data_dir)
train_file = data_dir / f"wikiann_{args.lang}_train.jsonl"
val_file = data_dir / f"wikiann_{args.lang}_validation.jsonl"

print(f"\nLoading training data from {train_file}...")
train_data = load_jsonl_examples(str(train_file), args.max_train)
print(f"  Loaded {len(train_data)} training examples (max: {args.max_train})")

print(f"Loading validation data from {val_file}...")
val_data = load_jsonl_examples(str(val_file), args.max_val)
print(f"  Loaded {len(val_data)} validation examples (max: {args.max_val})")


# ──────────────────────────────────────────────
# STEP 3: Load base model
# ──────────────────────────────────────────────
from gliner2 import GLiNER2
from gliner2.training.trainer import GLiNER2Trainer, TrainingConfig

print(f"\nLoading base model: {args.base_model}")
model = GLiNER2.from_pretrained(args.base_model)
print("  Model loaded successfully.")


# ──────────────────────────────────────────────
# STEP 4: Configure LoRA training
# ──────────────────────────────────────────────
"""
LoRA (Low-Rank Adaptation) explained:
  - The base model's weights are FROZEN (not updated)
  - Small "adapter" matrices are added alongside certain layers
  - Only these small matrices are trained
  - Result: ~5MB adapter vs ~450MB full model
  - At inference: adapter is loaded on top of frozen base

Key hyperparameters:
  - lora_r: Rank of the adapter matrices. Higher = more capacity but more params.
    Use 4 for small datasets (<500 examples), 8 for standard, 16 for large.
  - lora_alpha: Scaling factor. Usually set to 2 * lora_r.
  - lora_dropout: Regularisation. 0.05 is a safe default.
"""

output_path = Path(args.output_dir) / f"{args.lang}_adapter"

config = TrainingConfig(
    output_dir=str(output_path),
    experiment_name=f"lora_{args.lang}",
    num_epochs=args.epochs,
    batch_size=args.batch_size,
    encoder_lr=args.encoder_lr,
    task_lr=args.task_lr,
    warmup_ratio=0.1,
    scheduler_type="cosine",
    # LoRA settings
    use_lora=True,
    lora_r=args.lora_r,
    lora_alpha=args.lora_alpha,
    lora_dropout=0.05,
    save_adapter_only=True,   # Critical: saves ~5MB not ~450MB
    # Evaluation & saving
    eval_strategy="epoch",
    save_best=True,
    early_stopping=True,
    early_stopping_patience=3,
)

print(f"\nTraining configuration:")
print(f"  Output:      {output_path}")
print(f"  Epochs:      {args.epochs}")
print(f"  Batch size:  {args.batch_size}")
print(f"  LoRA rank:   {args.lora_r}")
print(f"  LoRA alpha:  {args.lora_alpha}")
print(f"  Encoder LR:  {args.encoder_lr}")
print(f"  Task LR:     {args.task_lr}")


# ──────────────────────────────────────────────
# STEP 5: Train
# ──────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"Starting training...")
print(f"{'='*60}\n")

trainer = GLiNER2Trainer(model, config)
trainer.train(train_data=train_data, val_data=val_data)

print(f"\n{'='*60}")
print(f"Training complete!")
print(f"Adapter saved to: {output_path}")
print(f"{'='*60}")

# Show adapter size
best_path = output_path / "best"
final_path = output_path / "final"
for p in [best_path, final_path, output_path]:
    if p.exists():
        total_size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        print(f"  {p.name}: {total_size / 1024 / 1024:.1f} MB")
