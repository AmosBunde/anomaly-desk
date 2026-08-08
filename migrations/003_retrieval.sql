-- Runbook chunks with provenance, and citations that can be verified. Sections 7 and 8.1.
--
-- The vector column lives here rather than in a separate service. A3 confirmed pgvector
-- inside PostgreSQL as the deployed topology, and this table is why: the citation-to-chunk
-- join stays inside a single query, which is what makes judge span verification simple.

CREATE TABLE runbook_chunks (
    -- Form DOCID:chunk-N, per specification section 7, so a citation is human-readable.
    chunk_id        text PRIMARY KEY,
    doc_id          text        NOT NULL,
    section_slug    text        NOT NULL,
    -- The exact span this chunk occupies in the normalized document. The judge checks a
    -- quoted span against these offsets rather than trusting the citation.
    span_start      integer     NOT NULL,
    span_end        integer     NOT NULL,
    body            text        NOT NULL,
    -- Pins the chunk to a corpus snapshot. A reindex that changes chunk boundaries must not
    -- silently invalidate citations recorded against the old boundaries.
    corpus_sha256   char(64)    NOT NULL,
    -- 384 dimensions: BAAI/bge-small-en-v1.5, the model pinned in specification section 4.
    embedding       vector(384),
    created_at      timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT runbook_chunks_span_ordered CHECK (span_end > span_start),
    CONSTRAINT runbook_chunks_span_nonnegative CHECK (span_start >= 0)
);

CREATE INDEX runbook_chunks_doc_idx ON runbook_chunks (doc_id);

CREATE TABLE citations (
    citation_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    triage_id       uuid        NOT NULL REFERENCES triages (triage_id) ON DELETE CASCADE,
    -- Nullable on purpose. A fabricated chunk_id is a scored grounding failure, and the judge
    -- must be able to record the fabrication rather than fail to insert it. A foreign key
    -- that rejected the row would hide exactly the failure this system is built to measure.
    chunk_id        text        REFERENCES runbook_chunks (chunk_id) ON DELETE SET NULL,
    -- What the drafting agent claimed the chunk says, kept verbatim so the judge can check it
    -- against the span rather than taking the citation on trust.
    quoted_text     text        NOT NULL,
    claimed_chunk_id text       NOT NULL,
    -- Set by the judge, not by the agent.
    span_verified   boolean,
    verification_note text,

    CONSTRAINT citations_quote_not_empty CHECK (length(trim(quoted_text)) > 0)
);

CREATE INDEX citations_triage_idx ON citations (triage_id);
CREATE INDEX citations_chunk_idx ON citations (chunk_id);

-- Which actions each citation supports. An uncited action is a scored failure, so the link is
-- explicit rather than inferred from ordering.
CREATE TABLE action_citations (
    action_id       uuid NOT NULL REFERENCES triage_actions (action_id) ON DELETE CASCADE,
    citation_id     uuid NOT NULL REFERENCES citations (citation_id) ON DELETE CASCADE,
    PRIMARY KEY (action_id, citation_id)
);
