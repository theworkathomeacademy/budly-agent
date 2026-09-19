CREATE SCHEMA IF NOT EXISTS bae_audit;

CREATE TABLE IF NOT EXISTS bae_audit.audit_events (
    audit_event_id uuid PRIMARY KEY,
    event_type text NOT NULL,
    objective_id uuid NOT NULL,
    action_id uuid NOT NULL,
    correlation_id uuid NOT NULL,
    parent_action_id uuid NULL,
    retry_attempt_number integer NOT NULL DEFAULT 1,
    root_action_id uuid NULL,
    capability_id text NOT NULL,
    capability_version text NOT NULL,
    actor_id text NOT NULL,
    actor_type text NOT NULL,
    environment text NOT NULL,
    channel text NOT NULL,
    purpose text NOT NULL,
    authority_level text NULL,
    autonomy_maturity text NULL,
    approval_level text NULL,
    tool_authority_class text NULL,
    execution_state text NOT NULL,
    verification_state text NULL,
    verification_outcome text NULL,
    verification_evidence_ref text NULL,
    verification_method text NULL,
    verification_source text NULL,
    idempotency_key text NULL,
    idempotency_decision text NULL,
    authorization_decision_status text NULL,
    authorization_denial_reason text NULL,
    error_classification text NULL,
    kill_switch_active boolean NOT NULL DEFAULT false,
    human_override_active boolean NOT NULL DEFAULT false,
    policy_version text NOT NULL DEFAULT '1.0',
    payload_hash text NULL,
    sanitized_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL,
    persisted_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS bae_audit_events_action_idx
    ON bae_audit.audit_events (action_id, occurred_at);

CREATE INDEX IF NOT EXISTS bae_audit_events_objective_idx
    ON bae_audit.audit_events (objective_id, occurred_at);

CREATE INDEX IF NOT EXISTS bae_audit_events_correlation_idx
    ON bae_audit.audit_events (correlation_id);

CREATE INDEX IF NOT EXISTS bae_audit_events_parent_action_idx
    ON bae_audit.audit_events (parent_action_id);

CREATE TABLE IF NOT EXISTS bae_audit.evidence_records (
    evidence_id uuid PRIMARY KEY,
    objective_id uuid NOT NULL,
    action_id uuid NOT NULL,
    correlation_id uuid NOT NULL,
    evidence_class text NOT NULL,
    verification_method text NOT NULL,
    source_identifier text NOT NULL,
    postcondition_name text NOT NULL,
    observed_state_hash text NOT NULL,
    expected_state_hash text NOT NULL,
    provenance_token_id text NULL,
    collector_actor_id text NOT NULL,
    collected_at timestamptz NOT NULL,
    persisted_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sanitized_observed_data jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS bae_evidence_action_idx
    ON bae_audit.evidence_records (action_id);

CREATE INDEX IF NOT EXISTS bae_evidence_objective_idx
    ON bae_audit.evidence_records (objective_id);

-- Append-only enforcement: prohibit UPDATE and DELETE at database boundary
CREATE OR REPLACE FUNCTION bae_audit.prohibit_audit_mutation()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Append-only violation: modifying or deleting records in % is prohibited', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_events_append_only ON bae_audit.audit_events;
CREATE TRIGGER trg_audit_events_append_only
    BEFORE UPDATE OR DELETE ON bae_audit.audit_events
    FOR EACH ROW EXECUTE FUNCTION bae_audit.prohibit_audit_mutation();

DROP TRIGGER IF EXISTS trg_evidence_records_append_only ON bae_audit.evidence_records;
CREATE TRIGGER trg_evidence_records_append_only
    BEFORE UPDATE OR DELETE ON bae_audit.evidence_records
    FOR EACH ROW EXECUTE FUNCTION bae_audit.prohibit_audit_mutation();

-- Least privilege runtime role configuration:
-- Ensures governed runtime identity (if provisioned) possesses ONLY INSERT and SELECT privileges.
-- Explicitly revokes and prevents UPDATE, DELETE, and TRUNCATE.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bae_runtime_user') THEN
        GRANT USAGE ON SCHEMA bae_audit TO bae_runtime_user;
        REVOKE ALL ON bae_audit.audit_events FROM bae_runtime_user;
        GRANT INSERT, SELECT ON bae_audit.audit_events TO bae_runtime_user;
        REVOKE ALL ON bae_audit.evidence_records FROM bae_runtime_user;
        GRANT INSERT, SELECT ON bae_audit.evidence_records TO bae_runtime_user;
    END IF;
END
$$;
