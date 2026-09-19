CREATE SCHEMA IF NOT EXISTS tg_p05a;

CREATE TABLE IF NOT EXISTS tg_p05a.customer_preferences (
    preference_id uuid PRIMARY KEY,
    subject_type text NOT NULL,
    subject_id text NOT NULL,
    category text NOT NULL,
    preference_key text NOT NULL,
    preference_value text NOT NULL,
    information_type text NOT NULL CHECK (information_type = 'CUSTOMER_STATED'),
    source_type text NOT NULL CHECK (source_type = 'conversation'),
    source_reference text NOT NULL,
    statement_reference text NOT NULL,
    purpose text NOT NULL,
    memory_permission_state_at_write text NOT NULL CHECK (memory_permission_state_at_write = 'ACTIVE'),
    stated_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL,
    correlation_id uuid NOT NULL,
    idempotency_key text NOT NULL,
    payload_fingerprint char(64) NOT NULL,
    status text NOT NULL CHECK (status IN ('ACTIVE', 'SUPERSEDED')),
    supersedes_preference_id uuid NULL REFERENCES tg_p05a.customer_preferences(preference_id),
    CONSTRAINT tg_p05a_preference_idempotency_unique UNIQUE (idempotency_key)
);

CREATE UNIQUE INDEX IF NOT EXISTS tg_p05a_one_active_preference
    ON tg_p05a.customer_preferences (subject_type, subject_id, preference_key)
    WHERE status = 'ACTIVE';
CREATE INDEX IF NOT EXISTS tg_p05a_preference_subject_history
    ON tg_p05a.customer_preferences (subject_id, preference_key, stated_at);
CREATE INDEX IF NOT EXISTS tg_p05a_preference_correlation
    ON tg_p05a.customer_preferences (correlation_id);

CREATE TABLE IF NOT EXISTS tg_p05a.preference_audit_events (
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
    preference_key text NOT NULL,
    idempotency_decision text NOT NULL,
    previous_preference_id uuid NULL REFERENCES tg_p05a.customer_preferences(preference_id),
    new_preference_id uuid NULL REFERENCES tg_p05a.customer_preferences(preference_id),
    tool_id text NOT NULL,
    tool_version text NOT NULL,
    execution_status text NOT NULL,
    error_classification text NULL,
    started_at timestamptz NOT NULL,
    completed_at timestamptz NOT NULL,
    permission_version text NOT NULL
);

CREATE INDEX IF NOT EXISTS tg_p05a_audit_subject
    ON tg_p05a.preference_audit_events (subject_id, preference_key);
CREATE INDEX IF NOT EXISTS tg_p05a_audit_correlation
    ON tg_p05a.preference_audit_events (correlation_id);
CREATE INDEX IF NOT EXISTS tg_p05a_audit_new_preference
    ON tg_p05a.preference_audit_events (new_preference_id);
