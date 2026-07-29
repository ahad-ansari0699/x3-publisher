"""Region-aware OCR that keeps body text and footnotes separate."""

from __future__ import annotations

import argparse
import base64
import difflib
import html
import json
import shutil
import subprocess
import tempfile
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

import cv2
import fitz
import numpy as np

from x3publisher.cleanup import clean_page_texts

OCR_KINDS = ("body", "footnote")


@dataclass(frozen=True)
class OcrRegionResult:
    page: int
    kind: str
    bbox: list[int]
    detector_confidence: float
    text: str
    raw_text: str = ""
    corrections: tuple[str, ...] = ()
    audit_text: str = ""
    agreement: float | None = None
    disagreements: tuple[str, ...] = ()


class OcrEngine(Protocol):
    def recognize(self, rgb: np.ndarray, kind: str) -> str: ...


class TesseractEngine:
    def __init__(self, language: str = "eng"):
        executable = shutil.which("tesseract")
        if not executable:
            raise RuntimeError("Tesseract is not installed or is not on PATH.")
        self.executable = executable
        self.language = language

    def recognize(self, rgb: np.ndarray, kind: str) -> str:
        del kind
        ok, encoded = cv2.imencode(".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        if not ok:
            raise RuntimeError("Could not encode OCR region.")
        process = subprocess.run(
            [
                self.executable,
                "stdin",
                "stdout",
                "-l",
                self.language,
                "--psm",
                "6",
            ],
            input=encoded.tobytes(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if process.returncode:
            message = process.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Tesseract failed: {message}")
        return process.stdout.decode("utf-8", errors="replace").strip()


class AppleVisionEngine:
    def __init__(self):
        if not shutil.which("swift"):
            raise RuntimeError("Apple Vision OCR requires Swift on macOS.")
        self.script = Path(__file__).parents[1] / "scripts" / "macos_vision_ocr.swift"

    def recognize(self, rgb: np.ndarray, kind: str) -> str:
        del kind
        with tempfile.NamedTemporaryFile(suffix=".png") as image_file:
            ok, encoded = cv2.imencode(
                ".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            )
            if not ok:
                raise RuntimeError("Could not encode Apple Vision OCR region.")
            image_file.write(encoded.tobytes())
            image_file.flush()
            process = subprocess.run(
                [
                    "swift",
                    "-module-cache-path",
                    "/private/tmp/x3-swift-module-cache",
                    str(self.script),
                    image_file.name,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        if process.returncode:
            message = process.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Apple Vision OCR failed: {message}")
        observations = json.loads(process.stdout)
        return "\n".join(item["text"] for item in observations)


def audit_texts(primary: str, secondary: str) -> tuple[float, tuple[str, ...]]:
    def words(value: str) -> list[str]:
        value = unicodedata.normalize("NFKC", value).casefold()
        return [word.strip(".,;:!?()[]{}\"“”") for word in value.split()]

    left, right = words(primary), words(secondary)
    matcher = difflib.SequenceMatcher(a=left, b=right, autojunk=False)
    disagreements = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            disagreements.append(
                f"{' '.join(left[i1:i2]) or '∅'} ↔ "
                f"{' '.join(right[j1:j2]) or '∅'}"
            )
    return round(matcher.ratio(), 4), tuple(disagreements)


def parse_pages(value: str) -> set[int]:
    pages: set[int] = set()
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        if "-" in item:
            start, end = (int(part) for part in item.split("-", 1))
            if start > end:
                raise ValueError(f"Invalid page range: {item}")
            pages.update(range(start, end + 1))
        else:
            pages.add(int(item))
    if not pages or min(pages) < 1:
        raise ValueError("Pages must be positive, one-based numbers.")
    return pages


def scale_bbox(
    bbox: list[int],
    source_size: tuple[int, int],
    target_size: tuple[int, int],
    padding: int = 8,
) -> list[int]:
    source_width, source_height = source_size
    target_width, target_height = target_size
    left, top, right, bottom = bbox
    x_scale = target_width / source_width
    y_scale = target_height / source_height
    return [
        max(0, int(left * x_scale) - padding),
        max(0, int(top * y_scale) - padding),
        min(target_width, int(np.ceil(right * x_scale)) + padding),
        min(target_height, int(np.ceil(bottom * y_scale)) + padding),
    ]


def render_page(page: fitz.Page, dpi: int) -> np.ndarray:
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, pix.n
    )
    return image[:, :, :3]


def extract_page_regions(
    rgb: np.ndarray,
    page_data: dict,
    engine: OcrEngine,
    audit_engine: OcrEngine | None = None,
) -> tuple[list[OcrRegionResult], list[tuple[OcrRegionResult, np.ndarray]]]:
    height, width = rgb.shape[:2]
    results = []
    review_items = []
    for region in page_data.get("regions", []):
        kind = region.get("kind")
        if kind not in OCR_KINDS:
            continue
        bbox = scale_bbox(
            region["bbox"],
            (page_data["width"], page_data["height"]),
            (width, height),
        )
        left, top, right, bottom = bbox
        crop = rgb[top:bottom, left:right]
        text = engine.recognize(crop, kind)
        audit_text = audit_engine.recognize(crop, kind) if audit_engine else ""
        agreement, disagreements = (
            audit_texts(text, audit_text) if audit_text else (None, ())
        )
        result = OcrRegionResult(
            page=page_data["page"],
            kind=kind,
            bbox=bbox,
            detector_confidence=float(region["confidence"]),
            text=text,
            audit_text=audit_text,
            agreement=agreement,
            disagreements=disagreements,
        )
        results.append(result)
        review_items.append((result, crop))
    return results, review_items


def clean_page_results(
    results: list[OcrRegionResult],
) -> list[OcrRegionResult]:
    body = next((result for result in results if result.kind == "body"), None)
    footnote = next((result for result in results if result.kind == "footnote"), None)
    if not body:
        return results
    clean_body, clean_footnote, corrections = clean_page_texts(
        body.text, footnote.text if footnote else ""
    )
    cleaned = []
    for result in results:
        text = clean_body if result.kind == "body" else clean_footnote
        cleaned.append(
            OcrRegionResult(
                page=result.page,
                kind=result.kind,
                bbox=result.bbox,
                detector_confidence=result.detector_confidence,
                text=text,
                raw_text=result.text,
                corrections=tuple(corrections),
                audit_text=result.audit_text,
                agreement=result.agreement,
                disagreements=result.disagreements,
            )
        )
    return cleaned


def data_image(rgb: np.ndarray, max_width: int = 760) -> str:
    if rgb.shape[1] > max_width:
        scale = max_width / rgb.shape[1]
        rgb = cv2.resize(
            rgb,
            (max_width, max(1, round(rgb.shape[0] * scale))),
            interpolation=cv2.INTER_AREA,
        )
    ok, encoded = cv2.imencode(
        ".jpg",
        cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR),
        [int(cv2.IMWRITE_JPEG_QUALITY), 86],
    )
    return base64.b64encode(encoded).decode("ascii") if ok else ""


def write_review_report(
    output: Path,
    source: Path,
    review_items: list[tuple[OcrRegionResult, np.ndarray]],
) -> None:
    cards = []
    for result, crop in review_items:
        text = html.escape(result.text) or "[No text recognized]"
        corrections = (
            "<p class=\"corrections\"><strong>Automatic corrections:</strong> "
            + html.escape("; ".join(result.corrections))
            + "</p>"
            if result.corrections
            else ""
        )
        audit = (
            f"<p class=\"audit\"><strong>Engine agreement:</strong> "
            f"{result.agreement * 100:.1f}%</p>"
            if result.agreement is not None
            else ""
        )
        cards.append(
            f"""<article class="card">
  <header><span>Page {result.page}</span><strong>{result.kind.title()}</strong></header>
  <div class="columns">
    <div><h2>Detected region</h2><img src="data:image/jpeg;base64,{data_image(crop)}"></div>
    <div><h2>Cleaned OCR text</h2>{audit}{corrections}<pre>{text}</pre></div>
  </div>
</article>"""
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        f"""<!doctype html><html><head><meta charset="utf-8">
<title>X3 Publisher OCR Review</title><style>
body{{margin:0;background:#f4f1ea;color:#20231f;font:16px system-ui,sans-serif}}
main{{max-width:1400px;margin:auto;padding:36px}}h1{{margin-bottom:8px}}
.intro{{color:#596158;margin-bottom:30px}}.card{{background:white;border:1px solid #d9d5ca;
border-radius:14px;margin:24px 0;overflow:hidden;box-shadow:0 3px 14px #0000000d}}
header{{display:flex;justify-content:space-between;padding:15px 20px;background:#173d32;color:white}}
.columns{{display:grid;grid-template-columns:1fr 1fr;gap:24px;padding:20px}}
h2{{font-size:14px;text-transform:uppercase;letter-spacing:.08em;color:#667066}}
.corrections{{background:#eef7f0;border-left:4px solid #28734d;padding:10px 12px}}
.audit{{background:#fff5dc;border-left:4px solid #b77a00;padding:10px 12px}}
img{{width:100%;height:auto;border:1px solid #ddd}}pre{{white-space:pre-wrap;line-height:1.55;
font:15px Georgia,serif;background:#faf9f6;padding:18px;border:1px solid #e2dfd7;border-radius:8px}}
@media(max-width:850px){{.columns{{grid-template-columns:1fr}}}}
</style></head><body><main><h1>X3 Publisher OCR human check</h1>
<p class="intro">{html.escape(source.name)} - body text and footnotes are intentionally kept separate.
Compare each image with the recognized text and note any missing lines, mixed regions, or obvious errors.</p>
{''.join(cards)}</main></body></html>""",
        encoding="utf-8",
    )


def run_ocr(
    pdf_path: Path,
    analysis_path: Path,
    output_path: Path,
    pages: set[int],
    dpi: int,
    engine: OcrEngine,
    audit_engine: OcrEngine | None = None,
    review_path: Path | None = None,
) -> list[OcrRegionResult]:
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    page_lookup = {page["page"]: page for page in analysis["pages"]}
    results: list[OcrRegionResult] = []
    review_items: list[tuple[OcrRegionResult, np.ndarray]] = []
    with fitz.open(pdf_path) as document:
        for page_number in sorted(pages):
            if page_number not in page_lookup or page_number > len(document):
                raise ValueError(f"Page {page_number} is unavailable.")
            rgb = render_page(document[page_number - 1], dpi)
            page_results, page_review = extract_page_regions(
                rgb, page_lookup[page_number], engine, audit_engine
            )
            page_results = clean_page_results(page_results)
            results.extend(page_results)
            if review_path:
                page_review = [
                    (cleaned, crop)
                    for cleaned, (_, crop) in zip(page_results, page_review)
                ]
                review_items.extend(page_review)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "source": str(pdf_path),
                "dpi": dpi,
                "pages": sorted(pages),
                "regions": [asdict(result) for result in results],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    if review_path:
        write_review_report(review_path, pdf_path, review_items)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("analysis", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--pages", required=True, help="Example: 16,17,40,48")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--language", default="eng")
    parser.add_argument("--review", type=Path)
    parser.add_argument(
        "--vision-audit",
        action="store_true",
        help="Compare Tesseract output with local Apple Vision OCR.",
    )
    args = parser.parse_args()
    results = run_ocr(
        args.pdf,
        args.analysis,
        args.output,
        parse_pages(args.pages),
        args.dpi,
        TesseractEngine(args.language),
        AppleVisionEngine() if args.vision_audit else None,
        args.review,
    )
    print(f"OCR complete: {len(results)} regions written to {args.output}")


if __name__ == "__main__":
    main()
