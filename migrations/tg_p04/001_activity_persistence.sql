CREATE SCHEMA IF NOT EXISTS tg_p04;

CREATE TABLE IF NOT EXISTS tg_p04.activities (
    activity_id uuid PRIMARY KEY,
    activity_type text NOT NULL,
    subject_type text NOT NULL,
    subject_id text NOT NULL,
    source_type text NOT NULL,
    source_id text NOT NULL,
    channel text NOT NULL,
    purpose text NOT NULL,
    occurred_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL,
    correlation_id uuid NOT NULL,
    idempotency_key text NOT NULL,
    payload_fingerprint char(64) NOT NULL,
    fact_classification text NOT NULL,
    properties jsonb NOT NULL,
    CONSTRAINT tg_p04_activities_idempotency_key_unique UNIQUE (idempotency_key)
);

CREATE INDEX IF NOT EXISTS tg_p04_activities_correlation_idx
    ON tg_p04.activities (correlation_id);

CREATE TABLE IF NOT EXISTS tg_p04.audit_events (
    audit_event_id uuid PRIMARY KEY,
    request_id uuid NOT NULL,
    correlation_id uuid NOT NULL,
    actor_id text NOT NULL,
    actor_type text NOT NULL,
    capability_id text NOT NULL,
    bros_authority_level integer NOT NULL,
    tool_authority_class text NOT NULL,
    environment text NOT NULL,
    channel text NOT NULL,
    purpose text NOT NULL,
    permission_decision text NOT NULL,
    activity_type text NOT NULL,
    idempotency_decision text NOT NULL,
    activity_id uuid NULL REFERENCES tg_p04.activities(activity_id),
    tool_id text NOT NULL,
    tool_version text NOT NULL,
    execution_status text NOT NULL,
    error_classification text NULL,
    started_at timestamptz NOT NULL,
    completed_at timestamptz NOT NULL,
    permission_version text NOT NULL
);

CREATE INDEX IF NOT EXISTS tg_p04_audit_activity_idx
    ON tg_p04.audit_events (activity_id);
CREATE INDEX IF NOT EXISTS tg_p04_audit_correlation_idx
    ON tg_p04.audit_events (correlation_id);
