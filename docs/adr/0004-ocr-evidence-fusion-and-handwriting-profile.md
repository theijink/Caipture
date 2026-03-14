# ADR 0004 - OCR Evidence Fusion and Handwriting-Oriented OCR Profile

Date: 2026-03-14
Status: Accepted
Decision Makers: Project Maintainer

---

## Context

Metadata extraction quality depended too heavily on limited OCR text handling and did not clearly guarantee that context-image evidence influenced canonical metadata.

Historical archive back/context notes are often handwritten and noisy, so OCR needs stronger preprocessing and selection strategy.

---

## Decision

1. Treat OCR evidence from both back and context images as first-class metadata inputs.
2. Persist OCR artifacts per context image (`context_ocr_###.txt`) in addition to merged context text.
3. Add multi-pass OCR strategy:
   - run OCR across multiple `psm` values
   - include preprocessing variants (grayscale/threshold) for handwriting robustness
   - select best candidate based on confidence + textual signal score
4. Expand metadata inference to use fused OCR evidence for:
   - date
   - location
   - people
   - event
   - source text traceability

---

## Consequences

### Positive

- stronger evidence-to-metadata mapping
- better behavior on handwritten notes without external cloud dependencies
- clearer auditability in canonical metadata

### Negative

- extra runtime cost from multi-pass OCR
- more derived artifacts generated per job

---

## Follow-up

1. Add optional specialized handwriting OCR model adapter behind the same OCR contract.
2. Add quality benchmarks for handwritten fixture sets.
