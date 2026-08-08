"""Tests for the Archify diagram specifications and the sync check, delivered by A41.

A6 generated `docs/architecture.html` from a generator I wrote and compared `data-node`
attributes in its output. A41 replaced that generator with Archify, whose output markup is
not mine to depend on, so the comparison moved to the Archify specifications. These tests
assert that boundary.

The consolidation map is the part worth testing hardest. Archify's showcase profile favours
roughly twelve primary nodes against the Mermaid source's twenty-one, so nodes merge. A
silent drop and a reviewed merge look identical to a set comparison, which is exactly why
every merge must carry a declared reason.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SYNC = REPO_ROOT / "scripts" / "diagram_sync.py"
ARCH_SPEC = REPO_ROOT / "architecture" / "system.architecture.json"
SEQ_SPEC = REPO_ROOT / "architecture" / "triage.sequence.json"
CONSOLIDATIONS = REPO_ROOT / "architecture" / "consolidations.json"
ARCH_PAGE = REPO_ROOT / "docs" / "architecture.html"
SEQ_PAGE = REPO_ROOT / "docs" / "triage-sequence.html"

# Archify loads JetBrains Mono from Google Fonts. That is a documented deviation from A6's
# stricter "no remote font" criterion, verified to degrade to the local monospace stack with
# all network blocked. The allowlist exists so a *new* external dependency still fails.
ALLOWED_EXTERNAL_HOSTS = {
    # An XML namespace URI on the <svg> element. It is an identifier, never fetched.
    "www.w3.org",
    # The webfont. Degrades to the local monospace stack; see the docstring below.
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    # A documentation link in the page footer, not a resource the page loads.
    "tt-a1i.github.io",
}


def run_sync() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SYNC)], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )


@pytest.fixture(scope="module")
def arch_spec() -> dict:
    return json.loads(ARCH_SPEC.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def seq_spec() -> dict:
    return json.loads(SEQ_SPEC.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def consolidations() -> dict:
    return json.loads(CONSOLIDATIONS.read_text(encoding="utf-8"))


def test_specs_and_pages_exist():
    for path in (ARCH_SPEC, SEQ_SPEC, CONSOLIDATIONS, ARCH_PAGE, SEQ_PAGE):
        assert path.exists(), f"{path.relative_to(REPO_ROOT)} is missing"


def test_the_old_hand_written_generator_is_gone():
    """A41 removed it. A test asserts the removal so it cannot quietly return."""
    assert not (REPO_ROOT / "scripts" / "render_architecture.py").exists()


def test_specs_declare_showcase_quality(arch_spec, seq_spec):
    """Showcase is what buys the nine artifact checks and the zero-warning guarantee."""
    for spec in (arch_spec, seq_spec):
        assert spec["meta"]["quality_profile"] == "showcase"


def test_sync_check_passes():
    result = run_sync()
    assert result.returncode == 0, f"specs are out of sync:\n{result.stdout}{result.stderr}"


def test_required_boundaries_exist(arch_spec):
    """The build prompt names these two explicitly."""
    labels = {b["label"] for b in arch_spec["boundaries"]}
    assert "Agent workflow boundary" in labels
    assert "Evaluation plane" in labels


def test_every_consolidation_has_a_reason(consolidations):
    """A merge without a stated reason is indistinguishable from an accidental omission."""
    targets: dict[object, list[str]] = {}
    for node, target in consolidations["map"].items():
        targets.setdefault(target, []).append(node)
    for target, nodes in targets.items():
        if len(nodes) == 1 and target is not None:
            continue
        for node in nodes:
            if target is not None and node == target:
                continue
            assert node in consolidations["reasons"], (
                f"{node!r} is consolidated into {target!r} with no reason declared"
            )


def test_pgvector_is_consolidated_into_postgres(consolidations):
    """The one consolidation that increases fidelity rather than reducing it.

    pgvector runs inside the PostgreSQL container, which A3 confirmed as the deployed
    topology. Two separate nodes in the Mermaid source overstate the deployment.
    """
    assert consolidations["map"]["vec"] == consolidations["map"]["pg"] == "store"
    assert "inside" in consolidations["reasons"]["vec"].lower()


def test_no_mermaid_edge_was_silently_dropped():
    """The check must account for every edge, not just every node.

    Four edges were dropped during authoring for routing convenience, including
    orch -> queue, which is the guarantee that no event is silently lost. The check caught it.
    """
    result = run_sync()
    assert "all present as Archify relationships" in result.stdout


@pytest.mark.parametrize("page", [ARCH_PAGE, SEQ_PAGE])
def test_pages_have_no_external_scripts_or_images(page):
    """No remote code and no remote images: those would not degrade, they would break."""
    text = re.sub(r"<!--.*?-->", "", page.read_text(encoding="utf-8"), flags=re.S)
    assert not re.search(r"<script[^>]+src\s*=\s*[\"']https?://", text)
    assert not re.search(r"<img[^>]+src\s*=\s*[\"']https?://", text)


@pytest.mark.parametrize("page", [ARCH_PAGE, SEQ_PAGE])
def test_external_references_stay_within_the_documented_allowlist(page):
    """Archify fetches a webfont, which A6's criterion forbade and A41 documents instead.

    Verified by hand with all network blocked: both pages render completely and fall back to
    the local monospace stack. This allowlist keeps that a known, bounded deviation rather
    than an open door for the next dependency.
    """
    text = re.sub(r"<!--.*?-->", "", page.read_text(encoding="utf-8"), flags=re.S)
    hosts = set(re.findall(r"https?://([A-Za-z0-9.-]+)", text))
    unexpected = hosts - ALLOWED_EXTERNAL_HOSTS
    assert not unexpected, (
        f"{page.name} references undocumented external hosts: {sorted(unexpected)}. "
        "Either remove the reference or extend ALLOWED_EXTERNAL_HOSTS with a reason."
    )


@pytest.mark.parametrize("page", [ARCH_PAGE, SEQ_PAGE])
def test_pages_default_to_the_dark_theme(page):
    """The build prompt asks for dark-themed output.

    Confirmed visually: the page root carries data-theme="dark", and a viewer whose system
    preference is light gets the light variant from a media query.
    """
    text = page.read_text(encoding="utf-8")
    assert re.search(r'<html[^>]+data-theme="dark"', text), (
        "the document root must default to the dark theme"
    )


def test_sync_fails_when_the_mermaid_source_gains_a_node(tmp_path):
    """The realistic failure: an agent is added to the specification and nowhere else."""
    readme = REPO_ROOT / "README.md"
    original = readme.read_text(encoding="utf-8")
    (tmp_path / "README.md").write_text(original, encoding="utf-8")
    try:
        mutated = original.replace(
            '        dlq[["Dead letter queue"]]:::ingest',
            '        dlq[["Dead letter queue"]]:::ingest\n'
            '        shadow["Shadow scorer<br/>probe"]:::evalnode',
        )
        assert mutated != original, "the fixture anchor changed; update this test"
        readme.write_text(mutated, encoding="utf-8")
        result = run_sync()
        assert result.returncode == 1
        assert "shadow" in result.stdout
    finally:
        readme.write_text((tmp_path / "README.md").read_text(encoding="utf-8"), encoding="utf-8")


def test_sync_fails_when_a_component_is_unclaimed(tmp_path):
    """An Archify component no Mermaid node claims means the picture asserts more than the
    specification does, which is the opposite failure and equally wrong."""
    original = ARCH_SPEC.read_text(encoding="utf-8")
    (tmp_path / "spec.json").write_text(original, encoding="utf-8")
    try:
        spec = json.loads(original)
        spec["components"].append(
            {
                "id": "ghost",
                "type": "backend",
                "label": "Ghost",
                "pos": [40, 900],
                "size": [140, 60],
            }
        )
        ARCH_SPEC.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
        result = run_sync()
        assert result.returncode == 1
        assert "ghost" in result.stdout
    finally:
        ARCH_SPEC.write_text((tmp_path / "spec.json").read_text(encoding="utf-8"), encoding="utf-8")


def test_sync_fails_when_a_consolidation_loses_its_reason(tmp_path):
    original = CONSOLIDATIONS.read_text(encoding="utf-8")
    (tmp_path / "cons.json").write_text(original, encoding="utf-8")
    try:
        cons = json.loads(original)
        cons["reasons"].pop("vec")
        CONSOLIDATIONS.write_text(json.dumps(cons, indent=2) + "\n", encoding="utf-8")
        result = run_sync()
        assert result.returncode == 1
        assert "vec" in result.stdout
    finally:
        CONSOLIDATIONS.write_text(
            (tmp_path / "cons.json").read_text(encoding="utf-8"), encoding="utf-8"
        )
