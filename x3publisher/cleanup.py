"""Conservative, document-aware cleanup for OCR output."""

from __future__ import annotations

import re

GLOSSARY_RULES = (
    (re.compile(r"\bDar[ .]+al-[‘'’]?(?:Uli+m|Ulam)\b", re.I), "Dar al-‘Ulum"),
    (
        re.compile(
            r"\bMufti Muhammad Sha(?:ff|fi)[‘'’]?(?=[\s.,;:!?]|$)", re.I
        ),
        "Mufti Muhammad Shafi‘",
    ),
    (re.compile(r"(?m)^Thad\b"), "I had"),
)

# Tesseract commonly turns small superscript references into stars, apostrophes,
# or a star plus the final digit. These deliberately narrow forms avoid touching
# ordinary punctuation.
INLINE_NOTE_MARKER = re.compile(r"(?<=\w)\*(?:[‘'’]|\d)?|(?<=[.!?])\*")
FOOTNOTE_START = re.compile(r"(?m)^(\d{1,3})\s")


def normalize_terms(text: str) -> tuple[str, list[str]]:
    changes = []
    for pattern, replacement in GLOSSARY_RULES:
        text, count = pattern.subn(replacement, text)
        if count:
            changes.append(f"{replacement} ({count})")
    return text, changes


def recover_inline_footnotes(
    body_text: str, footnote_text: str
) -> tuple[str, list[str]]:
    numbers = FOOTNOTE_START.findall(footnote_text)
    markers = list(INLINE_NOTE_MARKER.finditer(body_text))
    if not numbers or len(markers) != len(numbers):
        return body_text, []

    iterator = iter(numbers)
    recovered = INLINE_NOTE_MARKER.sub(lambda _: f"[{next(iterator)}]", body_text)
    return recovered, [f"Recovered inline footnotes: {', '.join(numbers)}"]


def clean_page_texts(
    body_text: str, footnote_text: str = ""
) -> tuple[str, str, list[str]]:
    body_text, changes = normalize_terms(body_text)
    footnote_text, footnote_changes = normalize_terms(footnote_text)
    body_text, reference_changes = recover_inline_footnotes(body_text, footnote_text)
    return body_text, footnote_text, changes + footnote_changes + reference_changes
