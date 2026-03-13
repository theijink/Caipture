# web service

JSON API + monitoring dashboard.

## Run

```bash
PYTHONPATH=src CAIPTURE_CONFIG=deploy/configs/dev/config.json python3 services/web/server.py
```

## Routes

- `GET /` monitoring dashboard (HTML)
- `GET /monitoring` monitoring payload (JSON)
- `GET /health` health check
- `POST /upload-web` multipart form upload endpoint (used by dashboard form)
- `POST /upload` create job
- `POST /run-all-once` run one processing sweep
- `POST /review/<job_id>` approve review
- `GET /jobs/<job_id>` fetch job state
