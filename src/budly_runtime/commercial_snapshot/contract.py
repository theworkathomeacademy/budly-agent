"""Canonical Commercial Catalog Data Contract (CCS-002).

Defines the normalized schema, validation rules, and checksum calculations for all
commercial catalog snapshot records.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

URL_REGEX = re.compile(
    r"^https?://[A-Za-z0-9\-\._~:/\?#\[\]@!$&'\(\)\*\+,;=%]+$"
)

ALLOWED_ENTITY_TYPES = frozenset({
    "PRODUCT",
    "BOOK",
    "COURSE",
    "COURSE_PAYMENT_PLAN",
    "SERVICE",
    "COMMUNITY_MEMBERSHIP",
    "NFT_MEMBERSHIP_PARENT",
    "NFT_MEMBERSHIP_TIER",
    "MEMBERSHIP",
    "SUBSCRIPTION",
    "BUNDLE",
})

ALLOWED_STATUSES = frozenset({
    "ACTIVE",
    "INACTIVE",
    "DRAFT",
    "ARCHIVED",
    "ACTIVE_CATALOG_GAP",
})

ALLOWED_APPROVAL_STATUSES = frozenset({
    "OWNER_APPROVED",
    "PENDING_REVIEW",
    "DEPRECATED",
})

ALLOWED_RELEASE_STATES = frozenset({
    "RELEASED",
    "APPROVED_NOT_RELEASED",
    "PRELAUNCH_CONFIGURATION_PRESENT",
    "DISCONTINUED",
})

ALLOWED_CATALOG_VISIBILITIES = frozenset({
    "visible",
    "catalog",
    "search",
    "hidden",
})

ALLOWED_STOCK_STATUSES = frozenset({
    "instock",
    "outofstock",
    "onbackorder",
    "not_applicable",
})

ALLOWED_BILLING_MODELS = frozenset({
    "ONE_TIME",
    "RECURRING_MONTHLY",
    "RECURRING_ANNUAL",
    "FREE",
    "INSTALLMENT",
})

ALLOWED_FULFILLMENT_TYPES = frozenset({
    "DIGITAL_DELIVERY",
    "PHYSICAL_SHIPPING",
    "MEMBERSHIP_ACCESS",
    "CONSULTATION_SERVICE",
    "EXTERNAL_ROUTE",
})

ALLOWED_FULFILLMENT_PLATFORMS = frozenset({
    "WOOCOMMERCE",
    "WIX_BOOKINGS",
    "WIX_PLANS",
    "STRIPE",
    "DISCORD",
    "EXTERNAL",
})

ALLOWED_PAYMENT_PROCESSORS = frozenset({
    "WOOCOMMERCE",
    "STRIPE",
    "WIX_BOOKINGS",
    "TBD_APPROVED_PROCESSOR",
    "NONE",
})

ALLOWED_SOURCE_AUTHORITIES = frozenset({
    "woocommerce",
    "wix_bookings",
    "owner_approved_specification",
    "woocommerce_external",
})

ALLOWED_BUDLY_VISIBILITIES = frozenset({
    "PUBLIC",
    "PRE_RELEASE_ALLOWED",
    "INTERNAL_ONLY",
    "EXCLUDED",
})


@dataclass
class CommercialCatalogRecord:
    canonical_id: str
    sku: str
    slug: str
    name: str
    entity_type: str
    category: list[str]
    brand: str
    status: str
    approval_status: str
    release_state: str
    customer_purchasable: bool
    catalog_visibility: str
    stock_status: str
    price_usd: float | None
    currency: str
    billing_model: str
    short_summary: str
    description: str
    benefits: list[str]
    audience: list[str]
    customer_goals: list[str]
    eligibility_rules: list[str]
    exclusions: list[str]
    fulfillment_type: str
    fulfillment_platform: str
    canonical_url: str
    checkout_url: str | None
    booking_url: str | None
    payment_plan_available: bool
    payment_plan_amount: float | None
    payment_plan_url: str | None
    payment_processor: str
    coupon_relationship: str | None
    wix_plan_id: str | None
    wordpress_page_id: int | str | None
    source_authority: str
    source_ids: dict[str, Any]
    source_updated_at: str | None
    snapshot_generated_at: str
    catalog_version: str
    budly_visibility: str = "PUBLIC"
    woo_product_id: int | None = None
    woo_parent_product_id: int | None = None
    woo_variation_id: int | None = None
    record_checksum: str = ""

    def __post_init__(self) -> None:
        if not self.record_checksum:
            self.record_checksum = self.compute_checksum()

    def compute_checksum(self) -> str:
        """Compute deterministic SHA256 checksum over canonical core attributes."""
        canonical_payload = {
            "canonical_id": self.canonical_id,
            "sku": self.sku,
            "slug": self.slug,
            "name": self.name,
            "entity_type": self.entity_type,
            "category": sorted(self.category),
            "brand": self.brand,
            "status": self.status,
            "approval_status": self.approval_status,
            "release_state": self.release_state,
            "customer_purchasable": self.customer_purchasable,
            "catalog_visibility": self.catalog_visibility,
            "stock_status": self.stock_status,
            "price_usd": self.price_usd,
            "currency": self.currency,
            "billing_model": self.billing_model,
            "short_summary": self.short_summary,
            "description": self.description,
            "benefits": self.benefits,
            "audience": self.audience,
            "customer_goals": self.customer_goals,
            "eligibility_rules": self.eligibility_rules,
            "exclusions": self.exclusions,
            "fulfillment_type": self.fulfillment_type,
            "fulfillment_platform": self.fulfillment_platform,
            "canonical_url": self.canonical_url,
            "checkout_url": self.checkout_url,
            "booking_url": self.booking_url,
            "payment_plan_available": self.payment_plan_available,
            "payment_plan_amount": self.payment_plan_amount,
            "payment_plan_url": self.payment_plan_url,
            "payment_processor": self.payment_processor,
            "coupon_relationship": self.coupon_relationship,
            "wix_plan_id": self.wix_plan_id,
            "wordpress_page_id": str(self.wordpress_page_id) if self.wordpress_page_id is not None else None,
            "source_authority": self.source_authority,
            "budly_visibility": self.budly_visibility,
            "woo_product_id": self.woo_product_id,
            "woo_parent_product_id": self.woo_parent_product_id,
            "woo_variation_id": self.woo_variation_id,
        }
        raw_bytes = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw_bytes).hexdigest()

    def validate(self) -> list[str]:
        """Validate record against CCS-002 data contract rules. Returns list of errors."""
        errors: list[str] = []
        if not self.canonical_id or not re.match(r"^[a-z0-9_]+:[a-z0-9_]+:[a-z0-9_\-:]+$", self.canonical_id):
            errors.append(f"Invalid canonical_id format: '{self.canonical_id}'")

        if not self.name or not self.name.strip():
            errors.append("Missing required field 'name'")

        if not self.slug or not self.slug.strip():
            errors.append("Missing required field 'slug'")

        if self.entity_type not in ALLOWED_ENTITY_TYPES:
            errors.append(f"Unknown entity_type: '{self.entity_type}'")

        if self.status not in ALLOWED_STATUSES:
            errors.append(f"Unknown status: '{self.status}'")

        if self.approval_status not in ALLOWED_APPROVAL_STATUSES:
            errors.append(f"Unknown approval_status: '{self.approval_status}'")

        if self.release_state not in ALLOWED_RELEASE_STATES:
            errors.append(f"Unknown release_state: '{self.release_state}'")

        if self.catalog_visibility not in ALLOWED_CATALOG_VISIBILITIES:
            errors.append(f"Unknown catalog_visibility: '{self.catalog_visibility}'")

        if self.stock_status not in ALLOWED_STOCK_STATUSES:
            errors.append(f"Unknown stock_status: '{self.stock_status}'")

        if self.billing_model not in ALLOWED_BILLING_MODELS:
            errors.append(f"Unknown billing_model: '{self.billing_model}'")

        if self.fulfillment_type not in ALLOWED_FULFILLMENT_TYPES:
            errors.append(f"Unknown fulfillment_type: '{self.fulfillment_type}'")

        if self.fulfillment_platform not in ALLOWED_FULFILLMENT_PLATFORMS:
            errors.append(f"Unknown fulfillment_platform: '{self.fulfillment_platform}'")

        if self.payment_processor not in ALLOWED_PAYMENT_PROCESSORS:
            errors.append(f"Unknown payment_processor: '{self.payment_processor}'")

        if self.source_authority not in ALLOWED_SOURCE_AUTHORITIES:
            errors.append(f"Unknown source_authority: '{self.source_authority}'")

        if self.budly_visibility not in ALLOWED_BUDLY_VISIBILITIES:
            errors.append(f"Unknown budly_visibility: '{self.budly_visibility}'")

        # URL validation
        if not self.canonical_url or not URL_REGEX.match(self.canonical_url):
            errors.append(f"Malformed canonical_url: '{self.canonical_url}'")

        if self.checkout_url and not URL_REGEX.match(self.checkout_url):
            errors.append(f"Malformed checkout_url: '{self.checkout_url}'")

        if self.booking_url and not URL_REGEX.match(self.booking_url):
            errors.append(f"Malformed booking_url: '{self.booking_url}'")

        if self.payment_plan_url and not URL_REGEX.match(self.payment_plan_url):
            errors.append(f"Malformed payment_plan_url: '{self.payment_plan_url}'")

        # Invariant: APPROVED_NOT_RELEASED must have customer_purchasable=False and budly_visibility=EXCLUDED
        if self.release_state == "APPROVED_NOT_RELEASED" and self.customer_purchasable:
            errors.append(
                f"Invariant violation: {self.canonical_id} is APPROVED_NOT_RELEASED but customer_purchasable is True"
            )

        if self.release_state == "APPROVED_NOT_RELEASED" and self.budly_visibility == "PUBLIC":
            errors.append(
                f"Invariant violation: {self.canonical_id} is APPROVED_NOT_RELEASED but budly_visibility is PUBLIC"
            )

        # Invariant: customer_purchasable=True must have valid destination URL
        if self.customer_purchasable and not self.canonical_url:
            errors.append(
                f"Invariant violation: {self.canonical_id} is customer_purchasable but has no valid destination URL"
            )

        # Checksum validation
        expected_checksum = self.compute_checksum()
        if self.record_checksum and self.record_checksum != expected_checksum:
            errors.append(
                f"Checksum mismatch for {self.canonical_id}: expected {expected_checksum}, found {self.record_checksum}"
            )

        return errors

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CommercialCatalogRecord":
        clean = dict(data)
        return cls(**clean)


@dataclass
class CatalogManifest:
    schema_version: str
    catalog_version: str
    generated_at: str
    source_max_updated_at: str | None
    event_reason: str
    triggering_entity: str
    source_record_count: int
    output_record_count: int
    generator_version: str
    csv_sha256: str
    json_sha256: str
    validation_status: str
    source_inventory_count: int = 0
    public_record_count: int = 0
    excluded_record_count: int = 0
    pre_release_record_count: int = 0
    internal_only_record_count: int = 0
    visibility_policy: str = "CCS-006"
    visibility_policy_version: str = "0.1"
    previous_catalog_version: str | None = None

    def __post_init__(self) -> None:
        if self.source_inventory_count == 0 and self.source_record_count > 0:
            self.source_inventory_count = self.source_record_count
        if self.public_record_count == 0 and self.output_record_count > 0:
            self.public_record_count = self.output_record_count

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CatalogManifest":
        return cls(**data)

