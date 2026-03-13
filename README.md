# Caipture

Caipture is a local-first, service-oriented pipeline for digitizing historical photographs and generating structured metadata with provenance and review support.

## Implemented PoC Components

- `services/web`: JSON API and monitoring dashboard
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

### Web Hosting Configuration

Web host/port can be configured in config file under `web.host` and `web.port`, or overridden by environment variables:

- `CAIPTURE_WEB_HOST`
- `CAIPTURE_WEB_PORT`

Default dev URL:

- `http://127.0.0.1:8080/`

## Web Access and Monitoring

When the web service is running:

- Monitoring dashboard (HTML): `GET /`
- Monitoring data (JSON): `GET /monitoring`
- Health probe: `GET /health`
- Job status: `GET /jobs/<job_id>`

Dashboard includes:

- status of services
- status of applications
- LLM usage since session start
- process counts (running/finished/aborted/possible queue)
- system load
- per-service process load bars (CPU/RSS)
- review queue with web approve actions
- recent central journal actions

Monitoring behavior is configurable via `monitoring` section in config:

- `runtime_dir`
- `llm_gateway_health_url`
- `refresh_seconds`

### Web Upload Flow

Open `http://127.0.0.1:8080/` and use **Upload Via Web Page** form:

1. Select front image and back image.
2. Optionally add context images.
3. Submit form.
4. Approve `review_required` jobs from **Jobs Queue and Approval**.
5. Track actions in **Recent Journal Actions**.

### Central Journal (debug)

All runtime actions are appended to:

- `storage/runtime/journal.jsonl`

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
PYTHONPATH=src python3 -m caipture.cli --config deploy/configs/dev/config.json \
  upload --front /path/to/front.png --back /path/to/back.png
```

### One-shot pipeline execution

```bash
scripts/dev/run_pipeline_once.sh
```

### Approve review and export

```bash
PYTHONPATH=src python3 -m caipture.cli --config deploy/configs/dev/config.json \
  review-approve --job-id <job_id> --approved-by <name>
PYTHONPATH=src python3 -m caipture.cli --config deploy/configs/dev/config.json run-export-once
```

## Container Run (Podman Compose)

```bash
scripts/dev/compose_up.sh
scripts/dev/compose_down.sh
```

## Tests

Unit + integration tests:

```bash
scripts/test/run_all.sh
```

BDD integration tests (Cucumber/Gherkin using `behave`):

```bash
scripts/test/run_bdd.sh
```

## Notes

Current implementation details:

- CV stage uses ImageMagick (`magick`) for auto-trim crop and resize.
- OCR stage uses `tesseract` CLI (sidecar `.txt` remains supported for deterministic tests).
- LLM gateway logic is enabled by default in config and contributes metadata descriptions.
- Export stage writes contextual comment metadata and aligns output file timestamp to inferred historical date when available.
