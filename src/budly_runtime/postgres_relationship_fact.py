"""TG-P05B durable adapter for bounded customer-stated relationship facts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .relationship_registry import RELATIONSHIP_FACT_REGISTRY
from .tool_gateway import (
    CapabilityDefinition, DurableActivityError, DurableRelationshipFactOutcome, ErrorClass,
    RelationshipFactAdapterContext, RelationshipFactRecord, ResultStatus, ToolHealth, ToolRequest, utc_now,
    verify_adapter_provenance,
)

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover
    psycopg = None
    dict_row = None

MIGRATION_PATH = Path(__file__).resolve().parents[2] / "migrations" / "tg_p05b" / "001_relationship_fact.sql"


def relationship_fact_capability_definition(*, enabled: bool = True) -> CapabilityDefinition:
    return CapabilityDefinition(
        capability_id="customer.relationship_fact.record", capability_version="1.0", bros_level=1, tool_class="T2",
        enabled=enabled,
        allowed_purposes=frozenset({
            "conversation_continuity", "relationship_continuity", "customer_service",
            "appropriate_personalization", "support_continuity", "internal_test",
        }),
        allowed_channels=frozenset({"website_chat", "internal_test", "admin_console"}),
        specifically_authorized_bounded_write=True,
    )


@dataclass
class PostgresRelationshipFactAdapter:
    dsn: str
    environment: str = "prototype"
    schema: str = "tg_p05b"
    state: ToolHealth = ToolHealth.HEALTHY
    fail_write: bool = False
    fail_audit: bool = False
    fail_postcondition: bool = False
    tool_id: str = "postgres_relationship_fact_tg_p05b"
    tool_version: str = "1.0"
    last_context: RelationshipFactAdapterContext | None = None

    def __post_init__(self) -> None:
        if self.environment == "production":
            raise ValueError("TG-P05B persistent adapter refuses production")
        if self.environment not in {"automated_test", "development", "prototype"}:
            raise ValueError("TG-P05B environment is not allowed")
        if self.schema != "tg_p05b":
            raise ValueError("TG-P05B schema must remain isolated")
        if psycopg is None:
            raise RuntimeError("psycopg is required for PostgresRelationshipFactAdapter")
        params = psycopg.conninfo.conninfo_to_dict(self.dsn)
        if params.get("host") not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("TG-P05B database must be localhost")
        if params.get("dbname") != "bros_tg_p05b_test":
            raise ValueError("TG-P05B database must be bros_tg_p05b_test")

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
    def _fingerprint(context: RelationshipFactAdapterContext) -> str:
        payload = {
            "subject": asdict(context.subject), "fact_key": context.relationship_fact.fact_key,
            "fact_value": context.relationship_fact.fact_value,
            "information_type": context.relationship_fact.information_type,
            "certainty": context.relationship_fact.certainty, "source": asdict(context.source),
            "purpose": context.memory_authorization.purpose, "stated_at": context.stated_at,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _record_from_row(row: dict[str, Any]) -> RelationshipFactRecord:
        return RelationshipFactRecord(
            str(row["relationship_fact_id"]), row["subject_type"], row["subject_id"], row["fact_category"],
            row["fact_key"], dict(row["fact_value"]), row["information_type"], row["certainty"],
            row["sensitivity_class"], row["source_type"], row["source_reference"], row["statement_reference"],
            row["source_context_summary"], row["purpose"], row["memory_permission_state_at_write"],
            row["stated_at"].isoformat(), row["recorded_at"].isoformat(), str(row["request_id"]),
            str(row["correlation_id"]), row["idempotency_key"], row["payload_fingerprint"], row["status"],
            str(row["supersedes_fact_id"]) if row["supersedes_fact_id"] else None,
            row["event_date_or_period"], dict(row["related_person_context"]) if row["related_person_context"] else None,
        )

    def execute_durable(self, *, context: RelationshipFactAdapterContext, request: ToolRequest,
                        definition: CapabilityDefinition, permission_version: str,
                        started_at: str, audit_event_id: str) -> DurableRelationshipFactOutcome:
        verify_adapter_provenance(getattr(context, "gateway_execution_context", None), request_id=request.request_id, capability_id=request.capability.capability_id)
        if self.environment == "production" or request.environment == "production":
            raise DurableActivityError(ErrorClass.ENVIRONMENT_DENIED, "persistent adapter refuses production", status=ResultStatus.DENIED)
        self.last_context = context
        registry_entry = RELATIONSHIP_FACT_REGISTRY.definitions[context.relationship_fact.fact_key]
        fingerprint = self._fingerprint(context)
        fact_id, completed_at = str(uuid4()), utc_now()
        conflict: DurableActivityError | None = None
        previous_id: str | None = None
        try:
            with self._connect() as connection:
                with connection.transaction():
                    cursor = connection.cursor()
                    cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (context.idempotency_key,))
                    scope_lock = f"{context.subject.subject_type}:{context.subject.subject_id}:{context.relationship_fact.fact_key}"
                    cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (scope_lock,))
                    cursor.execute(f"SELECT * FROM {self.schema}.relationship_facts WHERE idempotency_key = %s", (context.idempotency_key,))
                    existing_row = cursor.fetchone()
                    if existing_row is not None:
                        existing = self._record_from_row(existing_row)
                        decision = "DUPLICATE" if existing.payload_fingerprint == fingerprint else "CONFLICT"
                        self._insert_audit(cursor, audit_event_id, request, definition, permission_version, started_at,
                                           completed_at, decision, existing.supersedes_fact_id, existing.relationship_fact_id,
                                           None if decision == "DUPLICATE" else ErrorClass.IDEMPOTENCY_CONFLICT.value)
                        if decision == "CONFLICT":
                            conflict = DurableActivityError(
                                ErrorClass.IDEMPOTENCY_CONFLICT, "idempotency key payload conflict",
                                status=ResultStatus.DENIED, activity_id=existing.relationship_fact_id,
                                audit_event_id=audit_event_id,
                            )
                        else:
                            return DurableRelationshipFactOutcome(existing, False, True, decision, audit_event_id, existing.supersedes_fact_id)
                    else:
                        if self.fail_write:
                            raise DurableActivityError(ErrorClass.WRITE_FAILED, "durable relationship-fact write failed", retryable=True)
                        if registry_entry.supersession == "SUBJECT_KEY":
                            cursor.execute(
                                f"""SELECT * FROM {self.schema}.relationship_facts
                                WHERE subject_type = %s AND subject_id = %s AND fact_key = %s
                                AND status IN ('ACTIVE', 'UPCOMING') FOR UPDATE""",
                                (context.subject.subject_type, context.subject.subject_id, context.relationship_fact.fact_key),
                            )
                            previous_row = cursor.fetchone()
                            previous_id = str(previous_row["relationship_fact_id"]) if previous_row else None
                            if previous_id:
                                cursor.execute(
                                    f"UPDATE {self.schema}.relationship_facts SET status = 'SUPERSEDED' WHERE relationship_fact_id = %s",
                                    (previous_id,),
                                )
                        value = context.relationship_fact.fact_value
                        event_period = str(value.get("event_period")) if value.get("event_period") is not None else None
                        related_keys = {"first_name", "relationship", "is_minor", "stated_age", "birthday_month", "birthday_day", "related_person_first_name", "related_person_relationship"}
                        related_context = {key: value[key] for key in related_keys if key in value} if registry_entry.related_person else None
                        cursor.execute(
                            f"""INSERT INTO {self.schema}.relationship_facts
                            (relationship_fact_id, subject_type, subject_id, fact_category, fact_key, fact_value,
                             information_type, certainty, sensitivity_class, source_type, source_reference,
                             statement_reference, source_context_summary, purpose, memory_permission_state_at_write,
                             stated_at, recorded_at, request_id, correlation_id, idempotency_key, payload_fingerprint,
                             status, supersedes_fact_id, event_date_or_period, related_person_context, supersession_scope)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                            (fact_id, context.subject.subject_type, context.subject.subject_id, registry_entry.category,
                             context.relationship_fact.fact_key, json.dumps(value, sort_keys=True),
                             context.relationship_fact.information_type, context.relationship_fact.certainty,
                             registry_entry.sensitivity, context.source.source_type, context.source.source_reference,
                             context.source.statement_reference, context.source.source_context_summary,
                             context.memory_authorization.purpose, context.memory_authorization.state,
                             context.stated_at, completed_at, context.request_id, context.correlation_id,
                             context.idempotency_key, fingerprint, registry_entry.initial_status, previous_id,
                             event_period, json.dumps(related_context, sort_keys=True) if related_context else None,
                             registry_entry.supersession),
                        )
                        if self.fail_audit:
                            raise DurableActivityError(ErrorClass.AUDIT_FAILURE, "required relationship-fact audit could not be persisted")
                        self._insert_audit(cursor, audit_event_id, request, definition, permission_version, started_at,
                                           completed_at, "CREATED", previous_id, fact_id, None)
                        cursor.execute(
                            f"""SELECT
                            (SELECT COUNT(*) FROM {self.schema}.relationship_facts WHERE relationship_fact_id = %s) AS fact_count,
                            (SELECT COUNT(*) FROM {self.schema}.relationship_fact_audit_events WHERE audit_event_id = %s AND new_fact_id = %s) AS audit_count""",
                            (fact_id, audit_event_id, fact_id),
                        )
                        postcondition = cursor.fetchone()
                        if self.fail_postcondition or postcondition["fact_count"] != 1 or postcondition["audit_count"] != 1:
                            raise DurableActivityError(ErrorClass.POSTCONDITION_FAILED, "relationship-fact postcondition failed")
            if conflict is not None:
                raise conflict
            record = self.get(fact_id)
            if record is None:
                raise DurableActivityError(ErrorClass.POSTCONDITION_FAILED, "committed relationship fact could not be read")
            return DurableRelationshipFactOutcome(record, True, False, "CREATED", audit_event_id, previous_id)
        except DurableActivityError:
            raise
        except Exception as exc:
            raise DurableActivityError(ErrorClass.WRITE_FAILED, "durable relationship-fact transaction failed", retryable=True) from exc

    def _insert_audit(self, cursor: Any, audit_event_id: str, request: ToolRequest,
                      definition: CapabilityDefinition, permission_version: str, started_at: str, completed_at: str,
                      idempotency_decision: str, previous_id: str | None, new_id: str | None,
                      error_classification: str | None) -> None:
        item = request.input
        registry_entry = RELATIONSHIP_FACT_REGISTRY.definitions[item.relationship_fact.fact_key]
        cursor.execute(
            f"""INSERT INTO {self.schema}.relationship_fact_audit_events
            (audit_event_id, request_id, correlation_id, actor_id, actor_type, subject_id, capability_id,
             bros_authority_level, tool_authority_class, environment, channel, purpose, permission_decision,
             memory_permission_state, fact_key, sensitivity_class, idempotency_decision, previous_fact_id,
             new_fact_id, tool_id, tool_version, execution_status, error_classification, started_at,
             completed_at, permission_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ALLOW', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (audit_event_id, request.request_id, request.correlation_id, request.actor.actor_id, request.actor.actor_type,
             item.subject.subject_id, request.capability.capability_id, definition.bros_level, definition.tool_class,
             request.environment, request.channel, request.purpose, item.memory_authorization.state,
             item.relationship_fact.fact_key, registry_entry.sensitivity, idempotency_decision, previous_id, new_id,
             self.tool_id, self.tool_version, ResultStatus.DENIED.value if error_classification else ResultStatus.SUCCESS.value,
             error_classification, started_at, completed_at, permission_version),
        )

    def get(self, fact_id: str) -> RelationshipFactRecord | None:
        with self._connect() as connection:
            row = connection.execute(f"SELECT * FROM {self.schema}.relationship_facts WHERE relationship_fact_id = %s", (fact_id,)).fetchone()
        return None if row is None else self._record_from_row(row)

    def history(self, subject_id: str, fact_key: str) -> list[RelationshipFactRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM {self.schema}.relationship_facts WHERE subject_id = %s AND fact_key = %s ORDER BY recorded_at",
                (subject_id, fact_key),
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def count(self) -> int:
        with self._connect() as connection:
            row = connection.execute(f"SELECT COUNT(*) AS count FROM {self.schema}.relationship_facts").fetchone()
        return int(row["count"])

    def audits_for_fact(self, fact_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM {self.schema}.relationship_fact_audit_events WHERE new_fact_id = %s ORDER BY started_at",
                (fact_id,),
            ).fetchall()
        return [dict(row) for row in rows]
