FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md /app/
COPY src /app/src
COPY services /app/services
COPY deploy /app/deploy
RUN pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1
ENV CAIPTURE_CONFIG=/app/deploy/configs/dev/config.json
