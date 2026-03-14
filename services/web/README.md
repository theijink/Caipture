# Web Service (`services/web`)

## Purpose

Provides the local operator interface and API entrypoint for Caipture.

Core responsibilities:

- host dashboard UI (`/`)
- accept photo uploads via web form and JSON API
- expose monitoring and process state
- allow approving review-required jobs from queue widget
- provide download links for generated export image and metadata sidecar

## Network Hosting

- host/port come from config `web.host` and `web.port`
- defaults are intended for LAN access in dev (`0.0.0.0:8080`)

## Main Endpoints

- `GET /` full dashboard UI (dark mode + modal state viewer)
- `GET /monitoring` full monitoring payload (JSON)
- `GET /journal` central journal entries (JSON)
- `GET /health` health probe
- `GET /jobs/<job_id>` job state (JSON)
- `GET /process/<service_name>` service process state (JSON)
- `GET /download/<job_id>/image` download generated image
- `GET /download/<job_id>/sidecar` download metadata sidecar
- `POST /upload-web` multipart form upload
- `POST /upload` JSON upload API
- `POST /approve-web` approve review-required job
- `POST /run-all-once` run one processing sweep

## Runtime Data

- reads/writes under `storage/`
- central journal: `storage/runtime/journal.jsonl`

## Run

```bash
PYTHONPATH=src CAIPTURE_CONFIG=deploy/configs/dev/config.json python3 services/web/server.py
```
