"""Deterministic Rebuild Capability & Orchestration Engine (CCS-001 / CCS-003).

Provides `rebuild_catalog(event_reason, triggering_entity, ...)` orchestrating:
1. Full source fetch
2. Normalization & approved enrichment join
3. In-memory validation
4. Artifact generation (JSON, CSV, Manifest) to Staging
5. Staged artifact validation (hashes, parity)
6. Quarantine on failure / Atomic publish to Current on success
7. Cache invalidation & reload
8. Automated health probes
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .contract import CatalogManifest, CommercialCatalogRecord
from .enrichment import APPROVED_ENRICHMENT_REGISTRY, get_approved_enrichment
from .fetcher import WooCommerceCatalogFetcher
from .generator import CommercialSnapshotGenerator
from .loader import CommercialSnapshotLoader
from .resolver import DeterministicEntityResolver
from .validator import CommercialSnapshotValidator, SnapshotValidationError

logger = logging.getLogger("commercial_catalog.rebuild")


@dataclass
class HealthProbeResult:
    query: str
    target_canonical_id: str
    resolved_id: str | None
    success: bool
    details: str


@dataclass
class RebuildResult:
    success: bool
    catalog_version: str
    record_count: int
    json_path: str
    csv_path: str
    manifest_path: str
    json_sha256: str
    csv_sha256: str
    validation_status: str
    health_probes: list[dict[str, Any]]
    errors: list[str]
    quarantined_to: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_catalog_entry(
    raw_entry: dict[str, Any],
    catalog_version: str,
    snapshot_timestamp: str,
) -> CommercialCatalogRecord:
    """Normalize a raw entry (from WooCommerce or canonical catalog source) joined with approved enrichment."""
    cid = raw_entry.get("canonical_id", "")
    
    # If no canonical_id in raw_entry, check meta_data or ID/SKU matching
    if not cid:
        for meta in raw_entry.get("meta_data", []):
            if isinstance(meta, dict) and meta.get("key") == "_budly_canonical_id":
                cid = str(meta.get("value"))
                break

    enrichment = get_approved_enrichment(cid) or {}

    # 1. Authoritative Status Mapping
    raw_status = raw_entry.get("status")
    if raw_status == "publish":
        status = "ACTIVE"
        release_state = "RELEASED"
    elif raw_status == "draft":
        status = "DRAFT"
        release_state = "APPROVED_NOT_RELEASED"
    elif raw_status == "APPROVED_NOT_RELEASED":
        status = "DRAFT"
        release_state = "APPROVED_NOT_RELEASED"
    elif raw_status:
        status = raw_status
        release_state = enrichment.get("release_state") or raw_entry.get("release_state", "RELEASED")
    else:
        status = enrichment.get("status", "ACTIVE")
        release_state = enrichment.get("release_state", "RELEASED")

    entity_type = raw_entry.get("entity_type") or enrichment.get("entity_type", "PRODUCT")
    approval_status = raw_entry.get("approval_status") or enrichment.get("approval_status", "OWNER_APPROVED")
    
    # Customer purchasability rule: APPROVED_NOT_RELEASED is never purchasable
    if release_state == "APPROVED_NOT_RELEASED":
        customer_purchasable = False
        catalog_visibility = "hidden"
    else:
        customer_purchasable = bool(raw_entry.get("customer_purchasable", enrichment.get("customer_purchasable", True)))
        catalog_visibility = raw_entry.get("catalog_visibility", enrichment.get("catalog_visibility", "visible"))

    # Attach live/verified Woo IDs if present in enrichment or raw_entry
    woo_product_id = raw_entry.get("woo_parent_product_id") or raw_entry.get("woo_product_id") or raw_entry.get("id")
    if cid == "ccc:service:is-cannabis-right-for-me":
        woo_product_id = 1046
    elif cid == "wnb:community:lounge-pass":
        woo_product_id = 1047
    elif cid == "wnb:community:lounge-member":
        woo_product_id = 1048
    elif cid == "wnb:community:lounge-elite":
        woo_product_id = 1049

    # Authoritative Price Mapping: Live Woo price strictly takes precedence
    raw_price = raw_entry.get("price") or raw_entry.get("regular_price") or raw_entry.get("price_usd")
    if raw_price is not None and str(raw_price).strip() != "":
        try:
            price_usd = float(raw_price)
        except (ValueError, TypeError):
            price_usd = enrichment.get("price_usd")
    else:
        price_usd = enrichment.get("price_usd")
    
    stock_status = str(raw_entry.get("stock_status") or enrichment.get("stock_status", "instock"))
    
    benefits = enrichment.get("benefits") or raw_entry.get("full_benefits") or raw_entry.get("benefits") or []
    if isinstance(benefits, str):
        benefits = [benefits] if benefits != "BENEFIT_SOURCE_NOT_PRESENT_IN_WOOCOMMERCE" else []

    source_updated_at = (
        raw_entry.get("date_modified_gmt")
        or raw_entry.get("date_modified")
        or raw_entry.get("source_updated_at")
        or snapshot_timestamp
    )

    # Determine budly_visibility under CCS-006 policy
    raw_visibility = raw_entry.get("budly_visibility")
    if raw_visibility in ["PUBLIC", "PRE_RELEASE_ALLOWED", "INTERNAL_ONLY", "EXCLUDED"]:
        budly_visibility = raw_visibility
    elif release_state == "APPROVED_NOT_RELEASED" or status == "DRAFT" or catalog_visibility == "hidden":
        budly_visibility = "EXCLUDED"
    else:
        budly_visibility = "PUBLIC"

    record = CommercialCatalogRecord(
        canonical_id=cid,
        sku=str(raw_entry.get("sku") or enrichment.get("sku") or f"SKU-{cid.replace(':', '-').upper()}"),
        slug=str(raw_entry.get("slug") or enrichment.get("slug") or cid.split(":")[-1]),
        name=str(raw_entry.get("name") or enrichment.get("name") or cid),
        entity_type=str(entity_type),
        category=list(raw_entry.get("category") or enrichment.get("category") or ["General"]),
        brand=str(raw_entry.get("brand") or enrichment.get("brand") or "Compassionate Care Cultivators"),
        status=str(status),
        approval_status=str(approval_status),
        release_state=str(release_state),
        customer_purchasable=customer_purchasable,
        catalog_visibility=str(catalog_visibility),
        budly_visibility=str(budly_visibility),
        stock_status=stock_status,
        price_usd=float(price_usd) if price_usd is not None else None,
        currency=str(raw_entry.get("currency") or enrichment.get("currency", "USD")),
        billing_model=str(raw_entry.get("billing_model") or enrichment.get("billing_model") or raw_entry.get("billing_type", "ONE_TIME")),
        short_summary=str(enrichment.get("short_summary") or raw_entry.get("short_description") or raw_entry.get("description", "")),
        description=str(enrichment.get("description") or raw_entry.get("description", "")),
        benefits=list(benefits),
        audience=list(enrichment.get("audience") or raw_entry.get("audience") or []),
        customer_goals=list(enrichment.get("customer_goals") or raw_entry.get("customer_goals") or []),
        eligibility_rules=list(enrichment.get("eligibility_rules") or raw_entry.get("eligibility_rules") or []),
        exclusions=list(enrichment.get("exclusions") or raw_entry.get("exclusions") or []),
        fulfillment_type=str(enrichment.get("fulfillment_type") or raw_entry.get("fulfillment_type", "DIGITAL_DELIVERY")),
        fulfillment_platform=str(enrichment.get("fulfillment_platform") or raw_entry.get("fulfillment_platform", "WOOCOMMERCE")),
        canonical_url=str(raw_entry.get("canonical_url") or raw_entry.get("permalink") or enrichment.get("canonical_url", "")),
        checkout_url=raw_entry.get("checkout_url") or raw_entry.get("stripe_payment_link") or enrichment.get("checkout_url"),
        booking_url=raw_entry.get("booking_url") or enrichment.get("booking_url"),
        payment_plan_available=bool(raw_entry.get("payment_plan_available", enrichment.get("payment_plan_available", False))),
        payment_plan_amount=raw_entry.get("payment_plan_amount") or enrichment.get("payment_plan_amount"),
        payment_plan_url=raw_entry.get("payment_plan_url") or enrichment.get("payment_plan_url"),
        payment_processor=str(raw_entry.get("payment_processor") or enrichment.get("payment_processor", "WOOCOMMERCE")),
        coupon_relationship=raw_entry.get("coupon_relationship") or enrichment.get("coupon_relationship"),
        wix_plan_id=raw_entry.get("wix_plan_id") or enrichment.get("wix_plan_id"),
        wordpress_page_id=raw_entry.get("wordpress_page_id") or raw_entry.get("wordpress_page") or enrichment.get("wordpress_page_id"),
        source_authority=str(raw_entry.get("source_authority") or enrichment.get("source_authority", "woocommerce")),
        source_ids={
            "woo_parent_product_id": raw_entry.get("woo_parent_product_id") or raw_entry.get("parent_id"),
            "woo_variation_id": raw_entry.get("woo_variation_id"),
            "wix_entity": raw_entry.get("wix_entity"),
        },
        source_updated_at=str(source_updated_at),
        snapshot_generated_at=snapshot_timestamp,
        catalog_version=catalog_version,
        woo_product_id=woo_product_id,
        woo_parent_product_id=raw_entry.get("woo_parent_product_id") or raw_entry.get("parent_id"),
        woo_variation_id=raw_entry.get("woo_variation_id"),
    )
    return record


def include_public(record: CommercialCatalogRecord) -> bool:
    """Determine if a commercial record is authorized for the public catalog under CCS-006. Fail closed."""
    if record.budly_visibility != "PUBLIC":
        return False
    if record.release_state in ["APPROVED_NOT_RELEASED", "DISCONTINUED", "PRELAUNCH_CONFIGURATION_PRESENT"]:
        return False
    if record.status in ["DRAFT", "ARCHIVED", "INACTIVE"]:
        return False
    if record.catalog_visibility in ["hidden", "private"]:
        return False
    if record.approval_status != "OWNER_APPROVED":
        return False
    if not record.canonical_url or not record.canonical_url.strip():
        return False
    return True


def run_health_probes(loader: CommercialSnapshotLoader) -> list[HealthProbeResult]:
    """Execute standard health probes verifying public retrieval and exclusion boundaries under CCS-006."""
    probes = [
        ("What is Infused Basics?", "ccc:book:infused-basics", True),
        ("Is Cannabis Right For Me?", "ccc:service:is-cannabis-right-for-me", True),
        ("Torque", "wnb:nft:torque", True),
        ("Culinary Cannabis", "ccc:course:culinary-cannabis", True),
        ("Grow Cannabis @ Home", "ccc:course:grow-cannabis-home", True),
        # Excluded community records must not resolve in public mode (fail-closed)
        ("What is Lounge Member?", "wnb:community:lounge-member", False),
        ("What do I get with Lounge Elite?", "wnb:community:lounge-elite", False),
        ("What is Lounge Pass?", "wnb:community:lounge-pass", False),
    ]

    results: list[HealthProbeResult] = []
    resolver = DeterministicEntityResolver(public_only=True)

    for query, target_id, expected_public in probes:
        res = resolver.resolve(query)
        rec = loader.get_by_canonical_id(res.canonical_id or "") if res.canonical_id else None
        
        if expected_public:
            success = (res.status == "EXACT_MATCH" and res.canonical_id == target_id and rec is not None)
            details = f"Public entity: resolved to {res.canonical_id}, found record in loader: {rec is not None}"
        else:
            # Must fail closed: either no match, or not in loader
            success = (res.status == "NO_MATCH" or res.canonical_id is None or rec is None)
            details = f"Excluded entity: public lookup correctly failed-closed (res.status={res.status}, resolved_id={res.canonical_id}, in_public_loader={rec is not None})"

        results.append(HealthProbeResult(
            query=query,
            target_canonical_id=target_id,
            resolved_id=res.canonical_id,
            success=success,
            details=details,
        ))

    return results


def rebuild_catalog(
    event_reason: str,
    triggering_entity: str,
    root_dir: Path | str,
    canonical_source_path: Path | str | None = None,
    custom_records: Sequence[CommercialCatalogRecord] | None = None,
    catalog_version: str | None = None,
    previous_catalog_version: str | None = None,
    source_max_updated_at: str | None = None,
    woo_products: Sequence[dict[str, Any]] | None = None,
    filter_public: bool = True,
) -> RebuildResult:
    """Execute complete deterministic commercial catalog rebuild pipeline adhering to CCS-006 visibility policy."""
    root_path = Path(root_dir)
    now_iso = datetime.now(timezone.utc).isoformat()
    version = catalog_version or datetime.now(timezone.utc).strftime("1.%Y%m%d.%H%M")

    generator = CommercialSnapshotGenerator(root_path)
    all_records: list[CommercialCatalogRecord] = []

    # 1. Obtain Normalized Records (Full Source Inventory)
    if custom_records is not None:
        all_records = list(custom_records)
    elif woo_products is not None:
        for p in woo_products:
            rec = normalize_catalog_entry(p, version, now_iso)
            all_records.append(rec)
            for v in p.get("_variations", []):
                v_entry = dict(v)
                v_entry["parent_id"] = p.get("id")
                v_rec = normalize_catalog_entry(v_entry, version, now_iso)
                all_records.append(v_rec)
    else:
        # Load from canonical catalog seed source
        source_path = Path(canonical_source_path) if canonical_source_path else root_path.parent / "canonical_catalog.json"
        if not source_path.exists():
            source_path = root_path / "canonical_catalog.json"
        
        if source_path.exists():
            with open(source_path, "r", encoding="utf-8") as f:
                source_data = json.load(f)
            raw_entries = source_data.get("entries", [])
            for entry in raw_entries:
                rec = normalize_catalog_entry(entry, version, now_iso)
                all_records.append(rec)
        else:
            # Fallback: build from approved enrichment registry directly
            for cid, enrich in APPROVED_ENRICHMENT_REGISTRY.items():
                rec = normalize_catalog_entry(enrich, version, now_iso)
                all_records.append(rec)

    # 2. In-Memory Validation of All Records
    in_memory_errors = CommercialSnapshotValidator.validate_records(all_records)
    if in_memory_errors:
        quarantine_dir = generator.quarantine_staging("; ".join(in_memory_errors))
        return RebuildResult(
            success=False,
            catalog_version=version,
            record_count=len(all_records),
            json_path="",
            csv_path="",
            manifest_path="",
            json_sha256="",
            csv_sha256="",
            validation_status="FAILED_IN_MEMORY",
            health_probes=[],
            errors=in_memory_errors,
            quarantined_to=str(quarantine_dir),
        )

    # Calculate source_max_updated_at dynamically from records if not explicitly passed
    if source_max_updated_at is None and all_records:
        valid_ts = [r.source_updated_at for r in all_records if r.source_updated_at]
        if valid_ts:
            source_max_updated_at = max(valid_ts)

    # 3. Apply CCS-006 Public Filtering
    if filter_public:
        public_records = [r for r in all_records if include_public(r)]
        excluded_records = [r for r in all_records if not include_public(r)]
    else:
        public_records = list(all_records)
        excluded_records = []

    # Preserve complete Internal Canonical Inventory
    internal_dir = root_path / "Internal"
    internal_dir.mkdir(parents=True, exist_ok=True)
    with open(internal_dir / "budly-canonical-inventory.json", "w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in all_records], f, indent=2, ensure_ascii=False)

    # 4. Generate Staging Artifacts (Public Snapshot)
    json_path, csv_path, manifest_path, manifest = generator.generate_to_staging(
        records=public_records,
        catalog_version=version,
        event_reason=event_reason,
        triggering_entity=triggering_entity,
        source_record_count=len(all_records),
        source_inventory_count=len(all_records),
        public_record_count=len(public_records),
        excluded_record_count=len(excluded_records),
        pre_release_record_count=sum(1 for r in all_records if r.budly_visibility == "PRE_RELEASE_ALLOWED"),
        internal_only_record_count=sum(1 for r in all_records if r.budly_visibility == "INTERNAL_ONLY"),
        visibility_policy="CCS-006",
        visibility_policy_version="0.1",
        source_max_updated_at=source_max_updated_at,
        previous_catalog_version=previous_catalog_version,
    )

    # 5. Staging File Parity & Integrity Validation
    valid, staging_errors = CommercialSnapshotValidator.validate_staging_files(
        json_path=json_path,
        csv_path=csv_path,
        manifest_path=manifest_path,
    )

    if not valid:
        quarantine_dir = generator.quarantine_staging("; ".join(staging_errors))
        return RebuildResult(
            success=False,
            catalog_version=version,
            record_count=len(public_records),
            json_path=str(json_path),
            csv_path=str(csv_path),
            manifest_path=str(manifest_path),
            json_sha256=manifest.json_sha256,
            csv_sha256=manifest.csv_sha256,
            validation_status="FAILED_STAGING_VALIDATION",
            health_probes=[],
            errors=staging_errors,
            quarantined_to=str(quarantine_dir),
        )

    # 6. Atomic Publish Staging -> Current
    generator.publish_staging_to_current(manifest)

    # 7. Reload and Run Health Probes
    loader = CommercialSnapshotLoader(root_path)
    probes = run_health_probes(loader)
    all_probes_passed = all(p.success for p in probes)

    return RebuildResult(
        success=all_probes_passed,
        catalog_version=version,
        record_count=len(public_records),
        json_path=str(generator.current_dir / "budly-commercial-catalog.json"),
        csv_path=str(generator.current_dir / "budly-commercial-catalog.csv"),
        manifest_path=str(generator.current_dir / "catalog-manifest.json"),
        json_sha256=manifest.json_sha256,
        csv_sha256=manifest.csv_sha256,
        validation_status="PASSED" if all_probes_passed else "PROBES_FAILED",
        health_probes=[asdict(p) for p in probes],
        errors=[] if all_probes_passed else ["One or more health probes failed"],
        quarantined_to=None,
    )

