"""Skeleton tests for A2.

These assert structural properties the rest of the project depends on, so that A4 has real
assertions to run rather than an empty suite. Two of them encode rules from README.md that
would otherwise be enforced only by memory: hard rule 1 (no agent code before M1) and the
requirement that every run target in section 15 exists.
"""

import importlib
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Every subpackage README.md section 3 lists, except agents, which hard rule 1 defers to A22.
EXPECTED_SUBPACKAGES = [
    "consume",
    "evals",
    "ingest",
    "obs",
    "orchestrator",
    "policy",
    "retrieval",
    "serve",
]

# The run targets README.md section 15 promises. The deploy gate at A37 runs these same
# targets, so a missing one is a broken gate rather than a missing convenience.
SECTION_15_TARGETS = [
    "data",
    "index",
    "replay",
    "eval",
    "redteam",
    "smoke",
    "trace-report",
    "serve",
    "ui",
    "kind-up",
    "deploy",
    "gate",
]


def test_package_imports():
    module = importlib.import_module("anomalydesk")
    assert module.__version__ == "0.1.0"


@pytest.mark.parametrize("name", EXPECTED_SUBPACKAGES)
def test_subpackage_imports(name):
    module = importlib.import_module(f"anomalydesk.{name}")
    assert module.__doc__, f"anomalydesk.{name} must state its responsibility in a docstring"


def test_agents_subpackage_absent():
    """Hard rule 1: no agent code exists until the judge runs and the scoreboard prints.

    This is the ordering constraint most likely to be violated under time pressure, so it is
    asserted rather than remembered. A22 creates the subpackage together with the shared
    schemas; this test is updated in that pull request and not before.
    """
    assert not (REPO_ROOT / "anomalydesk" / "agents").exists(), (
        "anomalydesk/agents must not exist before A14 is merged. See BREAKDOWN.md "
        "ordering constraint 1 and README.md principle 1."
    )


@pytest.mark.parametrize("target", SECTION_15_TARGETS)
def test_makefile_declares_section_15_target(target):
    makefile = (REPO_ROOT / "Makefile").read_text()
    assert re.search(rf"^\.PHONY: {re.escape(target)}$", makefile, re.MULTILINE), (
        f"Makefile must declare the {target} target named in README.md section 15"
    )


def test_unimplemented_target_fails_loudly():
    """A declared-but-unimplemented target must exit non-zero and name its plan item.

    Exiting zero would make the deploy gate at A37 pass while running nothing.
    """
    result = subprocess.run(
        ["make", "eval"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0, "an unimplemented target must not exit zero"
    combined = result.stdout + result.stderr
    assert "A14" in combined, "the failure message must name the plan item that implements it"


def test_dependencies_are_declared_and_bounded():
    """Every dependency is implied by a README.md section; additions are owner decisions."""
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        config = tomllib.load(handle)

    declared = {re.split(r"[\[><=]", spec)[0].strip() for spec in config["project"]["dependencies"]}
    expected = {
        "anthropic",
        "pydantic",
        "confluent-kafka",
        "psycopg",
        "pgvector",
        "sentence-transformers",
        "fastapi",
        "uvicorn",
        "opentelemetry-sdk",
        "opentelemetry-exporter-otlp",
        "pyyaml",
    }
    assert declared == expected, (
        "the dependency set changed. Adding a dependency not implied by README.md is an "
        "owner decision per section 4, so update this test in the same pull request that "
        "records the decision."
    )


def test_requires_python_matches_the_running_interpreter():
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        config = tomllib.load(handle)
    assert config["project"]["requires-python"] == ">=3.12"
    assert sys.version_info >= (3, 12)
