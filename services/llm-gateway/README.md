# LLM Gateway (`services/llm-gateway`)

## Purpose

Single abstraction point for model-assisted metadata interpretation.

## Responsibilities

- normalize/sanitize model requests
- return structured summary fields to metadata worker
- keep model interactions controlled and observable

## Current PoC behavior

- local deterministic summary behavior
- usage counters are tracked in session metrics and surfaced on dashboard

## Run

```bash
PYTHONPATH=src python3 services/llm-gateway/main.py
```
