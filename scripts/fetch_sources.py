#!/usr/bin/env python3
"""Fetch the pinned event sources, verify their hashes, and cut the committed demo slice.

Idempotent: a source already present and matching its recorded hash is not refetched. A
source whose content no longer matches is a hard failure rather than a silent overwrite,
because the labeled set from A10 is scored against a specific snapshot and a source changing
underneath invalidates every comparison made against it.

The demo slice is committed so that ``docker compose up --build`` followed by ``make eval``
works from a clean checkout, which the definition of done requires. Every source pinned here
permits redistribution on condition of attribution, citation, and carrying the license
notice; ``data/demo/LICENSE`` is written alongside the slice for that reason and its presence
is asserted by a test.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG = REPO_ROOT / "configs" / "sources.yaml"
RAW_DIR = REPO_ROOT / "data" / "raw"
DEMO_DIR = REPO_ROOT / "data" / "demo"
TIMEOUT = 60


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_config() -> dict:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    # YAML parses an unquoted all-digit hash as an integer, which then never compares equal
    # to the hex digest computed at runtime, so the check would silently always fail. Found
    # while testing the mismatch path with a hash of sixty-four zeroes.
    for source in config["sources"]:
        source["sha256"] = str(source["sha256"]).strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", source["sha256"]):
            raise SystemExit(
                f"{source['id']}: sha256 {source['sha256']!r} is not a 64 character hex digest. "
                "Quote it in configs/sources.yaml."
            )
    return config


def fetch(source: dict, raw_path: Path) -> bytes:
    """Return the snapshot bytes, reusing a verified local copy when one exists."""
    if raw_path.exists():
        existing = raw_path.read_bytes()
        if sha256(existing) == source["sha256"]:
            print(f"  {source['id']}: cached and verified")
            return existing
        print(
            f"  {source['id']}: local copy does not match the pinned hash, refetching",
            file=sys.stderr,
        )

    print(f"  {source['id']}: fetching {source['origin']}")
    try:
        with urllib.request.urlopen(source["origin"], timeout=TIMEOUT) as response:
            data = response.read()
    except (urllib.error.URLError, TimeoutError) as error:
        print(
            f"\n{source['id']}: fetch failed: {error}\n"
            f"The pinned URL may have moved. The recorded hash is "
            f"{source['sha256']}; a mirror changes provenance and is an owner decision, so do "
            f"not substitute one silently.",
            file=sys.stderr,
        )
        raise SystemExit(2) from error

    actual = sha256(data)
    if actual != source["sha256"]:
        print(
            f"\n{source['id']}: hash mismatch.\n"
            f"  expected {source['sha256']}\n"
            f"  actual   {actual}\n"
            f"The upstream snapshot changed. Every label in evalset/ was written against the "
            f"pinned snapshot, so accepting this silently would invalidate the labeled set. "
            f"Update configs/sources.yaml deliberately and re-check the labels.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(data)
    return data


def write_demo_slice(source: dict, data: bytes, records: int) -> int:
    """Write the first N records to the committed demo slice."""
    lines = data.decode("utf-8", errors="replace").splitlines()
    slice_lines = lines[:records]
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    target = DEMO_DIR / f"{source['id']}.log"
    target.write_text("\n".join(slice_lines) + "\n", encoding="utf-8")
    return len(slice_lines)


def write_license_notice(config: dict) -> None:
    """Carry the upstream license notice with the redistributed slice, as required."""
    lines = [
        "The log samples in this directory are redistributed from the loghub collection.",
        "",
        f"Upstream: {config['sources'][0]['upstream']}",
        "",
        "The datasets are freely available for research or academic work, subject to the",
        "following condition: for any usage or distribution of the loghub datasets, refer to",
        "the loghub repository URL and cite the loghub paper. This notice is included in all",
        "copies, as the upstream license requires.",
        "",
        "Citation:",
        f"  {config['citation'].strip()}",
        "",
        "Per-source origin, license, retrieval date, record count, and snapshot hash are",
        "recorded in configs/sources.yaml and docs/sources.md.",
        "",
    ]
    (DEMO_DIR / "LICENSE").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="verify cached snapshots against their hashes without fetching",
    )
    args = parser.parse_args(argv)

    config = load_config()
    print(f"fetch_sources: {len(config['sources'])} pinned source(s)")

    total_demo = 0
    for source in config["sources"]:
        raw_path = RAW_DIR / f"{source['id']}.log"
        if args.verify_only:
            if not raw_path.exists():
                print(f"  {source['id']}: not fetched", file=sys.stderr)
                return 1
            if sha256(raw_path.read_bytes()) != source["sha256"]:
                print(f"  {source['id']}: hash mismatch", file=sys.stderr)
                return 1
            print(f"  {source['id']}: verified")
            continue

        data = fetch(source, raw_path)
        written = write_demo_slice(source, data, config["demo_slice_records"])
        total_demo += written
        print(f"  {source['id']}: demo slice {written} records")

    if not args.verify_only:
        write_license_notice(config)
        print(f"  wrote {DEMO_DIR.relative_to(REPO_ROOT)}/LICENSE")
        print(f"\n{total_demo} demo records across {len(config['sources'])} sources")
    return 0


if __name__ == "__main__":
    sys.exit(main())
