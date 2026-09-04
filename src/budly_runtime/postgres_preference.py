"""TG-P05A durable adapter for explicitly customer-stated preferences."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .preference_registry import PREFERENCE_REGISTRY
from .tool_gateway import (
    CapabilityDefinition, DurableActivityError, DurablePreferenceOutcome, ErrorClass,
    PreferenceAdapterContext, PreferenceRecord, ResultStatus, ToolHealth, ToolRequest, utc_now,
    verify_adapter_provenance,
)

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover
    psycopg = None
    dict_row = None

MIGRATION_PATH = Path(__file__).resolve().parents[2] / "migrations" / "tg_p05a" / "001_customer_preference.sql"


def preference_capability_definition(*, enabled: bool = True) -> CapabilityDefinition:
    return CapabilityDefinition(
        capability_id="customer.preference.record", capability_version="1.0", bros_level=1, tool_class="T2",
        enabled=enabled,
        allowed_purposes=frozenset({
            "conversation_continuity", "education_personalization", "approved_recommendation_context",
            "support_continuity", "internal_test",
        }),
        allowed_channels=frozenset({"website_chat", "internal_test", "admin_console"}),
        specifically_authorized_bounded_write=True,
    )


@dataclass
class PostgresPreferenceAdapter:
    dsn: str
    environment: str = "prototype"
    schema: str = "tg_p05a"
    state: ToolHealth = ToolHealth.HEALTHY
    fail_write: bool = False
    fail_audit: bool = False
    fail_postcondition: bool = False
    tool_id: str = "postgres_customer_preference_tg_p05a"
    tool_version: str = "1.0"
    last_context: PreferenceAdapterContext | None = None

    def __post_init__(self) -> None:
        if self.environment == "production":
            raise ValueError("TG-P05A persistent adapter refuses production")
        if self.environment not in {"automated_test", "development", "prototype"}:
            raise ValueError("TG-P05A environment is not allowed")
        if self.schema != "tg_p05a":
            raise ValueError("TG-P05A schema must remain isolated")
        if psycopg is None:
            raise RuntimeError("psycopg is required for PostgresPreferenceAdapter")
        params = psycopg.conninfo.conninfo_to_dict(self.dsn)
        if params.get("host") not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("TG-P05A database must be localhost")
        if params.get("dbname") != "bros_tg_p05a_test":
            raise ValueError("TG-P05A database must be bros_tg_p05a_test")

    def _connect(self):
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def health(self) -> ToolHealth:
        if self.state != ToolHealth.HEALTHY:
            return self.state
        try:
            with self._connect() as connection:
                connection.execute("SELECT 1")
            return ToolHealth.HEALTHY
        except Exception:
            return ToolHealth.UNAVAILABLE

    def apply_migration(self) -> None:
        with self._connect() as connection:
            connection.execute(MIGRATION_PATH.read_text(encoding="utf-8"))

    @staticmethod
    def _fingerprint(context: PreferenceAdapterContext) -> str:
        payload = {
            "subject": asdict(context.subject),
            "preference_key": context.preference.key,
            "preference_value": context.preference.value,
            "information_type": context.preference.information_type,
            "source": asdict(context.source),
            "purpose": context.memory_authorization.purpose,
            "stated_at": context.stated_at,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _record_from_row(row: dict[str, Any]) -> PreferenceRecord:
        return PreferenceRecord(
            str(row["preference_id"]), row["subject_type"], row["subject_id"], row["category"],
            row["preference_key"], row["preference_value"], row["information_type"], row["source_type"],
            row["source_reference"], row["statement_reference"], row["purpose"],
            row["memory_permission_state_at_write"], row["stated_at"].isoformat(), row["recorded_at"].isoformat(),
            str(row["correlation_id"]), row["idempotency_key"], row["payload_fingerprint"], row["status"],
            str(row["supersedes_preference_id"]) if row["supersedes_preference_id"] else None,
        )

    def execute_durable(self, *, context: PreferenceAdapterContext, request: ToolRequest,
                        definition: CapabilityDefinition, permission_version: str,
                        started_at: str, audit_event_id: str) -> DurablePreferenceOutcome:
        verify_adapter_provenance(getattr(context, "gateway_execution_context", None), request_id=request.request_id, capability_id=request.capability.capability_id)
        if self.environment == "production" or request.environment == "production":
            raise DurableActivityError(ErrorClass.ENVIRONMENT_DENIED, "persistent adapter refuses production", status=ResultStatus.DENIED)
        self.last_context = context
        fingerprint = self._fingerprint(context)
        preference_id = str(uuid4())
        completed_at = utc_now()
        conflict: DurableActivityError | None = None
        previous_id: str | None = None
        try:
            with self._connect() as connection:
                with connection.transaction():
                    cursor = connection.cursor()
                    cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (context.idempotency_key,))
                    subject_lock = f"{context.subject.subject_type}:{context.subject.subject_id}:{context.preference.key}"
                    cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (subject_lock,))
                    cursor.execute(f"SELECT * FROM {self.schema}.customer_preferences WHERE idempotency_key = %s", (context.idempotency_key,))
                    existing_row = cursor.fetchone()
                    if existing_row is not None:
                        existing = self._record_from_row(existing_row)
                        decision = "DUPLICATE" if existing.payload_fingerprint == fingerprint else "CONFLICT"
                        self._insert_audit(cursor, audit_event_id, request, definition, permission_version, started_at,
                                           completed_at, decision, existing.supersedes_preference_id, existing.preference_id,
                                           None if decision == "DUPLICATE" else ErrorClass.IDEMPOTENCY_CONFLICT.value)
                        if decision == "CONFLICT":
                            conflict = DurableActivityError(
                                ErrorClass.IDEMPOTENCY_CONFLICT, "idempotency key payload conflict",
                                status=ResultStatus.DENIED, activity_id=existing.preference_id,
                                audit_event_id=audit_event_id,
                            )
                        else:
                            return DurablePreferenceOutcome(existing, False, True, decision, audit_event_id, existing.supersedes_preference_id)
                    else:
                        if self.fail_write:
                            raise DurableActivityError(ErrorClass.WRITE_FAILED, "durable preference write failed", retryable=True)
                        cursor.execute(
                            f"""SELECT * FROM {self.schema}.customer_preferences
                            WHERE subject_type = %s AND subject_id = %s AND preference_key = %s AND status = 'ACTIVE'
                            FOR UPDATE""",
                            (context.subject.subject_type, context.subject.subject_id, context.preference.key),
                        )
                        previous_row = cursor.fetchone()
                        previous_id = str(previous_row["preference_id"]) if previous_row else None
                        if previous_id:
                            cursor.execute(
                                f"UPDATE {self.schema}.customer_preferences SET status = 'SUPERSEDED' WHERE preference_id = %s",
                                (previous_id,),
                            )
                        registry_entry = PREFERENCE_REGISTRY.definitions[context.preference.key]
                        cursor.execute(
                            f"""INSERT INTO {self.schema}.customer_preferences
                            (preference_id, subject_type, subject_id, category, preference_key, preference_value,
                             information_type, source_type, source_reference, statement_reference, purpose,
                             memory_permission_state_at_write, stated_at, recorded_at, correlation_id, idempotency_key,
                             payload_fingerprint, status, supersedes_preference_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVE', %s)""",
                            (preference_id, context.subject.subject_type, context.subject.subject_id, registry_entry.category,
                             context.preference.key, context.preference.value, context.preference.information_type,
                             context.source.source_type, context.source.source_reference, context.source.statement_reference,
                             context.memory_authorization.purpose, context.memory_authorization.state, context.stated_at,
                             completed_at, context.correlation_id, context.idempotency_key, fingerprint, previous_id),
                        )
                        if self.fail_audit:
                            raise DurableActivityError(ErrorClass.AUDIT_FAILURE, "required preference audit could not be persisted")
                        self._insert_audit(cursor, audit_event_id, request, definition, permission_version, started_at,
                                           completed_at, "CREATED", previous_id, preference_id, None)
                        cursor.execute(
                            f"""SELECT
                            (SELECT COUNT(*) FROM {self.schema}.customer_preferences WHERE preference_id = %s AND status = 'ACTIVE') AS new_count,
                            (SELECT COUNT(*) FROM {self.schema}.customer_preferences WHERE subject_id = %s AND preference_key = %s AND status = 'ACTIVE') AS active_count,
                            (SELECT COUNT(*) FROM {self.schema}.preference_audit_events WHERE audit_event_id = %s AND new_preference_id = %s) AS audit_count""",
                            (preference_id, context.subject.subject_id, context.preference.key, audit_event_id, preference_id),
                        )
                        postcondition = cursor.fetchone()
                        if self.fail_postcondition or any(postcondition[key] != 1 for key in ("new_count", "active_count", "audit_count")):
                            raise DurableActivityError(ErrorClass.POSTCONDITION_FAILED, "preference postcondition failed")
            if conflict is not None:
                raise conflict
            record = self.get(preference_id)
            if record is None:
                raise DurableActivityError(ErrorClass.POSTCONDITION_FAILED, "committed preference could not be read")
            return DurablePreferenceOutcome(record, True, False, "CREATED", audit_event_id, previous_id)
        except DurableActivityError:
            raise
        except Exception as exc:
            raise DurableActivityError(ErrorClass.WRITE_FAILED, "durable preference transaction failed", retryable=True) from exc

    def _insert_audit(self, cursor: Any, audit_event_id: str, request: ToolRequest,
                      definition: CapabilityDefinition, permission_version: str, started_at: str, completed_at: str,
                      idempotency_decision: str, previous_id: str | None, new_id: str | None,
                      error_classification: str | None) -> None:
        preference_input = request.input
        cursor.execute(
            f"""INSERT INTO {self.schema}.preference_audit_events
            (audit_event_id, request_id, correlation_id, actor_id, actor_type, subject_id, capability_id,
             bros_authority_level, tool_authority_class, environment, channel, purpose, permission_decision,
             memory_permission_state, preference_key, idempotency_decision, previous_preference_id,
             new_preference_id, tool_id, tool_version, execution_status, error_classification, started_at,
             completed_at, permission_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ALLOW', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (audit_event_id, request.request_id, request.correlation_id, request.actor.actor_id, request.actor.actor_type,
             preference_input.subject.subject_id, request.capability.capability_id, definition.bros_level,
             definition.tool_class, request.environment, request.channel, request.purpose,
             preference_input.memory_authorization.state, preference_input.preference.key, idempotency_decision,
             previous_id, new_id, self.tool_id, self.tool_version,
             ResultStatus.DENIED.value if error_classification else ResultStatus.SUCCESS.value,
             error_classification, started_at, completed_at, permission_version),
        )

    def get(self, preference_id: str) -> PreferenceRecord | None:
        with self._connect() as connection:
            row = connection.execute(f"SELECT * FROM {self.schema}.customer_preferences WHERE preference_id = %s", (preference_id,)).fetchone()
        return None if row is None else self._record_from_row(row)

    def history(self, subject_id: str, preference_key: str) -> list[PreferenceRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM {self.schema}.customer_preferences WHERE subject_id = %s AND preference_key = %s ORDER BY recorded_at",
                (subject_id, preference_key),
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def count(self) -> int:
        with self._connect() as connection:
            row = connection.execute(f"SELECT COUNT(*) AS count FROM {self.schema}.customer_preferences").fetchone()
        return int(row["count"])

    def audits_for_preference(self, preference_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM {self.schema}.preference_audit_events WHERE new_preference_id = %s ORDER BY started_at",
                (preference_id,),
            ).fetchall()
        return [dict(row) for row in rows]
