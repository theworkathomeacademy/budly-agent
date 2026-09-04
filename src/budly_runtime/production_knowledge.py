from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .tool_gateway import AdapterContext, ToolHealth


@dataclass
class ApprovedRepositoryKnowledgeAdapter:
    """Read-only adapter over owner-approved/verified repository knowledge.

    Policies are admitted only with ``owner_approved`` status. Product records
    expose the verified identity/link/format boundary only; current price,
    variants, stock and eligibility remain WordPress/WooCommerce authority.
    """

    policies_path: Path
    products_path: Path
    education_path: Path | None = None
    state: ToolHealth = ToolHealth.HEALTHY
    tool_id: str = "approved_repository_knowledge"
    tool_version: str = "1.0"
    last_context: AdapterContext | None = None

    def __post_init__(self) -> None:
        self._items = self._load()

    def health(self) -> ToolHealth:
        return self.state

    def retrieve(self, context: AdapterContext) -> list[dict[str, Any]]:
        self.last_context = context
        if self.state is not ToolHealth.HEALTHY:
            raise RuntimeError("approved knowledge source unavailable")
        terms = set(re.findall(r"[a-z0-9]+", context.query.lower()))
        matches: list[dict[str, Any]] = []
        for item in self._items:
            if item["domain"] != context.domain or item["classification"] not in context.access_classifications:
                continue
            searchable = f"{item['title']} {item['content']}".lower()
            if terms and not terms.intersection(re.findall(r"[a-z0-9]+", searchable)):
                continue
            matches.append(dict(item))
        return matches[: context.max_results]

    def _load(self) -> list[dict[str, Any]]:
        policies = self._read_json(self.policies_path)
        products = self._read_json(self.products_path)
        items: list[dict[str, Any]] = []
        if policies.get("status") != "owner_approved":
            raise ValueError("policy source is not owner approved")
        approved_on = str(policies.get("approved_on", ""))
        for key, value in policies.get("policies", {}).items():
            if not isinstance(value, dict) or not value.get("summary"):
                continue
            content = " ".join(str(part) for part in value.values() if isinstance(part, (str, int)))
            items.append({
                "knowledge_id": f"policy:{key}", "title": key.replace("_", " ").title(),
                "version": approved_on, "domain": "customer_policy", "status": "Active",
                "classification": "Public", "source_reference": f"repository://config/policies.json#{key}",
                "content": content[:2000],
            })
        if products.get("status") != "links_verified_details_pending_review":
            raise ValueError("product identity source status is not recognized")
        version = str(products.get("source", {}).get("verified_on", ""))
        for product in products.get("products", []):
            if not isinstance(product, dict) or not product.get("active") or not product.get("id") or not product.get("name"):
                continue
            safe = {
                "product_id": product["id"], "name": product["name"], "url": product.get("url"),
                "category": product.get("category"), "formats": product.get("formats", []),
                "authority_note": "Identity, link and listed formats only; WordPress controls current price, variants, stock and eligibility.",
            }
            items.append({
                "knowledge_id": f"product:{product['id']}", "title": str(product["name"]),
                "version": version, "domain": "product_catalog", "status": "Active",
                "classification": "Public", "source_reference": f"repository://config/products.json#{product['id']}",
                "content": json.dumps(safe, separators=(",", ":"))[:2000],
            })
        if self.education_path is not None:
            education = self._read_json(self.education_path)
            if education.get("status") != "owner_approved" or education.get("corpus_id") != "budly-conversational-education-corpus-v0.1":
                raise ValueError("education corpus is not owner approved")
            corpus_version = str(education.get("version", ""))
            source = education.get("source", {})
            for chunk in education.get("chunks", []):
                if not isinstance(chunk, dict) or chunk.get("classification") != "Public" or chunk.get("status") != "Active":
                    continue
                if not all(chunk.get(field) for field in ("id", "title", "domain", "content")):
                    continue
                items.append({
                    "knowledge_id": f"education:{chunk['id']}", "title": str(chunk["title"]),
                    "version": corpus_version, "domain": str(chunk["domain"]), "status": "Active",
                    "classification": "Public",
                    "source_reference": f"{source.get('reference', 'repository://approved-corpus')}#{chunk['id']}",
                    "content": str(chunk["content"])[:2000],
                })
        return items

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"knowledge source {path.name} is invalid")
        return value
