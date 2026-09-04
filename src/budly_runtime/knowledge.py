from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Iterable

RETRIEVAL_TERMS = re.compile(r"\b(price|cost|product|catalog|policy|return|membership|recipe|resource|ingredient|shipping|organization|ccc|cultivate)\b", re.I)


def retrieval_required(message: str) -> bool:
    return bool(RETRIEVAL_TERMS.search(message))


@dataclass(frozen=True)
class KnowledgeRecord:
    knowledge_id: str
    domain: str
    source: str
    version: str
    approval_status: str
    content: str
    active: bool = True
    access_classification: str = "public"


class KnowledgeGateway:
    """Minimal subordinate ADR-008-compatible read-only prototype interface."""

    def __init__(self, records: Iterable[KnowledgeRecord] = ()) -> None:
        self.records = list(records)
        self.gaps: list[dict[str, str]] = []

    def retrieve(self, query: str, access_classification: str = "public") -> dict:
        terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        candidates = [r for r in self.records if r.active and r.approval_status == "approved" and r.access_classification == access_classification and terms.intersection(re.findall(r"[a-z0-9]+", (r.domain + " " + r.content).lower()))]
        latest: dict[str, KnowledgeRecord] = {}
        for record in candidates:
            if record.domain not in latest or record.version > latest[record.domain].version:
                latest[record.domain] = record
        results = []
        for r in latest.values():
            item = asdict(r)
            item.pop("active")
            item.pop("access_classification")
            results.append(item)
        if not results:
            self.gaps.append({"query": query, "reason": "no_approved_active_match"})
            return {"status": "unavailable", "query": query, "results": []}
        return {"status": "success", "query": query, "results": results}


def normalize_tool_request(value: object) -> dict:
    """Normalize a model proposal; normalization never grants authority."""
    if not isinstance(value, dict):
        raise ValueError("tool request must be an object")
    capability, inputs = value.get("capability"), value.get("inputs", {})
    if capability != "knowledge.retrieve" or not isinstance(inputs, dict):
        raise ValueError("unsupported tool request")
    if set(inputs) != {"query"} or not isinstance(inputs["query"], str):
        raise ValueError("invalid knowledge.retrieve inputs")
    return {"capability": capability, "inputs": {"query": inputs["query"].strip()}}
