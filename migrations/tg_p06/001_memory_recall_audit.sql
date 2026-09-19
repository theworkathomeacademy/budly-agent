CREATE SCHEMA IF NOT EXISTS tg_p06;

CREATE TABLE IF NOT EXISTS tg_p06.memory_recall_audit_events (
    audit_event_id UUID PRIMARY KEY,
    request_id UUID NOT NULL,
    correlation_id UUID NOT NULL,
    actor_id TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    capability_id TEXT NOT NULL CHECK (capability_id = 'customer.memory.retrieve'),
    bros_authority_level SMALLINT NOT NULL CHECK (bros_authority_level = 1),
    tool_authority_class TEXT NOT NULL CHECK (tool_authority_class = 'T0'),
    environment TEXT NOT NULL CHECK (environment <> 'production'),
    channel TEXT NOT NULL,
    purpose TEXT NOT NULL,
    identity_verification_state TEXT NOT NULL,
    session_memory_use_state TEXT NOT NULL,
    memory_classes_considered TEXT[] NOT NULL,
    memory_ids_selected UUID[] NOT NULL,
    functional_count INTEGER NOT NULL CHECK (functional_count BETWEEN 0 AND 5),
    relationship_count INTEGER NOT NULL CHECK (relationship_count BETWEEN 0 AND 1),
    recall_modes TEXT[] NOT NULL,
    permission_decision TEXT NOT NULL,
    execution_status TEXT NOT NULL,
    error_classification TEXT NULL,
    tool_id TEXT NOT NULL,
    tool_version TEXT NOT NULL,
    permission_version TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS tg_p06_recall_audit_correlation
    ON tg_p06.memory_recall_audit_events (correlation_id);
CREATE INDEX IF NOT EXISTS tg_p06_recall_audit_subject
    ON tg_p06.memory_recall_audit_events (subject_id, completed_at);
