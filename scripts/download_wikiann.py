#!/usr/bin/env python3
"""
download_wikiann.py
===================
Downloads WikiANN NER data for target languages from HuggingFace,
converts IOB2 tags to GLiNER2 InputExample-compatible JSONL format.

Usage:
    python scripts/download_wikiann.py
    python scripts/download_wikiann.py --langs ru zh
    python scripts/download_wikiann.py --max-per-split 500
"""

import json
import os
import argparse
from pathlib import Path

# ──────────────────────────────────────────────
# STEP 1: Parse arguments
# ──────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Download WikiANN and convert to JSONL")
parser.add_argument("--langs", nargs="+", default=["ru", "zh", "id", "ur", "th"],
                    help="Language codes to download (default: ru zh id ur th)")
parser.add_argument("--output-dir", default="data", help="Output directory for JSONL files")
parser.add_argument("--max-per-split", type=int, default=None,
                    help="Max examples per split (for quick testing)")
args = parser.parse_args()

LANG_NAMES = {
    "ru": "Russian", "zh": "Mandarin", "id": "Indonesian",
    "ur": "Urdu", "th": "Thai", "en": "English"
}

# WikiANN uses integer tags:
# 0=O, 1=B-PER, 2=I-PER, 3=B-ORG, 4=I-ORG, 5=B-LOC, 6=I-LOC
TAG_MAP = {0: "O", 1: "B-PER", 2: "I-PER", 3: "B-ORG", 4: "I-ORG", 5: "B-LOC", 6: "I-LOC"}
LABEL_MAP = {"PER": "person", "ORG": "organization", "LOC": "location"}


# ──────────────────────────────────────────────
# STEP 2: IOB2 to entity dict converter
# ──────────────────────────────────────────────
def iob2_to_entities(tokens: list[str], tag_ids: list[int]) -> dict:
    """
    Convert IOB2 tags to {entity_type: [span_text, ...]} dictionary.

    Example:
        tokens:  ["Tim", "Cook", "visited", "Paris"]
        tag_ids: [1, 2, 0, 5]  # B-PER, I-PER, O, B-LOC
        output:  {"person": ["Tim Cook"], "location": ["Paris"]}

    How IOB2 works:
        B-XXX = Beginning of entity type XXX
        I-XXX = Inside (continuation) of entity type XXX
        O     = Outside any entity

    We collect tokens between B- and the next B-/O, join them with spaces.
    """
    entities = {"person": [], "organization": [], "location": []}
    current_tokens = []
    current_type = None

    for token, tag_id in zip(tokens, tag_ids):
        tag = TAG_MAP.get(tag_id, "O")

        if tag.startswith("B-"):
            # Save any in-progress entity
            if current_tokens and current_type:
                span = " ".join(current_tokens)
                entities[LABEL_MAP[current_type]].append(span)
            # Start new entity
            current_type = tag[2:]  # e.g. "PER"
            current_tokens = [token]

        elif tag.startswith("I-") and current_type == tag[2:]:
            # Continue current entity
            current_tokens.append(token)

        else:
            # O tag or type mismatch — flush
            if current_tokens and current_type:
                span = " ".join(current_tokens)
                entities[LABEL_MAP[current_type]].append(span)
            current_tokens = []
            current_type = None

    # Don't forget the last entity
    if current_tokens and current_type:
        span = " ".join(current_tokens)
        entities[LABEL_MAP[current_type]].append(span)

    # Remove empty categories
    return {k: v for k, v in entities.items() if v}


# ──────────────────────────────────────────────
# STEP 3: Download and convert
# ──────────────────────────────────────────────
def main():
    # Import here so the script shows a clear error if datasets isn't installed
    try:
        from datasets import load_dataset
    except ImportError:
        print("ERROR: 'datasets' library not installed.")
        print("Run: pip install datasets")
        return

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stats = {}

    for lang_code in args.langs:
        lang_name = LANG_NAMES.get(lang_code, lang_code)
        print(f"\n{'='*60}")
        print(f"Downloading WikiANN for {lang_name} ({lang_code})")
        print(f"{'='*60}")

        try:
            ds = load_dataset("wikiann", lang_code)
        except Exception as e:
            print(f"  ERROR downloading {lang_code}: {e}")
            continue

        stats[lang_code] = {}

        for split in ["train", "validation", "test"]:
            if split not in ds:
                print(f"  {split}: not available")
                continue

            examples = []
            skipped = 0

            for i, row in enumerate(ds[split]):
                if args.max_per_split and i >= args.max_per_split:
                    break

                tokens = row["tokens"]
                tags = row["ner_tags"]
                text = " ".join(tokens)
                entities = iob2_to_entities(tokens, tags)

                if entities:
                    examples.append({
                        "text": text,
                        "entities": entities
                    })
                else:
                    skipped += 1

            # Write JSONL
            outfile = output_dir / f"wikiann_{lang_code}_{split}.jsonl"
            with open(outfile, "w", encoding="utf-8") as f:
                for ex in examples:
                    f.write(json.dumps(ex, ensure_ascii=False) + "\n")

            stats[lang_code][split] = len(examples)
            print(f"  {split}: {len(examples)} examples "
                  f"(skipped {skipped} with no entities) -> {outfile}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for lang, splits in stats.items():
        total = sum(splits.values())
        print(f"  {lang} ({LANG_NAMES.get(lang, lang)}): {total} total "
              f"(train={splits.get('train', 0)}, "
              f"val={splits.get('validation', 0)}, "
              f"test={splits.get('test', 0)})")
    print(f"\nAll files saved to: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
