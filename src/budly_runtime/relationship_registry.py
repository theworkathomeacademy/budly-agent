"""Versioned relationship-fact definitions and minimum-necessary validation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path(__file__).resolve().parents[2] / "config" / "tool_gateway" / "tg-p05b-relationship-fact-registry.json"
MINOR_PROHIBITED_FIELDS = frozenset({
    "school", "school_name", "school_address", "home_address", "address", "phone", "email",
    "medical_information", "diagnosis", "government_identifier", "photo", "private_communications",
    "daily_schedule", "precise_location", "habitual_location", "credentials",
})


@dataclass(frozen=True)
class RelationshipFactDefinition:
    key: str
    category: str
    value_type: str
    sensitivity: str
    required_fields: frozenset[str]
    allowed_fields: frozenset[str]
    permitted_purposes: frozenset[str]
    related_person: bool
    minor_allowed: bool
    initial_status: str
    supersession: str


@dataclass(frozen=True)
class RelationshipFactRegistry:
    registry_id: str
    version: str
    definitions: dict[str, RelationshipFactDefinition]
    allowed_source_context_summaries: frozenset[str]

    @classmethod
    def load(cls, path: Path = REGISTRY_PATH) -> "RelationshipFactRegistry":
        raw = json.loads(path.read_text(encoding="utf-8"))
        purposes = frozenset(raw["permitted_purposes"])
        definitions = {
            key: RelationshipFactDefinition(
                key, item["category"], item["value_type"], item["sensitivity"],
                frozenset(item["required_fields"]), frozenset(item["allowed_fields"]), purposes,
                bool(item["related_person"]), bool(item["minor_allowed"]), item["status"], item["supersession"],
            )
            for key, item in raw["definitions"].items()
        }
        return cls(raw["registry_id"], raw["version"], definitions, frozenset(raw["allowed_source_context_summaries"]))

    @staticmethod
    def validate_value(definition: RelationshipFactDefinition, value: dict[str, Any]) -> bool:
        if not isinstance(value, dict) or not definition.required_fields.issubset(value) or not set(value).issubset(definition.allowed_fields):
            return False
        if len(value) > 8:
            return False
        for field, item in value.items():
            if isinstance(item, str):
                if not item.strip() or len(item) > 80 or not re.fullmatch(r"[A-Za-z0-9 _'-]+", item):
                    return False
            elif type(item) is int:
                if not 0 <= item <= 150:
                    return False
            elif type(item) is bool:
                continue
            else:
                return False
        if "month" in value and not 1 <= value["month"] <= 12:
            return False
        if "day" in value and not 1 <= value["day"] <= 31:
            return False
        if "birthday_month" in value and not 1 <= value["birthday_month"] <= 12:
            return False
        if "birthday_day" in value and not 1 <= value["birthday_day"] <= 31:
            return False
        if "count" in value and not 0 <= value["count"] <= 20:
            return False
        if "stated_age" in value and not 0 <= value["stated_age"] <= 120:
            return False
        return True


RELATIONSHIP_FACT_REGISTRY = RelationshipFactRegistry.load()
