"""FastAPI application for the API service.

A3 delivers the application object and a health endpoint, which is what the Compose health
check and the kind readiness probe at A38 need in order to exist at all. The operator queue
endpoints arrive at A29 and the override capture at A31.

The health endpoint is deliberately a liveness check rather than a readiness check: it
reports that this process is serving, and says nothing about PostgreSQL or Kafka. Compose
already gates this container on those two being healthy, so folding their status in here
would report the same fact twice and make a dependency outage look like an API fault. A
readiness endpoint that checks downstream dependencies belongs with A29, which is the first
issue whose endpoints actually use them.
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from anomalydesk import __version__

app = FastAPI(
    title="Anomaly Desk API",
    version=__version__,
    summary="Agentic triage of a continuous operational event stream.",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness. Returns 200 whenever this process is serving requests."""
    return {
        "status": "ok",
        "version": __version__,
        # Recorded because a triage scored against the wrong backend is not comparable to
        # one scored against the pinned model, per README.md section 4.
        "model_backend": os.getenv("MODEL_BACKEND", "api"),
    }


@app.get("/")
def root() -> dict[str, object]:
    """Names what is implemented and what is not, so the gap is visible rather than absent."""
    return {
        "service": "anomaly-desk-api",
        "version": __version__,
        "implemented": ["GET /health"],
        "pending": {
            "GET /queue": "A29, operator queue",
            "POST /queue/{triage_id}/disposition": "A31, accept, edit, or override capture",
        },
    }
