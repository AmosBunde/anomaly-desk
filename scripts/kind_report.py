#!/usr/bin/env python3
"""Report the measured memory cost of the idle kind cluster.

A5 exists partly to answer one question before A38 depends on it: does a Kubernetes control
plane fit alongside the Compose stack on this machine? The Compose stack measured 450 MB
idle with limits summing to 3 GB, against roughly 6.9 GB available, so the answer is a
number rather than a guess.

A kind node is a Docker container, so docker stats measures it the same way the Compose
stack was measured, and the two figures are directly comparable.
"""

from __future__ import annotations

import json
import subprocess
import sys

CLUSTER = "anomaly-desk"
NODE_CONTAINER = f"{CLUSTER}-control-plane"


def parse_bytes(value: str) -> float:
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


def human(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1000:
            return f"{num:.0f} {unit}"
        num /= 1000
    return f"{num:.1f} TB"


def main() -> int:
    result = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"docker stats failed:\n{result.stderr}", file=sys.stderr)
        return 2

    node = None
    compose_total = 0.0
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        name = row.get("Name", "")
        used = parse_bytes(row.get("MemUsage", "0B / 0B").split("/")[0])
        if name == NODE_CONTAINER:
            node = used
        elif name.startswith("anomaly-"):
            compose_total += used

    if node is None:
        print(f"No container named {NODE_CONTAINER}. Start it with: make kind-up")
        return 1

    print(f"{'component':<28}{'measured':>12}")
    print("-" * 40)
    print(f"{'kind control plane (idle)':<28}{human(node):>12}")
    if compose_total:
        print(f"{'compose stack (running)':<28}{human(compose_total):>12}")
        print("-" * 40)
        print(f"{'both together':<28}{human(node + compose_total):>12}")
    else:
        print(f"{'compose stack':<28}{'not running':>12}")

    print(
        "\nCompose measured 450 MB idle when A3 landed. If both fit inside the roughly\n"
        "6.9 GB available, A38 can deploy without stopping the Compose stack first, and\n"
        "deploy/runbook.md does not need to document that constraint."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
