"""Deterministic non-production Affiliate MVP engine.

The engine is deliberately repository-neutral. PostgreSQL remains financial truth;
this module supplies the policy/state machine used by services and acceptance tests.
It never submits funds and every feature gate defaults to OFF.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

MONEY_QUANTUM = Decimal("0.000001")
RATE_QUANTUM = Decimal("0.00000001")
AFFILIATE_CODE = re.compile(r"^AFF-[0-9]{6}$")
QR_CODE = re.compile(r"^AQR-[0-9A-HJKMNP-TV-Z]{10}$")
ALLOWED_ELIGIBILITY = {"ELIGIBLE", "EXCLUDED", "CAMPAIGN_ONLY", "CLASS_RESTRICTED", "PAUSED"}


class DomainError(ValueError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def money(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


@dataclass
class FeatureFlags:
    affiliate_referral_enabled: bool = False
    affiliate_attribution_enabled: bool = False
    affiliate_commission_processing_enabled: bool = False
    affiliate_portal_enabled: bool = False
    affiliate_payout_submission_enabled: bool = False


@dataclass(frozen=True)
class Affiliate:
    id: str
    code: str
    email: str
    affiliate_class: str = "STANDARD"
    status: str = "APPROVED_PENDING_TERMS"
    terms_version: str | None = None
    payout_profile_status: str = "INCOMPLETE"
    tax_profile_status: str = "NOT_REQUIRED_OR_UNKNOWN"


@dataclass(frozen=True)
class ReferralEvent:
    id: str
    affiliate_id: str
    method: str
    occurred_at: datetime
    expires_at: datetime
    correlation_id: str
    campaign_id: str | None = None
    qualified: bool = True


@dataclass(frozen=True)
class CouponMapping:
    code: str
    affiliate_id: str
    active: bool = True
    campaign_id: str | None = None


@dataclass(frozen=True)
class AttributionDecision:
    id: str
    order_id: str
    affiliate_id: str | None
    status: str
    method: str | None
    reason_code: str
    referral_event_id: str | None
    correlation_id: str
    version: str = "affiliate-attribution-v1"


@dataclass(frozen=True)
class CommissionRule:
    id: str
    rule_code: str
    rate: Decimal
    precedence: int
    priority: int = 0
    affiliate_id: str | None = None
    affiliate_class: str | None = None
    product_id: str | None = None
    product_class: str | None = None
    campaign_id: str | None = None
    version: int = 1
    active: bool = True


@dataclass
class Commission:
    id: str
    affiliate_id: str
    order_id: str
    currency: str
    qualifying_revenue: Decimal
    amount: Decimal
    balance: Decimal
    status: str
    hold_until: datetime
    correlation_id: str
    rule_ids: list[str]
    compliance_hold: bool = False
    dispute_status: str = "NONE"


@dataclass(frozen=True)
class LedgerEvent:
    id: str
    key: str
    commission_id: str
    event_type: str
    amount_delta: Decimal
    resulting_balance: Decimal
    reason_code: str
    correlation_id: str
    occurred_at: datetime


@dataclass(frozen=True)
class QuarantineEvent:
    id: str
    reason: str
    source_event_id: str
    correlation_id: str
    status: str = "OPEN"


class AffiliateEngine:
    """In-memory reference implementation of ratified financial policy."""

    def __init__(self, flags: FeatureFlags | None = None) -> None:
        self.flags = flags or FeatureFlags()
        self.applications: dict[str, dict[str, Any]] = {}
        self.application_idempotency: dict[str, str] = {}
        self.affiliates: dict[str, Affiliate] = {}
        self.referrals: dict[str, ReferralEvent] = {}
        self.coupons: dict[str, CouponMapping] = {}
        self.qr_owners: dict[str, str] = {}
        self.campaign_windows: dict[str, tuple[datetime, datetime]] = {}
        self.rules: list[CommissionRule] = []
        self.decisions: dict[str, AttributionDecision] = {}
        self.commissions: dict[str, Commission] = {}
        self.order_commission: dict[tuple[str, str], str] = {}
        self.ledger: list[LedgerEvent] = []
        self.ledger_keys: set[str] = set()
        self.processed_revenue_events: dict[str, dict[str, Any]] = {}
        self.processed_refunds: set[str] = set()
        self.processed_provider_callbacks: set[str] = set()
        self.quarantine: list[QuarantineEvent] = []
        self.risk_events: list[dict[str, Any]] = []
        self.disputes: list[dict[str, Any]] = []
        self.audit: list[dict[str, Any]] = []
        self.payout_batches: list[dict[str, Any]] = []

    @staticmethod
    def _id() -> str:
        return str(uuid.uuid4())

    def submit_application(self, payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        if idempotency_key in self.application_idempotency:
            return {**self.applications[self.application_idempotency[idempotency_key]], "idempotent_replay": True}
        email = str(payload.get("applicant_email", "")).strip().lower()
        desired = payload.get("desired_affiliate_class", "STANDARD")
        if "@" not in email or desired not in {"STANDARD", "STRATEGIC_PARTNER"}:
            raise DomainError("INVALID_APPLICATION")
        app_id = self._id()
        application = {"id": app_id, "applicant_email": email, "desired_affiliate_class": desired, "status": "SUBMITTED", "idempotency_key": idempotency_key, "idempotent_replay": False}
        self.applications[app_id] = application
        self.application_idempotency[idempotency_key] = app_id
        return dict(application)

    def review_application(self, application_id: str, approved: bool, actor_role: str = "AFFILIATE_OPERATOR") -> Affiliate | None:
        application = self.applications[application_id]
        if application["desired_affiliate_class"] == "STRATEGIC_PARTNER" and actor_role != "PROJECT_OWNER":
            raise DomainError("PROJECT_OWNER_REQUIRED")
        application["status"] = "APPROVED" if approved else "DECLINED"
        if not approved:
            return None
        sequence = len(self.affiliates) + 1
        affiliate = Affiliate(id=self._id(), code=f"AFF-{sequence:06d}", email=application["applicant_email"], affiliate_class=application["desired_affiliate_class"])
        self.affiliates[affiliate.id] = affiliate
        application["linked_affiliate_id"] = affiliate.id
        return affiliate

    def accept_terms(self, affiliate_id: str, version: str, checksum: str) -> Affiliate:
        current = self.affiliates[affiliate_id]
        replacement = Affiliate(**{**asdict(current), "terms_version": f"{version}:{checksum}"})
        self.affiliates[affiliate_id] = replacement
        return replacement

    def activate(self, affiliate_id: str, required_terms_version: str) -> Affiliate:
        current = self.affiliates[affiliate_id]
        if not current.terms_version or not current.terms_version.startswith(required_terms_version + ":"):
            raise DomainError("TERMS_REQUIRED")
        replacement = Affiliate(**{**asdict(current), "status": "ACTIVE"})
        self.affiliates[affiliate_id] = replacement
        return replacement

    def set_status(self, affiliate_id: str, status: str) -> Affiliate:
        if status not in {"APPROVED_PENDING_TERMS", "ACTIVE", "INACTIVE", "SUSPENDED", "TERMINATED"}:
            raise DomainError("INVALID_AFFILIATE_STATE")
        current = self.affiliates[affiliate_id]
        replacement = Affiliate(**{**asdict(current), "status": status})
        self.affiliates[affiliate_id] = replacement
        return replacement

    def create_referral(self, affiliate_id: str, method: str = "LINK", occurred_at: datetime | None = None, campaign_id: str | None = None, qr_code: str | None = None) -> ReferralEvent:
        if not self.flags.affiliate_referral_enabled:
            raise DomainError("AFFILIATE_REFERRAL_DISABLED")
        affiliate = self.affiliates[affiliate_id]
        if affiliate.status != "ACTIVE":
            raise DomainError("INVALID_AFFILIATE_STATE")
        if method == "QR" and (not qr_code or not QR_CODE.match(qr_code)):
            raise DomainError("INVALID_QR")
        if method == "QR" and self.qr_owners.get(qr_code) != affiliate_id:
            raise DomainError("QR_AFFILIATE_MISMATCH")
        if method not in {"LINK", "QR"}:
            raise DomainError("INVALID_REFERRAL_METHOD")
        occurred = occurred_at or utcnow()
        event = ReferralEvent(self._id(), affiliate_id, method, occurred, occurred + timedelta(days=30), self._id(), campaign_id)
        self.referrals[event.id] = event
        return event

    def register_qr(self, qr_code: str, affiliate_id: str) -> None:
        if not QR_CODE.match(qr_code):
            raise DomainError("INVALID_QR")
        self.qr_owners[qr_code] = affiliate_id

    def register_campaign(self, campaign_id: str, starts_at: datetime, ends_at: datetime) -> None:
        if ends_at <= starts_at:
            raise DomainError("INVALID_CAMPAIGN_WINDOW")
        self.campaign_windows[campaign_id] = (starts_at, ends_at)

    def add_coupon(self, code: str, affiliate_id: str, campaign_id: str | None = None) -> None:
        self.coupons[code.strip().lower()] = CouponMapping(code.strip().lower(), affiliate_id, True, campaign_id)

    def resolve_attribution(self, order_id: str, referral_event_ids: list[str], coupon_codes: list[str] | None = None, at: datetime | None = None, client_affiliate_id: str | None = None) -> AttributionDecision:
        if not self.flags.affiliate_attribution_enabled:
            raise DomainError("AFFILIATE_ATTRIBUTION_DISABLED")
        when = at or utcnow()
        correlation = self._id()
        candidates = []
        coupon_candidates = {self.coupons[c.lower()].affiliate_id for c in (coupon_codes or []) if c.lower() in self.coupons and self.coupons[c.lower()].active}
        if len(coupon_candidates) > 1:
            return self._unresolved(order_id, "CONFLICTING_ATTRIBUTION", correlation)
        if len(coupon_candidates) == 1:
            affiliate_id = next(iter(coupon_candidates))
            affiliate = self.affiliates.get(affiliate_id)
            if not affiliate or affiliate.status != "ACTIVE":
                return self._unresolved(order_id, "INVALID_AFFILIATE_STATE", correlation)
            return self._decision(order_id, affiliate_id, "ATTRIBUTED", "AFFILIATE_COUPON", "VALID_AFFILIATE_COUPON", None, correlation)
        for event_id in referral_event_ids:
            event = self.referrals.get(event_id)
            campaign_valid = not event or not event.campaign_id or (event.campaign_id in self.campaign_windows and self.campaign_windows[event.campaign_id][0] <= when <= self.campaign_windows[event.campaign_id][1])
            if event and campaign_valid and event.qualified and event.occurred_at <= when <= event.expires_at and self.affiliates[event.affiliate_id].status == "ACTIVE":
                candidates.append(event)
        if not candidates:
            return self._decision(order_id, None, "UNATTRIBUTED", None, "NO_VALID_ATTRIBUTION", None, correlation)
        winner = max(candidates, key=lambda item: (item.occurred_at, item.id))
        method = "QR_REFERRAL" if winner.method == "QR" else "REFERRAL_LINK"
        return self._decision(order_id, winner.affiliate_id, "ATTRIBUTED", method, "LAST_QUALIFIED_REFERRAL", winner.id, correlation)

    def _decision(self, order_id: str, affiliate_id: str | None, status: str, method: str | None, reason: str, referral_id: str | None, correlation: str) -> AttributionDecision:
        decision = AttributionDecision(self._id(), order_id, affiliate_id, status, method, reason, referral_id, correlation)
        self.decisions[decision.id] = decision
        return decision

    def _unresolved(self, order_id: str, reason: str, correlation: str) -> AttributionDecision:
        self._quarantine(reason, order_id, correlation)
        return self._decision(order_id, None, "UNRESOLVED", None, reason, None, correlation)

    def add_rule(self, **kwargs: Any) -> CommissionRule:
        rate = Decimal(str(kwargs.pop("rate"))).quantize(RATE_QUANTUM)
        if rate < 0 or rate > 1:
            raise DomainError("INVALID_COMMISSION_RATE")
        rule = CommissionRule(id=self._id(), rate=rate, **kwargs)
        self.rules.append(rule)
        return rule

    def resolve_rule(self, affiliate: Affiliate, product: dict[str, Any], campaign_id: str | None, at: datetime | None = None) -> CommissionRule:
        eligibility = product.get("affiliate_eligibility")
        if eligibility not in ALLOWED_ELIGIBILITY:
            raise DomainError("UNKNOWN_OR_MISSING_CCSS_ELIGIBILITY")
        if eligibility in {"EXCLUDED", "PAUSED"}:
            raise DomainError("PRODUCT_NOT_ELIGIBLE")
        if eligibility == "CAMPAIGN_ONLY" and not campaign_id:
            raise DomainError("PRODUCT_NOT_ELIGIBLE")
        if eligibility == "CLASS_RESTRICTED" and affiliate.affiliate_class not in product.get("affiliate_class_restriction", []):
            raise DomainError("PRODUCT_NOT_ELIGIBLE")
        matches = []
        for rule in self.rules:
            if not rule.active:
                continue
            if rule.affiliate_id and rule.affiliate_id != affiliate.id: continue
            if rule.affiliate_class and rule.affiliate_class != affiliate.affiliate_class: continue
            if rule.product_id and rule.product_id != str(product.get("product_id")): continue
            if rule.product_class and rule.product_class != product.get("product_class"): continue
            if rule.campaign_id and rule.campaign_id != campaign_id: continue
            matches.append(rule)
        if not matches:
            raise DomainError("MISSING_COMMISSION_RULE")
        best_key = min((r.precedence, -r.priority) for r in matches)
        best = [r for r in matches if (r.precedence, -r.priority) == best_key]
        if len(best) != 1:
            raise DomainError("CONFLICTING_COMMISSION_RULES")
        return best[0]

    def process_revenue_event(self, event: dict[str, Any], decision: AttributionDecision, products: dict[str, dict[str, Any]]) -> dict[str, Any]:
        event_id = str(event["event_id"])
        if event_id in self.processed_revenue_events:
            return {**self.processed_revenue_events[event_id], "idempotent_replay": True}
        if not self.flags.affiliate_commission_processing_enabled:
            result = {"status": "PRESERVED_PROCESSING_DISABLED", "commission_id": None, "idempotent_replay": False}
            self.processed_revenue_events[event_id] = result
            return result
        if decision.status != "ATTRIBUTED" or not decision.affiliate_id:
            result = {"status": "NO_COMMISSION_UNATTRIBUTED", "commission_id": None, "idempotent_replay": False}
            self.processed_revenue_events[event_id] = result
            return result
        affiliate = self.affiliates[decision.affiliate_id]
        order_id = str(event["order_id"])
        existing = self.order_commission.get((affiliate.id, order_id))
        if existing:
            result = {"status": "COMMISSION_EXISTS", "commission_id": existing, "idempotent_replay": True}
            self.processed_revenue_events[event_id] = result
            return result
        qualifying_total = money(0)
        commission_total = money(0)
        rule_ids: list[str] = []
        try:
            for line in event.get("line_items", []):
                product_id = str(line["product_id"])
                product = products.get(product_id)
                if product is None:
                    raise DomainError("UNKNOWN_PRODUCT")
                if product.get("affiliate_eligibility") == "EXCLUDED":
                    continue
                rule = self.resolve_rule(affiliate, product, decision.method and event.get("campaign_id"))
                gross = money(line.get("merchandise_total", 0))
                discount = money(line.get("discount", 0))
                refunded = money(line.get("refunded", 0))
                qualifying = max(money(0), money(gross - discount - refunded))
                amount = money(qualifying * rule.rate)
                qualifying_total += qualifying
                commission_total += amount
                rule_ids.append(rule.id)
        except DomainError as exc:
            self._quarantine(exc.code, event_id, decision.correlation_id)
            result = {"status": "QUARANTINED", "reason": exc.code, "commission_id": None, "idempotent_replay": False}
            self.processed_revenue_events[event_id] = result
            return result
        if commission_total == 0:
            result = {"status": "NO_COMMISSION", "commission_id": None, "idempotent_replay": False}
            self.processed_revenue_events[event_id] = result
            return result
        created_at = datetime.fromisoformat(event["occurred_at"].replace("Z", "+00:00"))
        commission = Commission(self._id(), affiliate.id, order_id, event["currency"].upper(), money(qualifying_total), money(commission_total), money(commission_total), "PENDING", created_at + timedelta(days=30), decision.correlation_id, rule_ids)
        self.commissions[commission.id] = commission
        self.order_commission[(affiliate.id, order_id)] = commission.id
        self._ledger(commission, "COMMISSION_CREATED", commission.amount, "ELIGIBLE_ORDER", event_id)
        result = {"status": "COMMISSION_CREATED", "commission_id": commission.id, "amount": str(commission.amount), "idempotent_replay": False}
        self.processed_revenue_events[event_id] = result
        return result

    def _ledger(self, commission: Commission, event_type: str, delta: Decimal, reason: str, source_event_id: str) -> LedgerEvent:
        key = f"{source_event_id}:{event_type}:{commission.id}"
        if key in self.ledger_keys:
            return next(item for item in self.ledger if item.key == key)
        event = LedgerEvent(self._id(), key, commission.id, event_type, money(delta), money(commission.balance), reason, commission.correlation_id, utcnow())
        self.ledger.append(event)
        self.ledger_keys.add(key)
        return event

    def process_refund(self, commission_id: str, refund_event_id: str, qualifying_refund: Any) -> Commission:
        if refund_event_id in self.processed_refunds:
            return self.commissions[commission_id]
        commission = self.commissions[commission_id]
        if commission.qualifying_revenue <= 0:
            raise DomainError("INVALID_COMMISSION_STATE")
        refund = min(money(qualifying_refund), commission.qualifying_revenue)
        reversal = money(commission.amount * refund / commission.qualifying_revenue)
        commission.balance = money(commission.balance - reversal)
        full = refund == commission.qualifying_revenue
        if full and commission.status != "PAID":
            commission.status = "REVERSED"
        event_type = "COMMISSION_FULL_REVERSAL" if full else "COMMISSION_PARTIAL_REVERSAL"
        if commission.status == "PAID":
            event_type = "COMMISSION_ADJUSTMENT_DEBIT"
        self._ledger(commission, event_type, -reversal, "AUTHORITATIVE_REFUND", refund_event_id)
        self.processed_refunds.add(refund_event_id)
        return commission

    def mature(self, commission_id: str, at: datetime | None = None) -> Commission:
        commission = self.commissions[commission_id]
        when = at or utcnow()
        if commission.status != "PENDING":
            raise DomainError("IMPOSSIBLE_STATE_TRANSITION")
        if when < commission.hold_until or commission.compliance_hold or commission.dispute_status not in {"NONE", "CLOSED"}:
            return commission
        commission.status = "PAYABLE"
        self._ledger(commission, "COMMISSION_PAYABLE", money(0), "HOLD_COMPLETE", f"maturity:{commission.id}")
        return commission

    def submit_dispute(self, affiliate_id: str, commission_id: str, notice_at: datetime, submitted_at: datetime) -> dict[str, Any]:
        dispute = {"id": self._id(), "affiliate_id": affiliate_id, "commission_id": commission_id, "within_standard_window": submitted_at <= notice_at + timedelta(days=30), "status": "OPEN"}
        self.disputes.append(dispute)
        self.commissions[commission_id].dispute_status = "OPEN"
        return dispute

    def flag_self_referral(self, affiliate_id: str, order_id: str, evidence: dict[str, Any]) -> dict[str, Any]:
        risk = {"id": self._id(), "affiliate_id": affiliate_id, "order_id": order_id, "risk_type": "SELF_REFERRAL_SUSPECTED", "review_status": "OPEN", "evidence_hash": hashlib.sha256(repr(sorted(evidence.items())).encode()).hexdigest()}
        self.risk_events.append(risk)
        return risk

    def prepare_payout_batch(self, currency: str, actor_role: str = "FINANCIAL_APPROVER") -> dict[str, Any]:
        if actor_role not in {"FINANCIAL_APPROVER", "PROJECT_OWNER"}:
            raise DomainError("FINANCIAL_APPROVER_REQUIRED")
        by_affiliate: dict[str, list[Commission]] = {}
        for item in self.commissions.values():
            if item.status == "PAYABLE" and item.currency == currency and not item.compliance_hold and item.dispute_status in {"NONE", "CLOSED"}:
                by_affiliate.setdefault(item.affiliate_id, []).append(item)
        items = []
        for affiliate_id, commissions in by_affiliate.items():
            affiliate = self.affiliates[affiliate_id]
            total = money(sum((c.balance for c in commissions), Decimal(0)))
            if total >= money("50") and affiliate.payout_profile_status == "VERIFIED" and affiliate.tax_profile_status in {"VERIFIED", "NOT_REQUIRED_OR_UNKNOWN"}:
                items.append({"affiliate_id": affiliate_id, "amount": str(total), "commission_ids": [c.id for c in commissions], "status": "PREPARED"})
        batch = {"id": self._id(), "currency": currency, "status": "UNDER_REVIEW", "items": items, "human_approved": False}
        self.payout_batches.append(batch)
        return batch

    def approve_payout_batch(self, batch_id: str, actor_role: str) -> dict[str, Any]:
        if actor_role not in {"FINANCIAL_APPROVER", "PROJECT_OWNER"}:
            raise DomainError("FINANCIAL_APPROVER_REQUIRED")
        batch = next(item for item in self.payout_batches if item["id"] == batch_id)
        batch["status"] = "APPROVED"
        batch["human_approved"] = True
        return batch

    def submit_payout_batch(self, batch_id: str) -> dict[str, Any]:
        if not self.flags.affiliate_payout_submission_enabled:
            raise DomainError("PAYOUT_SUBMISSION_DISABLED")
        batch = next(item for item in self.payout_batches if item["id"] == batch_id)
        if not batch["human_approved"]:
            raise DomainError("HUMAN_APPROVAL_REQUIRED")
        batch["status"] = "SUBMITTED"
        return batch

    def reconcile_provider_callback(self, batch_id: str, callback_id: str, authentic: bool, success: bool) -> dict[str, Any]:
        if not authentic:
            raise DomainError("INVALID_SIGNATURE")
        batch = next(item for item in self.payout_batches if item["id"] == batch_id)
        if callback_id in self.processed_provider_callbacks:
            return {**batch, "idempotent_replay": True}
        self.processed_provider_callbacks.add(callback_id)
        if not success:
            batch["status"] = "FAILED"
            return batch
        batch["status"] = "RECONCILED"
        for item in batch["items"]:
            for commission_id in item["commission_ids"]:
                commission = self.commissions[commission_id]
                commission.status = "PAID"
                self._ledger(commission, "COMMISSION_PAID", money(0), "PROVIDER_RECONCILED", callback_id)
        return batch

    def manual_override(self, original: AttributionDecision, replacement_affiliate_id: str | None, actor_role: str) -> AttributionDecision:
        if actor_role not in {"PROJECT_OWNER", "AFFILIATE_OPERATOR"}:
            raise DomainError("UNAUTHORIZED_OVERRIDE")
        replacement = self._decision(original.order_id, replacement_affiliate_id, "OVERRIDDEN", "MANUAL_CORRECTION", "AUTHORIZED_CORRECTION", None, original.correlation_id)
        self.audit.append({"action": "ATTRIBUTION_CORRECTION", "before": original.id, "after": replacement.id, "actor_role": actor_role})
        return replacement

    def affiliate_dashboard(self, affiliate_id: str) -> dict[str, Any]:
        if not self.flags.affiliate_portal_enabled:
            raise DomainError("AFFILIATE_PORTAL_DISABLED")
        affiliate = self.affiliates[affiliate_id]
        own = [c for c in self.commissions.values() if c.affiliate_id == affiliate_id]
        return {"affiliate_code": affiliate.code, "status": affiliate.status, "pending": str(money(sum((c.balance for c in own if c.status == 'PENDING'), Decimal(0)))), "payable": str(money(sum((c.balance for c in own if c.status == 'PAYABLE'), Decimal(0)))), "paid": str(money(sum((c.balance for c in own if c.status == 'PAID'), Decimal(0))))}

    def budly_context(self, affiliate_id: str) -> dict[str, Any]:
        affiliate = self.affiliates[affiliate_id]
        return {"affiliate_code": affiliate.code, "status": affiliate.status, "affiliate_class": affiliate.affiliate_class, "allowed_operations": ["retrieve_link", "retrieve_qr", "submit_support", "intake_dispute", "draft_campaign_content"], "prohibited_operations": ["change_commission", "override_attribution", "approve_payout", "change_affiliate_class", "alter_ledger"]}

    def _quarantine(self, reason: str, source_event_id: str, correlation_id: str) -> QuarantineEvent:
        event = QuarantineEvent(self._id(), reason, source_event_id, correlation_id)
        self.quarantine.append(event)
        return event
