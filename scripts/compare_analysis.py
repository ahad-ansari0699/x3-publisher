#!/usr/bin/env python3
"""Compare two X3 Publisher analysis JSON files."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def load_pages(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    pages = payload.get("pages")
    if not isinstance(pages, list):
        raise ValueError(f"{path} does not contain a pages list")
    return pages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()

    reference = load_pages(args.reference)
    candidate = load_pages(args.candidate)
    reference_by_page = {page["page"]: page for page in reference}
    candidate_by_page = {page["page"]: page for page in candidate}

    missing = sorted(reference_by_page.keys() - candidate_by_page.keys())
    added = sorted(candidate_by_page.keys() - reference_by_page.keys())
    shared = sorted(reference_by_page.keys() & candidate_by_page.keys())
    classification_changes = []
    confidence_changes = []

    for page_number in shared:
        old = reference_by_page[page_number]
        new = candidate_by_page[page_number]
        if old.get("classification") != new.get("classification"):
            classification_changes.append(
                (page_number, old.get("classification"), new.get("classification"))
            )
        if old.get("confidence") != new.get("confidence"):
            confidence_changes.append(
                (page_number, old.get("confidence"), new.get("confidence"))
            )

    counts = Counter(page.get("classification") for page in candidate)
    review_pages = [
        page["page"]
        for page in candidate
        if page.get("confidence", 0) < 0.75 or page.get("warnings")
    ]

    print(f"Reference pages: {len(reference)}")
    print(f"Candidate pages: {len(candidate)}")
    print(f"Missing pages: {missing or 'none'}")
    print(f"Added pages: {added or 'none'}")
    print(f"Classification changes: {len(classification_changes)}")
    for page_number, old, new in classification_changes:
        print(f"  Page {page_number}: {old} -> {new}")
    print(f"Confidence changes: {len(confidence_changes)}")
    print("Candidate classification counts:")
    for classification, count in counts.most_common():
        print(f"  {classification}: {count}")
    print(f"Pages flagged for review: {len(review_pages)}")

    return 1 if missing or added else 0


if __name__ == "__main__":
    raise SystemExit(main())
