# Caipture - Architecture Specification

Version: 0.2
Status: Draft
Applies to: PoC implementation baseline

---

# 1. Purpose

This document defines the architecture used to implement the requirements in `docs/requirements.md`.

The architecture must ensure:

- immutable raw evidence
- modular service boundaries
- reproducible processing
- constrained trust boundaries
- configuration-driven behavior
- canonical metadata consistency with `docs/metadata-schema.md`

---

# 2. Architectural Constraints

1. Canonical metadata file is `storage/jobs/<job_id>/metadata/photo_item.json`.
2. Only `llm-gateway` may access external AI providers.
3. Raw input artifacts under `inputs/` are immutable after upload.
4. Services exchange references and structured payloads, not large binaries over internal API.
5. Runtime behavior must be controlled by configuration wherever practical.

---

# 3. Logical Components

## 3.1 `services/web`

Responsibilities:

- upload ingestion
- job creation
- review UI/API
- status and metrics API
- export trigger/download
- operator dashboard (including queue approval actions and journal visibility)
- LAN/mobile-friendly hosting (local network bind support)

Must not:

- run heavy CV/OCR/metadata/export processing inline
- call external AI providers directly

## 3.2 `services/worker-cv`

Responsibilities:

- quality validation
- boundary-aware trim/crop
- resize/normalize output image
- artifact emission and event updates

## 3.3 `services/worker-ocr`

Responsibilities:

- OCR on back/context images
- confidence extraction
- artifact emission and event updates
- multi-pass OCR strategy with optional preprocessing for handwriting robustness

## 3.4 `services/worker-metadata`

Responsibilities:

- evidence aggregation
- normalization and interpretation
- optional call to `llm-gateway`
- canonical metadata generation
- schema validation
- review requirement decision
- explicit fusion of OCR evidence from back and all context images

## 3.5 `services/worker-export`

Responsibilities:

- load reviewed canonical metadata
- map internal fields to EXIF/IPTC/XMP
- write final export artifacts and sidecars

## 3.6 `services/llm-gateway`

Responsibilities:

- provider abstraction
- egress policy enforcement
- payload sanitization
- request/response telemetry

## 3.7 Operational Backing Services

- Queue implementation (replaceable)
- Operational database (job states, review actions, metrics snapshots)
- Shared storage rooted at `storage/`

---

# 4. Runtime Zones

Architecture enforces zones defined in `docs/trust-boundaries.md`:

- Development Zone
- Runtime Orchestration Zone
- Archive Data Zone
- External AI Zone

Network and mount policy must enforce these boundaries.

---

# 5. Canonical Data Flow

## 5.1 Upload

1. Web validates request and config constraints, including configured raw image formats such as PNG and JPEG.
2. Web assigns `job_id` and `item_id`.
3. Raw files are written unchanged to `storage/jobs/<job_id>/inputs/`, preserving original suffix/format.
4. Job state set to `uploaded` then `queued`.

## 5.2 CV Stage

1. CV worker consumes queued job.
2. Runs validation checks and subject-image transforms.
3. On validation failure: state `validation_failed`.
4. On success: writes derived artifacts, emits events.

## 5.3 OCR Stage

1. OCR worker processes `back_image` and each `context_image`.
2. Writes OCR artifacts and confidence summaries.
3. Emits events for downstream metadata stage.

## 5.4 Metadata Stage

1. Metadata worker aggregates all evidence.
2. Applies deterministic rules and optional AI assistance.
3. Writes canonical metadata JSON.
4. Validates against schema rules.
5. Sets state to `review_required` or `completed` depending on policy.

## 5.5 Review and Export

1. Reviewer inspects evidence/proposed fields.
2. Reviewer approves and/or edits.
3. Export worker maps canonical fields and writes export artifacts.
4. Job state becomes `completed` on success.

---

# 6. Storage Architecture

## 6.1 Required Layout

```text
storage/
  jobs/
    <job_id>/
      inputs/
      derived/
      metadata/
      logs/
      exports/
  uploads/
  exports/
  logs/
```

Notes:

- `jobs/<job_id>/...` is authoritative for per-item processing history.
- top-level `storage/uploads`, `storage/exports`, `storage/logs` can be used by deployment/runtime tooling but must not replace job-scoped evidence.

## 6.2 Immutability Rules

- `inputs/*` immutable after initial write
- derived artifacts append-only per processing attempt (new file names or versioned suffixes)
- canonical metadata updates must remain auditable (revision or event trail)

---

# 7. Service Interface Contracts

## 7.1 Job Event Contract (logical)

Minimum fields:

```json
{
  "job_id": "job_...",
  "item_id": "item_...",
  "stage": "upload|cv|ocr|metadata|review|export",
  "event": "started|succeeded|failed",
  "timestamp": "ISO-8601",
  "details": {}
}
```

## 7.2 State Transition Contract

Allowed statuses:

```text
uploaded
validation_failed
queued
processing
review_required
completed
failed
```

Implementations must enforce legal transitions only (configured transition map).

## 7.3 Artifact Reference Contract

Artifact references in metadata/events must be relative paths rooted at `storage/jobs/<job_id>/`.

---

# 8. Configuration Model

## 8.1 File Locations

Configuration files are environment-specific and version-controlled:

- `deploy/configs/dev/`
- `deploy/configs/rpi/`

## 8.2 Configuration Categories

- storage paths
- queue/retry policy
- CV thresholds
- OCR settings
- metadata interpretation policy
- review thresholds
- LLM gateway policy
- export mapping presets
- logging and metrics settings
- feature flags

## 8.3 Precedence

1. compiled defaults
2. config file
3. environment overrides
4. runtime secret injection

---

# 9. Failure Handling

## 9.1 Principles

- fail explicitly with machine-readable error codes
- preserve evidence and partial artifacts
- isolate failure to job scope
- support safe retries for retryable classes

## 9.2 Retry Categories

Retryable examples:

- transient provider timeout
- temporary file lock/contention
- temporary queue or DB unavailability

Non-retryable examples:

- unsupported file type
- irrecoverable image corruption
- schema-invalid canonical metadata after max attempts

---

# 10. Observability Architecture

## 10.1 Logs

Each service emits structured logs with:

- `timestamp`
- `service`
- `severity`
- `job_id` (if applicable)
- `event_type`
- `message`
- `context` object

## 10.2 Metrics

Required metrics:

- jobs uploaded/completed/failed
- queue depth
- per-stage duration
- OCR confidence distribution summary
- review-required rate
- export success/failure count

## 10.3 Health Endpoints

Each service should expose health endpoints for liveness/readiness.

Web service should also expose a monitoring dashboard/API aggregating service health, application status, queue/process counts, LLM usage counters, and system load.
For debugging, runtime actions should be appended to a central journal file (for example `storage/runtime/journal.jsonl`).
Dashboard detail views should be consumable in-page (for example modal/popup JSON views) rather than requiring navigation to raw JSON tabs.

---

# 11. Deployment Architecture

## 11.1 Development

- local Podman compose deployment
- synthetic fixtures only by default

## 11.2 Raspberry Pi Target

- same logical service topology
- ARM-compatible images
- systemd-managed Podman units preferred

## 11.3 Environment Parity

Differences between dev and rpi must be configuration-only.

---

# 12. Implementation Guidance

1. Define shared config schema first.
2. Implement canonical metadata validator as shared package/module.
3. Keep workers idempotent using job+stage execution guards.
4. Build contract tests around event/state/artifact contracts before scaling features.
5. Treat `docs/metadata-schema.md` as normative for metadata structure.
6. CV/OCR adapter implementations may be tool-backed (for example ImageMagick and Tesseract CLI), but must preserve service contracts.

---

# 13. Open Decisions (Implementation, Not Architecture)

- concrete queue technology
- concrete DB engine beyond PoC defaults
- exact OCR engine packaging strategy
- exact review UX details

These decisions must not violate the constraints and interfaces documented above.

Current PoC implementation choices are documented in ADR `docs/adr/0002-poc-runtime-stack.md`.
