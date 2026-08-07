#!/usr/bin/env python3
"""Render deploy/kind-config.yaml with host ports substituted from the environment.

kind does not interpolate variables in its own configuration file, so the template carries
${VAR} placeholders and this script fills them before the config reaches kind on stdin.

It exists because hardcoding host ports 8000 and 3000 made `kind create cluster` fail on the
development machine, where another project already holds both on loopback. Compose solved the
same problem with ${VAR:-default} syntax; kind needs it done explicitly. Defaults match
README.md section 15 and docker-compose.yml, so both paths publish on the same ports.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = REPO_ROOT / "deploy" / "kind-config.yaml"

DEFAULTS = {
    "BIND_ADDRESS": "127.0.0.1",
    "API_PORT": "8000",
    "UI_PORT": "3000",
}

PLACEHOLDER_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def load_dotenv() -> dict[str, str]:
    """Read .env so this script and Compose agree on the ports in use."""
    values: dict[str, str] = {}
    path = REPO_ROOT / ".env"
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> int:
    dotenv = load_dotenv()

    def resolve(name: str) -> str:
        # Shell environment wins over .env, which wins over the section 15 default.
        return os.environ.get(name) or dotenv.get(name) or DEFAULTS[name]

    text = TEMPLATE.read_text(encoding="utf-8")
    unknown = {n for n in PLACEHOLDER_RE.findall(text) if n not in DEFAULTS}
    if unknown:
        print(
            f"kind config references unknown variables: {sorted(unknown)}. Add them to "
            "DEFAULTS in this script so they cannot render empty.",
            file=sys.stderr,
        )
        return 2

    sys.stdout.write(PLACEHOLDER_RE.sub(lambda m: resolve(m.group(1)), text))
    return 0


if __name__ == "__main__":
    sys.exit(main())
