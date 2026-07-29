"""Conservative, document-aware cleanup for OCR output."""

from __future__ import annotations

import re

GLOSSARY_RULES = (
    (
        re.compile(
            r"\bDar[ .]+al-[‘'’ʿ]?(?:Uli+m|Ulum|Ulam|Ulūm)\b",
            re.I,
        ),
        "Dar al-ʿUlūm",
    ),
    (
        re.compile(
            r"\bMufti Muhammad Sha(?:ff|fi)[‘'’]?(?=[\s.,;:!?]|$)", re.I
        ),
        "Muftī Muḥammad Shafīʿ",
    ),
    (re.compile(r"(?m)^Thad\b"), "I had"),
    (
        re.compile(
            r"\bShuy(?:ttkh|itkb|ukb|ukh|ūkh)-o-Ak(?:abir|ābir)\b",
            re.I,
        ),
        "Shuyūkh-o-Akābir",
    ),
    (re.compile(r"\b(?:Kdilafahb|Kbilafah|Khilafab)\b", re.I), "Khilafah"),
    (
        re.compile(r"\b(?:al-)?La(?:hw|wh) al-Ma(?:bf|hf)uz\b", re.I),
        "al-Lawḥ al-Maḥfūẓ",
    ),
    (
        re.compile(r"\bMUHAMMAD TAqti [‘'’]?USMANT\b"),
        "MUḤAMMAD TAQĪ ʿUSMĀNĪ",
    ),
    (re.compile(r"\bBhaghalpiri\b", re.I), "Bhaghalpuri"),
    (re.compile(r"\bHaji Sabib\b", re.I), "Haji Sahib"),
    (re.compile(r"\bwithin 4o days\b", re.I), "within 40 days"),
    (re.compile(r"\bSaharanpar\b", re.I), "Saharanpur"),
    (re.compile(r"\bTadbkirat ar-Rashid\b", re.I), "Tadhkirat ar-Rashid"),
)

# Tesseract commonly turns small superscript references into stars, apostrophes,
# or a star plus the final digit. These deliberately narrow forms avoid touching
# ordinary punctuation.
INLINE_NOTE_MARKER = re.compile(r"(?<=\w)\*(?:[‘'’]|\d)?|(?<=[.!?])\*")
FOOTNOTE_START = re.compile(r"(?m)^(\d{1,3})\s")


def reflow_paragraphs(text: str) -> str:
    """Remove scan line wraps while retaining real paragraph boundaries."""
    paragraphs = re.split(r"\n\s*\n", text.strip())
    reflowed = []
    for paragraph in paragraphs:
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        if not lines:
            continue
        joined = lines[0]
        for line in lines[1:]:
            if joined.endswith("-") and line[:1].islower():
                joined = joined[:-1] + line
            else:
                joined += " " + line
        reflowed.append(joined)
    return "\n\n".join(reflowed)


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
    body_text = reflow_paragraphs(body_text)
    footnote_text = reflow_paragraphs(footnote_text)
    body_text, changes = normalize_terms(body_text)
    footnote_text, footnote_changes = normalize_terms(footnote_text)
    body_text, reference_changes = recover_inline_footnotes(body_text, footnote_text)
    return body_text, footnote_text, changes + footnote_changes + reference_changes
