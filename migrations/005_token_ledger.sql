-- Token accounting. Per README.md section 4 and hard rule 8.
--
-- The ledger stores counts and never money. Rates live in exactly one place,
-- configs/models.yaml, and are resolved at report time, so a price change alters every
-- historical report without reprocessing a single row. A cost column here would freeze the
-- rate at write time and make that impossible.

CREATE TABLE token_ledger (
    entry_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Nullable: the judge charges tokens against a triage, but a corpus embedding run charges
    -- against no event at all, and both belong in one ledger.
    event_id        text        REFERENCES events (event_id) ON DELETE CASCADE,
    triage_id       uuid        REFERENCES triages (triage_id) ON DELETE CASCADE,
    -- Which hop spent this: classifier, retrieval, drafting, judge, embedding.
    hop             text        NOT NULL,
    model           text        NOT NULL,
    backend         text        NOT NULL,
    input_tokens            integer NOT NULL DEFAULT 0,
    output_tokens           integer NOT NULL DEFAULT 0,
    cache_read_input_tokens integer NOT NULL DEFAULT 0,
    cache_creation_input_tokens integer NOT NULL DEFAULT 0,
    attempt         integer     NOT NULL DEFAULT 1,
    created_at      timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT token_ledger_hop_known CHECK (
        hop IN ('classifier', 'retrieval', 'drafting', 'orchestrator', 'judge', 'embedding')
    ),
    CONSTRAINT token_ledger_backend_known CHECK (backend IN ('api', 'local', 'fake')),
    CONSTRAINT token_ledger_counts_nonnegative CHECK (
        input_tokens >= 0 AND output_tokens >= 0
        AND cache_read_input_tokens >= 0 AND cache_creation_input_tokens >= 0
    )
);

CREATE INDEX token_ledger_event_idx ON token_ledger (event_id);
CREATE INDEX token_ledger_triage_idx ON token_ledger (triage_id);
CREATE INDEX token_ledger_hop_idx ON token_ledger (hop);
