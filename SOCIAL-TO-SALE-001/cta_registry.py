"""Governed CTA Registry for Budly Social-to-Sale Conversion Spine (STS-1)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config" / "cta_registry.json"


class CTAType(str, Enum):
    COMMUNITY_JOIN = "COMMUNITY_JOIN"
    ASK_BUDLY = "ASK_BUDLY"
    EXPLORE_PRODUCT = "EXPLORE_PRODUCT"
    SHOP_PRODUCT = "SHOP_PRODUCT"
    LEARN_MORE = "LEARN_MORE"
    SUBSCRIBE_UPDATES = "SUBSCRIBE_UPDATES"
    JOIN_CONVERSATION = "JOIN_CONVERSATION"


class ApprovalState(str, Enum):
    APPROVED = "APPROVED"
    DRAFT = "DRAFT"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True)
class CTARecord:
    cta_id: str
    cta_type: str
    display_label: str
    description: str
    destination_url: str
    destination_type: str
    product_or_topic: str
    active: bool
    approval_state: str
    allowed_platforms: list[str]
    created_at: str
    updated_at: str

    def validate(self) -> None:
        if not self.cta_id or not self.cta_id.strip():
            raise ValueError("cta_id cannot be empty")
        if self.cta_type not in {t.value for t in CTAType}:
            raise ValueError(f"Invalid cta_type: {self.cta_type}")
        if self.approval_state not in {s.value for s in ApprovalState}:
            raise ValueError(f"Invalid approval_state: {self.approval_state}")
        if not self.destination_url.startswith(("https://", "http://")):
            raise ValueError(f"destination_url must be an absolute URL: {self.destination_url}")
        if not self.display_label.strip():
            raise ValueError("display_label cannot be empty")
        if not isinstance(self.allowed_platforms, list) or not self.allowed_platforms:
            raise ValueError("allowed_platforms must be a non-empty list")

    @property
    def is_eligible(self) -> bool:
        return self.active and self.approval_state == ApprovalState.APPROVED.value

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CTARegistry:
    def __init__(self, config_path: str | Path | None = None) -> None:
        self.config_path = Path(config_path or DEFAULT_CONFIG)
        self._ctas: dict[str, CTARecord] = {}
        self.reload()

    def reload(self) -> None:
        if not self.config_path.exists():
            raise FileNotFoundError(f"CTA config file not found: {self.config_path}")
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        ctas = {}
        for entry in data.get("ctas", []):
            record = CTARecord(
                cta_id=entry["cta_id"],
                cta_type=entry["cta_type"],
                display_label=entry["display_label"],
                description=entry.get("description", ""),
                destination_url=entry["destination_url"],
                destination_type=entry.get("destination_type", "web_page"),
                product_or_topic=entry.get("product_or_topic", "UNKNOWN"),
                active=bool(entry.get("active", False)),
                approval_state=entry.get("approval_state", ApprovalState.DRAFT.value),
                allowed_platforms=list(entry.get("allowed_platforms", ["web"])),
                created_at=entry.get("created_at", ""),
                updated_at=entry.get("updated_at", ""),
            )
            record.validate()
            ctas[record.cta_id] = record
        self._ctas = ctas

    def get_cta(self, cta_id: str) -> CTARecord | None:
        return self._ctas.get(cta_id)

    def get_active_cta(self, cta_id: str) -> CTARecord | None:
        cta = self.get_cta(cta_id)
        if cta and cta.is_eligible:
            return cta
        return None

    def list_approved_ctas(self, platform: str | None = None, product_or_topic: str | None = None) -> list[CTARecord]:
        results = [cta for cta in self._ctas.values() if cta.is_eligible]
        if platform:
            norm_platform = platform.lower().strip()
            results = [cta for cta in results if norm_platform in [p.lower() for p in cta.allowed_platforms]]
        if product_or_topic:
            results = [cta for cta in results if cta.product_or_topic == product_or_topic]
        return results

    def find_cta(self, cta_type: CTAType | str, product_or_topic: str | None = None) -> CTARecord | None:
        type_val = cta_type.value if isinstance(cta_type, CTAType) else cta_type
        candidates = [
            cta for cta in self._ctas.values()
            if cta.is_eligible and cta.cta_type == type_val
        ]
        if product_or_topic:
            matched = [c for c in candidates if c.product_or_topic == product_or_topic]
            if matched:
                return matched[0]
        return candidates[0] if candidates else None
