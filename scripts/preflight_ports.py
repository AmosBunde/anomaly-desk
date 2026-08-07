#!/usr/bin/env python3
"""Fail with a readable message when a host port the stack needs is already taken.

Without this, a port collision surfaces as:

    Error response from daemon: failed to set up container networking: driver failed
    programming external connectivity on endpoint anomaly-postgres (b0938a3d...):
    Bind for 0.0.0.0:5432 failed: port is already allocated

which names neither the service, the override variable, nor what is holding the port. This
is not hypothetical: the development machine runs other stacks that hold 5432, 8000, and
3000, and specification section 15 fixes the API on 8000 and the console on 3000, so the
defaults cannot simply be moved.
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys

# (service, env var, default host port)
PORTS = [
    ("postgres", "POSTGRES_PORT", 5432),
    ("kafka", "KAFKA_PORT", 9092),
    ("api", "API_PORT", 8000),
    ("ui", "UI_PORT", 3000),
    ("otel-collector", "OTEL_GRPC_PORT", 4317),
    ("otel-collector", "OTEL_HTTP_PORT", 4318),
    ("otel-collector", "OTEL_HEALTH_PORT", 13133),
]

# The kind node publishes the API and console host ports through extraPortMappings, so the
# cluster collides with exactly the same host ports as the Compose stack. A5 found this the
# hard way: cluster creation failed on 127.0.0.1:3000, held by another project on this
# machine, with the same opaque Docker error the Compose preflight was written to replace.
KIND_PORTS = [
    ("kind node (API NodePort)", "API_PORT", 8000),
    ("kind node (console NodePort)", "UI_PORT", 3000),
]

OUR_CONTAINERS = (
    "anomaly-postgres",
    "anomaly-kafka",
    "anomaly-api",
    "anomaly-ui",
    "anomaly-otel",
    "anomaly-desk-control-plane",
)


def load_dotenv() -> dict[str, str]:
    """Read .env the way Compose does, so the preflight sees the same ports Compose will.

    Without this the check reads only the shell environment, reports a conflict on the
    default port, and blocks a stack that would have started fine on the overridden one.
    """
    values: dict[str, str] = {}
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.exists(path):
        return values
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
            return False
        except OSError:
            return True


def holder(port: int) -> str:
    """Best effort identification of what holds the port, for the error message."""
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}\t{{.Ports}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    for line in result.stdout.splitlines():
        if f":{port}->" in line:
            name = line.split("\t")[0]
            if name in OUR_CONTAINERS:
                return f"our own container {name}, already running"
            return f"container {name}"
    return "a process outside Docker"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--kind",
        action="store_true",
        help="check the kind node host ports instead of the Compose service ports",
    )
    args = parser.parse_args()
    checks = KIND_PORTS if args.kind else PORTS

    # Shell environment wins over .env, matching Compose precedence.
    dotenv = load_dotenv()
    conflicts = []
    for service, env_var, default in checks:
        port = int(os.getenv(env_var, dotenv.get(env_var, default)))
        if in_use(port):
            conflicts.append((service, env_var, port, holder(port)))

    if not conflicts:
        return 0

    print("Cannot start: host ports are already in use.\n", file=sys.stderr)
    for service, env_var, port, who in conflicts:
        print(f"  {service:<15} port {port:<6} held by {who}", file=sys.stderr)
        print(f"  {'':<15} override with {env_var}=<free port> in .env\n", file=sys.stderr)
    print(
        "Specification section 15 fixes the API on 8000 and the console on 3000, so the\n"
        "defaults are correct for a clean machine. Copy .env.example to .env and override\n"
        "the ports above when other stacks are running.",
        file=sys.stderr,
    )
    if args.kind:
        print(
            "\nThe kind node publishes these through extraPortMappings, so it collides with\n"
            "the same host ports as the Compose stack. Running both at once needs different\n"
            "ports for each, or the Compose stack stopped first.",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
