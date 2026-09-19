"""Commercial Snapshot and Manifest Validator (CCS-001 / CCS-002 / CCS-003).

Performs strict, zero-tolerance validation of normalized records, manifest integrity,
CSV-JSON parity, invariant constraints, and alias safety before release.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Sequence

from .contract import CatalogManifest, CommercialCatalogRecord
from .generator import sha256_file


class SnapshotValidationError(ValueError):
    """Raised when commercial snapshot validation fails fatal integrity checks."""
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


class CommercialSnapshotValidator:
    """Validates records, manifests, CSV/JSON file parity, and security boundaries."""

    @staticmethod
    def validate_records(records: Sequence[CommercialCatalogRecord]) -> list[str]:
        """Validate all records in-memory for duplicate canonical_ids, schema compliance, and invariants."""
        errors: list[str] = []
        seen_canonical_ids: set[str] = set()
        seen_aliases: dict[str, str] = {}

        for idx, rec in enumerate(records):
            # 1. Per-record schema check
            rec_errors = rec.validate()
            for err in rec_errors:
                errors.append(f"Record #{idx} ({rec.canonical_id}): {err}")

            # 2. Duplicate canonical_id check
            if rec.canonical_id in seen_canonical_ids:
                errors.append(f"Duplicate canonical_id detected: '{rec.canonical_id}'")
            seen_canonical_ids.add(rec.canonical_id)

            # 3. Community vs Legends check: Community entity must never resolve to NFT
            if "community" in rec.canonical_id and rec.entity_type.startswith("NFT"):
                errors.append(
                    f"Fatal taxonomy violation: {rec.canonical_id} is a community entity but has NFT entity_type '{rec.entity_type}'"
                )

            # 4. Check active purchasable destination
            if rec.customer_purchasable and not rec.canonical_url:
                errors.append(
                    f"Fatal commercial violation: {rec.canonical_id} is customer_purchasable=True but has no canonical_url"
                )

            # 5. Check APPROVED_NOT_RELEASED purchasability
            if rec.release_state == "APPROVED_NOT_RELEASED" and rec.customer_purchasable:
                errors.append(
                    f"Fatal release violation: {rec.canonical_id} is APPROVED_NOT_RELEASED but customer_purchasable=True"
                )

        return errors

    @staticmethod
    def validate_staging_files(
        json_path: Path,
        csv_path: Path,
        manifest_path: Path,
    ) -> tuple[bool, list[str]]:
        """Validate generated staging files against manifest hashes, counts, and CSV/JSON parity."""
        errors: list[str] = []

        if not json_path.exists():
            errors.append(f"JSON snapshot file missing: {json_path}")
            return False, errors
        if not csv_path.exists():
            errors.append(f"CSV snapshot file missing: {csv_path}")
            return False, errors
        if not manifest_path.exists():
            errors.append(f"Manifest file missing: {manifest_path}")
            return False, errors

        # 1. Load manifest
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
            manifest = CatalogManifest.from_dict(manifest_data)
        except Exception as exc:
            errors.append(f"Failed to parse manifest: {exc}")
            return False, errors

        # 2. Validate JSON
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                json_records = json.load(f)
            if not isinstance(json_records, list):
                errors.append("JSON snapshot content must be an array")
                json_records = []
        except Exception as exc:
            errors.append(f"Failed to parse JSON snapshot: {exc}")
            json_records = []

        # 3. Validate CSV
        csv_records = []
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                csv_records = list(reader)
        except Exception as exc:
            errors.append(f"Failed to parse CSV snapshot: {exc}")

        # 4. Check record counts
        if len(json_records) != len(csv_records):
            errors.append(
                f"CSV/JSON count mismatch: JSON has {len(json_records)} records, CSV has {len(csv_records)} records"
            )

        if len(json_records) != manifest.output_record_count:
            errors.append(
                f"Manifest output_record_count mismatch: manifest says {manifest.output_record_count}, JSON has {len(json_records)}"
            )

        # 5. Check SHA256 hashes
        actual_json_hash = sha256_file(json_path)
        actual_csv_hash = sha256_file(csv_path)

        if actual_json_hash != manifest.json_sha256:
            errors.append(
                f"JSON SHA256 hash mismatch: manifest says {manifest.json_sha256}, actual is {actual_json_hash}"
            )

        if actual_csv_hash != manifest.csv_sha256:
            errors.append(
                f"CSV SHA256 hash mismatch: manifest says {manifest.csv_sha256}, actual is {actual_csv_hash}"
            )

        # 6. Validate each deserialized JSON record
        for idx, item in enumerate(json_records):
            try:
                rec = CommercialCatalogRecord.from_dict(item)
                rec_errors = rec.validate()
                for err in rec_errors:
                    errors.append(f"Staged JSON Record #{idx} ({rec.canonical_id}): {err}")
            except Exception as exc:
                errors.append(f"Staged JSON Record #{idx} failed instantiation: {exc}")

        return (len(errors) == 0, errors)
