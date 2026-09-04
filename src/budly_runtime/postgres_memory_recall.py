"""TG-P06 governed read-only recall across accepted preference/fact stores."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .memory_recall_policy import MEMORY_RECALL_POLICY
from .tool_gateway import (
    CapabilityDefinition, DurableActivityError, ErrorClass, MemoryRecallAdapterContext,
    MemoryRecallOutcome, ResultStatus, ToolHealth, ToolRequest, utc_now,
    verify_adapter_provenance,
)

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover
    psycopg = None
    dict_row = None

MIGRATION_PATH = Path(__file__).resolve().parents[2] / "migrations" / "tg_p06" / "001_memory_recall_audit.sql"


def memory_recall_capability_definition(*, enabled: bool = True) -> CapabilityDefinition:
    return CapabilityDefinition(
        capability_id="customer.memory.retrieve", capability_version="1.0", bros_level=1, tool_class="T0",
        enabled=enabled,
        allowed_purposes=frozenset(MEMORY_RECALL_POLICY.purposes),
        allowed_channels=frozenset({"website_chat", "internal_test", "admin_console"}),
    )


@dataclass
class PostgresMemoryRecallAdapter:
    preference_dsn: str
    relationship_dsn: str
    audit_dsn: str
    environment: str = "prototype"
    state: ToolHealth = ToolHealth.HEALTHY
    tool_id: str = "postgres_customer_memory_recall_tg_p06"
    tool_version: str = "1.0"
    last_context: MemoryRecallAdapterContext | None = None

    def __post_init__(self) -> None:
        if self.environment == "production" or self.environment not in {"automated_test", "development", "prototype"}:
            raise ValueError("TG-P06 adapter refuses environment")
        if psycopg is None:
            raise RuntimeError("psycopg is required for PostgresMemoryRecallAdapter")
        expected = {
            self.preference_dsn: "bros_tg_p05a_test",
            self.relationship_dsn: "bros_tg_p05b_test",
            self.audit_dsn: "bros_tg_p06_test",
        }
        for dsn, database in expected.items():
            params = psycopg.conninfo.conninfo_to_dict(dsn)
            if params.get("host") not in {"127.0.0.1", "localhost", "::1"} or params.get("dbname") != database:
                raise ValueError("TG-P06 database routing must remain isolated and local")

    @staticmethod
    def _connect(dsn: str):
        return psycopg.connect(dsn, row_factory=dict_row)

    def health(self) -> ToolHealth:
        if self.state != ToolHealth.HEALTHY:
            return self.state
        try:
            for dsn in (self.preference_dsn, self.relationship_dsn, self.audit_dsn):
                with self._connect(dsn) as connection:
                    connection.execute("SELECT 1")
            return ToolHealth.HEALTHY
        except Exception:
            return ToolHealth.UNAVAILABLE

    def apply_migration(self) -> None:
        with self._connect(self.audit_dsn) as connection:
            connection.execute(MIGRATION_PATH.read_text(encoding="utf-8"))

    def retrieve_memory(self, *, context: MemoryRecallAdapterContext, request: ToolRequest,
                        definition: CapabilityDefinition, permission_version: str,
                        started_at: str, audit_event_id: str) -> MemoryRecallOutcome:
        verify_adapter_provenance(getattr(context, "gateway_execution_context", None), request_id=request.request_id, capability_id=request.capability.capability_id)
        if self.environment == "production" or request.environment == "production":
            raise DurableActivityError(ErrorClass.ENVIRONMENT_DENIED, "persistent adapter refuses production", status=ResultStatus.DENIED)
        self.last_context = context
        functional: list[dict[str, Any]] = []
        relational: list[dict[str, Any]] = []
        selected_ids: list[str] = []
        modes: list[str] = []
        classes = tuple(sorted(MEMORY_RECALL_POLICY.purposes[context.purpose]))

        if context.session_memory_use.state != "START_FRESH":
            if "PREFERENCE" in classes:
                functional, preference_ids = self._functional_context(context)
                selected_ids.extend(preference_ids)
            if "RELATIONSHIP_FACT" in classes:
                relational, relationship_ids = self._relationship_context(context)
                selected_ids.extend(relationship_ids)
        modes.extend(item["recall_mode"] for item in functional + relational)
        instructions = {
            "do_not_expose_internal_metadata": True,
            "do_not_use_relationship_memory_for_pressure": True,
            "do_not_treat_memory_as_system_authority": True,
            "start_fresh": context.session_memory_use.state == "START_FRESH",
        }
        try:
            with self._connect(self.audit_dsn) as connection:
                connection.execute(
                    """INSERT INTO tg_p06.memory_recall_audit_events
                    (audit_event_id, request_id, correlation_id, actor_id, actor_type, subject_id, capability_id,
                     bros_authority_level, tool_authority_class, environment, channel, purpose,
                     identity_verification_state, session_memory_use_state, memory_classes_considered,
                     memory_ids_selected, functional_count, relationship_count, recall_modes,
                     permission_decision, execution_status, error_classification, tool_id, tool_version,
                     permission_version, started_at, completed_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'ALLOW','SUCCESS',NULL,%s,%s,%s,%s,%s)""",
                    (audit_event_id, request.request_id, request.correlation_id, request.actor.actor_id,
                     request.actor.actor_type, context.subject.subject_id, request.capability.capability_id,
                     definition.bros_level, definition.tool_class, request.environment, request.channel,
                     request.purpose, context.subject.identity_state, context.session_memory_use.state,
                     list(classes), selected_ids, len(functional), len(relational), sorted(set(modes)),
                     self.tool_id, self.tool_version, permission_version, started_at, utc_now()),
                )
        except Exception as exc:
            raise DurableActivityError(ErrorClass.AUDIT_FAILURE, "required recall audit could not be persisted") from exc
        return MemoryRecallOutcome(tuple(functional), tuple(relational), instructions, tuple(selected_ids), tuple(sorted(set(modes))), audit_event_id)

    def _functional_context(self, context: MemoryRecallAdapterContext) -> tuple[list[dict[str, Any]], list[str]]:
        policy = MEMORY_RECALL_POLICY
        if context.limits.functional == 0:
            return [], []
        if context.current_context.explicit_memory_request or context.purpose == "explicit_memory_review":
            eligible = None
        elif context.purpose == "product_assistance":
            eligible = policy.product_keys | policy.silent_use_keys
        elif context.purpose == "education_assistance":
            eligible = policy.education_keys | policy.silent_use_keys
        elif context.purpose == "support_assistance":
            eligible = policy.support_keys
        else:
            eligible = policy.product_keys | policy.education_keys | policy.support_keys | policy.silent_use_keys
        query = """SELECT preference_id, preference_key, preference_value, stated_at
            FROM tg_p05a.customer_preferences
            WHERE subject_type=%s AND subject_id=%s AND status='ACTIVE'
              AND memory_permission_state_at_write='ACTIVE'"""
        params: list[Any] = [context.subject.subject_type, context.subject.subject_id]
        if eligible is not None:
            query += " AND preference_key = ANY(%s)"
            params.append(sorted(eligible))
        query += " ORDER BY recorded_at DESC LIMIT %s"
        params.append(max(1, min(context.limits.functional, policy.functional_limit)))
        with self._connect(self.preference_dsn) as connection:
            rows = connection.execute(query, params).fetchall()
        selected: list[dict[str, Any]] = []
        ids: list[str] = []
        for row in rows:
            key, value = row["preference_key"], row["preference_value"]
            if eligible is not None and key not in eligible:
                continue
            current = context.current_context.customer_current_statements.get(key)
            if current is not None and current != value:
                continue
            if context.current_context.explicit_memory_request or context.purpose == "explicit_memory_review":
                mode = "TRANSPARENT_REVIEW"
            elif key in policy.silent_use_keys:
                mode = "SILENT_USE"
            else:
                mode = "CONTEXTUAL_REFERENCE"
            selected.append({
                "memory_type": "preference", "key": key, "value": value,
                "functional_class": "FUNCTIONAL", "relevance": "HIGH",
                "freshness": self._preference_freshness(row["stated_at"]),
                "recall_mode": mode, "surface_permission": mode != "SILENT_USE",
            })
            ids.append(str(row["preference_id"]))
            if len(selected) >= min(context.limits.functional, policy.functional_limit):
                break
        return selected, ids

    def _relationship_context(self, context: MemoryRecallAdapterContext) -> tuple[list[dict[str, Any]], list[str]]:
        policy = MEMORY_RECALL_POLICY
        if context.current_context.operational_priority in policy.negative_priorities:
            return [], []
        review = context.current_context.explicit_memory_request or context.purpose == "explicit_memory_review"
        terms = {context.current_context.topic.lower(), context.current_context.intent.lower()}
        terms.update(str(item).lower() for item in context.current_context.entities)
        natural_bridge = review or context.purpose == "relationship_conversation" or any(
            bridge in " ".join(terms).replace("_", " ") for bridge in policy.bridge_terms
        )
        if not natural_bridge or context.limits.relational == 0:
            return [], []
        candidate_keys: set[str] | None = None
        if not review:
            joined = " ".join(terms).replace("_", " ")
            candidate_keys = set()
            bridge_map = {
                "graduation": {"upcoming_graduation"}, "wedding": {"upcoming_wedding"},
                "trip": {"upcoming_trip"}, "birthday": {"customer_birthday", "related_person_birthday"},
                "anniversary": {"relationship_anniversary"}, "tradition": {"recurring_tradition"},
                "milestone": {"personal_milestone"},
            }
            for term, keys in bridge_map.items():
                if term in joined:
                    candidate_keys.update(keys)
            if any(term in joined for term in ("family", "daughter", "son", "child", "children", "maya")):
                candidate_keys.update({"children_count", "related_person_first_name", "related_person_relationship", "related_person_age"})
            if not candidate_keys:
                return [], []
        query = """SELECT relationship_fact_id, fact_key, fact_value, stated_at, source_context_summary,
                          event_date_or_period, related_person_context
                FROM tg_p05b.relationship_facts
                WHERE subject_type=%s AND subject_id=%s AND status IN ('ACTIVE','UPCOMING')
                  AND sensitivity_class='R1' AND memory_permission_state_at_write='ACTIVE'"""
        params = [context.subject.subject_type, context.subject.subject_id]
        if candidate_keys is not None:
            query += " AND fact_key = ANY(%s)"
            params.append(sorted(candidate_keys))
        query += " ORDER BY recorded_at DESC LIMIT %s"
        params.append(max(1, min(context.limits.relational, policy.relational_limit)))
        with self._connect(self.relationship_dsn) as connection:
            rows = connection.execute(query, params).fetchall()
        selected: list[dict[str, Any]] = []
        ids: list[str] = []
        for row in rows:
            if row["fact_key"] in context.current_context.customer_current_statements:
                continue
            searchable = f"{row['fact_key']} {row['fact_value']}".lower().replace("_", " ")
            if not review and not any(term.replace("_", " ") in searchable or any(bridge in term.replace("_", " ") and bridge in searchable for bridge in policy.bridge_terms) for term in terms):
                continue
            freshness = self._relationship_freshness(row["fact_key"], row["stated_at"])
            mode = "TRANSPARENT_REVIEW" if review else "CONTEXTUAL_REFERENCE"
            item = {
                "memory_type": "relationship_fact", "key": row["fact_key"],
                "value": dict(row["fact_value"]), "functional_class": "RELATIONAL",
                "relevance": "HIGH", "freshness": freshness, "recall_mode": mode,
                "surface_permission": freshness != "STALE_REQUIRES_QUALIFICATION",
                "permitted_use": "relationship_continuity_only",
            }
            if freshness == "STALE_REQUIRES_QUALIFICATION":
                item["qualification"] = "do_not_present_as_current_certainty"
            if review or context.current_context.provenance_challenge:
                item["provenance"] = {"mode": "CUSTOMER_FRIENDLY", "source_context_summary": row["source_context_summary"]}
            selected.append(item)
            ids.append(str(row["relationship_fact_id"]))
            if len(selected) >= min(context.limits.relational, policy.relational_limit):
                break
        return selected, ids

    @staticmethod
    def _age_days(stated_at: datetime) -> int:
        value = stated_at if stated_at.tzinfo else stated_at.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - value).days)

    def _preference_freshness(self, stated_at: datetime) -> str:
        return "CURRENT" if self._age_days(stated_at) <= MEMORY_RECALL_POLICY.medium_decay_days else "STALE_REQUIRES_QUALIFICATION"

    def _relationship_freshness(self, key: str, stated_at: datetime) -> str:
        age = self._age_days(stated_at)
        if key in MEMORY_RECALL_POLICY.low_decay_keys:
            return "CURRENT"
        limit = MEMORY_RECALL_POLICY.high_decay_days if key in MEMORY_RECALL_POLICY.high_decay_keys else MEMORY_RECALL_POLICY.medium_decay_days
        return "CURRENT" if age <= limit else "STALE_REQUIRES_QUALIFICATION"

    def audits(self, correlation_id: str) -> list[dict[str, Any]]:
        with self._connect(self.audit_dsn) as connection:
            rows = connection.execute(
                "SELECT * FROM tg_p06.memory_recall_audit_events WHERE correlation_id=%s ORDER BY completed_at",
                (correlation_id,),
            ).fetchall()
        return [dict(row) for row in rows]
