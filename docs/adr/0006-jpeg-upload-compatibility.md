# ADR 0006 - JPEG Upload Compatibility for Mobile Capture

Date: 2026-03-14
Status: Accepted
Decision Makers: Project Maintainer

---

## Context

Caipture is intended to be operated from a computer while subject, back, or context photos may be captured and uploaded from a mobile phone over the local network.

The active development profile only accepted `.png` uploads, while common phone camera workflows typically produce `.jpg` or `.jpeg`. That created avoidable upload failures for normal mobile capture sessions.

The pipeline already:

- detects both PNG and JPEG image dimensions
- stores raw inputs immutably under `storage/jobs/<job_id>/inputs/`
- normalizes derived CV artifacts and exports to PNG

---

## Decision

1. Treat JPEG (`.jpg`, `.jpeg`) as a first-class upload format alongside PNG.
2. Preserve uploaded raw files in their original format and suffix under `inputs/`; do not convert raw evidence during ingest.
3. Continue writing normalized downstream derivatives and exports as PNG.
4. Cover JPEG support explicitly in unit and web-upload regression tests.

---

## Rationale

1. This removes the mobile-phone compatibility issue with the smallest change to the trust boundary and storage model.
2. Preserving originals keeps raw evidence immutable and avoids silent lossy re-encoding during upload.
3. The pipeline already emits normalized PNG artifacts downstream, so broadening accepted inputs does not fragment later stages.
4. A configuration and test-backed change is lower risk than introducing mandatory conversion logic into upload handling.

---

## Alternatives Considered

### A. Convert every upload to PNG during ingest

Pros:

- one canonical raw raster format internally

Cons:

- mutates the effective raw evidence representation
- adds upload-time processing and dependency risk
- can lose metadata/original encoding characteristics

### B. Add JPEG only in the web layer

Pros:

- minimal surface change

Cons:

- CLI/API and config behavior would remain inconsistent
- support would be accidental rather than explicit

JPEG acceptance across the configured upload contract was chosen.

---

## Consequences

### Positive

- mobile camera uploads work in the common case without operator conversion
- raw evidence remains unchanged after upload
- downstream artifacts stay consistent as PNG

### Negative

- accepted raw input formats expand and must remain test-covered
- some future formats such as HEIC still require a separate decision

---

## Follow-up

1. Revisit EXIF orientation normalization for mobile-origin JPEGs if real-world fixtures show issues in the OpenCV path.
2. Evaluate whether HEIC/HEIF support is needed for newer phone workflows.
