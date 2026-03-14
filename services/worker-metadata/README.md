# Metadata Worker (`services/worker-metadata`)

## Purpose

Builds canonical metadata from CV/OCR evidence and review policy.

## Responsibilities

- fuse OCR evidence from back and all context artifacts
- parse OCR evidence for date/location/people/event/context
- call LLM gateway abstraction for additional description
- populate canonical metadata document
- compute review-required state and reasons

Primary output:

- `storage/jobs/<job_id>/metadata/photo_item.json`

## Run

```bash
PYTHONPATH=src python3 services/worker-metadata/main.py
```
