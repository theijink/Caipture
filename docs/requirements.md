# Caipture — Requirements Specification

Version: 0.1 (PoC baseline)
Status: Draft
Scope: Personal and small-collection historical photograph digitization pipeline

---

# 1. Purpose

Caipture is a self-hosted software system designed to convert physical photograph collections into structured digital archive assets.

The system processes images of photo prints and album pages, extracts contextual information (e.g., handwritten notes), and produces corrected images with structured metadata while preserving provenance and processing history.

The system prioritizes:

* reproducibility
* verifiable processing pipelines
* privacy-preserving local operation
* structured archival metadata
* modular architecture suitable for automation

This document defines the functional and non-functional requirements that constrain the project scope.

---

# 2. Project Scope

## 2.1 In Scope

The Caipture system shall provide:

1. Digitization workflow support for physical photographs
2. Automated processing of uploaded images
3. Extraction of contextual metadata from photo backs and album pages
4. AI-assisted interpretation of contextual text
5. Structured metadata generation
6. Human verification and correction
7. Export of archival images with embedded metadata
8. Containerized deployment
9. Reproducible processing pipelines
10. Local hosting with minimal external dependencies
11. Logging, metrics, and traceability

## 2.2 Out of Scope

The following features are explicitly out of scope for the PoC:

* Cloud-hosted SaaS deployment
* Mobile application development
* Automatic face recognition / identification
* Social media integration
* Automatic public sharing of archives
* Large institutional archive workflows
* Distributed multi-node processing clusters
* Full DAM (Digital Asset Management) replacement systems

---

# 3. System Goals

The system must support the following goals:

1. Digitize historical photographs reliably
2. Preserve contextual information
3. Maintain provenance and traceability
4. Enable partial automation without removing human oversight
5. Minimize risk of data exposure
6. Support reproducible research-like workflows
7. Allow iterative improvement of processing components

---

# 4. System Actors

### Primary User

Person digitizing and organizing the photograph archive.

Capabilities:

* upload photos
* review extracted metadata
* approve or correct results
* export processed images

### Developer / Maintainer

Capabilities:

* modify codebase
* maintain processing pipeline
* improve algorithms
* review automated pull requests

### AI Assistant (e.g., OpenClaw / Codex)

Capabilities:

* assist with code generation
* propose improvements
* open issues and pull requests

Restrictions:

* must not access production archive data
* cannot deploy code without human approval

---

# 5. Functional Requirements

## 5.1 Image Upload

The system shall allow uploading of:

* photo front image
* photo back image
* optional contextual images (album page, captions)

Requirements:

* images must be stored unchanged as raw input
* each upload creates a **job identifier**
* job metadata must be persisted

Supported formats:

* JPEG
* PNG
* TIFF

Minimum resolution requirement:

* 1500px on the longest side

---

## 5.2 Early Image Quality Validation

Before accepting a job into the processing queue, the system shall perform image quality checks.

The system should detect:

* blur
* glare / reflections
* excessive perspective distortion
* cropped edges
* low resolution
* multi-photo frames

If problems are detected the system shall:

* return warnings or rejection messages
* allow user to retry upload

---

## 5.3 Image Processing Pipeline

The system shall perform automated processing on the front image:

1. detect photograph boundary
2. crop the photograph
3. rectify perspective
4. normalize orientation
5. produce corrected output image

Outputs must be stored as derived artifacts.

The raw input image must remain unchanged.

---

## 5.4 OCR Processing

The system shall perform OCR on:

* photo back image
* contextual images (album pages)

Outputs must include:

* raw OCR text
* extracted confidence values
* reference to source image

OCR results must be stored as artifacts.

---

## 5.5 Metadata Interpretation

The system shall convert contextual text into structured metadata.

Interpretation may include:

* date estimation
* location normalization
* subject names
* description generation

AI models may be used for interpretation.

Outputs must include:

* structured metadata
* confidence values
* provenance (source evidence)

---

## 5.6 Metadata Review

The system shall allow users to review extracted metadata.

Users must be able to:

* edit fields
* correct interpretations
* approve results
* reject results

Approval status must be stored.

---

## 5.7 Metadata Export

The system shall embed metadata into exported images.

Supported formats:

* EXIF
* IPTC
* XMP

Additionally:

* metadata JSON sidecar must be produced.

---

## 5.8 Job Tracking

Each job must maintain:

* job identifier
* processing state
* timestamps
* artifact references

Processing states:

```
uploaded
validation_failed
queued
processing
review_required
completed
failed
```

---

## 5.9 Logging

The system shall generate structured logs for:

* job events
* processing steps
* errors

Logs must include:

* job_id
* service
* timestamp
* severity

---

## 5.10 Metrics

The system shall provide operational metrics including:

* number of uploads
* queue length
* success/failure rate
* processing duration
* system errors

Metrics must be visible in the web interface.

---

# 6. Non-Functional Requirements

## 6.1 Privacy

The system must prioritize privacy.

Requirements:

* raw images must remain local
* minimal contextual data may be sent to external AI models
* system must operate without public internet exposure

---

## 6.2 Reproducibility

Processing results must be reproducible.

Requirements:

* pipeline version recorded
* tool versions recorded
* deterministic processing where possible

---

## 6.3 Modularity

The system shall be composed of modular services.

Services may include:

* web interface
* CV worker
* OCR worker
* metadata worker
* export worker
* AI gateway

Each service must run independently.

---

## 6.4 Containerization

The system must support containerized deployment.

Preferred runtime:

* Podman

Containers must support:

* reproducible builds
* configuration via environment variables

---

## 6.5 Deployment Targets

Supported environments:

1. Development workstation (macOS / Linux)
2. Raspberry Pi deployment (Linux ARM)

Configuration differences must be handled via configuration files.

---

# 7. Trust Boundaries

The system must define clear trust zones.

### Development Zone

Contains:

* source code
* CI pipelines
* OpenClaw integration

### Processing Zone

Contains:

* pipeline services
* job orchestration

### Archive Zone

Contains:

* raw uploads
* processed images
* metadata artifacts

### AI Gateway

Contains:

* outbound model requests

Only the AI gateway may communicate with external model providers.

---

# 8. Security Requirements

1. No production archive access from development tooling.
2. No external network access except AI gateway.
3. Secrets must not be stored in repository.
4. Environment variables must be used for secrets.
5. Job-level debug bundles must be generated for issue investigation.

---

# 9. Verification Requirements

## 9.1 Static Code Checks

Static checks must detect:

* unused code
* security vulnerabilities
* dependency issues
* formatting errors

Tools may include:

* Ruff
* MyPy
* Bandit
* dependency scanners

---

## 9.2 Dynamic Unit Tests

Each service must provide unit tests covering:

* input validation
* processing logic
* interface contracts

---

## 9.3 Integration Tests

Integration tests must verify:

* service interaction
* pipeline execution
* artifact generation

---

## 9.4 Deployment Tests

Smoke tests must verify system behavior on:

1. local development environment
2. Raspberry Pi target environment

---

# 10. Observability

The system shall provide:

* job dashboards
* pipeline status
* error reports
* processing statistics

All jobs must be traceable.

---

# 11. Data Storage

Data must be organized by job identifier.

Example structure:

```
storage/
jobs/<job_id>/
inputs/
derived/
metadata/
logs/
```

Raw inputs must never be modified.

---

# 12. External Dependencies

Potential external components:

* OCR engines
* language models
* metadata tools

These must be isolated behind defined interfaces.

---

# 13. Documentation Requirements

The repository must contain documentation for:

* architecture
* metadata schema
* trust boundaries
* testing strategy

Documentation must be version controlled.

---

# 14. Future Extensions (Non-PoC)

Possible future features:

* duplicate photo detection
* clustering similar photos
* improved handwriting recognition
* timeline reconstruction
* improved metadata inference
* large archive scaling

These are outside the PoC scope.

---

# 15. Acceptance Criteria for PoC

The PoC is considered successful if:

1. photos can be uploaded
2. image cropping works automatically
3. OCR text extraction works
4. metadata JSON is generated
5. metadata review is possible
6. export image contains metadata
7. system runs in containers
8. pipeline works on development workstation
9. pipeline deploys on Raspberry Pi
10. logging and metrics are visible
