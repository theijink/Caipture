# web service

JSON API + monitoring dashboard.

## Run

```bash
PYTHONPATH=src CAIPTURE_CONFIG=deploy/configs/dev/config.json python3 services/web/server.py
```

## Routes

- `GET /` monitoring dashboard (HTML)
- `GET /monitoring` monitoring payload (JSON)
- `GET /journal` central journal tail (JSON)
- `GET /health` health check
- `POST /upload-web` multipart form upload endpoint (used by dashboard form)
- `POST /approve-web` approve review-required job from dashboard form
- `POST /upload` create job
- `POST /run-all-once` run one processing sweep
- `POST /review/<job_id>` approve review
- `GET /jobs/<job_id>` fetch job state

## Dashboard capabilities

- dark/light mode following system preference
- larger journal widget with recent actions and link to full feed
- job queue table with links to job JSON and approve buttons
- process/system load bars
