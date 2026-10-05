"""Budly Secure Affiliate Management, Tenant Isolation & Owner Query Engine (G9B.7B).

Supports:
- Convergent lookup across: Canonical ID, Referral Token, Primary Slug, Historical Slug, Verified Email.
- Strict Tenant Isolation: Affiliate A cannot view Affiliate B's data.
- Profile Retrieval with all governed fields.
- Owner Budly Query Handler: Natural language analysis & recommendations (non-financial execution only).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .analytics import AnalyticsEngine
from .identity import CanonicalIdentity, IdentityError, normalize_slug
from .preferences import AffiliatePreferenceStore
from .routing import CanonicalRouter
from .vanity import VanityLinkManager


class AccessControlError(PermissionError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    role: str  # 'PROJECT_OWNER', 'AFFILIATE', 'ANONYMOUS'
    affiliate_id: str | None = None  # populated if role is AFFILIATE
    authenticated: bool = False


class BudlyAffiliateService:
    """Secure Budly runtime service for Affiliate management and owner queries."""

    def __init__(
        self,
        router: CanonicalRouter,
        vanity_manager: VanityLinkManager,
        preference_store: AffiliatePreferenceStore,
        analytics_engine: AnalyticsEngine,
    ) -> None:
        self.router = router
        self.vanity_manager = vanity_manager
        self.preference_store = preference_store
        self.analytics_engine = analytics_engine
        self.identities_by_id: dict[str, CanonicalIdentity] = {}
        self.identities_by_email: dict[str, str] = {}  # email -> affiliate_id
        self.identities_by_token: dict[str, str] = {}  # token -> affiliate_id
        self.affiliate_status: dict[str, str] = {}  # affiliate_id -> status
        self.affiliate_classes: dict[str, list[str]] = {}  # affiliate_id -> list of eligible classes

    def register_affiliate(
        self,
        identity: CanonicalIdentity,
        initial_slug: str | None = None,
        status: str = "ACTIVE",
        eligible_classes: list[str] | None = None,
    ) -> None:
        """Register an affiliate in the service."""
        self.identities_by_id[identity.affiliate_id] = identity
        self.identities_by_email[identity.email.lower()] = identity.affiliate_id
        self.identities_by_token[identity.referral_token] = identity.affiliate_id
        self.affiliate_status[identity.affiliate_id] = status
        self.affiliate_classes[identity.affiliate_id] = eligible_classes or [
            "BOTANICAL_COLLECTION_25", "INFUSED_BASICS_25", "WELLNESS_PHYSICAL_30", "LEGENDS_MEMBERSHIP_10"
        ]
        self.router.register_identity(identity)
        if initial_slug:
            self.vanity_manager.register_initial_alias(identity.affiliate_id, initial_slug)

    def resolve_canonical_id(self, query: str) -> str | None:
        """Resolve any authoritative canonical identifier to Canonical ID.
        
        Authoritative keys:
        - Canonical Affiliate ID (AFF-######)
        - Canonical Referral Token (8-12 alphanumeric chars)
        - Authorized Verified Email
        - Primary or Historical Vanity Slug
        
        NOTE: Per G9B.7B, Public Display Name is NOT an authoritative canonical-resolution key.
        """
        cleaned = query.strip()
        if not cleaned:
            return None

        # 1. Check direct Canonical ID (AFF-######)
        if cleaned.upper() in self.identities_by_id:
            return cleaned.upper()

        # 2. Check Token (8-12 chars)
        if cleaned.upper() in self.identities_by_token:
            return self.identities_by_token[cleaned.upper()]

        # 3. Check Email
        if "@" in cleaned and cleaned.lower() in self.identities_by_email:
            return self.identities_by_email[cleaned.lower()]

        # 4. Check Vanity Slug (Primary or Historical)
        slug = normalize_slug(cleaned)
        aff_id, _ = self.vanity_manager.resolve_slug(slug)
        if aff_id:
            return aff_id

        return None

    def search_by_name_hint(self, name_hint: str) -> list[CanonicalIdentity]:
        """Search identities by display name hint (Owner lookup aid / search field only)."""
        cleaned = name_hint.strip().lower()
        if not cleaned:
            return []
        matches = []
        for identity in self.identities_by_id.values():
            name_parts = [p.lower() for p in identity.public_display_name.split() if len(p) >= 3]
            if (
                cleaned == identity.public_display_name.lower()
                or any(part in cleaned for part in name_parts)
                or (len(cleaned) >= 3 and cleaned in identity.public_display_name.lower())
            ):
                matches.append(identity)
        return matches

    def _authorize(self, actor: ActorContext, target_affiliate_id: str) -> None:
        """Enforce strict tenant isolation and role-based access control."""
        if not actor.authenticated:
            raise AccessControlError("UNAUTHENTICATED", "Authentication required for affiliate data access")
        if actor.role == "PROJECT_OWNER":
            return
        if actor.role == "AFFILIATE":
            if actor.affiliate_id != target_affiliate_id:
                raise AccessControlError("TENANT_ISOLATION_VIOLATION", "Access to another affiliate's private data is prohibited")
            return
        raise AccessControlError("UNAUTHORIZED_ROLE", f"Role '{actor.role}' cannot access affiliate data")

    def get_profile(self, identifier: str, actor: ActorContext, engine_commissions: list[Any] | None = None) -> dict[str, Any]:
        """Retrieve authorized affiliate profile."""
        affiliate_id = self.resolve_canonical_id(identifier)
        if not affiliate_id or affiliate_id not in self.identities_by_id:
            raise IdentityError("AFFILIATE_NOT_FOUND", f"Could not resolve affiliate identifier '{identifier}'")

        self._authorize(actor, affiliate_id)
        identity = self.identities_by_id[affiliate_id]
        primary_slug = self.vanity_manager.affiliate_primary.get(affiliate_id)
        aliases = self.vanity_manager.get_affiliate_aliases(affiliate_id)
        preferences = self.preference_store.get_all_preferences(affiliate_id)

        primary_alias = self.vanity_manager.aliases.get(primary_slug) if primary_slug else None
        cooldown_until = primary_alias.cooldown_until.isoformat() if primary_alias else None
        rollback_deadline = primary_alias.rollback_deadline.isoformat() if primary_alias else None
        previous_alias = primary_alias.previous_alias if primary_alias else None

        analytics = self.analytics_engine.get_affiliate_analytics(affiliate_id, engine_commissions or [])

        return {
            "affiliate_id": identity.affiliate_id,
            "status": self.affiliate_status.get(affiliate_id, "ACTIVE"),
            "public_display_name": identity.public_display_name,
            "email": identity.email if actor.role != "AFFILIATE" or actor.affiliate_id == affiliate_id else None,
            "canonical_referral_token": identity.referral_token,
            "canonical_referral_url": f"https://wakenbakelounge.com/r/{identity.referral_token}",
            "primary_vanity_slug": primary_slug,
            "primary_vanity_url": f"https://wakenbakelounge.com/go/{primary_slug}" if primary_slug else None,
            "historical_aliases": [a.slug for a in aliases if a.status == "HISTORICAL_REDIRECT"],
            "eligible_commission_classes": self.affiliate_classes.get(affiliate_id, []),
            "cooldown_until": cooldown_until,
            "rollback_deadline": rollback_deadline,
            "previous_alias": previous_alias,
            "preferences": [p.to_dict() for p in preferences],
            "analytics": analytics.to_dict(),
        }

    def handle_owner_query(self, query: str, actor: ActorContext, engine_commissions: list[Any] | None = None) -> dict[str, Any]:
        """Execute authorized owner command (retrieve, analyze, summarize, recommend)."""
        if not actor.authenticated or actor.role != "PROJECT_OWNER":
            raise AccessControlError("OWNER_ROLE_REQUIRED", "Owner query handler requires PROJECT_OWNER authority")

        cleaned = query.strip()
        target_id = None

        # 1. Check direct Canonical ID, Token, or Email in query text
        for word in cleaned.split():
            clean_word = word.strip("?,.!\"'")
            res_id = self.resolve_canonical_id(clean_word)
            if res_id:
                target_id = res_id
                break

        # 2. Check direct Vanity Slugs in query text
        if not target_id:
            for slug, alias in self.vanity_manager.aliases.items():
                if slug in cleaned.lower():
                    target_id = alias.affiliate_id
                    break

        # 3. Name hint search & disambiguation (Search lookup aid only)
        if not target_id:
            matching_candidates = self.search_by_name_hint(cleaned)
            if len(matching_candidates) > 1:
                return {
                    "query": query,
                    "status": "AMBIGUOUS_MATCH",
                    "message": f"Multiple affiliates match '{query}'. Disambiguation required. Please specify by canonical ID (AFF-######) or vanity slug.",
                    "matching_candidates": [
                        {"affiliate_id": m.affiliate_id, "name": m.public_display_name, "email": m.email}
                        for m in matching_candidates
                    ],
                }
            elif len(matching_candidates) == 1:
                target_id = matching_candidates[0].affiliate_id

        if not target_id:
            return {
                "query": query,
                "status": "UNRESOLVED",
                "message": "Could not identify an affiliate from the query text. Please specify by canonical ID (AFF-######) or vanity slug.",
            }

        profile = self.get_profile(target_id, actor, engine_commissions)
        name = profile["public_display_name"]
        primary_slug = profile["primary_vanity_slug"]
        analytics = profile["analytics"]

        # Intent matching
        if "how is" in cleaned.lower() or "performing" in cleaned.lower() or "analytics" in cleaned.lower():
            return {
                "query": query,
                "affiliate_id": target_id,
                "name": name,
                "intent": "PERFORMANCE_SUMMARY",
                "summary": (
                    f"{name} ({target_id}) has generated {analytics['total_clicks']} clicks, "
                    f"{analytics['total_orders']} orders, ${analytics['qualifying_revenue']} qualifying revenue, "
                    f"and ${analytics['commission_total']} total commission (Pending: ${analytics['commission_pending']}, "
                    f"Payable: ${analytics['commission_payable']}, Paid: ${analytics['commission_paid']})."
                ),
                "data": analytics,
            }

        if "vanity link" in cleaned.lower() or "url" in cleaned.lower() or "slug" in cleaned.lower():
            return {
                "query": query,
                "affiliate_id": target_id,
                "name": name,
                "intent": "VANITY_LINK_INQUIRY",
                "primary_vanity_url": profile["primary_vanity_url"],
                "canonical_url": profile["canonical_referral_url"],
                "historical_aliases": profile["historical_aliases"],
                "cooldown_until": profile["cooldown_until"],
                "rollback_deadline": profile["rollback_deadline"],
            }

        if "when may" in cleaned.lower() or "change" in cleaned.lower() or "cooldown" in cleaned.lower():
            return {
                "query": query,
                "affiliate_id": target_id,
                "name": name,
                "intent": "COOLDOWN_STATUS",
                "cooldown_until": profile["cooldown_until"],
                "rollback_deadline": profile["rollback_deadline"],
                "can_rollback": profile["rollback_deadline"] is not None and datetime.fromisoformat(profile["rollback_deadline"]) >= datetime.now(timezone.utc),
            }

        if "preference" in cleaned.lower():
            return {
                "query": query,
                "affiliate_id": target_id,
                "name": name,
                "intent": "PREFERENCES_VIEW",
                "preferences": profile["preferences"],
            }

        if "recommend" in cleaned.lower() or "campaign" in cleaned.lower():
            # Build recommendation based on profile/preferences
            pref_dict = {p["preference_key"]: p["preference_value"] for p in profile["preferences"]}
            preferred_product = pref_dict.get("product_focus", "Infused Basics & Botanical Collection")
            return {
                "query": query,
                "affiliate_id": target_id,
                "name": name,
                "intent": "CAMPAIGN_RECOMMENDATION",
                "recommended_campaign": f"Educational Infusion Recipe Spotlight featuring {preferred_product}",
                "rationale": f"Aligned with {name}'s creator authority, educational focus, and preferred channels.",
                "proposed_routes": [
                    f"https://wakenbakelounge.com/go/{primary_slug}/infused-basics",
                    f"https://wakenbakelounge.com/go/{primary_slug}/botanical-collection",
                ],
            }

        # Default: Pull up full profile
        return {
            "query": query,
            "affiliate_id": target_id,
            "name": name,
            "intent": "PROFILE_RETRIEVAL",
            "profile": profile,
        }
