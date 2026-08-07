#!/usr/bin/env python3
"""Block until every Compose service reports healthy, then report what came up.

``docker compose up -d`` returns as soon as containers are created, not when they are
usable. Without this, ``make up && make data`` fails against a PostgreSQL that is still
running its init scripts, and the error looks like a schema bug rather than a race.

Exits non-zero with the failing service and its last health output, so a stack that does
not come up says why rather than leaving the reader to run docker inspect.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time

TIMEOUT_SECONDS = 240
POLL_SECONDS = 3

# A service with no health check is considered ready once it is running.
EXPECTED_SERVICES = ["postgres", "kafka", "otel-collector", "api", "ui"]


def compose_ps() -> list[dict]:
    result = subprocess.run(
        ["docker", "compose", "ps", "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"docker compose ps failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(2)

    # Compose emits either a JSON array or one object per line depending on version.
    text = result.stdout.strip()
    if not text:
        return []
    if text.startswith("["):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def state_of(container: dict) -> str:
    health = (container.get("Health") or "").strip()
    if health:
        return health
    return (container.get("State") or "unknown").strip()


def describe(container: dict) -> str:
    return f"  {container.get('Service', '?'):<15} {state_of(container)}"


def last_health_log(service: str) -> str:
    result = subprocess.run(
        ["docker", "compose", "logs", "--tail", "20", service],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout or result.stderr or "(no output)"


def main() -> int:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    last_render = ""

    while time.monotonic() < deadline:
        containers = compose_ps()
        by_service = {c.get("Service"): c for c in containers}

        missing = [s for s in EXPECTED_SERVICES if s not in by_service]
        states = {s: state_of(c) for s, c in by_service.items()}

        render = "\n".join(describe(c) for c in containers)
        if render != last_render:
            print(render)
            last_render = render

        unhealthy = [s for s, st in states.items() if st in {"unhealthy", "exited", "dead"}]
        if unhealthy:
            for service in unhealthy:
                print(f"\n{service} is {states[service]}. Last output:\n", file=sys.stderr)
                print(last_health_log(service), file=sys.stderr)
            return 1

        ready = not missing and all(st in {"healthy", "running"} for st in states.values())
        if ready:
            print(f"\nAll {len(EXPECTED_SERVICES)} services are up.")
            return 0

        time.sleep(POLL_SECONDS)

    print(f"\nTimed out after {TIMEOUT_SECONDS}s. Current state:", file=sys.stderr)
    for container in compose_ps():
        print(describe(container), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
