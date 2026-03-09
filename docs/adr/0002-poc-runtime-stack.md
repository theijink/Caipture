# ADR 0002 - PoC Runtime Stack and Deterministic Processing Surrogates

Date: 2026-03-09
Status: Accepted
Decision Makers: Project Maintainer

---

## Context

The PoC must provide a complete runnable system with tests and strong reproducibility while keeping setup lightweight.

Full production-grade CV/OCR/LLM dependencies (OpenCV/Tesseract/external providers) increase installation/runtime variance and reduce deterministic behavior in CI.

---

## Decision

For the PoC implementation baseline:

1. Use Python standard-library-first runtime where practical.
2. Use SQLite-backed job/event store for queue/state in local storage.
3. Implement deterministic surrogate logic for CV/OCR/LLM stages.
4. Keep interfaces and contracts aligned with production architecture so engines can be replaced later.

---

## Details

- Web API uses `http.server` JSON endpoints for upload/status/review.
- Workers are separate long-running processes per stage.
- Queue/state persisted at `storage/runtime/jobs.sqlite3`.
- OCR stage consumes optional `.txt` sidecars for deterministic fixture behavior.
- Metadata generation and review decision follow schema and config thresholds.
- Export stage writes image copy + sidecar JSON + export mapping metadata.

---

## Consequences

### Positive

- deterministic tests and reproducible outputs
- minimal dependency footprint
- easy local onboarding and Raspberry Pi viability

### Negative

- CV/OCR quality is placeholder-level for PoC
- API/UI is basic and not feature-complete for production usage

---

## Follow-up

Future ADR should define migration path from deterministic surrogates to OpenCV/Tesseract-backed adapters while preserving current contracts and tests.
