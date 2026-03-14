# Caipture - Requirements Specification

Version: 0.2 (PoC implementation baseline)
Status: Draft
Scope: Personal and small-collection historical photograph digitization pipeline

---

# 1. Purpose

Caipture is a self-hosted system that converts physical photograph collections into structured digital archive assets.

The system must:

- preserve original evidence
- produce reproducible outputs
- enforce privacy-aware boundaries
- support human-in-the-loop validation
- remain configurable so behavior can be adapted without changing source code

This document defines functional and non-functional requirements intended to be directly implementable.

---

# 2. Scope

## 2.1 In Scope

1. Upload subject/back/context images for a photo item
2. Automated CV processing of subject image
3. OCR extraction from back/context images
4. Metadata interpretation with provenance and confidence
5. Human review and correction
6. Export with EXIF/IPTC/XMP and sidecar JSON
7. Local-first deployment with containerized services
8. Job-level logging, metrics, and traceability

## 2.2 Out of Scope (PoC)

- Multi-tenant SaaS hosting
- Mobile app clients
- Autonomous identity recognition of people
- Social publishing integrations
- Distributed multi-node processing
- Full DAM replacement workflows

---

# 3. Actors

## 3.1 Primary User

Can upload items, review metadata, approve/correct results, and export outputs.

## 3.2 Maintainer

Can configure and operate deployments, inspect logs/metrics, and maintain services.

## 3.3 Development Assistant (Codex/OpenClaw)

Can assist code/docs/tests in development zone only.

Must not access production archive data or deploy without human approval.

---

# 4. Core Principles

1. Raw uploads are immutable.
2. Canonical metadata is the source of truth.
3. Exports are derived from canonical metadata.
4. All non-secret behavior should be parameterized in configuration.
5. Secrets must be injected via environment or secret files.

---

# 5. Functional Requirements

## 5.1 Upload and Job Creation

`FR-001` The system shall accept required `subject_image`, optional `back_image`, and optional `context_images[]`.

`FR-002` Accepted file formats shall be configurable via `allowed_image_formats`.

`FR-003` Minimum resolution threshold shall be configurable via `min_longest_side_px`.

`FR-004` Every accepted upload shall create a unique `job_id` and stable `item_id`.

`FR-005` Raw files shall be stored unchanged under `storage/jobs/<job_id>/inputs/`.

`FR-006` Input checksums (SHA-256) shall be stored in canonical metadata.

## 5.2 Validation and CV Processing

`FR-010` Validation shall evaluate blur, glare, perspective distortion, edge clipping, and multi-photo detection.

`FR-011` Validation thresholds shall be configurable (not hard-coded).

`FR-012` On validation failure, status shall become `validation_failed` with machine-readable reasons.

`FR-013` CV worker shall produce subject-image derivatives: boundary mask (optional), cropped image, rectified image, orientation-normalized image.

`FR-014` Output formats and quality settings shall be configurable.

## 5.3 OCR Processing

`FR-020` OCR shall run on back image and each context image.

`FR-021` OCR engine configuration (language packs, dpi hints, pre-processing toggles) shall be parameterized.

`FR-022` OCR output shall include raw text, confidence summary, and source reference.

`FR-023` OCR artifacts shall be retained even if downstream metadata parsing fails.

## 5.4 Metadata Interpretation

`FR-030` Metadata worker shall generate canonical `photo_item.json` conforming to `docs/metadata-schema.md`.

`FR-031` Every interpreted field shall include confidence and provenance sources.

`FR-032` Interpretation policy (thresholds, enabled heuristics, provider usage) shall be configurable.

`FR-033` If AI interpretation is enabled, only `llm-gateway` may perform external calls.

`FR-034` Metadata worker shall produce explicit `review.required` and `review.reasons[]` values.

## 5.5 Review Workflow

`FR-040` Web UI shall present proposed metadata with evidence and confidence.

`FR-041` User shall be able to approve or edit metadata fields.

`FR-042` Review actions shall be auditable with actor, timestamp, changed fields, and optional note.

`FR-043` Review-required policy shall be configuration-driven.

## 5.6 Export

`FR-050` Export worker shall generate files under `storage/jobs/<job_id>/exports/`.

`FR-051` Export worker shall map canonical metadata to EXIF/IPTC/XMP according to configurable mapping rules.

`FR-052` Export shall include sidecar JSON containing canonical metadata snapshot and export metadata.

`FR-053` Export shall never mutate raw inputs.

## 5.7 Job State Model

`FR-060` Jobs shall use the following statuses only:

```text
uploaded
validation_failed
queued
processing
review_required
completed
failed
```

`FR-061` State transitions shall be validated to prevent illegal jumps.

`FR-062` State transition policy shall be centrally defined and test-covered.

## 5.8 Observability

`FR-070` Each service shall emit structured logs containing at minimum: `timestamp`, `service`, `job_id` (if applicable), `severity`, `event_type`, `message`.

`FR-071` Metrics shall include upload count, queue depth, per-step duration, failure count, and review-required rate.

`FR-072` Per-job debug bundle generation shall be supported via scriptable command.
`FR-073` Web service shall expose an operator monitoring view containing service status, application status, process counts, LLM usage since session start, and system load.
`FR-074` System shall maintain a central append-only runtime journal file for debugging actions across web and queue/pipeline operations.
`FR-075` Web interface shall support approving review-required jobs without using CLI commands.
`FR-076` CV stage shall crop and resize subject-image content into derived output artifacts.
`FR-077` OCR stage shall execute OCR on back/context images and persist extracted text artifacts.
`FR-078` Export stage shall include inferred historical date/location/context fields in export metadata mapping and file metadata where supported.
`FR-079` Web service shall be configurable to bind to local-network interfaces for mobile device access.
`FR-080` Web upload form shall support direct camera capture on capable mobile devices.
`FR-081` State/detail views from dashboard interactions should be rendered in-page (modal/popup) instead of forcing raw JSON tabs.
`FR-082` Metadata extraction shall fuse OCR evidence from both back and context images; context-only evidence must still populate canonical metadata.
`FR-083` OCR pipeline shall support handwriting-oriented preprocessing and multi-pass OCR strategy, configurable by profile.

---

# 6. Configuration and Parameterization Requirements

## 6.1 Configuration Sources

`CFG-001` Non-secret runtime behavior shall be defined in version-controlled config files under:

- `deploy/configs/dev/`
- `deploy/configs/rpi/`

`CFG-002` Environment-specific overrides shall be supported.

`CFG-003` Secrets shall never be committed and must be injected via environment variables or mounted secret files.

## 6.2 Mandatory Parameterized Domains

`CFG-010` Storage paths and retention
`CFG-011` Queue behavior (retry counts, backoff, concurrency)
`CFG-012` CV thresholds
`CFG-013` OCR configuration
`CFG-014` Review thresholds and rules
`CFG-015` LLM gateway policy and provider settings
`CFG-016` Export mapping and output presets
`CFG-017` Logging level and sampling
`CFG-018` Feature flags (e.g., enable/disable external AI)

## 6.3 Configuration Validation

`CFG-020` Startup shall fail fast on invalid config with clear diagnostics.

`CFG-021` Config schema shall be versioned and validated in CI.

---

# 7. Security and Privacy Requirements

`SEC-001` Development zone must not mount production archive storage.

`SEC-002` Only `llm-gateway` may have outbound connectivity to model providers.

`SEC-003` Raw archive artifacts must remain local unless explicitly exported by user action.

`SEC-004` Access to secrets must follow least privilege per service.

`SEC-005` Logs must avoid secret leakage and should redact sensitive data.

---

# 8. Non-Functional Requirements

`NFR-001` Local-first operation without inbound internet requirement.

`NFR-002` Reproducibility via recorded pipeline/tool/config versions per job.

`NFR-003` Service modularity with replaceable implementations behind stable contracts.

`NFR-004` Deployability on both development workstation and Raspberry Pi with configuration changes only.

`NFR-005` Testability of each service independently and as integrated pipeline.

---

# 9. Acceptance Criteria (PoC)

PoC is acceptable when all criteria below pass:

1. Upload stores immutable raw files with checksums.
2. CV processing produces rectified front artifact or explicit validation failure.
3. OCR artifacts are generated for back/context images.
4. Canonical metadata validates against documented schema.
5. Review UI supports approve/edit with audit trail.
6. Export artifacts include embedded metadata and sidecar JSON.
7. Structured logs and key metrics are observable.
8. Pipeline runs in containers on dev and Raspberry Pi targets.
9. Configuration changes adjust behavior without code edits for supported knobs.

---

# 10. Traceability to Other Documents

- Architecture: `docs/architecture.md`
- Metadata schema: `docs/metadata-schema.md`
- Trust zones and policy: `docs/trust-boundaries.md`
- Verification: `docs/test-strategy.md`
- ADRs: `docs/adr/`

---

# 11. PoC Implementation Notes

The current implementation profile intentionally prioritizes deterministic behavior:

- default upload format in config is `png` (format list is configurable)
- OCR/CV/LLM behavior is implemented with deterministic local surrogates
- service and metadata contracts are stable so production engines can be swapped in later

These notes are captured in ADR `docs/adr/0002-poc-runtime-stack.md`.
