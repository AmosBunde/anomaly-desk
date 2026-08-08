"""Tests for the pinned event sources delivered by A7.

The labeled set from A10 is scored against a specific snapshot of each source. A source
changing underneath does not break a test somewhere; it silently invalidates every comparison
made against those labels. So the pins are asserted, and so is the licensing, because the
committed demo slice is a redistribution and its conditions are not optional.

These run without a network: they assert the configuration, the documentation, and the
committed slice. The fetch itself is exercised by `make data`.
"""

import hashlib
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG = REPO_ROOT / "configs" / "sources.yaml"
DOC = REPO_ROOT / "docs" / "sources.md"
DEMO = REPO_ROOT / "data" / "demo"

# Every field the issue requires per source.
REQUIRED_FIELDS = [
    "id",
    "origin",
    "upstream",
    "license",
    "license_url",
    "redistributable",
    "retrieved",
    "records",
    "sha256",
    "redactions",
    "kind",
    "service",
]


@pytest.fixture(scope="module")
def config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sources(config) -> list[dict]:
    return config["sources"]


def test_at_least_two_sources(sources):
    """A single-domain corpus cannot distinguish a working classifier from a constant one."""
    assert len(sources) >= 2


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_every_source_records_every_required_field(field, sources):
    for source in sources:
        assert field in source, f"{source.get('id', '?')} is missing {field!r}"
        assert source[field] not in (None, ""), f"{source['id']} has an empty {field!r}"


def test_sha256_values_are_quoted_hex(sources):
    """An unquoted all-digit hash is parsed by YAML as an integer and never matches.

    Found by testing the mismatch path with sixty-four zeroes, not by reading the file.
    """
    raw = CONFIG.read_text(encoding="utf-8")
    for source in sources:
        assert isinstance(source["sha256"], str), (
            f"{source['id']}: sha256 parsed as {type(source['sha256']).__name__}; quote it"
        )
        assert re.fullmatch(r"[0-9a-f]{64}", source["sha256"])
        assert f'"{source["sha256"]}"' in raw, f"{source['id']}: sha256 must be quoted in YAML"


def test_failure_modes_are_diverse(sources):
    """Distinct services, so severity and category labels have something to separate."""
    assert len({s["service"] for s in sources}) == len(sources)


def test_redistribution_conditions_recorded_where_redistributable(sources):
    for source in sources:
        if source["redistributable"]:
            assert source.get("redistribution_conditions"), (
                f"{source['id']} is redistributed with no conditions recorded"
            )


def test_only_redistributable_sources_have_a_committed_slice(sources):
    """A source whose license forbids redistribution must not appear under data/demo/."""
    for source in sources:
        slice_path = DEMO / f"{source['id']}.log"
        if source["redistributable"]:
            assert slice_path.exists(), f"{source['id']} has no committed demo slice"
        else:
            assert not slice_path.exists(), (
                f"{source['id']} is not redistributable but a slice is committed at "
                f"{slice_path.relative_to(REPO_ROOT)}"
            )


def test_license_notice_accompanies_the_redistributed_slice(config):
    """The upstream license requires the notice in all copies, so it ships with the slice."""
    notice = DEMO / "LICENSE"
    assert notice.exists(), "data/demo/LICENSE is required by the upstream license"
    text = notice.read_text(encoding="utf-8")
    assert "loghub" in text.lower()
    # The citation must be present verbatim, since citation is a stated condition.
    first_author = config["citation"].split(",")[0].strip()
    assert first_author in text, f"the citation must name {first_author!r}"


def test_committed_slice_matches_the_declared_record_count(config, sources):
    expected = config["demo_slice_records"]
    for source in sources:
        if not source["redistributable"]:
            continue
        lines = (DEMO / f"{source['id']}.log").read_text(encoding="utf-8").splitlines()
        assert len(lines) == expected, (
            f"{source['id']} demo slice has {len(lines)} records, expected {expected}"
        )


def test_committed_slice_is_a_prefix_of_the_pinned_snapshot(sources):
    """The slice must come from the pinned snapshot, not from an unrelated fetch.

    Skips when the full snapshot is absent, because data/raw/ is gitignored and a fresh
    checkout has not run make data yet.
    """
    for source in sources:
        raw = REPO_ROOT / "data" / "raw" / f"{source['id']}.log"
        if not raw.exists():
            pytest.skip("data/raw is gitignored; run make data to exercise this")
        assert hashlib.sha256(raw.read_bytes()).hexdigest() == source["sha256"]
        raw_lines = raw.read_text(encoding="utf-8", errors="replace").splitlines()
        demo_lines = (DEMO / f"{source['id']}.log").read_text(encoding="utf-8").splitlines()
        assert raw_lines[: len(demo_lines)] == demo_lines, (
            f"{source['id']} demo slice is not a prefix of the pinned snapshot"
        )


def test_documentation_records_every_source(sources):
    """docs/sources.md is the prose record; it must not fall behind the configuration."""
    doc = DOC.read_text(encoding="utf-8")
    for source in sources:
        assert source["id"] in doc, f"{source['id']} is not documented in docs/sources.md"
        assert source["sha256"][:16] in doc, (
            f"{source['id']} snapshot hash is not recorded in docs/sources.md"
        )


def test_documentation_reproduces_the_citation(config):
    doc = DOC.read_text(encoding="utf-8")
    first_author = config["citation"].split(",")[0].strip()
    assert first_author in doc
    assert "ISSRE" in doc, "the citation venue must appear, since citation is a license condition"
