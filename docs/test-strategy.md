# Caipture - Test Strategy

Version: 0.1
Status: Draft

---

# 1. Purpose

This document defines the test strategy for verifying Caipture against requirements and trust-boundary policies.

The strategy is designed for:

- high confidence in pipeline correctness
- reproducibility across dev and Raspberry Pi targets
- protection against regressions in schema and security policy

---

# 2. Test Layers

## 2.1 Unit Tests (`tests/unit/`)

Scope:

- pure functions
- service-local validation logic
- schema validators
- mapping and parsing utilities

Expectations:

- no network calls
- no dependence on external services
- deterministic and fast

Examples:

- date normalization logic
- status transition validator
- export mapping formatter
- config schema parser

## 2.2 Integration Tests (`tests/integration/`)

Scope:

- interactions between services
- queue-driven workflow
- storage and artifact contracts
- operational DB interactions

Expectations:

- containerized services with test configuration
- controlled fixture datasets
- assertions on artifacts, states, and logs

Examples:

- upload -> queue -> cv -> ocr -> metadata
- upload acceptance for both PNG and JPEG mobile-origin files
- metadata worker + llm-gateway stub interaction
- review update persistence
- export generation with sidecar

## 2.3 Smoke Tests (`tests/smoke/`)

Scope:

- critical happy-path checks in target-like environments

Required environments:

1. dev-local
2. target-rpi profile

Assertions:

- stack starts
- upload endpoint reachable
- one fixture job fully processes
- export artifact exists

## 2.4 BDD Integration Tests (`tests/bdd/`)

Scope:

- behavior-driven end-to-end workflow verification using Gherkin feature files
- user-visible process semantics (upload, process, review, export, failure handling)

Execution:

- `python3 -m behave tests/bdd/features`

Additional integration assertions must verify OCR evidence fusion:

- context-only date/location/event extraction
- back/context source text persistence into canonical metadata
- per-context OCR artifact references (`context_ocr_###.txt`)
- web upload path accepts JPEG subject images without converting raw evidence in place

---

# 3. Test Data Strategy

## 3.1 Fixtures (`tests/fixtures/`)

Fixtures should be small and curated:

- front image samples
- back image handwriting/text samples
- context album page samples
- expected OCR snippets
- expected canonical metadata snapshots

No real sensitive archive images should be committed unless explicitly approved.

## 3.2 Golden Files

Use golden JSON files for canonical metadata expectations.

Rules:

- include schema version in fixture metadata
- update intentionally with changelog note
- avoid brittle assertions on non-deterministic fields (timestamps, run ids)

---

# 4. Requirement Coverage Matrix

Each requirement ID in `docs/requirements.md` must map to at least one automated test.

Minimum required mapping:

- `FR-001..006`: upload and raw storage tests
- `FR-010..014`: CV validation and artifact tests
- `FR-020..023`: OCR artifact and confidence tests
- `FR-030..034`: metadata schema/provenance/review-reason tests
- `FR-040..043`: review action and audit trail tests
- `FR-050..053`: export and immutability tests
- `FR-060..062`: status transition tests
- `FR-070..072`: logs/metrics/debug-bundle tests
- `CFG-*`: config validation and override precedence tests
- `SEC-*`: trust-boundary and secret-handling tests

---

# 5. Contract Tests

## 5.1 Metadata Contract

- validate every generated `photo_item.json` against schema rules
- reject invalid enum, confidence, and date-range combinations

## 5.2 State Transition Contract

- enforce legal transition map
- verify invalid transitions are rejected with explicit errors

## 5.3 Artifact Contract

- verify required artifacts exist per stage
- verify artifact paths are relative and job-scoped
- verify raw `inputs/` immutability

---

# 6. Security and Trust-Boundary Tests

Required policy tests:

1. Only `llm-gateway` can egress to configured model endpoints.
2. Development context cannot mount production archive path.
3. Secrets are absent from logs under failure and success paths.
4. Data minimization policy is applied for AI outbound requests.

These tests should run in integration suite with policy-enabled config.

---

# 7. Non-Functional Validation

## 7.1 Performance (PoC Baseline)

Define configurable SLO-like targets for representative fixture set:

- upload latency
- end-to-end processing time
- per-stage median duration

Targets are environment-profiled and must be versioned in config.

## 7.2 Reliability

- retry behavior for transient failures
- idempotency checks for re-queued jobs
- failure isolation (one job failure does not block queue)

## 7.3 Reproducibility

Given same fixtures and config version, canonical metadata should be stable for deterministic stages.

---

# 8. CI and Local Execution

## 8.1 Suggested Pipeline Order

1. lint/static checks
2. unit tests
3. contract tests
4. integration tests
5. smoke tests (profile-gated)

## 8.2 Exit Criteria

A change is merge-ready when:

- all mandatory stages pass
- requirement coverage is not reduced
- schema version compatibility checks pass

---

# 9. Tooling Guidance (PoC)

Expected baseline tools:

- `pytest` test runner
- coverage reporting
- static checks (ruff, mypy)
- containerized integration harness

Exact tooling may evolve, but contracts and coverage obligations remain.

---

# 10. Initial Test Cases

1. `upload_rejects_unsupported_format`
2. `upload_stores_raw_and_checksum`
3. `cv_validation_flags_glare`
4. `cv_generates_rectified_artifact`
5. `ocr_emits_text_and_confidence`
6. `metadata_contains_provenance_for_interpreted_fields`
7. `metadata_schema_validator_rejects_invalid_confidence`
8. `review_actions_are_auditable`
9. `export_writes_sidecar_and_embedded_metadata`
10. `raw_inputs_remain_immutable`
11. `only_llm_gateway_has_ai_egress`
12. `state_transition_rejects_illegal_jump`
