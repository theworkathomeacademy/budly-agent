"""Versioned, bounded preference-key registry for TG-P05A."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve().parents[2] / "config" / "tool_gateway" / "tg-p05a-preference-registry.json"


@dataclass(frozen=True)
class PreferenceDefinition:
    key: str
    category: str
    allowed_values: frozenset[str]
    permitted_purposes: frozenset[str]
    classification: str
    durable_memory_eligible: bool


@dataclass(frozen=True)
class PreferenceRegistry:
    registry_id: str
    version: str
    definitions: dict[str, PreferenceDefinition]

    @classmethod
    def load(cls, path: Path = REGISTRY_PATH) -> "PreferenceRegistry":
        raw = json.loads(path.read_text(encoding="utf-8"))
        purposes = frozenset(raw["permitted_purposes"])
        definitions = {
            key: PreferenceDefinition(
                key, item["category"], frozenset(item["allowed_values"]), purposes,
                raw["classification"], bool(raw["durable_memory_eligible"]),
            )
            for key, item in raw["definitions"].items()
        }
        return cls(raw["registry_id"], raw["version"], definitions)


PREFERENCE_REGISTRY = PreferenceRegistry.load()
