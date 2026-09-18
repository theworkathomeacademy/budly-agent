"""Read-Only Commercial Snapshot Runtime Loader (CCS-001 / CCS-003).

Loads the validated Current snapshot into memory with hash verification and fast indexed lookup.
Maintains last-known-good state if an invalid snapshot is detected during reload.
Does not perform synchronous network calls during turn processing.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Sequence

from .contract import CatalogManifest, CommercialCatalogRecord
from .generator import sha256_file
from .resolver import DeterministicEntityResolver

logger = logging.getLogger("commercial_catalog.loader")


class CommercialSnapshotLoader:
    """Thread-safe, read-only commercial snapshot loader and indexed lookup engine."""

    def __init__(self, snapshot_dir: Path | str) -> None:
        self.snapshot_dir = Path(snapshot_dir)
        self.current_dir = self.snapshot_dir / "Current" if (self.snapshot_dir / "Current").exists() else self.snapshot_dir
        self.resolver = DeterministicEntityResolver()
        
        self._manifest: CatalogManifest | None = None
        self._records: list[CommercialCatalogRecord] = []
        self._by_canonical_id: dict[str, CommercialCatalogRecord] = {}
        self._by_woo_id: dict[int, CommercialCatalogRecord] = {}
        self._by_wix_plan_id: dict[str, CommercialCatalogRecord] = {}
        self._by_sku: dict[str, CommercialCatalogRecord] = {}
        self._by_entity_type: dict[str, list[CommercialCatalogRecord]] = {}
        self._by_category: dict[str, list[CommercialCatalogRecord]] = {}
        
        self.load()

    @property
    def loaded_catalog_version(self) -> str | None:
        return self._manifest.catalog_version if self._manifest else None

    @property
    def catalog_version(self) -> str | None:
        return self.loaded_catalog_version

    @property
    def manifest(self) -> CatalogManifest | None:
        return self._manifest

    @property
    def records(self) -> list[CommercialCatalogRecord]:
        return list(self._records)

    @property
    def record_count(self) -> int:
        return len(self._records)

    def load(self) -> bool:
        """Load and validate Current snapshot files. Retains last-known-good on failure."""
        manifest_path = self.current_dir / "catalog-manifest.json"
        json_path = self.current_dir / "budly-commercial-catalog.json"
        csv_path = self.current_dir / "budly-commercial-catalog.csv"

        if not manifest_path.exists() or not json_path.exists():
            logger.warning(f"Snapshot files missing in {self.current_dir}")
            return False

        try:
            # 1. Parse manifest
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
            manifest = CatalogManifest.from_dict(manifest_data)

            # 2. Hash check
            actual_json_hash = sha256_file(json_path)
            if actual_json_hash != manifest.json_sha256:
                raise ValueError(
                    f"JSON hash mismatch: manifest={manifest.json_sha256}, actual={actual_json_hash}"
                )

            if csv_path.exists():
                actual_csv_hash = sha256_file(csv_path)
                if actual_csv_hash != manifest.csv_sha256:
                    raise ValueError(
                        f"CSV hash mismatch: manifest={manifest.csv_sha256}, actual={actual_csv_hash}"
                    )

            # 3. Parse records
            with open(json_path, "r", encoding="utf-8") as f:
                records_data = json.load(f)

            if len(records_data) != manifest.output_record_count:
                raise ValueError(
                    f"Record count mismatch: manifest={manifest.output_record_count}, json={len(records_data)}"
                )

            new_records: list[CommercialCatalogRecord] = []
            by_cid: dict[str, CommercialCatalogRecord] = {}
            by_woo: dict[int, CommercialCatalogRecord] = {}
            by_wix: dict[str, CommercialCatalogRecord] = {}
            by_sku: dict[str, CommercialCatalogRecord] = {}
            by_type: dict[str, list[CommercialCatalogRecord]] = {}
            by_cat: dict[str, list[CommercialCatalogRecord]] = {}

            for item in records_data:
                rec = CommercialCatalogRecord.from_dict(item)
                new_records.append(rec)
                by_cid[rec.canonical_id] = rec

                if rec.woo_product_id is not None:
                    by_woo[rec.woo_product_id] = rec
                if rec.woo_parent_product_id is not None and rec.woo_parent_product_id not in by_woo:
                    by_woo[rec.woo_parent_product_id] = rec
                if rec.woo_variation_id is not None:
                    by_woo[rec.woo_variation_id] = rec

                if rec.wix_plan_id:
                    by_wix[rec.wix_plan_id] = rec

                if rec.sku:
                    by_sku[rec.sku.upper()] = rec

                by_type.setdefault(rec.entity_type, []).append(rec)

                for cat in rec.category:
                    by_cat.setdefault(cat.lower(), []).append(rec)

            # Atomic swap into active state
            self._manifest = manifest
            self._records = new_records
            self._by_canonical_id = by_cid
            self._by_woo_id = by_woo
            self._by_wix_plan_id = by_wix
            self._by_sku = by_sku
            self._by_entity_type = by_type
            self._by_category = by_cat

            logger.info(f"Loaded commercial catalog version {manifest.catalog_version} ({len(new_records)} records)")
            return True

        except Exception as exc:
            logger.error(f"Failed to load snapshot from {self.current_dir}: {exc}. Retaining last-known-good state.")
            return False

    def get_by_canonical_id(self, canonical_id: str) -> CommercialCatalogRecord | None:
        """Lookup record by exact canonical_id."""
        return self._by_canonical_id.get(canonical_id)

    def get_by_woo_id(self, woo_id: int) -> CommercialCatalogRecord | None:
        """Lookup record by WooCommerce product, parent, or variation ID."""
        return self._by_woo_id.get(woo_id)

    def get_by_wix_plan_id(self, wix_plan_id: str) -> CommercialCatalogRecord | None:
        """Lookup record by Wix plan ID."""
        return self._by_wix_plan_id.get(wix_plan_id)

    def get_by_sku(self, sku: str) -> CommercialCatalogRecord | None:
        """Lookup record by SKU."""
        return self._by_sku.get(sku.strip().upper())

    def get_by_alias(self, alias_text: str) -> CommercialCatalogRecord | None:
        """Lookup record by natural language alias using deterministic entity resolver."""
        res = self.resolver.resolve(alias_text)
        if res.status == "EXACT_MATCH" and res.canonical_id:
            return self.get_by_canonical_id(res.canonical_id)
        return None

    def get_by_entity_type(self, entity_type: str) -> list[CommercialCatalogRecord]:
        """List all records for a given entity_type."""
        return list(self._by_entity_type.get(entity_type, []))

    def get_by_category(self, category: str) -> list[CommercialCatalogRecord]:
        """List all records for a given category name."""
        return list(self._by_category.get(category.lower(), []))

    def get_all_active_records(self) -> list[CommercialCatalogRecord]:
        """List all active records."""
        return [r for r in self._records if r.status == "ACTIVE" or r.status == "ACTIVE_CATALOG_GAP"]

    def get_all_records(self) -> list[CommercialCatalogRecord]:
        """List all loaded records."""
        return list(self._records)
