"""Versioned deterministic recall policy for TG-P06."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

POLICY_PATH = Path(__file__).resolve().parents[2] / "config" / "tool_gateway" / "tg-p06-memory-recall-policy.json"


@dataclass(frozen=True)
class MemoryRecallPolicy:
    policy_id: str
    version: str
    purposes: dict[str, frozenset[str]]
    silent_use_keys: frozenset[str]
    product_keys: frozenset[str]
    education_keys: frozenset[str]
    support_keys: frozenset[str]
    negative_priorities: frozenset[str]
    bridge_terms: frozenset[str]
    high_decay_keys: frozenset[str]
    low_decay_keys: frozenset[str]
    high_decay_days: int
    medium_decay_days: int
    functional_limit: int
    relational_limit: int


def load_policy(path: Path = POLICY_PATH) -> MemoryRecallPolicy:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return MemoryRecallPolicy(
        raw["policy_id"], raw["version"],
        {key: frozenset(value) for key, value in raw["purposes"].items()},
        frozenset(raw["functional"]["silent_use_keys"]),
        frozenset(raw["functional"]["product_keys"]),
        frozenset(raw["functional"]["education_keys"]),
        frozenset(raw["functional"]["support_keys"]),
        frozenset(raw["relational"]["negative_priorities"]),
        frozenset(raw["relational"]["bridge_terms"]),
        frozenset(raw["relational"]["high_decay_keys"]),
        frozenset(raw["relational"]["low_decay_keys"]),
        int(raw["relational"]["high_decay_days"]), int(raw["relational"]["medium_decay_days"]),
        int(raw["limits"]["functional"]), int(raw["limits"]["relational"]),
    )


MEMORY_RECALL_POLICY = load_policy()
