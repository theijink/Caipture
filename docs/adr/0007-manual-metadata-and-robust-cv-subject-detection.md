# ADR 0007 - Manual Metadata First-Class Support and Robust CV Subject Detection

Date: 2026-03-14
Status: Accepted
Decision Makers: Project Maintainer

---

## Context

Two operational problems remained after JPEG upload support was added:

1. Manual metadata entry is expected to be a common workflow, especially when the back of a photo is unavailable, but upload handling was too strict about the exact field shape that had to be submitted.
2. Subject cropping in `worker-cv` behaved inconsistently because it relied on a brittle contour-first heuristic. Real phone captures of a physical photograph often include rotation, EXIF orientation, shadows, table edges, and glare.

---

## Decision

1. Normalize manual upload metadata at ingest into canonical `date`, `location`, and `comment` fields, while accepting common aliases such as `manual_date`, `manual_location`, `manual_comment`, and `description`.
2. Treat manual metadata as first-class evidence even when no back image is present.
3. Auto-orient CV input before subject detection.
4. Replace the first-contour-wins crop heuristic with scored OpenCV candidate selection across multiple preprocessing variants.
5. Keep ImageMagick as a fallback path, but only after the auto-oriented and candidate-scored OpenCV attempt.

---

## Rationale

1. Manual metadata should be a reliable primary workflow, not a fragile edge case.
2. Phone-origin images frequently depend on orientation metadata, so CV should normalize orientation before trying to detect the photograph boundary.
3. A scored multi-candidate approach is more robust than trusting the first quadrilateral or largest contour.
4. Keeping a fallback path preserves operability when OpenCV detection still cannot confidently isolate the photograph.

---

## Consequences

### Positive

- subject-only uploads with manual metadata can complete successfully
- JSON API, CLI, and web uploads are more tolerant of field naming variation
- CV cropping is more stable across rotated and cluttered “photo of a photo” inputs

### Negative

- CV logic becomes more complex and requires dedicated fixture coverage
- very difficult scenes may still need future tuning or operator fallback tools

---

## Follow-up

1. Add real-world regression fixtures for glare, heavy shadows, and dark-background albums.
2. Consider a review overlay that shows detected crop bounds so operators can spot CV failures faster.
