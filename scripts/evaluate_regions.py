#!/usr/bin/env python3
"""Evaluate detected footnote regions against human page labels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("labels", type=Path)
    parser.add_argument("analysis", type=Path)
    args = parser.parse_args()

    label_payload = json.loads(args.labels.read_text(encoding="utf-8"))
    labels = {
        int(page): bool(value) for page, value in label_payload["labels"].items()
    }
    analysis = json.loads(args.analysis.read_text(encoding="utf-8"))
    pages = {page["page"]: page for page in analysis["pages"]}

    missing = sorted(labels.keys() - pages.keys())
    if missing:
        raise SystemExit(f"Analysis is missing labeled pages: {missing}")

    true_positive = []
    true_negative = []
    false_positive = []
    false_negative = []
    for page_number, expected in sorted(labels.items()):
        regions = pages[page_number].get("regions", [])
        detected = any(region.get("kind") == "footnote" for region in regions)
        if expected and detected:
            true_positive.append(page_number)
        elif not expected and not detected:
            true_negative.append(page_number)
        elif detected:
            false_positive.append(page_number)
        else:
            false_negative.append(page_number)

    precision = ratio(len(true_positive), len(true_positive) + len(false_positive))
    recall = ratio(len(true_positive), len(true_positive) + len(false_negative))
    f1 = ratio(2 * precision * recall, precision + recall)
    accuracy = ratio(
        len(true_positive) + len(true_negative),
        len(labels),
    )

    print(f"Labeled pages: {len(labels)}")
    print(f"True positives: {len(true_positive)} {true_positive}")
    print(f"True negatives: {len(true_negative)} {true_negative}")
    print(f"False positives: {len(false_positive)} {false_positive}")
    print(f"False negatives: {len(false_negative)} {false_negative}")
    print(f"Precision: {precision:.1%}")
    print(f"Recall: {recall:.1%}")
    print(f"F1: {f1:.1%}")
    print(f"Accuracy: {accuracy:.1%}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
