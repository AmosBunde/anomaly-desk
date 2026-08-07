"""Tests for the architecture page and the diagram synchronization check, delivered by A6.

Specification section 2 requires the Mermaid source in README.md and docs/architecture.html to
change together. A requirement enforced only by remembering is not enforced, and between A16
and A38 the architecture changes repeatedly.

These assert both halves: that the committed page is in sync, and that the check actually
fails when it is not. A synchronization check nobody has seen fail is indistinguishable from
one that always passes.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SYNC = REPO_ROOT / "scripts" / "diagram_sync.py"
RENDER = REPO_ROOT / "scripts" / "render_architecture.py"
PAGE = REPO_ROOT / "docs" / "architecture.html"
README = REPO_ROOT / "README.md"


def run(script: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script)], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )


def test_committed_page_is_in_sync():
    result = run(SYNC)
    assert result.returncode == 0, f"the committed page is stale:\n{result.stdout}{result.stderr}"


def test_page_is_regenerated_deterministically():
    """Regenerating must not change the committed file, or every diff carries noise."""
    before = PAGE.read_text(encoding="utf-8")
    assert run(RENDER).returncode == 0
    assert PAGE.read_text(encoding="utf-8") == before, (
        "regenerating changed the page; the committed copy is stale or the generator is "
        "not deterministic"
    )


def test_page_is_self_contained():
    """No external stylesheet, font, script, or image: it must render with no network."""
    text = PAGE.read_text(encoding="utf-8")
    body = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    assert "http://" not in body and "https://" not in body
    assert "<script" not in body
    assert "@import" not in body
    assert not re.search(r'src\s*=\s*"', body)


def test_page_requests_jetbrains_mono_first():
    assert 'font-family: "JetBrains Mono"' in PAGE.read_text(encoding="utf-8")


def test_legend_sits_outside_every_boundary():
    """The build prompt requires the legend outside all boundary boxes."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    try:
        import render_architecture as ra
    finally:
        sys.path.pop(0)
    lowest = max(by + bh for _, by, _, bh in ra.BOUNDARY_BOX.values())
    assert lowest < ra.LEGEND_Y
    assert 'data-legend="outside-all-boundaries"' in PAGE.read_text(encoding="utf-8")


def test_agent_workflow_and_evaluation_plane_have_boundary_boxes():
    """Both are called out explicitly in the build prompt."""
    text = PAGE.read_text(encoding="utf-8")
    assert 'data-boundary-title="workflow:Agent workflow boundary"' in text
    assert 'data-boundary-title="evalplane:Evaluation plane"' in text


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        pytest.param(
            lambda t: t.replace('data-node="judge"', 'data-node="ghost"'),
            "ghost",
            id="node-renamed",
        ),
        pytest.param(
            lambda t: t.replace('data-edge="judge->board"', 'data-edge="judge->cost"'),
            "judge",
            id="edge-retargeted",
        ),
        pytest.param(
            lambda t: t.replace(
                'data-node="judge" data-boundary="evalplane"',
                'data-node="judge" data-boundary="obs"',
            ),
            "boundary membership differs",
            id="boundary-membership-moved",
        ),
    ],
)
def test_check_fails_when_the_page_diverges(mutation, expected, tmp_path):
    """The check must fail and name what diverged.

    'The diagrams are out of sync' without saying how is not actionable at the moment
    someone is trying to merge.
    """
    original = PAGE.read_text(encoding="utf-8")
    backup = tmp_path / "page.html"
    backup.write_text(original, encoding="utf-8")
    try:
        PAGE.write_text(mutation(original), encoding="utf-8")
        result = run(SYNC)
        assert result.returncode == 1, "divergence must fail the check"
        assert expected in result.stdout, (
            f"the failure must name what diverged; got:\n{result.stdout}"
        )
    finally:
        PAGE.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")


def test_check_fails_when_the_mermaid_source_gains_a_node(tmp_path):
    """The realistic failure: someone adds an agent to the specification and forgets the page."""
    original = README.read_text(encoding="utf-8")
    backup = tmp_path / "README.md"
    backup.write_text(original, encoding="utf-8")
    try:
        mutated = original.replace(
            '        dlq[["Dead letter queue"]]:::ingest',
            '        dlq[["Dead letter queue"]]:::ingest\n'
            '        shadow["Shadow scorer<br/>probe"]:::evalnode',
        )
        assert mutated != original, "the fixture anchor line changed; update this test"
        README.write_text(mutated, encoding="utf-8")
        result = run(SYNC)
        assert result.returncode == 1
        assert "shadow" in result.stdout
    finally:
        README.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")


def test_generator_rejects_a_node_it_has_no_layout_for(tmp_path):
    """Adding a node to the source must fail loudly rather than silently omit it."""
    original = README.read_text(encoding="utf-8")
    backup = tmp_path / "README.md"
    backup.write_text(original, encoding="utf-8")
    page_before = PAGE.read_text(encoding="utf-8")
    try:
        README.write_text(
            original.replace(
                '        dlq[["Dead letter queue"]]:::ingest',
                '        dlq[["Dead letter queue"]]:::ingest\n'
                '        shadow["Shadow scorer<br/>probe"]:::evalnode',
            ),
            encoding="utf-8",
        )
        result = run(RENDER)
        assert result.returncode != 0
        assert "shadow" in (result.stdout + result.stderr)
    finally:
        README.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")
        PAGE.write_text(page_before, encoding="utf-8")
