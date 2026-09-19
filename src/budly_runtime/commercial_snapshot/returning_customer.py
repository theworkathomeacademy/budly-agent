"""Returning Customer & Member Retrieval Contract & Guardrails (CCS-001 / Phase 11).

Implements the verified customer context integration:
verified identity -> consent/use-scope check -> CRM lookup -> canonical IDs -> Snapshot lookup -> deterministic rules -> response

Strictly enforces:
- No fuzzy identity matching
- No unauthenticated account/purchase history disclosure
- No active benefit entitlement claim without active verified entitlement evidence
- No marketing follow-up when consent is not granted
- CRM outage fallback to general commercial assistance
- Duplicate identity escalation (no automatic merge)
- Cancelled/former membership benefit suppression
- Existing ownership recognition to avoid reselling non-repeat items
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Sequence

from .contract import CommercialCatalogRecord
from .enrichment import get_approved_enrichment
from .loader import CommercialSnapshotLoader

logger = logging.getLogger("commercial_catalog.returning_customer")


@dataclass(frozen=True)
class CustomerVerificationState:
    customer_id: str | None
    email: str | None
    is_verified: bool
    consent_scope: set[str]  # e.g. {"session", "crm_storage", "marketing_followup", "purchase_history_access"}
    is_duplicate_candidate: bool = False


@dataclass(frozen=True)
class EntitlementRecord:
    canonical_id: str
    entity_type: str
    status: str  # ACTIVE, CANCELLED, EXPIRED, PENDING
    purchased_at: str | None = None
    expires_at: str | None = None


@dataclass
class ReturningCustomerContext:
    verification_status: str  # ANONYMOUS, UNVERIFIED, VERIFIED, DUPLICATE_ESCALATION
    can_disclose_history: bool
    can_market_follow_up: bool
    active_entitlements: list[EntitlementRecord] = field(default_factory=list)
    past_purchases: list[str] = field(default_factory=list)
    available_benefits: list[str] = field(default_factory=list)
    guidance_message: str = ""
    crm_healthy: bool = True


class ReturningCustomerRetrievalService:
    """Service governing returning member and customer commercial interactions."""

    def __init__(self, snapshot_loader: CommercialSnapshotLoader) -> None:
        self.loader = snapshot_loader

    def evaluate_customer_turn(
        self,
        verification: CustomerVerificationState,
        crm_record: dict[str, Any] | None,
        crm_available: bool = True,
    ) -> ReturningCustomerContext:
        """Resolve returning customer context safely against snapshot data."""
        # 1. CRM Outage Handling: Fallback to general commercial assistance only
        if not crm_available:
            return ReturningCustomerContext(
                verification_status="CRM_OUTAGE",
                can_disclose_history=False,
                can_market_follow_up=False,
                guidance_message="I'm unable to access account records right now. I can help with general product information.",
                crm_healthy=False,
            )

        # 2. Duplicate Identity Candidate Check: Must Escalate, Never Merge Automatically
        if verification.is_duplicate_candidate:
            return ReturningCustomerContext(
                verification_status="DUPLICATE_ESCALATION",
                can_disclose_history=False,
                can_market_follow_up=False,
                guidance_message="There appears to be multiple records matching this contact. A team member will need to review your account.",
            )

        # 3. Anonymous / Unverified Customers: No Account History Disclosure
        if not verification.is_verified or not verification.customer_id:
            return ReturningCustomerContext(
                verification_status="ANONYMOUS" if not verification.email else "UNVERIFIED",
                can_disclose_history=False,
                can_market_follow_up=False,
                guidance_message="To access previous purchases or member benefits, identity verification is required.",
            )

        # 4. Verified Customer: Check Consent Scope
        can_disclose = "purchase_history_access" in verification.consent_scope or "crm_storage" in verification.consent_scope
        can_followup = "marketing_followup" in verification.consent_scope

        if not crm_record:
            return ReturningCustomerContext(
                verification_status="VERIFIED",
                can_disclose_history=can_disclose,
                can_market_follow_up=can_followup,
                guidance_message="No previous order history found.",
            )

        # 5. Extract Entitlements and Resolve Against Commercial Snapshot
        raw_entitlements = crm_record.get("entitlements", [])
        active_entitlements: list[EntitlementRecord] = []
        past_purchases: list[str] = crm_record.get("purchased_canonical_ids", [])
        benefits: list[str] = []

        for item in raw_entitlements:
            cid = item.get("canonical_id", "")
            status = item.get("status", "ACTIVE").upper()
            ent = EntitlementRecord(
                canonical_id=cid,
                entity_type=item.get("entity_type", "MEMBERSHIP"),
                status=status,
                purchased_at=item.get("purchased_at"),
                expires_at=item.get("expires_at"),
            )
            
            # Guardrail: Only ACTIVE entitlements yield current benefits
            if status == "ACTIVE":
                active_entitlements.append(ent)
                rec = self.loader.get_by_canonical_id(cid)
                if rec and rec.benefits:
                    benefits.extend(rec.benefits)
                elif not rec:
                    enrich = get_approved_enrichment(cid)
                    if enrich and enrich.get("benefits"):
                        benefits.extend(enrich["benefits"])

        return ReturningCustomerContext(
            verification_status="VERIFIED",
            can_disclose_history=can_disclose,
            can_market_follow_up=can_followup,
            active_entitlements=active_entitlements,
            past_purchases=past_purchases,
            available_benefits=list(dict.fromkeys(benefits)),  # deduplicate
            guidance_message="Active verified profile retrieved.",
        )

    def filter_recommendations_for_ownership(
        self,
        candidate_canonical_ids: Sequence[str],
        customer_context: ReturningCustomerContext,
    ) -> list[CommercialCatalogRecord]:
        """Filter out non-repeatable items (e.g. lifetime memberships, courses, books) already owned."""
        filtered_records: list[CommercialCatalogRecord] = []
        owned_set = set(customer_context.past_purchases)
        for ent in customer_context.active_entitlements:
            owned_set.add(ent.canonical_id)

        for cid in candidate_canonical_ids:
            rec = self.loader.get_by_canonical_id(cid)
            if not rec:
                continue

            # If user already owns this non-repeatable course/book/membership, suppress duplicate sale
            if cid in owned_set and rec.entity_type in {"COURSE", "BOOK", "NFT_MEMBERSHIP_PARENT", "NFT_MEMBERSHIP_TIER", "COMMUNITY_MEMBERSHIP"}:
                logger.info(f"Suppressing recommendation for already owned entity {cid}")
                continue

            filtered_records.append(rec)

        return filtered_records
