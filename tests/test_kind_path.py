"""Structural tests for the Kubernetes path delivered by A5.

These parse the config and the installer rather than creating a cluster, so they run in
continuous integration without Docker. Cluster creation, health, and the memory measurement
were performed by hand and the transcript is in the pull request.

A5 landed at M0 rather than M5 to answer one question before A38 depends on it: does a
control plane fit alongside the Compose stack on this machine? It does, and the constraint
turned out to be host ports rather than memory. These tests encode what that cost to learn.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
KIND_CONFIG = REPO_ROOT / "deploy" / "kind-config.yaml"
INSTALLER = REPO_ROOT / "scripts" / "install_k8s_tools.sh"
RENDERER = REPO_ROOT / "scripts" / "render_kind_config.py"
MAKEFILE = REPO_ROOT / "Makefile"


def render(**env: str) -> dict:
    """Render the kind config the way make kind-up does, and parse the result."""
    environ = {**os.environ, **env}
    result = subprocess.run(
        [sys.executable, str(RENDERER)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        env=environ,
    )
    return yaml.safe_load(result.stdout)


def test_template_is_not_valid_yaml_until_rendered():
    """The raw template carries ${VAR} placeholders, which kind cannot interpolate itself.

    This asserts the reason the renderer exists: feeding the template straight to kind would
    pass an unsubstituted string as a port number.
    """
    raw = KIND_CONFIG.read_text(encoding="utf-8")
    assert "${API_PORT}" in raw and "${BIND_ADDRESS}" in raw


def test_rendered_config_is_valid_and_single_node():
    config = render()
    assert config["kind"] == "Cluster"
    nodes = config["nodes"]
    assert len(nodes) == 1, "one node: a second spends memory on scheduling A38 does not need"
    assert nodes[0]["role"] == "control-plane"


def test_declared_defaults_match_section_15():
    """Defaults must match README.md section 15 and docker-compose.yml.

    Two publishing paths disagreeing about which port the API is on would be a genuinely
    confusing thing to debug.

    This asserts the declared defaults rather than rendering with an empty environment,
    because a developer .env legitimately overrides the ports on this machine and the
    renderer is supposed to honour it. Testing the fallback by unsetting everything would
    test the .env file rather than the contract.
    """
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    try:
        import render_kind_config
    finally:
        sys.path.pop(0)

    assert render_kind_config.DEFAULTS["API_PORT"] == "8000"
    assert render_kind_config.DEFAULTS["UI_PORT"] == "3000"
    assert render_kind_config.DEFAULTS["BIND_ADDRESS"] == "127.0.0.1"


def test_rendered_host_ports_are_overridable():
    """kind collides with the Compose stack on host ports, so both must be movable.

    Found by A5: cluster creation failed on 127.0.0.1:3000, held by another project on this
    machine, with the same opaque Docker error the Compose preflight was written to replace.
    """
    config = render(API_PORT="28000", UI_PORT="23000")
    ports = {m["hostPort"] for m in config["nodes"][0]["extraPortMappings"]}
    assert ports == {28000, 23000}


def test_rendered_bind_address_defaults_to_loopback():
    """Same reasoning as issue 11: the kind default is 0.0.0.0, which exposes the node."""
    config = render(BIND_ADDRESS="")
    for mapping in config["nodes"][0]["extraPortMappings"]:
        assert mapping["listenAddress"] == "127.0.0.1"


def test_renderer_rejects_unknown_placeholders():
    """An unknown variable must fail loudly rather than render an empty port number."""
    raw = KIND_CONFIG.read_text(encoding="utf-8")
    assert "DEFAULTS" in RENDERER.read_text(encoding="utf-8")
    placeholders = set(re.findall(r"\$\{([A-Z_][A-Z0-9_]*)\}", raw))
    assert placeholders <= {"API_PORT", "UI_PORT", "BIND_ADDRESS"}, (
        f"unhandled placeholders would render empty: {placeholders}"
    )


@pytest.mark.parametrize("tool", ["kind", "kubectl", "helm"])
def test_installer_pins_a_version_for_every_tool(tool):
    """Unpinned installs drift from what the node image expects, months later."""
    makefile = MAKEFILE.read_text(encoding="utf-8")
    variable = f"{tool.upper()}_VERSION"
    assert re.search(rf"^{variable}\s*\?=\s*v?\d", makefile, re.MULTILINE), (
        f"{variable} must be a pinned Makefile variable so bumping it is a reviewed change"
    )


def test_installer_needs_no_sudo_and_installs_into_bin():
    installer = INSTALLER.read_text(encoding="utf-8")
    # Match an actual invocation rather than the word, which appears in a comment saying the
    # installer needs none. The first version of this test failed on its own documentation.
    code_lines = [
        line for line in installer.splitlines() if line.strip() and not line.strip().startswith("#")
    ]
    offenders = [line for line in code_lines if re.search(r"\bsudo\b", line)]
    assert not offenders, f"the toolchain must install without elevated privileges: {offenders}"
    assert 'BIN_DIR="${REPO_ROOT}/bin"' in installer
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert re.search(r"^bin/$", gitignore, re.MULTILINE), "bin/ must be gitignored"


def test_installer_is_idempotent():
    """A target that fails on second invocation gets worked around with manual cleanup, and
    manual cleanup is how a documented path stops matching what people actually do."""
    installer = INSTALLER.read_text(encoding="utf-8")
    assert "already_installed" in installer


def test_kind_targets_are_idempotent_and_preflighted():
    makefile = MAKEFILE.read_text(encoding="utf-8")
    assert "preflight_ports.py --kind" in makefile, (
        "kind-up must preflight host ports; the raw Docker error names neither the service "
        "nor a remedy"
    )
    assert "get clusters" in makefile, "kind-up must not fail when the cluster already exists"
    assert "nothing to delete" in makefile, "kind-down must not fail when there is no cluster"
