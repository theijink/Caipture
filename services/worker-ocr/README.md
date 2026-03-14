# OCR Worker (`services/worker-ocr`)

## Purpose

Extracts text from back/context images and stores OCR artifacts for metadata stage.

## Implementation

- uses `tesseract` CLI for OCR
- runs multi-pass OCR (`psm_candidates`) and selects strongest result
- applies optional preprocessing variants for handwriting robustness (`enable_preprocessing`)
- computes confidence estimate from TSV output when available
- deterministic sidecar fallback (`<image>.txt`) remains enabled for tests

Artifacts:

- `derived/back_ocr.txt`
- `derived/context_ocr.txt`
- `derived/context_ocr_###.txt` (one per context image)
- `derived/ocr_report.json`

## Run

```bash
PYTHONPATH=src python3 services/worker-ocr/main.py
```
