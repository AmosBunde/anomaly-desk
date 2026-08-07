#!/usr/bin/env python3
"""Report measured memory use per service against its declared Compose limit.

A3 declares a memory limit per service so the stack fails loudly against the roughly 7 GB
available on the development machine, rather than meeting the kernel out-of-memory killer,
which presents as an unexplained container death. A declared limit nobody measures against
is a guess, so this prints both numbers side by side.

The total is the figure A5 needs: a kind control plane has to fit in what is left.
"""

from __future__ import annotations

import json
import subprocess
import sys

import yaml

COMPOSE_FILE = "docker-compose.yml"


def parse_bytes(value: str) -> float:
    """Parse both Compose limit syntax (768M, 1G) and docker stats output (231.4MiB).

    These are two different notations for the same quantity and the script reads both, so
    handling only one of them silently crashes on the other.
    """
    value = value.strip()
    units = {
        "B": 1,
        "K": 1024,
        "KB": 1e3,
        "KIB": 1024,
        "M": 1024**2,
        "MB": 1e6,
        "MIB": 1024**2,
        "G": 1024**3,
        "GB": 1e9,
        "GIB": 1024**3,
    }
    upper = value.upper()
    for suffix in sorted(units, key=len, reverse=True):
        if upper.endswith(suffix):
            head = value[: -len(suffix)].strip()
            if head:
                return float(head) * units[suffix]
    return float(value)


def declared_limits() -> dict[str, float]:
    with open(COMPOSE_FILE, encoding="utf-8") as handle:
        spec = yaml.safe_load(handle)
    limits: dict[str, float] = {}
    for name, service in spec.get("services", {}).items():
        raw = service.get("deploy", {}).get("resources", {}).get("limits", {}).get("memory")
        if raw:
            limits[name] = parse_bytes(str(raw))
    return limits


def measured_usage() -> dict[str, tuple[float, str]]:
    result = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"docker stats failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(2)

    usage: dict[str, tuple[float, str]] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        name = row.get("Name", "")
        if not name.startswith("anomaly-"):
            continue
        service = name.removeprefix("anomaly-")
        used_text = row.get("MemUsage", "0B / 0B").split("/")[0].strip()
        usage[service] = (parse_bytes(used_text), row.get("MemPerc", "?"))
    return usage


def human(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1000:
            return f"{num:.0f} {unit}"
        num /= 1000
    return f"{num:.1f} TB"


# Compose service names differ from container suffixes for one service.
CONTAINER_ALIASES = {"otel-collector": "otel"}


def main() -> int:
    limits = declared_limits()
    usage = measured_usage()

    if not usage:
        print("No anomaly-desk containers are running. Start the stack with: make up")
        return 1

    print(f"{'service':<16}{'measured':>12}{'limit':>12}{'of limit':>12}")
    print("-" * 52)

    total_used = 0.0
    total_limit = 0.0
    for service, limit in sorted(limits.items()):
        key = CONTAINER_ALIASES.get(service, service)
        used, _ = usage.get(key, (0.0, "-"))
        total_used += used
        total_limit += limit
        pct = f"{used / limit * 100:.0f}%" if limit else "-"
        print(f"{service:<16}{human(used):>12}{human(limit):>12}{pct:>12}")

    print("-" * 52)
    print(f"{'total':<16}{human(total_used):>12}{human(total_limit):>12}")
    print(
        "\nThe total is the figure A5 needs: a kind control plane must fit in what remains "
        "of the roughly 7 GB available."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
