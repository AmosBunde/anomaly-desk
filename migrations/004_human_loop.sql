-- Escalations, operator dispositions, and the second scoreboard. Sections 8.2 and 9.

CREATE TABLE escalations (
    escalation_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    triage_id       uuid        NOT NULL REFERENCES triages (triage_id) ON DELETE CASCADE,
    -- Which version of configs/escalation.yaml decided this. Hard rule 4 versions the policy,
    -- so a scored run must record which policy produced its escalations.
    policy_version  integer     NOT NULL,
    rule            text        NOT NULL,
    -- True for the unconditional rules, which a high confidence score never overrides.
    must_escalate   boolean     NOT NULL DEFAULT false,
    -- Set when the orchestrator failed, timed out, or exhausted its step budget. Every such
    -- path still produces a queue entry, so the reason is recorded rather than lost.
    degraded        boolean     NOT NULL DEFAULT false,
    queued_at       timestamptz NOT NULL DEFAULT now(),
    resolved_at     timestamptz,

    CONSTRAINT escalations_policy_version_positive CHECK (policy_version >= 1)
);

CREATE INDEX escalations_triage_idx ON escalations (triage_id);
CREATE INDEX escalations_unresolved_idx ON escalations (queued_at) WHERE resolved_at IS NULL;

-- Field-level operator dispositions. This is the second scoreboard.
--
-- Granularity is deliberate: a single boolean would tell us an operator changed something and
-- nothing about what, making the override rate far less useful than the effort of collecting
-- it. An override of severity is a different signal from an override of the action list.
CREATE TABLE dispositions (
    disposition_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    triage_id       uuid        NOT NULL REFERENCES triages (triage_id) ON DELETE CASCADE,
    operator        text        NOT NULL,
    verdict         text        NOT NULL,
    -- Which field was changed, null for a plain accept.
    field           text,
    old_value       text,
    new_value       text,
    note            text,
    created_at      timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT dispositions_verdict_known CHECK (verdict IN ('accept', 'edit', 'override')),
    CONSTRAINT dispositions_field_known CHECK (
        field IS NULL OR field IN ('severity', 'category', 'summary', 'actions', 'escalation')
    ),
    -- An accept changes nothing; an edit or override must say what it changed.
    CONSTRAINT dispositions_accept_has_no_field CHECK (
        (verdict = 'accept' AND field IS NULL) OR (verdict <> 'accept' AND field IS NOT NULL)
    )
);

CREATE INDEX dispositions_triage_idx ON dispositions (triage_id);
CREATE INDEX dispositions_verdict_idx ON dispositions (verdict);
