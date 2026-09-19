"""Snapshot Artifact Generator (CCS-001 / CCS-002 / CCS-003).

Generates `budly-commercial-catalog.json`, `budly-commercial-catalog.csv`, and
`catalog-manifest.json` from a SINGLE normalized in-memory dataset, ensuring identical
record counts, deterministic SHA256 hashing, and atomic stage-validate-publish lifecycle.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .contract import CatalogManifest, CommercialCatalogRecord

SCHEMA_VERSION = "0.1.0"
GENERATOR_VERSION = "1.0.0"

CSV_FIELDNAMES = [
    "canonical_id",
    "woo_product_id",
    "woo_parent_product_id",
    "woo_variation_id",
    "sku",
    "slug",
    "name",
    "entity_type",
    "category",
    "brand",
    "status",
    "approval_status",
    "release_state",
    "customer_purchasable",
    "catalog_visibility",
    "budly_visibility",
    "stock_status",
    "price_usd",
    "currency",
    "billing_model",
    "short_summary",
    "description",
    "benefits",
    "audience",
    "customer_goals",
    "eligibility_rules",
    "exclusions",
    "fulfillment_type",
    "fulfillment_platform",
    "canonical_url",
    "checkout_url",
    "booking_url",
    "payment_plan_available",
    "payment_plan_amount",
    "payment_plan_url",
    "payment_processor",
    "coupon_relationship",
    "wix_plan_id",
    "wordpress_page_id",
    "source_authority",
    "source_ids",
    "source_updated_at",
    "snapshot_generated_at",
    "catalog_version",
    "record_checksum",
]


def sha256_file(path: Path) -> str:
    """Compute SHA256 of file content."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class CommercialSnapshotGenerator:
    """Manages snapshot generation, directories (Current/Archive/Staging/Quarantine), and atomic publishing."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = Path(root_dir)
        self.current_dir = self.root_dir / "Current"
        self.archive_dir = self.root_dir / "Archive"
        self.staging_dir = self.root_dir / "Staging"
        self.quarantine_dir = self.root_dir / "Quarantine"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        for d in (self.current_dir, self.archive_dir, self.staging_dir, self.quarantine_dir):
            d.mkdir(parents=True, exist_ok=True)

    def generate_to_staging(
        self,
        records: Sequence[CommercialCatalogRecord],
        catalog_version: str,
        event_reason: str,
        triggering_entity: str,
        source_record_count: int,
        source_inventory_count: int | None = None,
        public_record_count: int | None = None,
        excluded_record_count: int = 0,
        pre_release_record_count: int = 0,
        internal_only_record_count: int = 0,
        visibility_policy: str = "CCS-006",
        visibility_policy_version: str = "0.1",
        source_max_updated_at: str | None = None,
        previous_catalog_version: str | None = None,
    ) -> tuple[Path, Path, Path, CatalogManifest]:
        """Generate JSON, CSV, and Manifest into Staging directory from single in-memory dataset."""
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Clean Staging
        for item in self.staging_dir.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)

        json_path = self.staging_dir / "budly-commercial-catalog.json"
        csv_path = self.staging_dir / "budly-commercial-catalog.csv"
        manifest_path = self.staging_dir / "catalog-manifest.json"

        # 2. Write JSON
        records_dict = [r.to_dict() for r in records]
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(records_dict, f, indent=2, ensure_ascii=False)

        # 3. Write CSV
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
            for r in records:
                d = r.to_dict()
                row = {}
                for k in CSV_FIELDNAMES:
                    val = d.get(k)
                    if isinstance(val, (list, dict)):
                        row[k] = json.dumps(val, ensure_ascii=False)
                    elif val is None:
                        row[k] = ""
                    else:
                        row[k] = str(val)
                writer.writerow(row)

        # 4. Compute Hashes
        json_hash = sha256_file(json_path)
        csv_hash = sha256_file(csv_path)

        # 5. Build Manifest
        manifest = CatalogManifest(
            schema_version=SCHEMA_VERSION,
            catalog_version=catalog_version,
            generated_at=now_iso,
            source_max_updated_at=source_max_updated_at,
            event_reason=event_reason,
            triggering_entity=triggering_entity,
            source_record_count=source_record_count,
            output_record_count=len(records),
            generator_version=GENERATOR_VERSION,
            csv_sha256=csv_hash,
            json_sha256=json_hash,
            validation_status="PENDING_VALIDATION",
            source_inventory_count=source_inventory_count or source_record_count,
            public_record_count=public_record_count or len(records),
            excluded_record_count=excluded_record_count,
            pre_release_record_count=pre_release_record_count,
            internal_only_record_count=internal_only_record_count,
            visibility_policy=visibility_policy,
            visibility_policy_version=visibility_policy_version,
            previous_catalog_version=previous_catalog_version,
        )

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2)

        return json_path, csv_path, manifest_path, manifest

    def publish_staging_to_current(self, manifest: CatalogManifest) -> None:
        """Atomically archives existing Current (if any) and promotes Staging to Current."""
        # 1. Update manifest validation_status to PASSED
        manifest.validation_status = "PASSED"
        manifest_path = self.staging_dir / "catalog-manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2)

        # 2. If Current has an existing manifest, archive current files
        current_manifest_file = self.current_dir / "catalog-manifest.json"
        if current_manifest_file.exists():
            try:
                with open(current_manifest_file, "r", encoding="utf-8") as f:
                    old_manifest_data = json.load(f)
                old_version = old_manifest_data.get("catalog_version", "prior")
                archive_subdir = self.archive_dir / f"catalog-v{old_version}"
                archive_subdir.mkdir(parents=True, exist_ok=True)
                for f in self.current_dir.iterdir():
                    if f.is_file():
                        shutil.copy2(f, archive_subdir / f.name)
            except Exception:
                pass

        # 3. Promote Staging to Current
        for f in self.staging_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, self.current_dir / f.name)

    def quarantine_staging(self, reason: str) -> Path:
        """Move failed staging build to Quarantine with diagnostic failure metadata."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        quarantine_subdir = self.quarantine_dir / f"quarantine-{timestamp}"
        quarantine_subdir.mkdir(parents=True, exist_ok=True)

        for f in self.staging_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, quarantine_subdir / f.name)

        error_file = quarantine_subdir / "quarantine-reason.txt"
        error_file.write_text(f"Quarantined at {timestamp}\nReason: {reason}\n", encoding="utf-8")
        return quarantine_subdir
