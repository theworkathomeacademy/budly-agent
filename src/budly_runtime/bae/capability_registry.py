"""BAE Pilot 001 Capability Registry.

Manages governed capability definitions, lifecycle state validation, and seed loading.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import CapabilityRecord, SchemaValidationError
from .types import (
    ApprovalLevel,
    AuthorityClass,
    AutonomyMaturity,
    CapabilityLifecycleState,
    PilotWave,
    ToolAuthorityClass,
)


class CapabilityRegistryError(RuntimeError):
    """Raised when capability registry lookup or validation fails."""
    pass


class BAECapabilityRegistry:
    """Canonical registry for BAE Pilot 001 capabilities."""

    def __init__(self, records: list[CapabilityRecord] | None = None) -> None:
        self._records: dict[str, CapabilityRecord] = {}
        if records:
            for record in records:
                self.register(record)

    @classmethod
    def load_seed(cls, seed_path: Path | str | None = None) -> "BAECapabilityRegistry":
        """Load capability seed registry from JSON configuration."""
        if seed_path is None:
            seed_path = Path(__file__).resolve().parents[3] / "config" / "tool_gateway" / "bae-pilot-001-capability-seed.json"
        else:
            seed_path = Path(seed_path)

        with open(seed_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        records: list[CapabilityRecord] = []
        for item in raw_data:
            records.append(
                CapabilityRecord(
                    capability_id=item["capability_id"],
                    capability_version=item["capability_version"],
                    capability_name=item["capability_name"],
                    wave=PilotWave(item["wave"]),
                    authority_class=AuthorityClass(item["authority_class"]) if item.get("authority_class") else None,
                    current_certified_maturity=AutonomyMaturity(item["current_certified_maturity"]) if item.get("current_certified_maturity") else None,
                    target_pilot_entry_maturity=AutonomyMaturity(item["target_pilot_entry_maturity"]) if item.get("target_pilot_entry_maturity") else None,
                    maximum_governable_maturity=AutonomyMaturity(item["maximum_governable_maturity"]) if item.get("maximum_governable_maturity") else None,
                    approval_level=ApprovalLevel(item["approval_level"]) if item.get("approval_level") else None,
                    tool_authority=ToolAuthorityClass(item["tool_authority"]) if item.get("tool_authority") else None,
                    lifecycle_state=CapabilityLifecycleState(item["lifecycle_state"]),
                    specifically_authorized_bounded_write=item.get("specifically_authorized_bounded_write", False),
                    certification_signature=item.get("certification_signature"),
                    certified_at=item.get("certified_at"),
                    certified_by=item.get("certified_by"),
                    classification_state=item.get("classification_state", "RESOLVED"),
                    executable=item.get("executable", False),
                    allowed_environments=frozenset(item.get("allowed_environments", [])),
                    allowed_purposes=frozenset(item.get("allowed_purposes", [])),
                    allowed_channels=frozenset(item.get("allowed_channels", [])),
                )
            )
        return cls(records)

    def register(self, record: CapabilityRecord) -> None:
        """Register a new capability record."""
        if record.capability_id in self._records:
            raise CapabilityRegistryError(f"Capability {record.capability_id} is already registered")
        self._records[record.capability_id] = record

    def get(self, capability_id: str, version: str | None = None) -> CapabilityRecord | None:
        """Lookup a capability by ID and optional version."""
        record = self._records.get(capability_id)
        if record and (version is None or record.capability_version == version):
            return record
        return None

    def list_all(self) -> list[CapabilityRecord]:
        """Return all registered capability records."""
        return list(self._records.values())

    def list_by_wave(self, wave: PilotWave) -> list[CapabilityRecord]:
        """Filter capabilities by rollout wave."""
        return [r for r in self._records.values() if r.wave == wave]
