-- Creates the extensions the stack depends on. The schema itself is owned by A8.
--
-- pgvector lives inside PostgreSQL rather than in a separate vector service, so the
-- citation-to-chunk join in README.md section 7 stays inside a single query. The health
-- check in docker-compose.yml asserts this extension exists, because pg_isready reports
-- readiness before the init scripts have run.
CREATE EXTENSION IF NOT EXISTS vector;

-- Used by A17 to build deterministic idempotency keys from event content.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
