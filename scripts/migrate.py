#!/usr/bin/env python3
"""Apply forward-only SQL migrations, recording a checksum for each.

Plain SQL applied by a small runner rather than an ORM or a migration framework. The
specification implies neither, and adding one is an owner decision under the deviation policy.

Forward-only with checksums is the load-bearing choice. Schema churn through M2 to M4 is
certain, and the failure mode to prevent is editing a migration that some database has already
applied: the edit then exists in the file and not in that database, and the two disagree
silently forever. This runner records the checksum at apply time and refuses to proceed when a
recorded migration's content has changed, so that disagreement is loud.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

import psycopg

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = REPO_ROOT / "migrations"

BOOTSTRAP = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     text PRIMARY KEY,
    filename    text        NOT NULL,
    sha256      char(64)    NOT NULL,
    applied_at  timestamptz NOT NULL DEFAULT now()
);
"""


def dsn() -> str:
    return (
        f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
        f"port={os.getenv('POSTGRES_PORT', '5432')} "
        f"dbname={os.getenv('POSTGRES_DB', 'anomalydesk')} "
        f"user={os.getenv('POSTGRES_USER', 'anomalydesk')} "
        f"password={os.getenv('POSTGRES_PASSWORD', 'anomalydesk')}"
    )


def discover() -> list[tuple[str, Path]]:
    """Return (version, path) in lexical order, which is apply order."""
    found = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = path.name.split("_", 1)[0]
        if not version.isdigit():
            raise SystemExit(
                f"{path.name}: migrations must start with a numeric version, as in 001_name.sql"
            )
        found.append((version, path))

    versions = [v for v, _ in found]
    duplicates = {v for v in versions if versions.count(v) > 1}
    if duplicates:
        raise SystemExit(f"duplicate migration versions: {sorted(duplicates)}")
    return found


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report status without applying")
    args = parser.parse_args(argv)

    migrations = discover()
    if not migrations:
        print("migrate: no migrations found", file=sys.stderr)
        return 2

    try:
        connection = psycopg.connect(dsn())
    except psycopg.OperationalError as error:
        print(
            f"migrate: cannot reach PostgreSQL: {error}\nStart the stack with: make up",
            file=sys.stderr,
        )
        return 2

    with connection:
        with connection.cursor() as cursor:
            cursor.execute(BOOTSTRAP)
            cursor.execute("SELECT version, filename, sha256 FROM schema_migrations")
            applied = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
        connection.commit()

        # Detect an edited applied migration before applying anything, so a divergent database
        # is never partially advanced on top of a file that no longer matches it.
        drift = []
        for version, path in migrations:
            if version in applied and applied[version][1] != sha256(path):
                drift.append((version, path.name, applied[version][1], sha256(path)))
        if drift:
            print("migrate: applied migrations have been edited:", file=sys.stderr)
            for version, name, recorded, actual in drift:
                print(f"  {version} {name}", file=sys.stderr)
                print(f"    recorded {recorded}", file=sys.stderr)
                print(f"    actual   {actual}", file=sys.stderr)
            print(
                "\nMigrations are forward-only. This database applied a different version of "
                "the file, so the two now disagree and no later migration can be trusted. "
                "Write a new migration that makes the change instead of editing this one.",
                file=sys.stderr,
            )
            return 1

        pending = [(v, p) for v, p in migrations if v not in applied]
        print(f"migrate: {len(applied)} applied, {len(pending)} pending")

        if args.check:
            for version, path in pending:
                print(f"  pending {version} {path.name}")
            return 1 if pending else 0

        for version, path in pending:
            print(f"  applying {version} {path.name}")
            # Each migration is one transaction: a failure leaves nothing half applied.
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(path.read_text(encoding="utf-8"))
                cursor.execute(
                    "INSERT INTO schema_migrations (version, filename, sha256) VALUES (%s, %s, %s)",
                    (version, path.name, sha256(path)),
                )

        if pending:
            print(f"\napplied {len(pending)} migration(s)")
        else:
            print("  nothing to do")
    return 0


if __name__ == "__main__":
    sys.exit(main())
