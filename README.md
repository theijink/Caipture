# Caipture

Caipture is a local-first, service-oriented pipeline for digitizing historical photographs and generating structured metadata with provenance and review support.

## Implemented PoC Components

- `services/web`: JSON API for upload/status/review and one-shot processing trigger
- `services/worker-cv`: validation + front-image derivative generation
- `services/worker-ocr`: OCR artifact generation (deterministic PoC surrogate)
- `services/worker-metadata`: canonical metadata generation and review decision
- `services/worker-export`: export file + sidecar generation
- `services/llm-gateway`: constrained model-gateway abstraction
- `src/caipture`: shared contracts, queue, storage, pipeline logic

## Configuration

Runtime behavior is parameterized via JSON config files:

- `deploy/configs/dev/config.json`
- `deploy/configs/rpi/config.json`

Set config explicitly:

```bash
export CAIPTURE_CONFIG=deploy/configs/dev/config.json
```

## Local Run (without containers)

Start all services:

```bash
scripts/dev/start_all.sh
```

Stop all services:

```bash
scripts/dev/stop_all.sh
```

### Upload a job

```bash
PYTHONPATH=src python -m caipture.cli --config deploy/configs/dev/config.json \
  upload --front /path/to/front.png --back /path/to/back.png
```

### One-shot pipeline execution

```bash
scripts/dev/run_pipeline_once.sh
```

### Approve review and export

```bash
PYTHONPATH=src python -m caipture.cli --config deploy/configs/dev/config.json \
  review-approve --job-id <job_id> --approved-by <name>
PYTHONPATH=src python -m caipture.cli --config deploy/configs/dev/config.json run-export-once
```

## Container Run (Podman Compose)

```bash
scripts/dev/compose_up.sh
scripts/dev/compose_down.sh
```

## Tests

Run all unit + integration tests:

```bash
scripts/test/run_all.sh
```

## Notes

This PoC uses deterministic, local surrogate logic for CV/OCR/LLM behavior so tests are reproducible and do not require external dependencies.
