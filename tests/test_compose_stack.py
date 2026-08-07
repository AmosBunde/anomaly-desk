"""Structural tests for the Compose stack delivered by A3.

These parse docker-compose.yml rather than running it, so they execute in continuous
integration without a Docker daemon. Runtime behavior (services reaching healthy, the
pgvector round trip, the Kafka round trip, OTLP ingestion) was verified by hand and the
transcript is in the pull request; automating that needs a daemon in the pipeline, which is
a larger change than this issue.

What these guard is the class of mistake that is invisible until it costs an afternoon: a
service without a health check, a dependant that does not wait for it, a replication factor
left at its default of 3 on a single broker, or a memory limit quietly removed.
"""

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSE = REPO_ROOT / "docker-compose.yml"

EXPECTED_SERVICES = {"postgres", "kafka", "otel-collector", "api", "ui"}

# Compose interpolation is ${VAR:-default}, so a naive split(":") on a port mapping cuts
# the default value in half. Blank each expression to a single token before splitting.
VARIABLE_RE = re.compile(r"\$\{[^}]*\}")


def split_port_mapping(mapping: object) -> list[str]:
    """Split a port mapping into fields, treating ${VAR:-default} as one opaque field."""
    text = str(mapping)
    placeholders: list[str] = []

    def stash(match: re.Match[str]) -> str:
        placeholders.append(match.group(0))
        return f"\x00{len(placeholders) - 1}\x00"

    masked = VARIABLE_RE.sub(stash, text)
    fields = masked.split(":")
    return [
        re.sub(r"\x00(\d+)\x00", lambda m: placeholders[int(m.group(1))], field) for field in fields
    ]


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_exactly_the_expected_services(compose):
    assert set(compose["services"]) == EXPECTED_SERVICES


def test_no_separate_vector_service(compose):
    """The vector store lives inside PostgreSQL, per the confirmed deviation in BREAKDOWN.md.

    Reintroducing a standalone vector service would split the citation-to-chunk join across
    two stores and add a container to a constrained memory budget. If that is ever the right
    call it is an owner decision, not a quiet addition.
    """
    images = " ".join(
        str(service.get("image", "")) for service in compose["services"].values()
    ).lower()
    for forbidden in ("qdrant", "weaviate", "milvus", "chroma"):
        assert forbidden not in images, (
            f"{forbidden} would be a second vector store; the confirmed decision is pgvector "
            "inside PostgreSQL"
        )
    assert "pgvector" in compose["services"]["postgres"]["image"]


@pytest.mark.parametrize("name", sorted(EXPECTED_SERVICES))
def test_every_service_declares_a_health_check(name, compose):
    """A stack that reports itself up before it is usable produces failures that look like
    application bugs. A8 in particular would see schema errors from a PostgreSQL still
    running its init scripts."""
    assert "healthcheck" in compose["services"][name], (
        f"{name} has no health check, so dependants cannot wait for it"
    )


@pytest.mark.parametrize("name", sorted(EXPECTED_SERVICES))
def test_every_service_declares_a_memory_limit(name, compose):
    """Declared limits make the stack fail against the budget loudly rather than meeting the
    kernel out-of-memory killer, which presents as an unexplained container death."""
    limits = compose["services"][name].get("deploy", {}).get("resources", {}).get("limits", {})
    assert limits.get("memory"), f"{name} declares no memory limit"


def test_api_waits_for_its_dependencies_to_be_healthy(compose):
    depends = compose["services"]["api"]["depends_on"]
    for dependency in ("postgres", "kafka"):
        assert depends[dependency]["condition"] == "service_healthy", (
            f"api must wait for {dependency} to be healthy, not merely started"
        )


def test_postgres_health_check_verifies_the_vector_extension(compose):
    """pg_isready reports readiness before the init scripts have run.

    Checking only pg_isready would let a dependant start against a database with no vector
    extension, and the failure would surface at A19 as a missing type rather than a race.
    """
    test = " ".join(str(x) for x in compose["services"]["postgres"]["healthcheck"]["test"])
    assert "pg_isready" in test
    assert "pg_extension" in test and "vector" in test, (
        "the health check must confirm the vector extension exists, not just that the "
        "server accepts connections"
    )


def test_kafka_runs_in_kraft_mode_without_zookeeper(compose):
    env = compose["services"]["kafka"]["environment"]
    assert "KAFKA_PROCESS_ROLES" in env, "KRaft mode requires KAFKA_PROCESS_ROLES"
    assert "controller" in env["KAFKA_PROCESS_ROLES"]
    images = " ".join(str(s.get("image", "")) for s in compose["services"].values()).lower()
    assert "zookeeper" not in images, "the confirmed decision is KRaft with no ZooKeeper"


@pytest.mark.parametrize(
    "setting",
    [
        "KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR",
        "KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR",
    ],
)
def test_replication_factors_suit_a_single_broker(setting, compose):
    """Left at their default of 3, internal topic creation fails on a one-node cluster.

    The symptom is a broker that reports healthy while every produce call times out, which
    is a genuinely confusing failure to debug from the outside.
    """
    assert int(compose["services"]["kafka"]["environment"][setting]) == 1


def test_kafka_heap_is_bounded(compose):
    """The default JVM heap sizes itself from host memory.

    On a 30 GB machine that reserves far more than this stack's share of the roughly 7 GB
    actually available.
    """
    assert "-Xmx" in compose["services"]["kafka"]["environment"]["KAFKA_HEAP_OPTS"]


def test_host_ports_are_overridable(compose):
    """The development machine runs other stacks holding 5432, 8000, and 3000.

    Specification section 15 fixes the API on 8000 and the console on 3000, so the defaults
    are right and the override is what makes the stack runnable alongside them.
    """
    for name in EXPECTED_SERVICES:
        for mapping in compose["services"][name].get("ports", []):
            fields = split_port_mapping(mapping)
            host_side = fields[-2]
            assert not host_side.isdigit(), (
                f"{name} publishes host port {host_side} with no override variable, so it "
                "cannot coexist with another stack already holding that port"
            )


def test_api_dockerfile_installs_cpu_only_torch():
    """The image would otherwise carry the CUDA stack A2 removed from local installs.

    Same defect, different surface: the container installs from the same pyproject.toml, so
    without the CPU index it reintroduces gigabytes of GPU libraries into a memory
    constrained stack.
    """
    dockerfile = (REPO_ROOT / "docker" / "api.Dockerfile").read_text(encoding="utf-8")
    assert "download.pytorch.org/whl/cpu" in dockerfile
    assert "nvidia-" in dockerfile and "cuda-" in dockerfile, (
        "the image build must fail if CUDA packages are present"
    )


def test_api_image_runs_as_a_non_root_user():
    dockerfile = (REPO_ROOT / "docker" / "api.Dockerfile").read_text(encoding="utf-8")
    assert "USER appuser" in dockerfile, "the API container must not run as root"


@pytest.mark.parametrize("name", sorted(EXPECTED_SERVICES))
def test_published_ports_bind_to_loopback_by_default(name, compose):
    """Every published port must carry an explicit bind address defaulting to loopback.

    A Compose mapping written as "5432:5432" binds 0.0.0.0. On an untrusted network that
    exposes PostgreSQL with its development password and a Kafka broker with no
    authentication at all, which is the defect an automated review found in 923993a after
    A3 merged.

    This asserts the shape rather than the runtime binding, so it runs without a daemon and
    fails when a service is added without a bind address rather than after someone notices.
    """
    for mapping in compose["services"][name].get("ports", []):
        fields = split_port_mapping(mapping)
        assert len(fields) == 3, (
            f"{name} publishes {mapping!r} with no bind address, so it binds 0.0.0.0. "
            'Use "${BIND_ADDRESS:-127.0.0.1}:<host>:<container>".'
        )
        bind = fields[0]
        assert "BIND_ADDRESS" in bind or bind == "127.0.0.1", (
            f"{name} publishes {mapping!r}; the bind address must default to loopback"
        )
        assert "0.0.0.0" not in bind or "BIND_ADDRESS" in bind, (
            f"{name} binds {bind!r} unconditionally"
        )


def test_bind_address_default_is_loopback(compose):
    """The default must be loopback everywhere, not merely overridable."""
    raw = COMPOSE.read_text(encoding="utf-8")
    assert "${BIND_ADDRESS:-127.0.0.1}" in raw
    assert "${BIND_ADDRESS:-0.0.0.0}" not in raw, (
        "defaulting the bind address to 0.0.0.0 defeats the purpose of the variable"
    )
