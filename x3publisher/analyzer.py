#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import fitz
import numpy as np

from x3publisher.regions import detect_regions


@dataclass
class PageAnalysis:
    page: int
    width: int
    height: int
    dark_ink_ratio: float
    medium_ink_ratio: float
    colorfulness: float
    text_line_count: int
    text_block_count: int
    body_bbox: list[int] | None
    top_ink_ratio: float
    bottom_ink_ratio: float
    left_margin_ratio: float | None
    right_margin_ratio: float | None
    classification: str
    confidence: float
    warnings: list[str]
    regions: list[dict]
    thumbnail: str


def render_page(page: fitz.Page, dpi: int = 110) -> np.ndarray:
    scale = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, pix.n
    )
    if pix.n == 4:
        image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
    return image[:, :, :3]


def connected_components(mask: np.ndarray, min_area: int = 12):
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    components = []
    for index in range(1, count):
        x, y, width, height, area = stats[index]
        if area >= min_area:
            components.append((x, y, width, height, area))
    return components


def line_boxes(gray: np.ndarray) -> list[tuple[int, int, int, int]]:
    ink = (gray < 155).astype(np.uint8) * 255
    height, width = gray.shape
    joined = cv2.morphologyEx(
        ink,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, width // 55), 2)),
    )
    components = connected_components(
        joined, min_area=max(18, width * height // 250000)
    )
    lines = []
    for x, y, component_width, component_height, _ in components:
        if component_width >= width * 0.06 and 2 <= component_height <= height * 0.06:
            lines.append((x, y, component_width, component_height))
    return sorted(lines, key=lambda box: (box[1], box[0]))


def block_boxes(gray: np.ndarray) -> list[tuple[int, int, int, int]]:
    ink = (gray < 155).astype(np.uint8) * 255
    height, width = gray.shape
    merged = cv2.morphologyEx(
        ink,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(
            cv2.MORPH_RECT, (max(7, width // 90), max(7, height // 90))
        ),
    )
    components = connected_components(
        merged, min_area=max(60, width * height // 70000)
    )
    blocks = []
    for x, y, component_width, component_height, _ in components:
        if component_width >= width * 0.04 and component_height >= height * 0.008:
            blocks.append((x, y, component_width, component_height))
    return sorted(blocks, key=lambda box: (box[1], box[0]))


def bbox_from_ink(gray: np.ndarray):
    ys, xs = np.where(gray < 155)
    if len(xs) == 0:
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def classify(
    page_number: int,
    rgb: np.ndarray,
    gray: np.ndarray,
    lines: list[tuple[int, int, int, int]],
    blocks: list[tuple[int, int, int, int]],
    bbox,
):
    del blocks
    height, width = gray.shape
    dark = float(np.mean(gray < 155))
    medium = float(np.mean(gray < 220))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    colorfulness = float(np.mean(hsv[:, :, 1]) / 255.0)
    warnings = []

    if dark < 0.00065:
        return "Blank", 0.99, warnings

    if page_number == 1 or (colorfulness > 0.08 and medium > 0.06):
        confidence = 0.97 if page_number == 1 else 0.82
        return "Cover / image page", confidence, warnings

    if not bbox:
        return "Blank", 0.95, warnings

    x0, y0, x1, y1 = bbox
    box_width, box_height = x1 - x0 + 1, y1 - y0 + 1
    area_fraction = (box_width * box_height) / (width * height)

    if len(lines) <= 6 and area_fraction < 0.25:
        if page_number <= 4:
            return "Arabic / decorative front matter", 0.88, warnings
        return "Title / dedication page", 0.87, warnings

    if page_number <= 10 and len(lines) >= 12:
        return "Publication details", 0.86, warnings

    if page_number <= 15 and len(lines) >= 14:
        widths = [line_width / width for _, _, line_width, _ in lines]
        short_share = sum(value < 0.55 for value in widths) / max(1, len(widths))
        if short_share > 0.45:
            return "Contents", 0.83, warnings

    top_lines = [box for box in lines if box[1] < height * 0.38]
    lower_lines = [box for box in lines if box[1] >= height * 0.38]
    if 1 <= len(top_lines) <= 5 and len(lower_lines) >= 8 and page_number > 10:
        return "Chapter opening", 0.79, warnings

    if len(lines) >= 12:
        return "Body text", 0.92, warnings

    if len(lines) >= 6:
        return "Sparse body / section page", 0.72, warnings

    return "Uncertain", 0.50, ["Manual review recommended"]


def thumbnail_data(rgb: np.ndarray, max_width: int = 230) -> str:
    height, width, _ = rgb.shape
    scale = max_width / width
    resized = cv2.resize(
        rgb,
        (max_width, max(1, int(height * scale))),
        interpolation=cv2.INTER_AREA,
    )
    success, buffer = cv2.imencode(
        ".jpg",
        cv2.cvtColor(resized, cv2.COLOR_RGB2BGR),
        [int(cv2.IMWRITE_JPEG_QUALITY), 76],
    )
    return base64.b64encode(buffer).decode("ascii") if success else ""


def analyze_page(page_number: int, page: fitz.Page, dpi: int) -> PageAnalysis:
    rgb = render_page(page, dpi)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    height, width = gray.shape
    lines = line_boxes(gray)
    blocks = block_boxes(gray)
    bbox = bbox_from_ink(gray)

    top = float(np.mean(gray[: max(1, int(height * 0.11)), :] < 155))
    bottom = float(np.mean(gray[int(height * 0.88) :, :] < 155))
    dark = float(np.mean(gray < 155))
    medium = float(np.mean(gray < 220))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    colorfulness = float(np.mean(hsv[:, :, 1]) / 255.0)

    left_margin = right_margin = None
    if bbox:
        left_margin = bbox[0] / width
        right_margin = 1 - bbox[2] / width

    classification, confidence, warnings = classify(
        page_number, rgb, gray, lines, blocks, bbox
    )
    body_types = {"Body text", "Chapter opening", "Sparse body / section page"}
    regions = detect_regions(
        gray, lines, allow_footnotes=classification in body_types
    )

    return PageAnalysis(
        page=page_number,
        width=width,
        height=height,
        dark_ink_ratio=round(dark, 6),
        medium_ink_ratio=round(medium, 6),
        colorfulness=round(colorfulness, 5),
        text_line_count=len(lines),
        text_block_count=len(blocks),
        body_bbox=bbox,
        top_ink_ratio=round(top, 6),
        bottom_ink_ratio=round(bottom, 6),
        left_margin_ratio=round(left_margin, 4) if left_margin is not None else None,
        right_margin_ratio=round(right_margin, 4) if right_margin is not None else None,
        classification=classification,
        confidence=round(confidence, 2),
        warnings=warnings,
        regions=[region.to_dict() for region in regions],
        thumbnail=thumbnail_data(rgb),
    )


def region_overlay_html(page: PageAnalysis) -> str:
    overlays = []
    for region in page.regions:
        left, top, right, bottom = region["bbox"]
        left_percent = max(0.0, min(100.0, left / page.width * 100))
        top_percent = max(0.0, min(100.0, top / page.height * 100))
        width_percent = max(
            0.0, min(100.0 - left_percent, (right - left) / page.width * 100)
        )
        height_percent = max(
            0.0, min(100.0 - top_percent, (bottom - top) / page.height * 100)
        )
        kind = region["kind"]
        label = kind.capitalize()
        overlays.append(
            f'<span class="region region-{kind}" data-region="{kind}" '
            f'title="{label}: {region["line_count"]} lines" '
            f'style="left:{left_percent:.2f}%;top:{top_percent:.2f}%;'
            f'width:{width_percent:.2f}%;height:{height_percent:.2f}%">'
            f"<span>{label}</span></span>"
        )
    return "".join(overlays)


def html_report(pdf_path: Path, pages: list[PageAnalysis], output: Path):
    from collections import Counter

    counts = Counter(page.classification for page in pages)
    review = [page for page in pages if page.confidence < 0.75 or page.warnings]
    body_types = {"Body text", "Chapter opening", "Sparse body / section page"}
    body_pages = [
        page
        for page in pages
        if page.classification in body_types and page.body_bbox
    ]

    if body_pages:
        left_margins = [
            page.left_margin_ratio
            for page in body_pages
            if page.left_margin_ratio is not None
        ]
        right_margins = [
            page.right_margin_ratio
            for page in body_pages
            if page.right_margin_ratio is not None
        ]
        typical_left = (
            round(float(np.median(left_margins)), 3) if left_margins else None
        )
        typical_right = (
            round(float(np.median(right_margins)), 3) if right_margins else None
        )
    else:
        typical_left = typical_right = None

    cards = []
    for page in pages:
        warnings = "".join(f"<li>{warning}</li>" for warning in page.warnings)
        region_summary = ", ".join(
            f"{region['kind']} ({region['line_count']} lines)"
            for region in page.regions
        )
        overlays = region_overlay_html(page)
        cards.append(
            f"""
        <article class="card">
          <div class="thumbnail">
            <img src="data:image/jpeg;base64,{page.thumbnail}" alt="Page {page.page}"/>
            {overlays}
          </div>
          <div>
            <h3>Page {page.page}: {page.classification}</h3>
            <p><strong>Confidence:</strong> {round(page.confidence * 100)}%</p>
            <p><strong>Detected lines:</strong> {page.text_line_count} &nbsp; <strong>blocks:</strong> {page.text_block_count}</p>
            <p><strong>Regions:</strong> {region_summary or "none"}</p>
            <p><strong>Dark ink:</strong> {page.dark_ink_ratio:.4f} &nbsp; <strong>colour:</strong> {page.colorfulness:.3f}</p>
            {"<ul>" + warnings + "</ul>" if warnings else ""}
          </div>
        </article>
        """
        )

    count_html = "".join(
        f"<tr><td>{name}</td><td>{count}</td></tr>"
        for name, count in counts.most_common()
    )
    output.write_text(
        f"""<!doctype html>
<html><head><meta charset="utf-8"/>
<title>X3 Publisher analysis</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;max-width:1120px;margin:36px auto;padding:0 22px;line-height:1.45;background:#f5f5f5;color:#171717}}
header,.summary{{background:white;border-radius:14px;padding:22px;margin-bottom:20px;box-shadow:0 2px 12px #0001}}
h1{{margin-top:0}} table{{border-collapse:collapse;width:100%}}td,th{{padding:7px 10px;border-bottom:1px solid #ddd;text-align:left}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px}}
.card{{display:flex;gap:16px;background:white;border-radius:12px;padding:14px;box-shadow:0 2px 10px #0001}}
.thumbnail{{position:relative;width:128px;flex:0 0 128px;align-self:flex-start;line-height:0}}
.thumbnail img{{display:block;width:100%;height:auto;border:1px solid #ddd;box-sizing:border-box}}
.region{{position:absolute;box-sizing:border-box;border:1.5px solid;pointer-events:auto}}
.region span{{position:absolute;left:-1px;top:-11px;padding:1px 3px;font-size:7px;line-height:9px;font-weight:700;color:white;text-transform:uppercase;letter-spacing:.03em}}
.region-header{{border-color:#2563eb;background:#2563eb12}}.region-header span{{background:#2563eb}}
.region-body{{border-color:#16a34a;background:#16a34a0d}}.region-body span{{background:#16a34a}}
.region-footnote{{border-color:#dc2626;background:#dc26261a}}.region-footnote span{{background:#dc2626}}
.region-footer{{border-color:#9333ea;background:#9333ea12}}.region-footer span{{background:#9333ea}}
.card h3{{margin:0 0 8px;font-size:1rem}}.card p{{margin:4px 0;font-size:.9rem}}
code{{background:#eee;padding:2px 5px;border-radius:4px}}
</style></head>
<body>
<header>
<h1>X3 Publisher Alpha - Document Analysis</h1>
<p><strong>Source:</strong> {pdf_path.name}</p>
<p><strong>Pages:</strong> {len(pages)} &nbsp; <strong>Pages flagged for review:</strong> {len(review)}</p>
<p><strong>Typical detected body margins:</strong> left {typical_left if typical_left is not None else "n/a"}, right {typical_right if typical_right is not None else "n/a"} (fractions of page width).</p>
</header>
<section class="summary"><h2>Page classification</h2><table><tr><th>Type</th><th>Count</th></tr>{count_html}</table></section>
<section class="grid">{''.join(cards)}</section>
</body></html>""",
        encoding="utf-8",
    )


def analyze(pdf: Path, output_directory: Path, dpi: int = 110):
    output_directory.mkdir(parents=True, exist_ok=True)
    document = fitz.open(pdf)
    results = []
    for page_number, page in enumerate(document, 1):
        print(f"Analyzing page {page_number}/{len(document)}", flush=True)
        results.append(analyze_page(page_number, page, dpi))

    payload = {
        "source": str(pdf),
        "page_count": len(results),
        "generated_at": __import__("datetime").datetime.now().isoformat(
            timespec="seconds"
        ),
        "pages": [asdict(page) | {"thumbnail": None} for page in results],
    }
    (output_directory / "analysis.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    html_report(pdf, results, output_directory / "report.html")
    print(
        f"\nComplete.\nReport: {output_directory / 'report.html'}"
        f"\nData: {output_directory / 'analysis.json'}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Analyze a scanned PDF before OCR and EPUB reconstruction."
    )
    parser.add_argument("pdf", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--dpi", type=int, default=110)
    args = parser.parse_args()

    pdf = args.pdf.expanduser().resolve()
    if not pdf.exists() or pdf.suffix.lower() != ".pdf":
        raise SystemExit("Please provide an existing PDF file.")

    output = args.output or pdf.with_name(pdf.stem + " - X3 Analysis")
    analyze(pdf, output, args.dpi)


if __name__ == "__main__":
    main()
