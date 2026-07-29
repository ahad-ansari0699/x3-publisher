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

## Status

Alpha 0.1.1 focuses on pre-OCR analysis. Planned stages are:

PDF → Analyzer → Region Detection → OCR → Cleanup → EPUB Builder
