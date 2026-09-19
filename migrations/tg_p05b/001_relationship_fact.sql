CREATE SCHEMA IF NOT EXISTS tg_p05b;

CREATE TABLE IF NOT EXISTS tg_p05b.relationship_facts (
    relationship_fact_id uuid PRIMARY KEY,
    subject_type text NOT NULL,
    subject_id text NOT NULL,
    fact_category text NOT NULL,
    fact_key text NOT NULL,
    fact_value jsonb NOT NULL,
    information_type text NOT NULL CHECK (information_type = 'CUSTOMER_STATED_RELATIONSHIP_FACT'),
    certainty text NOT NULL CHECK (certainty IN ('EXPLICIT', 'CONFIRMED')),
    sensitivity_class text NOT NULL CHECK (sensitivity_class = 'R1'),
    source_type text NOT NULL CHECK (source_type = 'conversation'),
    source_reference text NOT NULL,
    statement_reference text NOT NULL,
    source_context_summary text NOT NULL,
    purpose text NOT NULL,
    memory_permission_state_at_write text NOT NULL CHECK (memory_permission_state_at_write = 'ACTIVE'),
    stated_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL,
    request_id uuid NOT NULL,
    correlation_id uuid NOT NULL,
    idempotency_key text NOT NULL,
    payload_fingerprint char(64) NOT NULL,
    status text NOT NULL CHECK (status IN ('ACTIVE', 'UPCOMING', 'PAST', 'SUPERSEDED', 'ARCHIVED')),
    supersedes_fact_id uuid NULL REFERENCES tg_p05b.relationship_facts(relationship_fact_id),
    event_date_or_period text NULL,
    related_person_context jsonb NULL,
    supersession_scope text NOT NULL CHECK (supersession_scope IN ('SUBJECT_KEY', 'NONE')),
    CONSTRAINT tg_p05b_fact_idempotency_unique UNIQUE (idempotency_key)
);

CREATE UNIQUE INDEX IF NOT EXISTS tg_p05b_one_active_singleton_fact
    ON tg_p05b.relationship_facts (subject_type, subject_id, fact_key)
    WHERE supersession_scope = 'SUBJECT_KEY' AND status IN ('ACTIVE', 'UPCOMING');
CREATE INDEX IF NOT EXISTS tg_p05b_fact_subject_history
    ON tg_p05b.relationship_facts (subject_id, fact_key, stated_at);
CREATE INDEX IF NOT EXISTS tg_p05b_fact_correlation
    ON tg_p05b.relationship_facts (correlation_id);

CREATE TABLE IF NOT EXISTS tg_p05b.relationship_fact_audit_events (
    audit_event_id uuid PRIMARY KEY,
    request_id uuid NOT NULL,
    correlation_id uuid NOT NULL,
    actor_id text NOT NULL,
    actor_type text NOT NULL,
    subject_id text NOT NULL,
    capability_id text NOT NULL,
    bros_authority_level integer NOT NULL,
    tool_authority_class text NOT NULL,
    environment text NOT NULL,
    channel text NOT NULL,
    purpose text NOT NULL,
    permission_decision text NOT NULL,
    memory_permission_state text NOT NULL,
    fact_key text NOT NULL,
    sensitivity_class text NOT NULL,
    idempotency_decision text NOT NULL,
    previous_fact_id uuid NULL REFERENCES tg_p05b.relationship_facts(relationship_fact_id),
    new_fact_id uuid NULL REFERENCES tg_p05b.relationship_facts(relationship_fact_id),
    tool_id text NOT NULL,
    tool_version text NOT NULL,
    execution_status text NOT NULL,
    error_classification text NULL,
    started_at timestamptz NOT NULL,
    completed_at timestamptz NOT NULL,
    permission_version text NOT NULL
);

CREATE INDEX IF NOT EXISTS tg_p05b_audit_subject
    ON tg_p05b.relationship_fact_audit_events (subject_id, fact_key);
CREATE INDEX IF NOT EXISTS tg_p05b_audit_correlation
    ON tg_p05b.relationship_fact_audit_events (correlation_id);
CREATE INDEX IF NOT EXISTS tg_p05b_audit_new_fact
    ON tg_p05b.relationship_fact_audit_events (new_fact_id);
