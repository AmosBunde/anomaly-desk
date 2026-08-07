"""Tests for the continuous integration workflow delivered by A4.

The workflow is the mechanism behind specification section 16.7, which states that merges
happen only with continuous integration green. A silently broken workflow file does not fail
loudly; GitHub reports it as a missing check, which is easy to read as "no checks configured"
and merge past. So its structure is asserted here, where a break shows up as a red test.

The specific failure this guards against is real: the first version of this file had a
missing colon after ``steps`` in one job, which made the whole document invalid YAML.
"""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# Each job maps to a requirement. The prose job enforces principle 9, the install job
# enforces the CPU-only constraint from section 4, and the smoke job is the section 16.7
# evaluation slice that A14 fills in.
REQUIRED_JOBS = ["lint", "test", "prose", "install", "smoke"]


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_workflow_is_valid_yaml(workflow):
    assert isinstance(workflow, dict), "the workflow must parse as a YAML mapping"


@pytest.mark.parametrize("job", REQUIRED_JOBS)
def test_required_job_present(job, workflow):
    assert job in workflow["jobs"], (
        f"the {job} job is required; see A4 in BREAKDOWN.md for what each job enforces"
    )


def test_jobs_are_independent(workflow):
    """Jobs must fail independently so a prose defect is distinguishable from a test failure.

    A `needs:` chain would make one red job mask every job after it, which is exactly the
    situation the issue said to avoid.
    """
    chained = [name for name, body in workflow["jobs"].items() if "needs" in body]
    assert not chained, f"these jobs declare needs and would mask downstream results: {chained}"


def test_runs_on_pull_request(workflow):
    # PyYAML parses the unquoted key `on` as the boolean True, so accept either form.
    triggers = workflow.get("on", workflow.get(True))
    assert triggers is not None, "the workflow must declare triggers"
    assert "pull_request" in triggers, "the workflow must run on pull requests to gate merges"


def test_prose_job_runs_the_linter(workflow):
    steps = workflow["jobs"]["prose"]["steps"]
    commands = " ".join(step.get("run", "") for step in steps)
    assert "scripts/prose_lint.py" in commands, "the prose job must run the prose linter"


def test_install_job_asserts_absence_of_cuda(workflow):
    """The CPU-only constraint is enforced in the pipeline, not only in make install.

    A2 found that the dependency set pulled the full CUDA stack on a machine with no GPU,
    and that nothing in the declaration mentioned CUDA. The pipeline therefore installs for
    real and asserts the outcome rather than trusting the declaration.
    """
    steps = workflow["jobs"]["install"]["steps"]
    commands = " ".join(step.get("run", "") for step in steps)
    assert "make install" in commands, "the install job must run the real install"
    assert "nvidia-" in commands and "cuda-" in commands, (
        "the install job must assert no CUDA packages were pulled in"
    )
    assert "+cpu" in commands, "the install job must assert the CPU-only torch build"


def test_smoke_job_distinguishes_unimplemented_from_broken(workflow):
    """An unimplemented target is a skip; a real failure is red.

    Treating every non-zero exit as a skip would let a genuinely broken evaluation slice
    pass continuous integration, which is the opposite of what section 16.7 wants.
    """
    steps = workflow["jobs"]["smoke"]["steps"]
    commands = " ".join(step.get("run", "") for step in steps)
    assert "is not implemented yet" in commands, (
        "the smoke job must recognise the unimplemented-target message specifically"
    )
    assert "::error::" in commands, (
        "the smoke job must fail loudly when make smoke fails for any other reason"
    )


def test_no_untrusted_event_interpolation():
    """Workflow injection guard.

    Interpolating github.event.* or github.head_ref into a run block lets a pull request
    title or branch name execute shell. Nothing here needs that data, so the safe state is
    none at all, and this test keeps it that way as the workflow grows.
    """
    raw = WORKFLOW.read_text(encoding="utf-8")
    for marker in ("github.event", "github.head_ref"):
        assert marker not in raw, (
            f"{marker} must not appear in the workflow; it is attacker-controlled input. "
            "Pass it through env: with quoting if it ever becomes necessary."
        )
