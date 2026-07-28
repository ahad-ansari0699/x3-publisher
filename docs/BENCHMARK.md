# Analyzer Benchmark

## Benchmark document

*The Great Scholars of the Deoband Islamic Seminary*, 146 scanned pages.

The source PDF and generated HTML reports are intentionally excluded from Git.

## Alpha 0.1.1 baseline

The imported analyzer was run at the default 110 DPI and compared with the
supplied Alpha 0.1.1 `analysis.json`.

- Page count: 146
- Classification differences: 0
- Confidence differences: 0
- Pages flagged for review: 96
- Pages with warnings: 94
- Pages below 75% confidence: 3

### Classification distribution

| Classification | Pages |
| --- | ---: |
| Body text | 107 |
| Chapter opening | 16 |
| Blank | 11 |
| Cover / image page | 2 |
| Title / dedication page | 2 |
| Publication details | 2 |
| Contents | 2 |
| Sparse body / section page | 2 |
| Arabic / decorative front matter | 1 |
| Uncertain | 1 |

## Visual audit findings

The supplied JSON is output from the same Alpha algorithm, so exact agreement
proves reproducibility rather than classification accuracy.

A visual review of pages 1-20 found:

- Front-matter categories are too broad. Half-title, title, dedication,
  foreword, and preface openings are collapsed into generic categories.
- Page 16 is ordinary body text but receives a possible-footnote warning.
- Page 17 contains a genuine footnote and receives the same warning.
- The footnote heuristic flags 94 of 146 pages, making the review queue too
  noisy to be useful.
- Page 20 is a continuation page classified as sparse body / section page.

## Next measurement targets

1. Separate page classification from region detection.
2. Detect footnote regions from layout changes, not merely a wide line near
   the bottom of a page.
3. Add a small human-labeled page set for front matter, chapter openings,
   body pages, and footnotes.
4. Track classification accuracy and footnote precision/recall against those
   labels.

## Region detection

The region detector preserves all 146 Alpha classifications and
confidence scores while adding header, body, footnote, and footer regions to
each page record.

- Classification changes: 0
- Confidence changes: 0
- Detected footnote pages: 73
- Manual review queue: reduced from 96 pages to 3 low-confidence pages
- Page 16 false-positive footnote detection: absent
- Page 17 genuine footnote: detected

Detected footnotes are structured regions rather than warnings. They can be
routed to a dedicated OCR path without requiring manual review.

## Human-labeled footnote evaluation

Pages 16-55 were visually reviewed at high resolution and labeled for footnote
presence. The labels live in `benchmarks/deoband-footnotes.json`.

Region detector results:

| Metric | Result |
| --- | ---: |
| Labeled pages | 40 |
| Precision | 100.0% |
| Recall | 100.0% |
| F1 | 100.0% |
| Accuracy | 100.0% |
| False positives | 0 |
| False negatives | 0 |

The label set is intentionally small and document-specific, so these results
establish a regression baseline rather than proving performance across all
book designs.

Run the evaluation with:

```bash
python scripts/evaluate_regions.py \
  benchmarks/deoband-footnotes.json \
  candidate-analysis.json
```

## Comparing future runs

```bash
python scripts/compare_analysis.py reference.json candidate.json
```

The comparison tool reports page-set differences, classification changes,
confidence changes, distribution totals, and review-queue size.
