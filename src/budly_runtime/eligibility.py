"""Governed Product Eligibility & Identity Normalization (MA-005 Phase B).

Deterministic eligibility resolver distinguishing:
- PUBLIC_APPROVED
- RESTRICTED
- UNRESOLVED

Fail-closed on RESTRICTED and UNRESOLVED.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ProductEligibilityStatus(str, Enum):
    PUBLIC_APPROVED = "PUBLIC_APPROVED"
    RESTRICTED = "RESTRICTED"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class ProductEligibilityDecision:
    status: ProductEligibilityStatus
    reason: str
    product_id: str | int | None = None
    slug: str | None = None
    canonical_id: str | None = None
    details: dict[str, Any] | None = None


# Explicit BROS / CCSS / unreleased community tier exclusions (Fail Closed)
EXCLUDED_PRODUCT_SLUGS: frozenset[str] = frozenset({
    "lounge-pass",
    "lounge-member",
    "lounge-elite",
})

EXCLUDED_CANONICAL_PREFIXES: tuple[str, ...] = (
    "wnb:community:",
)

# Canonical Identity / Slug / Alias normalization table
KNOWN_PRODUCT_MAPPINGS: dict[str, dict[str, Any]] = {
    "50": {
        "woo_id": 50,
        "slug": "therapeutic-body-butter",
        "canonical_id": "ccc:product:therapeutic-body-butter",
        "name": "Therapeutic Body Butter",
        "canonical_url": "https://cccultivate.com/product/therapeutic-body-butter/",
    },
    "therapeutic-body-butter": {
        "woo_id": 50,
        "slug": "therapeutic-body-butter",
        "canonical_id": "ccc:product:therapeutic-body-butter",
        "name": "Therapeutic Body Butter",
        "canonical_url": "https://cccultivate.com/product/therapeutic-body-butter/",
    },
    "ccc:product:therapeutic-body-butter": {
        "woo_id": 50,
        "slug": "therapeutic-body-butter",
        "canonical_id": "ccc:product:therapeutic-body-butter",
        "name": "Therapeutic Body Butter",
        "canonical_url": "https://cccultivate.com/product/therapeutic-body-butter/",
    },
    "57": {
        "woo_id": 57,
        "slug": "therapeutic-oil-tincture-1-time",
        "canonical_id": "ccc:product:therapeutic-oil-tincture",
        "name": "Therapeutic Oil Tincture 1-time",
        "canonical_url": "https://cccultivate.com/product/therapeutic-oil-tincture-1-time/",
    },
    "therapeutic-oil-tincture": {
        "woo_id": 57,
        "slug": "therapeutic-oil-tincture-1-time",
        "canonical_id": "ccc:product:therapeutic-oil-tincture",
        "name": "Therapeutic Oil Tincture 1-time",
        "canonical_url": "https://cccultivate.com/product/therapeutic-oil-tincture-1-time/",
    },
    "therapeutic-oil-tincture-1-time": {
        "woo_id": 57,
        "slug": "therapeutic-oil-tincture-1-time",
        "canonical_id": "ccc:product:therapeutic-oil-tincture",
        "name": "Therapeutic Oil Tincture 1-time",
        "canonical_url": "https://cccultivate.com/product/therapeutic-oil-tincture-1-time/",
    },
    "ccc:product:therapeutic-oil-tincture": {
        "woo_id": 57,
        "slug": "therapeutic-oil-tincture-1-time",
        "canonical_id": "ccc:product:therapeutic-oil-tincture",
        "name": "Therapeutic Oil Tincture 1-time",
        "canonical_url": "https://cccultivate.com/product/therapeutic-oil-tincture-1-time/",
    },
    "130": {
        "woo_id": 130,
        "slug": "cbd-tincture-spray",
        "canonical_id": "ccc:product:cbd-tincture-spray",
        "name": "CBD Tincture Spray",
        "canonical_url": "https://cccultivate.com/product/cbd-tincture-spray/",
    },
    "cbd-tincture-spray": {
        "woo_id": 130,
        "slug": "cbd-tincture-spray",
        "canonical_id": "ccc:product:cbd-tincture-spray",
        "name": "CBD Tincture Spray",
        "canonical_url": "https://cccultivate.com/product/cbd-tincture-spray/",
    },
    "therapeutic-spray": {
        "woo_id": 130,
        "slug": "cbd-tincture-spray",
        "canonical_id": "ccc:product:cbd-tincture-spray",
        "name": "CBD Tincture Spray",
        "canonical_url": "https://cccultivate.com/product/cbd-tincture-spray/",
    },
    "ccc:product:cbd-tincture-spray": {
        "woo_id": 130,
        "slug": "cbd-tincture-spray",
        "canonical_id": "ccc:product:cbd-tincture-spray",
        "name": "CBD Tincture Spray",
        "canonical_url": "https://cccultivate.com/product/cbd-tincture-spray/",
    },
    "101": {
        "woo_id": 101,
        "slug": "therapeutic-combo-one-time-purchase",
        "canonical_id": "ccc:product:therapeutic-combo",
        "name": "Therapeutic Combo | One-Time Purchase",
        "canonical_url": "https://cccultivate.com/product/therapeutic-combo-one-time-purchase/",
    },
    "therapeutic-combo": {
        "woo_id": 101,
        "slug": "therapeutic-combo-one-time-purchase",
        "canonical_id": "ccc:product:therapeutic-combo",
        "name": "Therapeutic Combo | One-Time Purchase",
        "canonical_url": "https://cccultivate.com/product/therapeutic-combo-one-time-purchase/",
    },
    "therapeutic-combo-one-time-purchase": {
        "woo_id": 101,
        "slug": "therapeutic-combo-one-time-purchase",
        "canonical_id": "ccc:product:therapeutic-combo",
        "name": "Therapeutic Combo | One-Time Purchase",
        "canonical_url": "https://cccultivate.com/product/therapeutic-combo-one-time-purchase/",
    },
    "ccc:product:therapeutic-combo": {
        "woo_id": 101,
        "slug": "therapeutic-combo-one-time-purchase",
        "canonical_id": "ccc:product:therapeutic-combo",
        "name": "Therapeutic Combo | One-Time Purchase",
        "canonical_url": "https://cccultivate.com/product/therapeutic-combo-one-time-purchase/",
    },
    "913": {
        "woo_id": 913,
        "slug": "wakenbake-lounge-cannabis-botanical-collection-volume-1",
        "canonical_id": "ccc:book:wakenbake-lounge-cannabis-botanical-collection-volume-1",
        "name": "Wake'n'Bake Lounge Cannabis Botanical Collection – Volume 1",
        "canonical_url": "https://cccultivate.com/product/wakenbake-lounge-cannabis-botanical-collection-volume-1/",
    },
    "wakenbake-lounge-cannabis-botanical-collection-volume-1": {
        "woo_id": 913,
        "slug": "wakenbake-lounge-cannabis-botanical-collection-volume-1",
        "canonical_id": "ccc:book:wakenbake-lounge-cannabis-botanical-collection-volume-1",
        "name": "Wake'n'Bake Lounge Cannabis Botanical Collection – Volume 1",
        "canonical_url": "https://cccultivate.com/product/wakenbake-lounge-cannabis-botanical-collection-volume-1/",
    },
    "botanical-collection": {
        "woo_id": 913,
        "slug": "wakenbake-lounge-cannabis-botanical-collection-volume-1",
        "canonical_id": "ccc:book:wakenbake-lounge-cannabis-botanical-collection-volume-1",
        "name": "Wake'n'Bake Lounge Cannabis Botanical Collection – Volume 1",
        "canonical_url": "https://cccultivate.com/product/wakenbake-lounge-cannabis-botanical-collection-volume-1/",
    },
    "150": {
        "woo_id": 150,
        "slug": "culinary-cannabis",
        "canonical_id": "ccc:course:culinary-cannabis",
        "name": "Culinary Cannabis",
        "canonical_url": "https://cccultivate.com/product/culinary-cannabis/",
    },
    "culinary-cannabis": {
        "woo_id": 150,
        "slug": "culinary-cannabis",
        "canonical_id": "ccc:course:culinary-cannabis",
        "name": "Culinary Cannabis",
        "canonical_url": "https://cccultivate.com/product/culinary-cannabis/",
    },
}


class ProductEligibilityResolver:
    """Evaluates governed product eligibility and normalizes identity across live WooCommerce and snapshots."""

    def __init__(self, overrides_by_slug: dict[str, dict[str, Any]] | None = None) -> None:
        self.overrides_by_slug = overrides_by_slug or {}

    def resolve(self, product: dict[str, Any] | None) -> ProductEligibilityDecision:
        if not product or not isinstance(product, dict):
            return ProductEligibilityDecision(
                status=ProductEligibilityStatus.UNRESOLVED,
                reason="EMPTY_OR_INVALID_PRODUCT_PAYLOAD",
            )

        slug = str(product.get("slug", "")).strip().lower()
        prod_id = product.get("id") or product.get("product_id")
        canonical_id = product.get("canonical_id")

        # 1. Check explicit exclusions (BROS / CCSS / unreleased community tiers)
        if slug in EXCLUDED_PRODUCT_SLUGS:
            return ProductEligibilityDecision(
                status=ProductEligibilityStatus.RESTRICTED,
                reason="EXPLICIT_EXCLUSION_UNRELEASED_COMMUNITY_TIER",
                product_id=prod_id,
                slug=slug,
            )
        if canonical_id and any(canonical_id.startswith(p) for p in EXCLUDED_CANONICAL_PREFIXES):
            return ProductEligibilityDecision(
                status=ProductEligibilityStatus.RESTRICTED,
                reason="EXPLICIT_EXCLUSION_UNRELEASED_COMMUNITY_TIER",
                product_id=prod_id,
                slug=slug,
                canonical_id=canonical_id,
            )

        # 2. Check password protection
        if product.get("is_password_protected") is True:
            return ProductEligibilityDecision(
                status=ProductEligibilityStatus.RESTRICTED,
                reason="PASSWORD_PROTECTED",
                product_id=prod_id,
                slug=slug,
            )

        # 3. Check publication status
        status = str(product.get("status", "publish")).lower()
        if status in {"draft", "trash", "private", "pending", "archived"}:
            return ProductEligibilityDecision(
                status=ProductEligibilityStatus.RESTRICTED,
                reason=f"NON_PUBLIC_STATUS_{status.upper()}",
                product_id=prod_id,
                slug=slug,
            )

        # 4. Check explicit override from products.json layer
        override = self.overrides_by_slug.get(slug)
        if override:
            if override.get("active") is False or override.get("status") in {"denied", "restricted", "blocked"}:
                return ProductEligibilityDecision(
                    status=ProductEligibilityStatus.RESTRICTED,
                    reason="CONFIG_OVERRIDE_DENIED",
                    product_id=prod_id,
                    slug=slug,
                )

        # 5. Check catalog visibility
        catalog_vis = str(product.get("catalog_visibility", "visible")).lower()
        if catalog_vis in {"hidden", "search"}:
            return ProductEligibilityDecision(
                status=ProductEligibilityStatus.RESTRICTED,
                reason=f"CATALOG_VISIBILITY_{catalog_vis.upper()}",
                product_id=prod_id,
                slug=slug,
            )

        prod_type = str(product.get("type", "simple")).lower()
        if prod_type not in {"simple", "variable", "external", "grouped", "fsb-subscription"}:
            return ProductEligibilityDecision(
                status=ProductEligibilityStatus.RESTRICTED,
                reason="UNSUPPORTED_PRODUCT_TYPE",
                product_id=prod_id,
                slug=slug,
            )

        # Look up canonical identity
        norm = KNOWN_PRODUCT_MAPPINGS.get(slug) or (KNOWN_PRODUCT_MAPPINGS.get(str(prod_id)) if prod_id else None)
        resolved_canonical_id = canonical_id or (norm["canonical_id"] if norm else f"ccc:product:{slug}")

        return ProductEligibilityDecision(
            status=ProductEligibilityStatus.PUBLIC_APPROVED,
            reason="GOVERNED_PUBLIC_APPROVED",
            product_id=prod_id,
            slug=slug,
            canonical_id=resolved_canonical_id,
        )

    def normalize_identity(self, identifier: str | int) -> ProductEligibilityDecision:
        key = str(identifier).strip().lower()
        if not key:
            return ProductEligibilityDecision(
                status=ProductEligibilityStatus.UNRESOLVED,
                reason="EMPTY_IDENTIFIER",
            )

        # Check ambiguous identifiers
        ambiguous_terms = {"membership", "memberships", "class", "classes", "course", "courses", "payment plan", "payment plans"}
        if key in ambiguous_terms:
            return ProductEligibilityDecision(
                status=ProductEligibilityStatus.UNRESOLVED,
                reason="AMBIGUOUS_IDENTIFIER",
            )

        # Direct canonical mapping lookup
        if key in KNOWN_PRODUCT_MAPPINGS:
            entry = KNOWN_PRODUCT_MAPPINGS[key]
            slug = entry["slug"]
            if slug in EXCLUDED_PRODUCT_SLUGS:
                return ProductEligibilityDecision(
                    status=ProductEligibilityStatus.RESTRICTED,
                    reason="EXPLICIT_EXCLUSION_UNRELEASED_COMMUNITY_TIER",
                    product_id=entry["woo_id"],
                    slug=slug,
                    canonical_id=entry["canonical_id"],
                )
            return ProductEligibilityDecision(
                status=ProductEligibilityStatus.PUBLIC_APPROVED,
                reason="CANONICAL_IDENTITY_RESOLVED",
                product_id=entry["woo_id"],
                slug=slug,
                canonical_id=entry["canonical_id"],
                details=entry,
            )

        if key.isdigit():
            return ProductEligibilityDecision(
                status=ProductEligibilityStatus.UNRESOLVED,
                reason="UNKNOWN_PRODUCT_ID",
                product_id=int(key),
            )

        return ProductEligibilityDecision(
            status=ProductEligibilityStatus.UNRESOLVED,
            reason="UNKNOWN_IDENTIFIER",
            slug=key,
        )
