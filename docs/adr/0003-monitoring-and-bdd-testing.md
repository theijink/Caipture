# ADR 0003 - Web Control Center, Central Journal, and BDD Integration Tests

Date: 2026-03-13
Status: Accepted
Decision Makers: Project Maintainer

---

## Context

The initial PoC lacked:

- a practical operator-facing web page
- end-to-end browser-facing upload verification
- centralized runtime action journaling for debugging

Operational observability and behavior-level verification were therefore incomplete.

---

## Decision

1. Extend web service into a control center:
   - HTML dashboard at `/`
   - JSON monitoring API at `/monitoring`
   - multipart form upload endpoint at `/upload-web`
2. Provide dashboard-level operational visibility for:
   - service status
   - application status
   - LLM usage since session start
   - process counts (running, finished, aborted, possible queue)
   - host system load
   - recent runtime journal actions
   - per-service process load (CPU/RSS) visualization
3. Introduce central append-only runtime journal:
   - `storage/runtime/journal.jsonl`
   - written by web actions and queue/pipeline events
4. Add/extend Cucumber-style BDD tests with `behave` under `tests/bdd/features`, including web page access and fixture upload scenario.
5. Enable web-based approval actions for review-required jobs from dashboard queue widget.

---

## Implementation Notes

- Web dashboard now includes an upload form so test and debug workflows can be executed from the browser.
- Dashboard style supports system dark/light preference for readability.
- Monitoring values are aggregated from queue state, PID checks, session metrics, and system load.
- Session metrics are persisted in runtime storage (`session_metrics.json`) and surfaced by the dashboard.
- Fixture compatibility updated: image dimension detection now supports both PNG and JPEG signatures (important for mixed fixture content).
- Dev config allows lower upload resolution threshold to support fixture-driven debug runs.

---

## Consequences

### Positive

- significantly better local operability and debugability
- immediate visual insight into pipeline and service health
- durable action trace for diagnostics (`journal.jsonl`)
- executable behavior specs now include browser-facing upload flow

### Negative

- additional moving parts in web layer (multipart handling + dashboard rendering)
- additional dev dependency (`behave`)
- local process/port contention can occur when stale processes are not stopped
- PID-based service checks remain lightweight and environment-dependent

---

## Operational Guidance

- Use `scripts/dev/start_all.sh` and `scripts/dev/stop_all.sh` to manage local processes.
- If port binding fails, stop stale processes before restart.
- Use `storage/runtime/journal.jsonl` as first-line debug trace.

---

## Follow-up

1. Add dedicated worker health endpoints (instead of only PID inference).
2. Replace lightweight host metrics with richer telemetry backend as needed.
3. Consider stronger file-upload security checks if internet-exposed deployment is introduced.
