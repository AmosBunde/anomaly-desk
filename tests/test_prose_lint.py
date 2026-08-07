"""Tests for the prose linter delivered by A4.

The linter enforces README.md principle 9 and the definition of done. These tests assert it
against a fixture with one violation per rule, and assert the exemptions that keep it from
becoming an obstacle: a contraction inside a shell transcript is data, not prose, but a
placeholder inside one is still unfinished work.

The false positive these tests were written to prevent is real rather than hypothetical. The
first version of the article rule flagged "a one-row ledger update" in BREAKDOWN.md, because
it read the hyphenated compound rather than its first component. A rule that fires on correct
prose gets the whole check switched off, so the exemption cases below matter as much as the
detection cases.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LINTER = REPO_ROOT / "scripts" / "prose_lint.py"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "prose_violations.md"

# (line, rule) pairs the fixture must produce. Line numbers are asserted deliberately: a
# linter that reports a count without locating anything is not actionable at merge time.
EXPECTED = [
    (10, "dash"),  # em dash in prose
    (11, "dash"),  # en dash in prose
    (12, "contraction"),  # isn't
    (13, "placeholder"),  # TODO in prose
    (14, "article"),  # an grounding
    (32, "placeholder"),  # TODO inside a fenced code block, still reported
]


def run_linter(*paths: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LINTER), *[str(p) for p in paths]],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def parse_findings(stdout: str) -> list[tuple[int, str]]:
    findings = []
    for line in stdout.splitlines():
        if ":" not in line or line.startswith(" ") or line.startswith("prose_lint:"):
            continue
        parts = line.split(":")
        if len(parts) < 4:
            continue
        try:
            lineno = int(parts[1])
        except ValueError:
            continue
        findings.append((lineno, parts[3].strip()))
    return findings


def test_tracked_documents_are_clean():
    """The merged specification and plan must pass, reproducing their merge-time state."""
    result = run_linter()
    assert result.returncode == 0, (
        f"tracked Markdown must be clean, but the linter reported:\n{result.stdout}"
    )


def test_fixture_reports_every_rule():
    result = run_linter(FIXTURE)
    assert result.returncode == 1, "a file with violations must exit 1"
    findings = parse_findings(result.stdout)
    assert findings == EXPECTED, (
        f"expected {EXPECTED}\ngot {findings}\nfull output:\n{result.stdout}"
    )


@pytest.mark.parametrize("rule", ["dash", "contraction", "placeholder", "article"])
def test_each_rule_fires_at_least_once(rule):
    findings = parse_findings(run_linter(FIXTURE).stdout)
    assert any(found_rule == rule for _, found_rule in findings), (
        f"the {rule} rule did not fire on the fixture, so it is not being exercised"
    )


def test_contraction_inside_code_fence_is_exempt():
    """A contraction in a shell transcript is data. Flagging it would be a false positive."""
    findings = parse_findings(run_linter(FIXTURE).stdout)
    fence_body = range(20, 27)
    contractions_in_fence = [
        line for line, rule in findings if rule == "contraction" and line in fence_body
    ]
    assert not contractions_in_fence, (
        f"contractions inside a fenced block must be exempt, but lines "
        f"{contractions_in_fence} were reported"
    )


def test_article_error_inside_code_fence_is_exempt():
    findings = parse_findings(run_linter(FIXTURE).stdout)
    fence_body = range(20, 27)
    articles_in_fence = [
        line for line, rule in findings if rule == "article" and line in fence_body
    ]
    assert not articles_in_fence, (
        f"article errors inside a fenced block must be exempt, but lines "
        f"{articles_in_fence} were reported"
    )


def test_placeholder_inside_code_fence_is_still_reported():
    """Unfinished work is unfinished wherever it appears."""
    findings = parse_findings(run_linter(FIXTURE).stdout)
    assert (32, "placeholder") in findings, (
        "a TODO inside a fenced code block must still be reported"
    )


def test_inline_code_is_stripped_before_prose_rules():
    findings = parse_findings(run_linter(FIXTURE).stdout)
    assert not any(line == 36 for line, _ in findings), (
        "a contraction inside an inline code span must not be reported"
    )


@pytest.mark.parametrize(
    "text",
    [
        "The gate enforces an SLA on recall.",
        "The judge reads an HTTP endpoint.",
        "This is an XML document and an F1 score.",
        "A one-row ledger update is bookkeeping.",
        "The run takes an hour on eight cores.",
        "This is a unique identifier.",
        "The console shows a user-facing field.",
        "It returns a URL and an offset.",
        "This is an M0 milestone and an M5 target.",
    ],
)
def test_correct_article_usage_is_not_reported(text, tmp_path):
    """Initialisms and consonant-sound vowels must not produce false positives.

    An initialism starting with a vowel-sound letter takes "an" (an SLA, an HTTP, an F1),
    a word spelled with a vowel but spoken with a consonant takes "a" (a unique, a user),
    and a hyphenated compound agrees with its first component (a one-row update).
    """
    sample = tmp_path / "sample.md"
    sample.write_text(text + "\n", encoding="utf-8")
    result = run_linter(sample)
    article_findings = [f for f in parse_findings(result.stdout) if f[1] == "article"]
    assert not article_findings, f"false positive on correct prose: {result.stdout}"


@pytest.mark.parametrize(
    "text",
    [
        "The gate enforces a SLA on recall.",
        "This is a M5 target.",
        "It reads a HTTP endpoint.",
        "The judge writes a XML report.",
    ],
)
def test_a_before_vowel_sound_initialism_is_reported(text, tmp_path):
    """The rule must fire in both directions, not only on "an" before a consonant.

    Each initialism here begins with a letter spoken as a vowel sound (S, M, H, X), so it
    takes "an". The M5 case was found by this suite: it was written into a not-reported
    fixture by mistake and the linter correctly rejected it.
    """
    sample = tmp_path / "sample.md"
    sample.write_text(text + "\n", encoding="utf-8")
    result = run_linter(sample)
    findings = parse_findings(result.stdout)
    assert (1, "article") in findings, (
        f"{text!r} must be reported; the initialism is spoken beginning with a vowel "
        f"sound. Output:\n{result.stdout}"
    )


def test_missing_file_is_an_error_not_a_pass():
    """A typo in a path must not look like a clean run."""
    result = run_linter(REPO_ROOT / "does-not-exist.md")
    assert result.returncode == 2, "a missing file must exit 2, distinct from clean or dirty"
