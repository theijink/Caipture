# Caipture - Trust Boundaries and Data Handling Policy

Version: 0.1
Status: Draft

---

# 1. Purpose

This document defines trust zones, allowed data flows, and controls for Caipture.

It is normative for architecture and deployment decisions.

---

# 2. Data Classification

## 2.1 Classes

- `PUBLIC_DOCS`: repository documentation and non-sensitive code metadata
- `DEV_INTERNAL`: development logs, test outputs, CI artifacts
- `ARCHIVE_SENSITIVE`: raw/derived photo artifacts, OCR text, canonical metadata, review notes
- `SECRET`: provider API keys, credentials, tokens

## 2.2 Handling Rules

- `ARCHIVE_SENSITIVE` must remain local unless explicit user export action is taken.
- `SECRET` must never be committed and must be redacted from logs.

---

# 3. Trust Zones

## 3.1 Zone A - Development Zone

Contains:

- source code
- docs
- tests and fixtures
- local dev tools and assistants

Allowed data:

- `PUBLIC_DOCS`
- `DEV_INTERNAL`
- synthetic fixtures

Forbidden:

- direct access to production `ARCHIVE_SENSITIVE` data
- runtime secrets for production services

## 3.2 Zone B - Runtime Orchestration Zone

Contains:

- deployed service containers
- queue runtime
- operational database
- service configuration runtime

Allowed data:

- `ARCHIVE_SENSITIVE` references and processing context
- service-level secrets required for operation

Restrictions:

- least-privilege secret access
- no code-authoring or CI operations

## 3.3 Zone C - Archive Data Zone

Contains:

- `storage/jobs/<job_id>/...`
- uploaded and derived artifacts
- canonical metadata and logs

Restrictions:

- not publicly exposed
- mounted read/write only by required services
- immutable-write rules for raw inputs

## 3.4 Zone D - External AI Zone

Contains:

- model provider APIs and remote inference endpoints

Restrictions:

- reachable only by `services/llm-gateway`
- outbound destinations allowlisted
- payload minimization required

---

# 4. Allowed Data Flows

## 4.1 Allowed Flows

1. Zone A -> Zone B: deploy artifacts/config manifests
2. Zone B <-> Zone C: processing services read/write job data
3. Zone B (`llm-gateway` only) -> Zone D: constrained AI requests
4. Zone B -> Zone A: operational metrics/log summaries without secret leakage

## 4.2 Disallowed Flows

1. Zone A -> Zone C direct production archive mounts
2. Any service except `llm-gateway` -> Zone D
3. Zone D -> Zone C direct writes
4. Secrets -> repository or plaintext logs

---

# 5. Enforcement Controls

## 5.1 Network Controls

- container network policy restricting egress by service
- only `llm-gateway` has outbound AI provider route

## 5.2 Filesystem Controls

- explicit volume mounts per service
- read-only mounts where feasible
- `inputs/` marked immutable by policy and tested by integration checks

## 5.3 Identity and Secrets

- per-service credentials
- secret distribution through environment or secret files
- periodic key rotation support

## 5.4 Logging and Redaction

- redact API keys/tokens and secret-like patterns
- avoid full sensitive payload logging for AI requests

---

# 6. AI Gateway Data Minimization Policy

`llm-gateway` must apply:

1. send OCR/context excerpts before raw images
2. include only fields required for inference request
3. enforce max payload size from configuration
4. annotate each outbound request with policy reason and correlation id

Optional full-image transfer must be feature-flagged and disabled by default.

---

# 7. Development Assistant Policy

Assistants in Zone A may:

- read/write repository files
- run tests on fixture data
- propose architecture/code updates

Assistants may not:

- access production archive mounts
- execute production deployments autonomously
- bypass review and CI gates

---

# 8. Incident and Audit Requirements

## 8.1 Security Events to Log

- denied network egress attempts
- denied volume mount attempts
- secret access failures
- schema/policy validation failures

## 8.2 Audit Artifacts

- deployment config snapshots
- service policy config versions
- job-level event trails

---

# 9. Verification Requirements

The controls in this document must be validated by tests in `docs/test-strategy.md`:

- policy test: only `llm-gateway` can egress to AI endpoints
- mount test: development context cannot mount production archive
- immutability test: raw input cannot be modified after ingest
- redaction test: logs do not emit configured secret patterns
