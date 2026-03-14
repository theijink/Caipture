# Export Worker (`services/worker-export`)

## Purpose

Generates final export artifacts from approved metadata.

## Responsibilities

- copy/write final export image
- include export mapping fields (date/location/comment context)
- set file timestamp from inferred historical date when available
- write sidecar metadata JSON

Artifacts:

- `exports/photo_export.png`
- `exports/photo_export.sidecar.json`

## Run

```bash
PYTHONPATH=src python3 services/worker-export/main.py
```
