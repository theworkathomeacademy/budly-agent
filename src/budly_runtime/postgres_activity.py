"""TG-P04 PostgreSQL persistence adapter for the accepted activity.record capability."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .tool_gateway import (
    ActivityAdapterContext, ActivityRecord, CapabilityDefinition, DurableActivityError,
    DurableActivityOutcome, ErrorClass, ResultStatus, ToolHealth, ToolRequest, utc_now,
    verify_adapter_provenance,
)

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - exercised by the health failure path
    psycopg = None
    dict_row = None


MIGRATION_PATH = Path(__file__).resolve().parents[2] / "migrations" / "tg_p04" / "001_activity_persistence.sql"


@dataclass
class PostgresActivityAdapter:
    dsn: str
    environment: str = "prototype"
    schema: str = "tg_p04"
    state: ToolHealth = ToolHealth.HEALTHY
    fail_write: bool = False
    fail_audit: bool = False
    fail_postcondition: bool = False
    tool_id: str = "postgres_activity_tg_p04"
    tool_version: str = "1.0"
    last_context: ActivityAdapterContext | None = None

    def __post_init__(self) -> None:
        if self.environment == "production":
            raise ValueError("TG-P04 persistent adapter refuses production")
        if self.environment not in {"automated_test", "development", "prototype"}:
            raise ValueError("TG-P04 environment is not allowed")
        if self.schema != "tg_p04":
            raise ValueError("TG-P04 schema must remain isolated")
        if psycopg is None:
            raise RuntimeError("psycopg is required for PostgresActivityAdapter")
        params = psycopg.conninfo.conninfo_to_dict(self.dsn)
        if params.get("host") not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("TG-P04 database must be localhost")
        if params.get("dbname") != "bros_tg_p04_test":
            raise ValueError("TG-P04 database must be bros_tg_p04_test")

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
        sql = MIGRATION_PATH.read_text(encoding="utf-8")
        with self._connect() as connection:
            connection.execute(sql)

    @staticmethod
    def _fingerprint(context: ActivityAdapterContext) -> str:
        payload = {
            "activity_type": context.activity_type,
            "subject": asdict(context.subject),
            "source": asdict(context.source),
            "channel": context.channel,
            "purpose": context.purpose,
            "occurred_at": context.occurred_at,
            "properties": context.properties,
            "fact_classification": context.fact_classification,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _record_from_row(row: dict[str, Any]) -> ActivityRecord:
        return ActivityRecord(
            str(row["activity_id"]), row["activity_type"], row["subject_type"], row["subject_id"],
            row["source_type"], row["source_id"], row["channel"], row["purpose"],
            row["occurred_at"].isoformat(), row["recorded_at"].isoformat(), str(row["correlation_id"]),
            row["idempotency_key"], dict(row["properties"]), row["fact_classification"], row["payload_fingerprint"],
        )

    def execute_durable(self, *, context: ActivityAdapterContext, request: ToolRequest,
                        definition: CapabilityDefinition, permission_version: str,
                        started_at: str, audit_event_id: str) -> DurableActivityOutcome:
        verify_adapter_provenance(getattr(context, "gateway_execution_context", None), request_id=request.request_id, capability_id=request.capability.capability_id)
        if self.environment == "production" or request.environment == "production":
            raise DurableActivityError(ErrorClass.ENVIRONMENT_DENIED, "persistent adapter refuses production", status=ResultStatus.DENIED)
        self.last_context = context
        fingerprint = self._fingerprint(context)
        activity_id = str(uuid4())
        completed_at = utc_now()
        conflict: DurableActivityError | None = None
        try:
            with self._connect() as connection:
                with connection.transaction():
                    cursor = connection.cursor()
                    cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (context.idempotency_key,))
                    cursor.execute(f"SELECT * FROM {self.schema}.activities WHERE idempotency_key = %s", (context.idempotency_key,))
                    existing_row = cursor.fetchone()
                    if existing_row is not None:
                        existing = self._record_from_row(existing_row)
                        decision = "DUPLICATE" if existing.semantic_fingerprint == fingerprint else "CONFLICT"
                        self._insert_audit(cursor, audit_event_id, request, definition, permission_version, started_at,
                                           completed_at, decision, existing.activity_id,
                                           None if decision == "DUPLICATE" else ErrorClass.IDEMPOTENCY_CONFLICT.value)
                        if decision == "CONFLICT":
                            conflict = DurableActivityError(
                                ErrorClass.IDEMPOTENCY_CONFLICT, "idempotency key payload conflict",
                                status=ResultStatus.DENIED, activity_id=existing.activity_id,
                                audit_event_id=audit_event_id,
                            )
                        else:
                            return DurableActivityOutcome(existing, False, True, decision, audit_event_id)
                    else:
                        if self.fail_write:
                            raise DurableActivityError(ErrorClass.WRITE_FAILED, "durable activity append failed", retryable=True)
                        cursor.execute(
                            f"""INSERT INTO {self.schema}.activities
                            (activity_id, activity_type, subject_type, subject_id, source_type, source_id, channel, purpose,
                             occurred_at, recorded_at, correlation_id, idempotency_key, payload_fingerprint,
                             fact_classification, properties)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                            (activity_id, context.activity_type, context.subject.subject_type, context.subject.subject_id,
                             context.source.source_type, context.source.source_id, context.channel, context.purpose,
                             context.occurred_at, completed_at, context.correlation_id, context.idempotency_key,
                             fingerprint, context.fact_classification, json.dumps(context.properties, sort_keys=True)),
                        )
                        if self.fail_audit:
                            raise DurableActivityError(ErrorClass.AUDIT_FAILURE, "required durable audit could not be persisted")
                        self._insert_audit(cursor, audit_event_id, request, definition, permission_version, started_at,
                                           completed_at, "CREATED", activity_id, None)
                        cursor.execute(
                            f"""SELECT COUNT(*) AS activity_count,
                            (SELECT COUNT(*) FROM {self.schema}.audit_events WHERE audit_event_id = %s AND activity_id = %s) AS audit_count
                            FROM {self.schema}.activities WHERE activity_id = %s AND idempotency_key = %s AND payload_fingerprint = %s""",
                            (audit_event_id, activity_id, activity_id, context.idempotency_key, fingerprint),
                        )
                        postcondition = cursor.fetchone()
                        if self.fail_postcondition or postcondition["activity_count"] != 1 or postcondition["audit_count"] != 1:
                            raise DurableActivityError(ErrorClass.POSTCONDITION_FAILED, "durable postcondition failed")
            if conflict is not None:
                raise conflict
            record = self.get(activity_id)
            if record is None:
                raise DurableActivityError(ErrorClass.POSTCONDITION_FAILED, "committed activity could not be read")
            return DurableActivityOutcome(record, True, False, "CREATED", audit_event_id)
        except DurableActivityError:
            raise
        except Exception as exc:
            raise DurableActivityError(ErrorClass.WRITE_FAILED, "durable activity transaction failed", retryable=True) from exc

    def _insert_audit(self, cursor: Any, audit_event_id: str, request: ToolRequest,
                      definition: CapabilityDefinition, permission_version: str, started_at: str,
                      completed_at: str, idempotency_decision: str, activity_id: str | None,
                      error_classification: str | None) -> None:
        cursor.execute(
            f"""INSERT INTO {self.schema}.audit_events
            (audit_event_id, request_id, correlation_id, actor_id, actor_type, capability_id,
             bros_authority_level, tool_authority_class, environment, channel, purpose, permission_decision,
             activity_type, idempotency_decision, activity_id, tool_id, tool_version, execution_status,
             error_classification, started_at, completed_at, permission_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ALLOW', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (audit_event_id, request.request_id, request.correlation_id, request.actor.actor_id,
             request.actor.actor_type, request.capability.capability_id, definition.bros_level,
             definition.tool_class, request.environment, request.channel, request.purpose,
             context_activity_type(request), idempotency_decision, activity_id, self.tool_id, self.tool_version,
             ResultStatus.DENIED.value if error_classification else ResultStatus.SUCCESS.value,
             error_classification, started_at, completed_at, permission_version),
        )

    def get(self, activity_id: str) -> ActivityRecord | None:
        with self._connect() as connection:
            row = connection.execute(f"SELECT * FROM {self.schema}.activities WHERE activity_id = %s", (activity_id,)).fetchone()
        return None if row is None else self._record_from_row(row)

    def get_by_idempotency_key(self, key: str) -> ActivityRecord | None:
        with self._connect() as connection:
            row = connection.execute(f"SELECT * FROM {self.schema}.activities WHERE idempotency_key = %s", (key,)).fetchone()
        return None if row is None else self._record_from_row(row)

    def count(self, key: str | None = None) -> int:
        where, params = (" WHERE idempotency_key = %s", (key,)) if key is not None else ("", ())
        with self._connect() as connection:
            row = connection.execute(f"SELECT COUNT(*) AS count FROM {self.schema}.activities{where}", params).fetchone()
        return int(row["count"])

    def audits_for_activity(self, activity_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM {self.schema}.audit_events WHERE activity_id = %s ORDER BY started_at", (activity_id,)
            ).fetchall()
        return [dict(row) for row in rows]


def context_activity_type(request: ToolRequest) -> str:
    return getattr(request.input, "activity_type", "unknown")
