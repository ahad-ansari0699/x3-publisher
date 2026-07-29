# X3 Publisher

X3 Publisher converts PDFs—especially scanned books—into high-quality EPUBs optimized for the Xteink X3 running CrossInk.

This branch imports Alpha 0.1.1, which provides a local browser interface and a document analyzer that classifies pages before OCR and EPUB reconstruction.

## macOS setup

1. Double-click `Setup.command` once.
2. Double-click `X3 Publisher.command`.
3. Your browser opens to the local X3 Publisher screen.
4. Choose a PDF and click **Analyze PDF**.
5. Keep the Terminal window open while the local app is running.

Uploaded PDFs and analysis reports are saved under:

`~/Downloads/X3 Publisher Uploads/`

Nothing is uploaded to the internet. The browser page is served only from your Mac at `127.0.0.1`.

## Command-line use

```bash
python -m x3publisher.analyzer input.pdf
```

Use `--output` to choose the analysis directory and `--dpi` to change the render resolution.

See [`docs/BENCHMARK.md`](docs/BENCHMARK.md) for the current analyzer baseline
and visual-audit findings.

Generated HTML reports include color-coded overlays for detected headers,
body text, footnotes, and footers.

## Region-aware OCR preview

After analysis, OCR selected pages while preserving body text and footnotes as
separate records:

```bash
python -m x3publisher.ocr book.pdf analysis.json \
  --pages 16,17,40,48 \
  --output output/ocr-review/ocr.json \
  --review output/ocr-review/report.html \
  --vision-audit
```

The self-contained HTML report places every detected crop beside its recognized
text so OCR quality and region boundaries can be approved before a full-book run.
On macOS, `--vision-audit` compares Tesseract with Apple's local Vision OCR and
records their agreement and every differing word group. The book stays on the Mac.

## Status

Alpha 0.1.1 focuses on pre-OCR analysis. Planned stages are:

PDF → Analyzer → Region Detection → OCR → Cleanup → EPUB Builder
