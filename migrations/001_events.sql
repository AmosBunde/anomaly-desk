-- Events and idempotency. Per README.md sections 5 and 2.
--
-- event_claims exists so a redelivered Kafka message cannot produce a second triage. A17
-- claims by idempotency key before any agent work begins, which is why the claim table is
-- separate from events: the claim is a concurrency primitive, the event is data.

CREATE TABLE events (
    event_id        text PRIMARY KEY,
    -- Assigned by the producer in a stable order for a given snapshot. The replayer emits a
    -- fixed list of these, which is what specification section 10 pins.
    offset_index    bigint      NOT NULL,
    source          text        NOT NULL,
    observed_at     timestamptz NOT NULL,
    kind            text        NOT NULL,
    -- Deliberately nullable and never trusted as a label. A label derived from the source is
    -- not an independent measurement of the system that reads the source.
    severity_hint   text,
    body            text        NOT NULL,
    attributes      jsonb       NOT NULL DEFAULT '{}'::jsonb,
    -- Ties every event back to the pinned snapshot in configs/sources.yaml.
    source_sha256   char(64)    NOT NULL,
    ingested_at     timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT events_offset_unique_per_source UNIQUE (source, offset_index),
    CONSTRAINT events_kind_known CHECK (
        kind IN ('log_burst', 'api_log', 'hardware_alert', 'ticket', 'metric_alert')
    )
);

CREATE INDEX events_offset_idx ON events (offset_index);
CREATE INDEX events_source_idx ON events (source);

CREATE TABLE event_claims (
    -- Derived from event content by A17, so the same event always yields the same key.
    idempotency_key text PRIMARY KEY,
    event_id        text        NOT NULL REFERENCES events (event_id) ON DELETE CASCADE,
    claimed_at      timestamptz NOT NULL DEFAULT now(),
    -- A claim that is never released is how a crashed consumer blocks an event forever, so
    -- the release is recorded rather than the row deleted.
    released_at     timestamptz,
    attempt         integer     NOT NULL DEFAULT 1,

    CONSTRAINT event_claims_attempt_positive CHECK (attempt >= 1)
);

CREATE INDEX event_claims_event_idx ON event_claims (event_id);
