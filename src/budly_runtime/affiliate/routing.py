"""Canonical Routing Engine, Campaign Links & QR Router (G9B.7B).

Supports:
- /r/{token} -> Canonical token routing
- /go/{slug} -> Primary vanity or Historical Redirect routing
- /go/{slug}/{campaign} -> Campaign-specific vanity routing
- /qr/{token} -> Permanent QR routing
All resolve deterministically to ONE canonical Affiliate ID.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .identity import CanonicalIdentity
from .vanity import VanityLinkManager

ROUTE_R_REGEX = re.compile(r"^/r/([A-HJ-NP-Z2-9]{8,12})$")
ROUTE_QR_REGEX = re.compile(r"^/qr/([A-HJ-NP-Z2-9]{8,12})$")
ROUTE_GO_CAMPAIGN_REGEX = re.compile(r"^/go/([a-z0-9_-]+)/([a-z0-9_-]+)$")
ROUTE_GO_REGEX = re.compile(r"^/go/([a-z0-9_-]+)$")


@dataclass(frozen=True)
class ResolvedRoute:
    affiliate_id: str
    routing_method: str  # 'CANONICAL_TOKEN', 'PRIMARY_VANITY', 'HISTORICAL_REDIRECT', 'CAMPAIGN_VANITY', 'PERMANENT_QR'
    referral_token: str
    canonical_url: str
    target_slug: str | None = None
    campaign_id: str | None = None
    product_id: str | None = None
    source: str | None = None
    platform: str | None = None


class CanonicalRouter:
    """Deterministic routing engine that resolves web/QR paths to canonical affiliate identities."""

    def __init__(self, vanity_manager: VanityLinkManager) -> None:
        self.vanity_manager = vanity_manager
        self.identities_by_id: dict[str, CanonicalIdentity] = {}
        self.identities_by_token: dict[str, CanonicalIdentity] = {}
        self.campaigns: dict[str, dict[str, Any]] = {}  # campaign_id -> metadata

    def register_identity(self, identity: CanonicalIdentity) -> None:
        """Register a canonical identity."""
        self.identities_by_id[identity.affiliate_id] = identity
        self.identities_by_token[identity.referral_token] = identity

    def register_campaign(self, campaign_id: str, slug: str, product_id: str | None = None, title: str = "") -> None:
        """Register an approved campaign route."""
        self.campaigns[slug.lower()] = {
            "campaign_id": campaign_id,
            "slug": slug.lower(),
            "product_id": product_id,
            "title": title,
        }

    def resolve_path(self, path: str, query_params: dict[str, str] | None = None) -> ResolvedRoute | None:
        """Resolve any incoming path (/r/..., /go/..., /qr/...) to canonical affiliate identity."""
        cleaned_path = "/" + path.strip("/")
        params = query_params or {}

        # 1. Permanent QR Route: /qr/{token}
        qr_match = ROUTE_QR_REGEX.match(cleaned_path)
        if qr_match:
            token = qr_match.group(1)
            identity = self.identities_by_token.get(token)
            if not identity:
                return None
            return ResolvedRoute(
                affiliate_id=identity.affiliate_id,
                routing_method="PERMANENT_QR",
                referral_token=identity.referral_token,
                canonical_url=f"/r/{identity.referral_token}",
                source=params.get("source", "qr"),
                platform=params.get("platform"),
            )

        # 2. Canonical Token Route: /r/{token}
        r_match = ROUTE_R_REGEX.match(cleaned_path)
        if r_match:
            token = r_match.group(1)
            identity = self.identities_by_token.get(token)
            if not identity:
                return None
            return ResolvedRoute(
                affiliate_id=identity.affiliate_id,
                routing_method="CANONICAL_TOKEN",
                referral_token=identity.referral_token,
                canonical_url=f"/r/{identity.referral_token}",
                source=params.get("source"),
                platform=params.get("platform"),
            )

        # 3. Campaign Vanity Route: /go/{slug}/{campaign}
        camp_match = ROUTE_GO_CAMPAIGN_REGEX.match(cleaned_path)
        if camp_match:
            slug = camp_match.group(1)
            campaign_slug = camp_match.group(2)
            affiliate_id, alias_status = self.vanity_manager.resolve_slug(slug)
            if not affiliate_id:
                return None
            identity = self.identities_by_id.get(affiliate_id)
            if not identity:
                return None
            camp_info = self.campaigns.get(campaign_slug.lower())
            return ResolvedRoute(
                affiliate_id=identity.affiliate_id,
                routing_method="CAMPAIGN_VANITY",
                referral_token=identity.referral_token,
                canonical_url=f"/r/{identity.referral_token}",
                target_slug=slug,
                campaign_id=camp_info["campaign_id"] if camp_info else campaign_slug,
                product_id=camp_info["product_id"] if camp_info else None,
                source=params.get("source", "social"),
                platform=params.get("platform"),
            )

        # 4. Standard Vanity Route: /go/{slug}
        go_match = ROUTE_GO_REGEX.match(cleaned_path)
        if go_match:
            slug = go_match.group(1)
            affiliate_id, alias_status = self.vanity_manager.resolve_slug(slug)
            if not affiliate_id:
                return None
            identity = self.identities_by_id.get(affiliate_id)
            if not identity:
                return None
            routing_method = "PRIMARY_VANITY" if alias_status == "PRIMARY" else "HISTORICAL_REDIRECT"
            return ResolvedRoute(
                affiliate_id=identity.affiliate_id,
                routing_method=routing_method,
                referral_token=identity.referral_token,
                canonical_url=f"/r/{identity.referral_token}",
                target_slug=slug,
                source=params.get("source"),
                platform=params.get("platform"),
            )

        return None
