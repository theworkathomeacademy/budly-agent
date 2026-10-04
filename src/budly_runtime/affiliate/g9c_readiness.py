"""G9C Affiliate readiness proof harness (non-production, synthetic only).

This module extends the existing Affiliate reference engine.  It deliberately
keeps production feature flags outside the harness OFF and never calls a
payment provider, WordPress, WooCommerce, Supabase, n8n, or an outreach
transport.  Its purpose is to prove the human-facing policy and authorization
contract deterministically before a production implementation is activated.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from .engine import Affiliate, AffiliateEngine, DomainError, FeatureFlags, money
from .identity import CanonicalIdentity, generate_referral_token


class ReadinessError(ValueError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


@dataclass(frozen=True)
class ReadinessActor:
    actor_id: str
    role: str
    affiliate_id: str | None = None
    authenticated: bool = False


@dataclass
class AuditEvent:
    sequence: int
    event_type: str
    actor_id: str
    actor_role: str
    subject_id: str
    reason: str
    evidence_ref: str
    occurred_at: str
    before_hash: str | None = None
    after_hash: str | None = None


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class PublicAffiliateKnowledge:
    """Public Budly answers built only from injected governed facts.

    Public answers expose program facts, never private tokens or application
    URLs.  Exact rates come from the supplied CCSS truth snapshot.
    """

    def __init__(self, governed_facts: dict[str, Any]) -> None:
        required = {"program_state", "applications_open", "eligibility", "offers", "rates", "recurring", "budly_help"}
        missing = required.difference(governed_facts)
        if missing:
            raise ReadinessError("MISSING_GOVERNED_FACT", ",".join(sorted(missing)))
        self.facts = governed_facts

    def answer(self, question: str) -> dict[str, Any]:
        words = {word.strip("?.,!'\"").lower() for word in question.split()}
        state = self.facts["program_state"]
        closed = not bool(self.facts["applications_open"])
        common = {"program_state": state, "public_applications_open": not closed, "source": "GOVERNED_AFFILIATE_AND_CCSS_TRUTH"}

        if {"apply", "applications", "open"}.intersection(words):
            answer = "The Affiliate program is in a private pilot. Public applications are closed. A valid private invitation may enable a private application later."
            return {**common, "intent": "APPLICATION_STATE", "answer": answer, "private_token_exposed": False}
        if {"earn", "commission", "commissions", "recurring"}.intersection(words):
            return {**common, "intent": "COMPENSATION", "answer": "Commission depends on the governed eligible offer and payment sequence.", "rates": dict(self.facts["rates"]), "recurring": self.facts["recurring"]}
        if {"products", "promote", "offers"}.intersection(words):
            return {**common, "intent": "ELIGIBLE_OFFERS", "answer": "Only CCSS-approved eligible offers may be promoted.", "offers": list(self.facts["offers"])}
        if {"followers", "eligible", "affiliate", "who"}.intersection(words):
            return {**common, "intent": "ELIGIBILITY", "answer": self.facts["eligibility"]}
        if {"budly", "help", "support"}.intersection(words):
            return {**common, "intent": "BUDLY_SUPPORT", "answer": self.facts["budly_help"]}
        return {**common, "intent": "PROGRAM_OVERVIEW", "answer": "Wake'n'Bake Lounge is proving a paid, five-person private Affiliate pilot before any broader enrollment. Public applications are closed."}


class G9COperatingExperience:
    """Role-isolated application, affiliate, owner, and audit experience."""

    OWNER_ROLES = {"PROJECT_OWNER"}
    AFFILIATE_ROLES = {"AFFILIATE"}

    def __init__(self, engine: AffiliateEngine, public_knowledge: PublicAffiliateKnowledge) -> None:
        self.engine = engine
        self.public_knowledge = public_knowledge
        self.application_details: dict[str, dict[str, Any]] = {}
        self.identities: dict[str, CanonicalIdentity] = {}
        self.verified_channels: dict[str, list[str]] = {}
        self.vanity_aliases: dict[str, dict[str, Any]] = {}
        self.terms: dict[str, dict[str, Any]] = {}
        self.referral_assets: dict[str, dict[str, Any]] = {}
        self.audit: list[AuditEvent] = []

    @staticmethod
    def _require_owner(actor: ReadinessActor) -> None:
        if not actor.authenticated or actor.role != "PROJECT_OWNER":
            raise ReadinessError("OWNER_AUTHORIZATION_REQUIRED")

    @staticmethod
    def _require_affiliate_self(actor: ReadinessActor, affiliate_id: str) -> None:
        if not actor.authenticated:
            raise ReadinessError("AUTHENTICATION_REQUIRED")
        if actor.role != "AFFILIATE":
            raise ReadinessError("AFFILIATE_ROLE_REQUIRED")
        if actor.affiliate_id != affiliate_id:
            raise ReadinessError("TENANT_ISOLATION_VIOLATION")

    def _record(self, event_type: str, actor: ReadinessActor, subject_id: str, reason: str, evidence_ref: str, before: Any = None, after: Any = None, at: datetime | None = None) -> None:
        self.audit.append(AuditEvent(
            sequence=len(self.audit) + 1,
            event_type=event_type,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            subject_id=subject_id,
            reason=reason,
            evidence_ref=evidence_ref,
            occurred_at=(at or datetime.now(timezone.utc)).isoformat(),
            before_hash=_stable_hash(before) if before is not None else None,
            after_hash=_stable_hash(after) if after is not None else None,
        ))

    def submit_private_application(self, invitation: dict[str, Any], payload: dict[str, Any], idempotency_key: str, actor: ReadinessActor) -> dict[str, Any]:
        if invitation.get("classification") != "TEST_SYNTHETIC_NON_PRODUCTION_PERSON" or not invitation.get("valid"):
            raise ReadinessError("VALID_SYNTHETIC_PRIVATE_INVITATION_REQUIRED")
        if actor.role != "SYNTHETIC_APPLICANT":
            raise ReadinessError("INVALID_APPLICATION_ACTOR")
        app = self.engine.submit_application(payload, idempotency_key)
        details = {
            **app,
            "classification": invitation["classification"],
            "display_name": payload["public_display_name"],
            "contact_email": payload["applicant_email"].lower(),
            "social_channels": list(payload.get("social_channels", [])),
            "review_evidence": list(payload.get("review_evidence", [])),
            "status": "PENDING_REVIEW",
        }
        self.application_details[app["id"]] = details
        self._record("APPLICATION_SUBMITTED", actor, app["id"], "PRIVATE_SYNTHETIC_INVITATION", invitation["evidence_ref"], after=details)
        return dict(details)

    def application_queue(self, actor: ReadinessActor) -> list[dict[str, Any]]:
        self._require_owner(actor)
        return [dict(item) for item in self.application_details.values() if item["status"] in {"PENDING_REVIEW", "NEEDS_REVIEW", "HELD"}]

    def decide_application(self, application_id: str, decision: str, reason: str, evidence_ref: str, actor: ReadinessActor) -> Affiliate | None:
        self._require_owner(actor)
        if decision not in {"APPROVE", "REJECT", "HOLD"}:
            raise ReadinessError("INVALID_OWNER_DECISION")
        details = self.application_details[application_id]
        before = dict(details)
        if decision == "HOLD":
            details["status"] = "HELD"
            self._record("APPLICATION_HELD", actor, application_id, reason, evidence_ref, before, details)
            return None
        approved = decision == "APPROVE"
        affiliate = self.engine.review_application(application_id, approved=approved, actor_role="PROJECT_OWNER")
        details["status"] = "APPROVED_PENDING_TERMS" if approved else "REJECTED"
        self._record("APPLICATION_DECIDED", actor, application_id, reason, evidence_ref, before, details)
        return affiliate

    def accept_terms(self, affiliate_id: str, version: str, checksum: str, actor: ReadinessActor, evidence_ref: str) -> Affiliate:
        self._require_affiliate_self(actor, affiliate_id)
        before = asdict(self.engine.affiliates[affiliate_id])
        affiliate = self.engine.accept_terms(affiliate_id, version, checksum)
        self.terms[affiliate_id] = {"version": version, "checksum": checksum, "accepted": True, "evidence_ref": evidence_ref}
        self._record("TERMS_ACCEPTED", actor, affiliate_id, "AFFILIATE_ACCEPTANCE", evidence_ref, before, asdict(affiliate))
        return affiliate

    def activate_and_create_assets(self, affiliate_id: str, public_display_name: str, email: str, verified_channels: list[str], vanity_slug: str, required_terms_version: str, actor: ReadinessActor, evidence_ref: str) -> dict[str, Any]:
        self._require_owner(actor)
        affiliate = self.engine.activate(affiliate_id, required_terms_version)
        token = generate_referral_token()
        identity = CanonicalIdentity(
            affiliate_id=affiliate.code,
            referral_token=token,
            public_display_name=public_display_name,
            email=email,
            affiliate_class=affiliate.affiliate_class,
        )
        self.identities[affiliate_id] = identity
        self.verified_channels[affiliate_id] = list(verified_channels)
        self.vanity_aliases[affiliate_id] = {"current": vanity_slug, "historical": []}
        assets = {
            "canonical_referral_token": token,
            "canonical_referral_path": f"/r/{token}",
            "current_vanity_path": f"/go/{vanity_slug}",
            "qr_asset": f"synthetic://qr/{token}",
            "campaign_links": [],
        }
        self.referral_assets[affiliate_id] = assets
        self._record("AFFILIATE_ACTIVATED", actor, affiliate_id, "OWNER_APPROVED_AFTER_TERMS", evidence_ref, after={"identity": asdict(identity), "assets": assets})
        return {"affiliate": asdict(affiliate), "identity": asdict(identity), "assets": dict(assets)}

    def affiliate_experience(self, affiliate_id: str, actor: ReadinessActor, products: list[dict[str, Any]]) -> dict[str, Any]:
        self._require_affiliate_self(actor, affiliate_id)
        identity = self.identities[affiliate_id]
        eligible = [dict(p) for p in products if p.get("affiliate_eligibility") in {"ELIGIBLE", "AFFILIATE_ELIGIBLE"}]
        commissions = [c for c in self.engine.commissions.values() if c.affiliate_id == affiliate_id]
        return {
            "identity": {**asdict(identity), "verified_channels": list(self.verified_channels[affiliate_id]), "status": self.engine.affiliates[affiliate_id].status},
            "assets": dict(self.referral_assets[affiliate_id]),
            "products": eligible,
            "performance": {
                "referral_events": len([r for r in self.engine.referrals.values() if r.affiliate_id == affiliate_id]),
                "attributed_orders": len([d for d in self.engine.decisions.values() if d.affiliate_id == affiliate_id and d.status == "ATTRIBUTED"]),
                "commissions": [{"order_id": c.order_id, "amount": str(c.amount), "status": c.status, "hold_until": c.hold_until.isoformat(), "payable": c.status == "PAYABLE", "exception": c.dispute_status} for c in commissions],
            },
            "support": {"allowed": ["campaign_ideas", "compliant_content_drafts", "product_education", "disclosure_guidance", "link_help", "qr_help", "preference_management"], "prohibited": ["approve_affiliate", "change_commission_rate", "rewrite_attribution", "authorize_payout", "erase_financial_history", "invent_entitlements", "suspend_without_authority"]},
        }

    def owner_experience(self, actor: ReadinessActor) -> dict[str, Any]:
        self._require_owner(actor)
        applications = [dict(item) for item in self.application_details.values()]
        affiliates = []
        for internal_id, affiliate in self.engine.affiliates.items():
            identity = self.identities.get(internal_id)
            affiliates.append({
                "internal_id": internal_id,
                "aff_id": affiliate.code,
                "status": affiliate.status,
                "classification": affiliate.affiliate_class,
                "verified_channels": list(self.verified_channels.get(internal_id, [])),
                "referral_token": identity.referral_token if identity else None,
                "vanity": dict(self.vanity_aliases.get(internal_id, {})),
                "terms": dict(self.terms.get(internal_id, {})),
            })
        decisions = [asdict(d) for d in self.engine.decisions.values()]
        commissions = [{**asdict(c), "amount": str(c.amount), "balance": str(c.balance), "qualifying_revenue": str(c.qualifying_revenue), "hold_until": c.hold_until.isoformat()} for c in self.engine.commissions.values()]
        payable = [c for c in commissions if c["status"] == "PAYABLE" and not c["compliance_hold"]]
        return {"applications": applications, "affiliates": affiliates, "attribution": decisions, "commissions": commissions, "payout_readiness": {"items": payable, "actual_payout_authorized": False}, "audit": [asdict(e) for e in self.audit]}

    def prepare_authority_action(self, action: str, subject_id: str, actor: ReadinessActor) -> dict[str, Any]:
        self._require_owner(actor)
        return {"action": action, "subject_id": subject_id, "state": "PREPARED_AWAITING_OWNER_AUTHORIZATION", "executed": False}


def governed_test_facts() -> dict[str, Any]:
    return {
        "program_state": "PRIVATE_PILOT",
        "applications_open": False,
        "eligibility": "Private-pilot invitations are reviewed individually; no follower-count entitlement is promised.",
        "offers": [
            {"product_id": "SYNTH-WELLNESS", "name": "Synthetic Wellness Offer", "affiliate_eligibility": "AFFILIATE_ELIGIBLE", "affiliate_commission_class": "WELLNESS_PHYSICAL_30", "rate": "0.30000000", "synthetic": True},
            {"product_id": "SYNTH-SUB", "name": "Synthetic Subscription Offer", "affiliate_eligibility": "AFFILIATE_ELIGIBLE", "affiliate_commission_class": "WELLNESS_SUB_30_5", "rate_sequence": {"payments_1_3": "0.30000000", "payments_4_plus": "0.05000000"}, "synthetic": True},
        ],
        "rates": {"WELLNESS_PHYSICAL_30": "0.30000000", "WELLNESS_SUB_30_5": {"payments_1_3": "0.30000000", "payments_4_plus": "0.05000000"}},
        "recurring": "Only governed subscription payment sequences earn recurring commission; cancellation produces no new commission.",
        "budly_help": "Budly may explain products, disclosures, links and QR assets, and draft compliant campaign ideas. Budly cannot approve Affiliates, change rates, rewrite attribution, or authorize payouts.",
    }


def run_synthetic_round_trip() -> dict[str, Any]:
    """Exercise the deterministic lifecycle without touching external systems."""
    synthetic_flags = FeatureFlags(True, True, True, True, False)
    engine = AffiliateEngine(synthetic_flags)
    service = G9COperatingExperience(engine, PublicAffiliateKnowledge(governed_test_facts()))
    applicant = ReadinessActor("synthetic-applicant", "SYNTHETIC_APPLICANT")
    owner = ReadinessActor("d-mac-synthetic-proof", "PROJECT_OWNER", authenticated=True)
    invitation = {"valid": True, "classification": "TEST_SYNTHETIC_NON_PRODUCTION_PERSON", "evidence_ref": "G9C-SYNTH-INV-001"}
    application = service.submit_private_application(invitation, {
        "applicant_email": "synthetic-affiliate@example.invalid",
        "desired_affiliate_class": "STANDARD",
        "public_display_name": "G9C Synthetic Affiliate",
        "social_channels": ["synthetic://instagram/g9c-test"],
        "review_evidence": ["TEST_ONLY", "NON_PRODUCTION_PERSON"],
    }, "g9c:synthetic:application:v1", applicant)
    affiliate = service.decide_application(application["id"], "APPROVE", "BOUNDED_SYNTHETIC_PROOF", "G9C-OWNER-REVIEW-001", owner)
    assert affiliate is not None
    affiliate_actor = ReadinessActor("synthetic-user", "AFFILIATE", affiliate.id, True)
    service.accept_terms(affiliate.id, "SYNTHETIC-TERMS-v1", _stable_hash("synthetic terms"), affiliate_actor, "G9C-TERMS-001")
    activation = service.activate_and_create_assets(affiliate.id, "G9C Synthetic Affiliate", affiliate.email, ["synthetic://instagram/g9c-test"], "g9c-synthetic", "SYNTHETIC-TERMS-v1", owner, "G9C-ACTIVATE-001")
    # Synthetic-only readiness state; no provider or real compliance profile is created.
    engine.affiliates[affiliate.id] = replace(
        engine.affiliates[affiliate.id],
        payout_profile_status="VERIFIED",
        tax_profile_status="NOT_REQUIRED_OR_UNKNOWN",
    )
    referral = engine.create_referral(affiliate.id, occurred_at=datetime(2026, 10, 5, 13, 0, tzinfo=timezone.utc))
    decision = engine.resolve_attribution("SYNTH-ORDER-001", [referral.id], at=datetime(2026, 10, 5, 14, 0, tzinfo=timezone.utc))
    product = governed_test_facts()["offers"][0]
    revenue = engine.process_revenue_event({
        "event_id": "SYNTH-REV-001", "order_id": "SYNTH-ORDER-001", "currency": "USD", "occurred_at": "2026-10-05T14:00:00+00:00",
        "line_items": [{"product_id": "SYNTH-WELLNESS", "merchandise_total": "200.00", "discount": "0", "refunded": "0"}],
    }, decision, {"SYNTH-WELLNESS": product})
    commission = engine.commissions[revenue["commission_id"]]
    pending_state = commission.status
    engine.mature(commission.id, commission.hold_until + timedelta(seconds=1))
    payout = engine.prepare_payout_batch("USD", actor_role="PROJECT_OWNER")
    owner_view = service.owner_experience(owner)
    affiliate_view = service.affiliate_experience(affiliate.id, affiliate_actor, governed_test_facts()["offers"])
    return {
        "classification": "TEST_SYNTHETIC_NON_PRODUCTION_PERSON",
        "application": application,
        "activation": activation,
        "referral_id": referral.id,
        "attribution": asdict(decision),
        "commission": {"id": commission.id, "amount": str(commission.amount), "pending_state": pending_state, "final_state": commission.status, "hold_until": commission.hold_until.isoformat()},
        "payout_readiness": payout,
        "payout_submitted": False,
        "affiliate_view": affiliate_view,
        "owner_view": owner_view,
        "production_feature_flags_touched": 0,
        "external_calls": 0,
    }
