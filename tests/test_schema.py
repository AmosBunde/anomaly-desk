"""Tests for the schema and migration runner delivered by A8.

Split deliberately. The structural tests parse the SQL and the runner and execute in
continuous integration, where there is no database. The integration tests need the Compose
PostgreSQL and skip cleanly without it, so a contributor without the stack running still gets
a meaningful suite rather than a wall of errors.

The structural half carries the rules that outlive any one database: forward-only versioning,
no money in the ledger, and the constraints that encode the hard rules.
"""

import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = sorted((REPO_ROOT / "migrations").glob("*.sql"))
RUNNER = REPO_ROOT / "scripts" / "migrate.py"

DSN = (
    f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
    f"port={os.getenv('POSTGRES_PORT', '55432')} "
    f"dbname={os.getenv('POSTGRES_DB', 'anomalydesk')} "
    f"user={os.getenv('POSTGRES_USER', 'anomalydesk')} "
    f"password={os.getenv('POSTGRES_PASSWORD', 'anomalydesk')}"
)

EXPECTED_TABLES = {
    "events",
    "event_claims",
    "triages",
    "triage_actions",
    "runbook_chunks",
    "citations",
    "action_citations",
    "escalations",
    "dispositions",
    "token_ledger",
}


def sql_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in MIGRATIONS)


# ---------------------------------------------------------------------------
# Structural: no database required
# ---------------------------------------------------------------------------


def test_migrations_exist():
    assert MIGRATIONS, "no migrations found"


def test_every_migration_is_numerically_versioned():
    """The runner applies in lexical order, so the version prefix is the apply order."""
    versions = []
    for path in MIGRATIONS:
        prefix = path.name.split("_", 1)[0]
        assert prefix.isdigit(), f"{path.name} must start with a numeric version"
        versions.append(prefix)
    assert len(set(versions)) == len(versions), f"duplicate versions: {versions}"
    assert versions == sorted(versions)


def test_every_expected_table_is_created():
    created = set(re.findall(r"CREATE TABLE (\w+)", sql_text()))
    missing = EXPECTED_TABLES - created
    assert not missing, f"missing tables: {sorted(missing)}"


def test_token_ledger_stores_counts_not_money():
    """Hard rule 8 and section 4: rates live in one place and resolve at report time.

    A cost column would freeze the rate at write time, so a price change could not be applied
    to historical reports without reprocessing every row.
    """
    ledger = next(p for p in MIGRATIONS if "token_ledger" in p.name).read_text(encoding="utf-8")
    body = ledger[ledger.index("CREATE TABLE token_ledger") :]
    for forbidden in ("cost", "price", "usd", "dollar", "rate"):
        assert not re.search(rf"^\s+\w*{forbidden}\w*\s", body, re.M | re.I), (
            f"token_ledger must not carry a {forbidden} column; rates resolve at report time"
        )


def test_citation_chunk_reference_is_nullable():
    """A fabricated chunk identifier is a scored grounding failure, so it must be recordable.

    A non-null foreign key would reject the row and hide exactly the failure the judge exists
    to measure. `claimed_chunk_id` keeps what the agent actually said.
    """
    text = sql_text()
    block = text[text.index("CREATE TABLE citations") : text.index("CREATE INDEX citations_triage")]
    # Anchor to the start of a column definition. An unanchored "chunk_id" also matches
    # inside "claimed_chunk_id", which is NOT NULL, so the first version of this test failed
    # on the neighbouring column rather than on the one it was checking.
    declaration = re.search(r"^\s+chunk_id\s+text\s+(.*)$", block, re.M)
    assert declaration, "citations must declare a chunk_id column"
    assert "REFERENCES runbook_chunks" in declaration.group(1)
    assert "NOT NULL" not in declaration.group(1), (
        "citations.chunk_id must be nullable so a fabricated citation can be recorded"
    )
    assert "claimed_chunk_id" in block, "the agent's claimed identifier must be kept verbatim"


def test_embedding_dimension_matches_the_pinned_model():
    """BAAI/bge-small-en-v1.5 emits 384 dimensions, per specification section 4."""
    assert "vector(384)" in sql_text()


@pytest.mark.parametrize(
    "constraint",
    [
        "triages_escalation_has_reason",
        "triages_confidence_range",
        "triage_actions_side_effect_confirmed",
        "dispositions_accept_has_no_field",
        "events_offset_unique_per_source",
    ],
)
def test_constraints_encoding_the_hard_rules_exist(constraint):
    """Each of these makes a specification rule unenforceable to violate by accident."""
    assert constraint in sql_text(), f"{constraint} is missing"


def test_runner_is_forward_only_with_checksums():
    """Editing an applied migration must fail loudly rather than diverge silently."""
    runner = RUNNER.read_text(encoding="utf-8")
    assert "sha256" in runner
    assert "forward-only" in runner.lower()
    assert "have been edited" in runner, "the runner must detect an edited applied migration"


def test_no_orm_dependency_was_added():
    """The specification implies no ORM; adding one is an owner decision."""
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for orm in ("sqlalchemy", "alembic", "django", "tortoise", "peewee"):
        assert orm not in pyproject.lower(), f"{orm} was added without an owner decision"


# ---------------------------------------------------------------------------
# Integration: needs the Compose PostgreSQL
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def connection():
    psycopg = pytest.importorskip("psycopg")
    try:
        conn = psycopg.connect(DSN, connect_timeout=3)
    except Exception:  # noqa: BLE001 - any connection failure is a skip, not an error
        pytest.skip("Compose PostgreSQL is not reachable; run make up && make migrate")
    with conn:
        yield conn


def test_every_table_exists_in_the_database(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        )
        present = {row[0] for row in cursor.fetchall()}
    missing = EXPECTED_TABLES - present
    assert not missing, f"not applied: {sorted(missing)}. Run make migrate."
    connection.rollback()


def test_migrations_are_recorded_with_checksums(connection):
    with connection.cursor() as cursor:
        cursor.execute("SELECT version, sha256 FROM schema_migrations ORDER BY version")
        rows = cursor.fetchall()
    assert len(rows) == len(MIGRATIONS)
    for _, digest in rows:
        assert re.fullmatch(r"[0-9a-f]{64}", digest)
    connection.rollback()


def test_a_fabricated_citation_can_be_recorded(connection):
    """The judge must be able to persist the failure it found, not be blocked by the schema."""
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO events (event_id, offset_index, source, observed_at, kind, body, "
            "source_sha256) VALUES ('evt-fab', 9001, 'loghub-hdfs', now(), 'log_burst', 'x', "
            "repeat('a',64))"
        )
        cursor.execute(
            "INSERT INTO triages (event_id, variant, severity, category, confidence, summary) "
            "VALUES ('evt-fab','t','sev3','unknown',0.5,'s') RETURNING triage_id"
        )
        triage_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO citations (triage_id, chunk_id, claimed_chunk_id, quoted_text, "
            "span_verified) VALUES (%s, NULL, 'rb-99:chunk-1', 'invented', false)",
            (triage_id,),
        )
    connection.rollback()


@pytest.mark.parametrize(
    ("label", "sql"),
    [
        (
            "escalated with no reason",
            "INSERT INTO triages (event_id,variant,severity,category,confidence,summary,escalated)"
            " VALUES ('evt-rej','t','sev2','hardware',0.5,'s',true)",
        ),
        (
            "confidence above one",
            "INSERT INTO triages (event_id,variant,severity,category,confidence,summary)"
            " VALUES ('evt-rej','t','sev2','hardware',1.5,'s')",
        ),
        (
            "unknown severity",
            "INSERT INTO triages (event_id,variant,severity,category,confidence,summary)"
            " VALUES ('evt-rej','t','sev9','hardware',0.5,'s')",
        ),
    ],
)
def test_database_rejects_what_the_hard_rules_forbid(connection, label, sql):
    psycopg = pytest.importorskip("psycopg")
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO events (event_id, offset_index, source, observed_at, kind, body, "
            "source_sha256) VALUES ('evt-rej', 9002, 'loghub-hdfs', now(), 'log_burst', 'x', "
            "repeat('a',64))"
        )
        with pytest.raises(psycopg.errors.Error):
            cursor.execute(sql)
    connection.rollback()
