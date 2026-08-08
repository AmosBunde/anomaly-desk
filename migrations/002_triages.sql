-- Triage output and its citations. Per README.md sections 6 and 7.

CREATE TABLE triages (
    triage_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        text        NOT NULL REFERENCES events (event_id) ON DELETE CASCADE,
    -- Which configuration produced this triage. Every scored comparison is between variants,
    -- so a triage with no variant is not comparable to anything.
    variant         text        NOT NULL,
    severity        text        NOT NULL,
    category        text        NOT NULL,
    -- A number the escalation policy reads, per hard rule 2. Not prose, not optional.
    confidence      numeric(4, 3) NOT NULL,
    summary         text        NOT NULL,
    -- Set by the orchestrator, never by an agent. An agent's requires_operator is advisory.
    escalated       boolean     NOT NULL DEFAULT false,
    escalation_reason text,
    -- Counted rather than reinterpreted, per hard rule 2.
    schema_violations integer   NOT NULL DEFAULT 0,
    step_count      integer     NOT NULL DEFAULT 0,
    latency_ms      integer,
    created_at      timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT triages_severity_known CHECK (severity IN ('sev1', 'sev2', 'sev3', 'sev4')),
    CONSTRAINT triages_category_known CHECK (
        category IN ('capacity', 'hardware', 'config', 'dependency', 'security', 'unknown')
    ),
    CONSTRAINT triages_confidence_range CHECK (confidence >= 0 AND confidence <= 1),
    CONSTRAINT triages_violations_nonnegative CHECK (schema_violations >= 0),
    -- An escalated triage must say why, so a queue entry is never unexplained to the operator.
    CONSTRAINT triages_escalation_has_reason CHECK (
        (escalated = false) OR (escalation_reason IS NOT NULL)
    )
);

CREATE INDEX triages_event_idx ON triages (event_id);
CREATE INDEX triages_variant_idx ON triages (variant);

CREATE TABLE triage_actions (
    action_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    triage_id       uuid        NOT NULL REFERENCES triages (triage_id) ON DELETE CASCADE,
    step            integer     NOT NULL,
    action          text        NOT NULL,
    -- True when the action changes state. Specification section 12 requires an operator
    -- confirmation for these, enforced in the orchestrator rather than requested in a prompt.
    side_effecting  boolean     NOT NULL DEFAULT false,
    confirmed_by    text,
    confirmed_at    timestamptz,

    CONSTRAINT triage_actions_step_positive CHECK (step >= 1),
    CONSTRAINT triage_actions_step_unique UNIQUE (triage_id, step),
    -- A side-effecting action with no confirmation must not be recorded as executed.
    CONSTRAINT triage_actions_side_effect_confirmed CHECK (
        (side_effecting = false) OR (confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)
    )
);

CREATE INDEX triage_actions_triage_idx ON triage_actions (triage_id);
