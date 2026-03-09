# architecture.md


# Caipture — Architecture Specification

Version: 0.1  
Status: Draft  
Applies to: Proof of Concept (PoC) baseline

---

# 1. Purpose

This document defines the target architecture of Caipture.

The architecture is intended to support:

- local-first historical photo digitization
- modular processing services
- reproducible and testable pipelines
- privacy-preserving operation
- AI-assisted metadata extraction with controlled trust boundaries
- deployment on both development hardware and Raspberry Pi

This document is consistent with:

- `docs/requirements.md`
- `docs/metadata-schema.md`

The architecture must ensure that every processed item results in a metadata document conforming to the canonical internal schema defined in `metadata-schema.md`.

---

# 2. Architectural Goals

The architecture shall satisfy the following goals:

1. **Preserve raw evidence**
   - Raw uploaded images must remain unchanged.
2. **Use modular services**
   - Processing responsibilities must be isolated.
3. **Support reproducibility**
   - Pipeline versions, tool versions, and job artifacts must be recorded.
4. **Enable verification**
   - Every service must be testable independently.
5. **Enforce trust boundaries**
   - Development tooling must be isolated from archive data.
6. **Limit external exposure**
   - Only one controlled gateway may access external AI services.
7. **Support local-first deployment**
   - Public internet exposure must not be required.
8. **Allow human review**
   - Automated output must be reviewable and correctable before final export.

---

# 3. System Context

Caipture is a self-hosted system that processes uploaded images of:

- photo fronts
- photo backs
- album pages or other contextual sources

The system produces:

- corrected image derivatives
- OCR artifacts
- structured metadata
- final export assets

The system is composed of multiple containerized services coordinated through a queue and a shared storage structure.

---

# 4. High-Level Architecture

## 4.1 Main Components

The baseline PoC architecture contains the following logical components:

1. **Web Service**
   - user interface
   - upload endpoint
   - review interface
   - metrics dashboard
   - export endpoint

2. **Job Queue**
   - manages asynchronous processing
   - decouples upload from processing

3. **CV Worker**
   - image quality validation
   - boundary detection
   - crop and perspective rectification
   - orientation normalization

4. **OCR Worker**
   - OCR processing for back/context images
   - raw text extraction
   - OCR confidence capture

5. **Metadata Worker**
   - transforms OCR/context evidence into canonical metadata
   - invokes AI gateway where needed
   - produces `photo_item.json`

6. **Export Worker**
   - maps canonical metadata to EXIF/IPTC/XMP
   - creates export artifacts
   - preserves sidecar JSON

7. **LLM Gateway**
   - single approved egress point for external AI calls
   - prompt sanitization
   - outbound request control
   - model/provider abstraction

8. **Storage Layer**
   - raw inputs
   - derived artifacts
   - metadata files
   - logs
   - exports

9. **Operational Database**
   - stores job states
   - review state
   - metrics/event summaries
   - user actions

10. **Observability Layer**
    - structured logs
    - per-job events
    - service health information
    - system metrics

---

## 4.2 High-Level Flow

```text
User
  │
  ▼
Web Service
  │
  ├── store raw input files
  ├── create job record
  └── enqueue job
          │
          ▼
      CV Worker
          │
          ├── quality validation
          ├── crop / rectify front
          └── emit artifacts
          │
          ▼
      OCR Worker
          │
          ├── OCR back/context
          └── emit OCR artifacts
          │
          ▼
    Metadata Worker
          │
          ├── parse OCR/context evidence
          ├── optionally call LLM Gateway
          └── write canonical metadata
          │
          ▼
      Review Stage
          │
          ├── user validation/correction
          └── approval state
          │
          ▼
      Export Worker
          │
          ├── map canonical metadata
          ├── embed EXIF/IPTC/XMP
          └── write final exports
```

---

# 5. Trust Boundaries

The architecture shall enforce the trust boundaries defined below.

## 5.1 Zone A — Development Zone

Contains:

* source code repository
* design documents
* CI pipelines
* static analysis
* tests
* OpenClaw / Codex development workflows

Restrictions:

* must not access production archive data
* must not mount production storage
* may only use synthetic or explicitly approved fixture data

Purpose:

* code authoring
* verification
* PR generation
* controlled maintenance workflow

---

## 5.2 Zone B — Production Orchestration Zone

Contains:

* deployed services
* queue orchestration
* runtime configs
* operational DB
* container supervision

Restrictions:

* no direct code-authoring responsibilities
* limited secret exposure
* only approved services may read/write archive paths

Purpose:

* execute deployed pipeline
* manage runtime operations
* track job state

---

## 5.3 Zone C — Archive Processing Zone

Contains:

* raw uploaded images
* derived images
* OCR artifacts
* metadata documents
* export assets

Restrictions:

* must not be directly accessible by development assistants
* must not be publicly exposed
* access only by processing services requiring it

Purpose:

* preserve operational evidence and outputs

---

## 5.4 Zone D — External AI Zone

Contains:

* outbound AI requests
* model-provider interaction
* prompt/response exchange

Restrictions:

* only the `llm-gateway` service may reach this zone
* full raw archive content should not be sent unless explicitly enabled
* outbound destinations must be allowlisted

Purpose:

* constrained AI-assisted interpretation

---

# 6. Deployment Model

## 6.1 Target Environments

The architecture must support:

1. **Development environment**

   * macOS or Linux workstation
   * local containers
   * representative functionality
   * synthetic or approved test data

2. **Target environment**

   * Raspberry Pi (Linux ARM)
   * local-only hosting
   * same logical services with environment-specific configuration

The architecture must use the same service model in both environments.

Differences between environments must be handled through configuration, not separate implementations.

---

## 6.2 Hosting Model

Recommended default deployment model:

* Web UI hosted locally
* No public internet exposure required
* Remote access via LAN or VPN
* Outbound-only network access for AI gateway, package installation, and optional update flows

The pipeline must remain functional without inbound internet accessibility.

---

## 6.3 Container Runtime

Preferred runtime:

* Podman

Requirements:

* reproducible container builds
* service-level isolation
* environment-based configuration
* compatibility with ARM deployment target

Container supervision on Raspberry Pi should preferably be handled by:

* systemd + Podman-generated units

---

# 7. Service Architecture

## 7.1 Web Service

### Responsibilities

* handle uploads
* validate request structure
* create jobs
* expose job status
* provide review UI
* provide metrics/dashboard UI
* provide export/download access

### Inputs

* front image
* back image
* optional context images
* review actions
* export requests

### Outputs

* job record creation
* queue events
* review state updates
* export download streams

### Constraints

* must not perform heavy processing inline
* must return quickly after job creation
* must not directly call external AI providers

---

## 7.2 Job Queue

### Responsibilities

* manage asynchronous work
* maintain retry-safe task delivery
* decouple ingest from processing
* support per-step status updates

### Requirements

* jobs must be idempotent where possible
* retries must not overwrite raw evidence
* queue state must be observable

### PoC Note

For the PoC, the queue may be implemented using a simple database-backed or in-memory-backed mechanism, provided the interfaces remain replaceable.

---

## 7.3 CV Worker

### Responsibilities

* perform early image quality validation
* detect photo boundaries
* crop image
* rectify perspective
* normalize orientation
* write derived front-image artifacts

### Inputs

* raw front image

### Outputs

* validation report
* cropped image
* rectified image
* processing metrics
* step logs

### Failure Cases

* boundary not detected
* low image quality
* excessive glare
* unsupported framing
* image corrupt/unreadable

### Requirements

* raw input must remain unchanged
* output paths must be recorded in metadata/artifacts
* failures must be traceable per job

---

## 7.4 OCR Worker

### Responsibilities

* run OCR on back image
* run OCR on context images
* preserve raw OCR output
* record OCR confidence and provenance

### Inputs

* raw back image
* raw context images

### Outputs

* OCR text files
* OCR confidence summaries
* step logs

### Requirements

* OCR output must remain available even if later parsing fails
* OCR source linkage must be preserved

---

## 7.5 Metadata Worker

### Responsibilities

* collect evidence from OCR and derived artifacts
* parse contextual text into canonical schema
* perform normalization
* optionally invoke AI gateway for ambiguous interpretation
* write `photo_item.json`
* determine review requirement state

### Inputs

* OCR artifacts
* derived artifact references
* job metadata
* optional AI model responses

### Outputs

* canonical metadata document conforming to `metadata-schema.md`
* review reasons
* validation results
* step logs

### Important Constraint

This service owns the creation of:

```text
storage/jobs/<job_id>/metadata/photo_item.json
```

That file is the canonical metadata record for the item.

### Field-Level Responsibilities

The metadata worker must populate at minimum:

* top-level identifiers
* input references
* derived references
* `historical_metadata`
* `digitization_metadata`
* `review`
* optionally `export_mapping`

If some historical fields are unavailable, they must be represented as absent or null in a schema-valid manner rather than fabricated.

---

## 7.6 Export Worker

### Responsibilities

* read canonical metadata
* map metadata to EXIF/IPTC/XMP
* produce export image(s)
* generate sidecar metadata files
* preserve export traceability

### Inputs

* canonical metadata
* approved/corrected review state
* rectified image artifact

### Outputs

* final export image(s)
* sidecar JSON
* optional XMP sidecar
* export logs

### Requirements

* export must not modify raw input files
* export mappings must be traceable back to canonical metadata
* all exported fields must be explainable through evidence or user review history

---

## 7.7 LLM Gateway

### Responsibilities

* abstract model providers
* sanitize outbound requests
* log AI interaction metadata
* enforce network egress policy
* prevent direct model access by other services

### Inputs

* structured requests from metadata worker

### Outputs

* structured model responses
* request/response logs
* provider metrics

### Constraints

* must be the only service with outbound AI connectivity
* should avoid sending full raw images unless explicitly enabled
* should prefer sending OCR text and limited context
* must not expose provider credentials to other services

---

## 7.8 Operational Database

### Responsibilities

* store job status
* store event summaries
* store review state
* store user actions
* support dashboard queries

### Example Entities

* jobs
* job_events
* reviews
* exports
* service_health
* metrics_snapshots

### Constraints

* DB is not the canonical storage for raw artifacts
* DB stores references, not heavy binaries

---

## 7.9 Storage Layer

### Responsibilities

* preserve raw files
* preserve derived artifacts
* preserve metadata files
* preserve per-job logs
* preserve export assets

### Storage Principles

* immutable raw inputs
* job-scoped organization
* explicit artifact references
* stable relative paths

Recommended structure:

```text
storage/
  jobs/
    <job_id>/
      inputs/
      derived/
      metadata/
      logs/
      exports/
```

---

# 8. Canonical Data Flow

## 8.1 Job Creation

When a user uploads files:

1. Web service generates `job_id`
2. Raw files are stored in:

   * `storage/jobs/<job_id>/inputs/`
3. Job record is inserted into operational DB
4. Initial status is set:

   * `uploaded`
5. Job is queued

---

## 8.2 Validation and Front Processing

The CV worker:

1. loads `inputs/front.*`
2. computes quality checks
3. either:

   * marks job `validation_failed`, or
   * produces crop/rectification artifacts
4. writes artifacts to:

   * `storage/jobs/<job_id>/derived/`
5. emits job events

---

## 8.3 OCR Processing

The OCR worker:

1. loads `inputs/back.*` and `inputs/context_*`
2. runs OCR
3. writes text artifacts into `derived/`
4. emits confidence/event records

---

## 8.4 Metadata Generation

The metadata worker:

1. collects all available evidence
2. parses OCR content
3. optionally calls `llm-gateway`
4. produces canonical metadata
5. validates metadata schema compliance
6. determines review requirement
7. writes:

```text
storage/jobs/<job_id>/metadata/photo_item.json
```

---

## 8.5 Review and Approval

The review UI:

1. reads canonical metadata
2. presents editable fields
3. shows evidence and confidence
4. stores review actions
5. updates approval state

The system should never hide uncertainty from the reviewer.

---

## 8.6 Export

The export worker:

1. loads reviewed metadata
2. loads corrected front image
3. maps canonical fields to output formats
4. writes exports to:

   * `storage/jobs/<job_id>/exports/`
5. updates job status to:

   * `completed`

---

# 9. Consistency with `metadata-schema.md`

The architecture must enforce the following schema-related guarantees.

## 9.1 Canonical Ownership

The canonical metadata file is:

```text
storage/jobs/<job_id>/metadata/photo_item.json
```

No other service may define an alternative canonical metadata format.

---

## 9.2 Evidence Preservation

The architecture must ensure the schema fields can be backed by stored evidence:

* `inputs` ↔ raw uploaded files
* `derived` ↔ generated artifacts
* `historical_metadata.*.sources` ↔ OCR/model/manual provenance
* `review` ↔ approval actions stored by web service/DB
* `digitization_metadata` ↔ runtime/job context

---

## 9.3 Historical Uncertainty

Because the metadata schema supports date ranges, confidence, and provenance, the architecture must preserve all upstream evidence required to justify those fields.

This means:

* raw OCR text must be retained
* context image references must be retained
* model outputs used for interpretation must be retained or summarized reproducibly
* manual corrections must be auditable

---

## 9.4 Export is Derived, Not Canonical

EXIF/IPTC/XMP values are derived outputs.

The export worker must not become the source of truth for historical metadata.

The source of truth remains the canonical metadata document.

---

# 10. Review Model

## 10.1 Human Review Philosophy

The architecture assumes that automated extraction may be useful but not fully reliable.

Human review is mandatory when:

* field confidence is below configured threshold
* date precision is coarse or ambiguous
* multiple interpretations conflict
* OCR quality is poor
* validation warnings exist

---

## 10.2 Review UI Requirements

The review interface should display:

* front corrected image
* raw back/context images
* OCR text
* proposed structured metadata
* field confidence
* provenance per field
* reasons for review requirement

Users must be able to:

* approve
* edit
* reject
* defer

---

## 10.3 Auditability

Review actions must record:

* reviewer identity
* timestamp
* changed fields
* before/after values
* optional comment

---

# 11. Observability Architecture

## 11.1 Structured Logging

Every service must emit structured logs including:

* timestamp
* service name
* job_id
* severity
* event type
* message
* optional artifact reference

Logs should be machine-readable.

---

## 11.2 Metrics

The system shall expose metrics including:

* jobs uploaded
* jobs queued
* jobs failed
* jobs completed
* step durations
* OCR success rate
* AI request count
* review-required rate

Metrics may initially be computed from DB/event tables and later extended with a dedicated metrics backend.

---

## 11.3 Per-Job Debug Bundles

The architecture should support generation of a job-level debug bundle containing only one item’s relevant evidence:

* selected input files
* derived artifacts
* OCR outputs
* canonical metadata
* relevant logs
* model interaction traces where appropriate

This enables debugging without exposing the whole archive.

---

# 12. Verification Architecture

## 12.1 Static Verification

The repository should include automated static checks such as:

* formatting/linting
* type checking
* dead/unused code checks
* dependency audit
* secret scanning
* container scanning

These checks operate in the Development Zone.

---

## 12.2 Dynamic Service Verification

Each service must support standalone tests covering:

* input handling
* output contracts
* failure behavior
* health checks

Examples:

* CV worker fixture tests
* OCR worker fixture tests
* metadata worker schema validation tests
* export worker output validation tests

---

## 12.3 Integration Verification

The full stack must support integration testing in two configurations:

1. **dev-localhost**
2. **target-rpi**

Both must use the same logical services, with environment-specific configs.

Smoke tests should verify:

* upload succeeds
* queue advances
* crop exists
* OCR exists
* metadata validates
* review path works
* export exists

---

## 12.4 Policy Verification

Security assumptions should also be testable.

Examples:

* only `llm-gateway` has outbound network access
* development assistants cannot mount production archive paths
* services only receive required secrets
* raw inputs are immutable after upload

---

# 13. AI and Automation Strategy

## 13.1 Use of AI in Runtime Pipeline

AI usage should be narrow and justified.

Preferred order:

1. deterministic computer vision
2. OCR extraction
3. rule-based normalization
4. AI-assisted interpretation only where needed

This reduces cost, latency, and privacy risk.

---

## 13.2 Use of OpenClaw / Codex in Development

Development assistants may be used for:

* writing code
* maintaining docs
* proposing tests
* generating PRs
* triaging issues from chat channels

They must not:

* directly access production archive storage
* deploy unreviewed code to production
* bypass CI or human approval

Recommended development workflow:

```text
Issue / Request
   ↓
Assistant proposes change
   ↓
PR created
   ↓
Static checks + tests
   ↓
Human review
   ↓
Merge
   ↓
Deploy
```

---

# 14. Configuration Model

The architecture must support environment-based configuration.

Configuration categories include:

* storage paths
* service endpoints
* queue settings
* model provider settings
* feature flags
* review thresholds
* export settings
* logging verbosity

Recommended configuration separation:

* shared defaults
* environment-specific overrides
* secrets via environment variables or mounted secret files

---

# 15. Failure Handling

## 15.1 Failure Principles

Failures must be:

* explicit
* logged
* recoverable where possible
* isolated per job

A single failed job must not block the whole pipeline.

---

## 15.2 Failure States

Typical failure points:

* invalid upload
* CV boundary detection failure
* OCR extraction failure
* AI timeout/provider failure
* schema validation failure
* export mapping failure

The system must record which step failed and preserve intermediate evidence.

---

## 15.3 Retry Policy

Retryable failures may include:

* temporary AI provider errors
* transient queue errors
* temporary file access issues

Non-retryable failures may include:

* corrupt image input
* unsupported format
* invalid review state

Retries must not duplicate canonical outputs incorrectly.

---

# 16. PoC Boundaries

The following architectural choices are part of the PoC scope:

## Included

* local web app
* asynchronous queue
* CV processing
* OCR processing
* metadata generation
* review flow
* export flow
* logging
* metrics
* containerized deployment
* local dev + Raspberry Pi target configs

## Excluded from initial PoC

* public multi-tenant deployment
* advanced face recognition
* automatic person identity linking
* collection-scale deduplication
* large-scale distributed processing
* autonomous deployment by OpenClaw

---

# 17. Recommended Initial Technology Choices

The following stack is recommended for the PoC:

* **Python** for backend and workers
* **FastAPI** for API/web backend
* **Jinja templates** or lightweight frontend initially
* **OpenCV** for image processing
* **Tesseract OCR** or equivalent for OCR
* **ExifTool** for metadata writing
* **SQLite** for PoC operational DB
* **Podman** for containers
* **systemd** for Pi supervision
* **pytest** for testing

This stack may evolve, but the service contracts and trust boundaries should remain stable.

---

# 18. Architecture Decision Records

Important architectural decisions should be recorded as ADRs in:

```text
docs/adr/
```

Recommended initial ADR topics:

1. monorepo structure
2. canonical metadata schema ownership
3. single AI egress gateway
4. local-only hosting by default
5. review-required workflow
6. Podman as default container runtime

---

# 19. Open Questions

The following items may require later refinement:

* exact queue technology
* exact OCR engine choice
* exact DB schema
* exact review thresholds
* model provider strategy
* whether vision models are enabled in PoC or deferred

These are implementation choices, not reasons to alter the architecture boundaries.

---

# 20. Summary

Caipture uses a modular, local-first, containerized architecture built around:

* immutable raw evidence
* job-scoped processing artifacts
* a canonical metadata document
* constrained AI interaction
* human review
* testable service boundaries

The central architectural rule is:

**all services contribute evidence, but only the canonical metadata file defines the structured truth of an item.**

That canonical file must remain consistent with `docs/metadata-schema.md`.

```
One important improvement to make next is tightening `metadata-schema.md` itself: it is good structurally, but for implementation it should eventually define required vs optional fields, allowed enums, null-handling rules, and a JSON Schema or Pydantic model. That will make both testing and AI-generated code much more reliable.
```
