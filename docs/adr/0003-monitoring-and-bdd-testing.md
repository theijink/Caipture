# ADR 0003 - Add Web Monitoring Dashboard and BDD Integration Tests

Date: 2026-03-13
Status: Accepted
Decision Makers: Project Maintainer

---

## Context

Operational visibility and behavior-level verification were missing from the initial PoC implementation.

The project now requires:

- clear runtime monitoring from the web entrypoint
- Cucumber-style behavior-driven integration tests

---

## Decision

1. Extend web service to expose:
   - HTML dashboard at `/`
   - JSON monitoring API at `/monitoring`
2. Aggregate monitoring from:
   - queue/job states
   - runtime PID files
   - LLM session usage counters
   - host system load
3. Add `behave`-based BDD tests under `tests/bdd/features`.

---

## Consequences

### Positive

- better operational debugging during PoC runs
- executable behavior specifications in Gherkin
- improved alignment between requirements and observable runtime behavior

### Negative

- additional dev dependency (`behave`)
- lightweight PID-based service checks are environment-dependent

---

## Follow-up

Future iterations should expose worker health endpoints directly and collect richer metrics via a dedicated telemetry backend.
