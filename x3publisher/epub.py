"""Build a compact EPUB 3 from cleaned, region-aware OCR results."""

from __future__ import annotations

import argparse
import html
import json
import re
import unicodedata
import uuid
import zipfile
from pathlib import Path

from x3publisher.cleanup import normalize_terms
from x3publisher.ocr import parse_pages

FOOTNOTE_ENTRY = re.compile(r"(?ms)^(\d{1,3})\s+(.+?)(?=^\d{1,3}\s+|\Z)")
INLINE_REFERENCE = re.compile(r"\[(\d{1,3})\]")


def page_xhtml(page: int, regions: list[dict]) -> str:
    def cleaned_text(region: dict) -> str:
        # Reapply the current verified glossary at publication time so improved
        # rules can repair audited OCR without another recognition pass. NFD
        # keeps scholarly diacritics as base glyphs plus CrossInk-supported
        # combining marks.
        text = normalize_terms(region["text"])[0]
        return unicodedata.normalize("NFD", text)

    body_parts = [
        cleaned_text(region)
        for region in regions
        if region["kind"] in {"body", "body_left", "body_right"}
    ]
    footnote_text = "\n\n".join(
        cleaned_text(region) for region in regions if region["kind"] == "footnote"
    )
    notes = {
        number: text.strip()
        for number, text in FOOTNOTE_ENTRY.findall(footnote_text)
    }

    paragraphs = []
    for paragraph in "\n\n".join(body_parts).split("\n\n"):
        escaped = html.escape(paragraph.strip())

        def reference(match: re.Match) -> str:
            number = match.group(1)
            if number not in notes:
                return match.group(0)
            return (
                f'<a class="noteref" epub:type="noteref" id="ref-{page}-{number}" '
                f'href="#note-{page}-{number}">{number}</a>'
            )

        escaped = INLINE_REFERENCE.sub(reference, escaped)
        if escaped:
            paragraphs.append(f"<p>{escaped}</p>")

    asides = []
    for number, text in notes.items():
        asides.append(
            f'<aside epub:type="footnote" id="note-{page}-{number}">'
            f'<p><a href="#ref-{page}-{number}">{number}</a> '
            f"{html.escape(text)}</p></aside>"
        )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>Source page {page}</title>
<link rel="stylesheet" type="text/css" href="../styles/book.css"/></head>
<body><section epub:type="chapter"><h1>Page {page}</h1>
{''.join(paragraphs)}{''.join(asides)}</section></body></html>"""


def build_epub(
    ocr_path: Path,
    output: Path,
    pages: set[int],
    title: str = "X3 Publisher CrossInk Review",
) -> None:
    data = json.loads(ocr_path.read_text(encoding="utf-8"))
    selected = {}
    for region in data["regions"]:
        if region["page"] in pages:
            selected.setdefault(region["page"], []).append(region)
    missing = pages - selected.keys()
    if missing:
        raise ValueError(f"No OCR regions for pages: {sorted(missing)}")

    book_id = f"urn:uuid:{uuid.uuid4()}"
    manifest = []
    spine = []
    nav_links = []
    chapters = {}
    for page in sorted(selected):
        item_id = f"page-{page}"
        filename = f"{item_id}.xhtml"
        chapters[f"OEBPS/text/{filename}"] = page_xhtml(page, selected[page])
        manifest.append(
            f'<item id="{item_id}" href="text/{filename}" '
            'media-type="application/xhtml+xml"/>'
        )
        spine.append(f'<itemref idref="{item_id}"/>')
        nav_links.append(f'<li><a href="text/{filename}">Page {page}</a></li>')

    container = """<?xml version="1.0"?>
<container version="1.0"
 xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/package.opf"
 media-type="application/oebps-package+xml"/></rootfiles></container>"""
    package = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0"
 unique-identifier="book-id"><metadata
 xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="book-id">{book_id}</dc:identifier>
<dc:title>{html.escape(title)}</dc:title><dc:language>en</dc:language>
<meta property="dcterms:modified">2026-07-28T00:00:00Z</meta>
</metadata><manifest>
<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml"
 properties="nav"/>
<item id="css" href="styles/book.css" media-type="text/css"/>
{''.join(manifest)}</manifest><spine>{''.join(spine)}</spine></package>"""
    nav = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml"
 xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Contents</title></head>
<body><nav epub:type="toc"><h1>Contents</h1><ol>
{''.join(nav_links)}</ol></nav></body></html>"""
    css = """body { line-height: 1.35; margin: 0; padding: 0; }
h1 { font-size: 1.15em; margin: 0 0 1em; }
p { margin: 0 0 .75em; text-indent: 1.2em; }
a.noteref { vertical-align: super; font-size: .75em; }
aside { margin: 1em 0; padding-top: .5em; border-top: 1px solid; }
aside p { text-indent: 0; font-size: .9em; }
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED
        )
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("OEBPS/package.opf", package)
        archive.writestr("OEBPS/nav.xhtml", nav)
        archive.writestr("OEBPS/styles/book.css", css)
        for path, content in chapters.items():
            archive.writestr(path, content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ocr", type=Path)
    parser.add_argument("-o", "--output", required=True, type=Path)
    parser.add_argument("--pages", required=True)
    parser.add_argument("--title", default="X3 Publisher CrossInk Review")
    args = parser.parse_args()
    build_epub(args.ocr, args.output, parse_pages(args.pages), args.title)
    print(f"EPUB written to {args.output}")


if __name__ == "__main__":
    main()
