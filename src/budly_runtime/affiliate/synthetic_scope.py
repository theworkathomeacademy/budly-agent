"""Fail-closed G9E synthetic-only authorization boundary.

The caller must load ``SyntheticScopeRecord`` from trusted server-side
PostgreSQL/Supabase state.  No request field can create or upgrade a scope.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SYNTHETIC_CLASSIFICATION = "TEST_SYNTHETIC_NON_PRODUCTION_PERSON"
SCOPED_GATES = frozenset({
    "affiliate_portal_enabled",
    "affiliate_referral_enabled",
    "affiliate_attribution_enabled",
    "affiliate_commission_processing_enabled",
})
PAYOUT_GATE = "affiliate_payout_submission_enabled"


@dataclass(frozen=True)
class SyntheticScopeRecord:
    scope_id: str
    classification: str
    wordpress_user_id: int
    affiliate_id: str
    affiliate_code: str
    referral_token: str
    destination_key: str
    campaign_id: str
    event_id: str
    order_id: str
    expires_at: datetime
    active: bool = True


@dataclass(frozen=True)
class ScopeRequest:
    operation: str
    actor: str
    wordpress_user_id: int | None = None
    affiliate_id: str | None = None
    affiliate_code: str | None = None
    referral_token: str | None = None
    destination_key: str | None = None
    campaign_id: str | None = None
    event_id: str | None = None
    order_id: str | None = None
    trusted_event_classification: str | None = None
    upstream_attribution_allowed: bool = False
    idempotency_key: str | None = None


@dataclass(frozen=True)
class ScopeDecision:
    allowed: bool
    reason: str
    idempotent_replay: bool = False


class DurableScopeAudit:
    """Append-only SQLite evidence store used by deterministic/local proof.

    Production uses the equivalent PostgreSQL contract in integration/g9e1.
    """

    def __init__(self, path: Path) -> None:
        self.connection = sqlite3.connect(path)
        self.connection.execute("""create table if not exists synthetic_scope_audit (
          audit_id integer primary key autoincrement,
          idempotency_key text unique,
          operation text not null, actor text not null, synthetic_identity text,
          event_or_order_id text, gate_name text not null, gate_state integer not null,
          scope_result text not null, decision text not null, reason text not null,
          occurred_at text not null, evidence_json text not null
        )""")
        self.connection.execute("""create trigger if not exists synthetic_scope_audit_no_update
          before update on synthetic_scope_audit begin select raise(abort,'SYNTHETIC_SCOPE_AUDIT_IMMUTABLE'); end""")
        self.connection.execute("""create trigger if not exists synthetic_scope_audit_no_delete
          before delete on synthetic_scope_audit begin select raise(abort,'SYNTHETIC_SCOPE_AUDIT_IMMUTABLE'); end""")
        self.connection.commit()

    def record(self, request: ScopeRequest, gate: str, gate_state: bool, decision: ScopeDecision) -> ScopeDecision:
        evidence = {
            "wordpress_user_id": request.wordpress_user_id,
            "affiliate_id": request.affiliate_id,
            "affiliate_code": request.affiliate_code,
            "destination_key": request.destination_key,
            "campaign_id": request.campaign_id,
            "classification": request.trusted_event_classification,
        }
        try:
            self.connection.execute(
                "insert into synthetic_scope_audit(idempotency_key,operation,actor,synthetic_identity,event_or_order_id,gate_name,gate_state,scope_result,decision,reason,occurred_at,evidence_json) values(?,?,?,?,?,?,?,?,?,?,?,?)",
                (request.idempotency_key, request.operation, request.actor, request.affiliate_code,
                 request.event_id or request.order_id, gate, int(gate_state),
                 "MATCH" if decision.allowed else "NO_MATCH", "ALLOW" if decision.allowed else "DENY",
                 decision.reason, datetime.now(timezone.utc).isoformat(), json.dumps(evidence, sort_keys=True)),
            )
            self.connection.commit()
            return decision
        except sqlite3.IntegrityError:
            if not request.idempotency_key:
                raise
            row = self.connection.execute(
                "select decision,reason from synthetic_scope_audit where idempotency_key=?", (request.idempotency_key,)
            ).fetchone()
            return ScopeDecision(row[0] == "ALLOW", row[1], True)

    def rows(self) -> list[dict[str, Any]]:
        cursor = self.connection.execute("select operation,actor,synthetic_identity,event_or_order_id,gate_name,gate_state,scope_result,decision,reason,occurred_at,evidence_json from synthetic_scope_audit order by audit_id")
        names = [item[0] for item in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]


class SyntheticScopeGuard:
    def __init__(self, gates: dict[str, bool], trusted_scope: SyntheticScopeRecord | None, audit: DurableScopeAudit) -> None:
        self.gates = dict(gates)
        self.scope = trusted_scope
        self.audit = audit
        if self.gates.get(PAYOUT_GATE, False):
            raise ValueError("PAYOUT_GATE_MUST_REMAIN_OFF")

    def authorize(self, request: ScopeRequest) -> ScopeDecision:
        gate = {
            "portal": "affiliate_portal_enabled",
            "referral": "affiliate_referral_enabled",
            "attribution": "affiliate_attribution_enabled",
            "commission": "affiliate_commission_processing_enabled",
        }.get(request.operation)
        if gate is None:
            raise ValueError("UNKNOWN_SYNTHETIC_SCOPE_OPERATION")
        gate_state = self.gates.get(gate, False)
        decision = self._decide(request, gate_state)
        return self.audit.record(request, gate, gate_state, decision)

    def _decide(self, request: ScopeRequest, gate_state: bool) -> ScopeDecision:
        if not gate_state:
            return ScopeDecision(False, "GLOBAL_GATE_OFF")
        scope = self.scope
        if scope is None or not scope.active or scope.expires_at <= datetime.now(timezone.utc) or scope.classification != SYNTHETIC_CLASSIFICATION:
            return ScopeDecision(False, "TRUSTED_SYNTHETIC_SCOPE_MISSING_OR_INVALID")
        if request.affiliate_id != scope.affiliate_id or request.affiliate_code != scope.affiliate_code:
            return ScopeDecision(False, "AFFILIATE_SCOPE_MISMATCH")
        if request.operation == "portal":
            if request.wordpress_user_id != scope.wordpress_user_id:
                return ScopeDecision(False, "WORDPRESS_IDENTITY_MAPPING_MISMATCH")
            return ScopeDecision(True, "TRUSTED_SYNTHETIC_PORTAL_MATCH")
        if request.trusted_event_classification != SYNTHETIC_CLASSIFICATION:
            return ScopeDecision(False, "TRUSTED_EVENT_CLASSIFICATION_MISMATCH")
        if request.operation == "referral":
            if (request.referral_token, request.destination_key, request.campaign_id) != (scope.referral_token, scope.destination_key, scope.campaign_id):
                return ScopeDecision(False, "REFERRAL_SCOPE_MISMATCH")
            return ScopeDecision(True, "TRUSTED_SYNTHETIC_REFERRAL_MATCH")
        if (request.event_id, request.order_id) != (scope.event_id, scope.order_id):
            return ScopeDecision(False, "EVENT_ORDER_SCOPE_MISMATCH")
        if request.operation == "attribution":
            return ScopeDecision(True, "TRUSTED_SYNTHETIC_ATTRIBUTION_MATCH")
        if not request.upstream_attribution_allowed:
            return ScopeDecision(False, "SYNTHETIC_ATTRIBUTION_NOT_PROVEN")
        return ScopeDecision(True, "TRUSTED_SYNTHETIC_COMMISSION_MATCH")

    def payout_allowed(self) -> bool:
        return False
