# ADR 0001 - Adopt Monorepo Structure

Date: 2026-03-09
Status: Accepted
Decision Makers: Project Maintainer

---

## Context

Caipture is built as multiple cooperating services:

- web
- worker-cv
- worker-ocr
- worker-metadata
- worker-export
- llm-gateway

The project also requires tightly coupled shared artifacts:

- requirements and architecture documents
- canonical metadata schema
- trust-boundary policy
- integration tests and fixtures
- deployment configurations for dev and Raspberry Pi

A repository strategy is required that supports coordinated evolution of these components and their contracts.

---

## Decision

Use a single monorepo containing all services, shared documentation, tests, and deployment assets.

Repository root structure includes:

- `services/` for service implementations
- `docs/` for normative design and policy documents
- `tests/` for unit/integration/smoke suites and fixtures
- `deploy/` for environment configurations and runtime assets
- `scripts/` for development/build/test automation

---

## Rationale

1. Contract changes are easier to keep consistent across services.
2. Shared schema/version changes can be atomically updated with workers and tests.
3. Integration tests can run against current service versions without cross-repo synchronization.
4. Trust-boundary and configuration policies remain visible and reviewable in one place.
5. PoC team size and deployment model favor simplicity over repo-level isolation.

---

## Alternatives Considered

### A. Polyrepo (one repo per service)

Pros:

- strong service autonomy
- independent release cycles

Cons:

- higher coordination overhead
- difficult atomic updates across schema/contracts/tests
- fragmented documentation and policy enforcement

### B. Hybrid (service repos + central infra/docs repo)

Pros:

- partial autonomy
- central policy location

Cons:

- dual-change workflows still complex
- increased tooling and synchronization burden for PoC stage

Monorepo chosen due to lower operational and coordination cost for current scope.

---

## Consequences

### Positive

- single source of truth for contracts and policies
- easier cross-service refactors
- straightforward full-stack CI

### Negative

- larger repository over time
- potentially longer CI unless selectively scoped
- needs discipline around ownership and boundaries

---

## Implementation Notes

1. Keep clear folder boundaries per service.
2. Enforce contract tests and docs consistency in CI.
3. Use configuration profiles to avoid environment-specific forks.
4. Keep shared code explicit (no implicit cross-service coupling).

---

## Follow-Up ADRs

Recommended next ADR topics:

1. canonical metadata validator implementation strategy
2. queue technology selection
3. operational database choice
4. review policy thresholds and auto-approval rules
5. llm-gateway provider abstraction model
