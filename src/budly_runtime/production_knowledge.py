from __future__ import annotations

import html
import json
import re
import urllib.request
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
    commercial_path: Path | None = None
    commerce_url: str = "https://cccultivate.com/wp-json/wc/store/v1/products?per_page=100"
    opener: Any = urllib.request.urlopen
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
        if context.domain == "product_catalog":
            return self._retrieve_live_catalog(context)
        raw_terms = set(re.findall(r"[a-z0-9]+", context.query.lower()))
        terms = set(raw_terms)
        for t in raw_terms:
            if t.endswith("s") and len(t) > 3:
                terms.add(t[:-1])
            if t.endswith("ies") and len(t) > 4:
                terms.add(t[:-3] + "y")
            if t in {"memberships", "membership", "legends", "nft"}:
                terms.update({"membership", "memberships", "legends", "nft", "tier", "silver", "gold", "og"})
            elif t in {"classes", "class", "courses", "course"}:
                terms.update({"class", "classes", "course", "courses", "grow", "cooking", "culinary", "education"})
            elif t in {"books", "book", "guides", "guide"}:
                terms.update({"book", "books", "guide", "guides", "botanical", "collection", "basics"})
            elif t in {"policies", "policy", "returns", "return", "refunds", "refund"}:
                terms.update({"policy", "policies", "return", "returns", "refund", "refunds"})

        matches: list[dict[str, Any]] = []
        for item in self._items:
            if item["domain"] != context.domain or item["classification"] not in context.access_classifications:
                continue
            searchable = f"{item['title']} {item['content']}".lower()
            if terms and not terms.intersection(re.findall(r"[a-z0-9]+", searchable)):
                continue
            matches.append(dict(item))

        def _score_item(it: dict[str, Any]) -> int:
            score = 0
            title_lower = it["title"].lower()
            content_lower = it["content"].lower()
            q_lower = context.query.lower()
            
            matched_terms = terms.intersection(re.findall(r"[a-z0-9]+", f"{title_lower} {content_lower}"))
            score += len(matched_terms) * 10
            
            is_destination = any(w in q_lower for w in ["how do i find", "where is", "how to get to", "how do i get", "where can i find", "where can i sign up", "where to join", "find them", "find the", "find", "access"])
            
            if "wake'n'bake" in q_lower or "wakenbake" in q_lower or "lounge" in q_lower:
                if "wake'n'bake" in title_lower or "lounge" in title_lower or "wakenbake" in it["knowledge_id"].lower():
                    score += 50
                    if "canonical_url" in content_lower:
                        score += 20
                if ("get to" in q_lower or "how do i get" in q_lower or "tell me how to get" in q_lower) and "entity:wakenbake-lounge" in it["knowledge_id"]:
                    score += 100
            if any(w in q_lower for w in ["membership", "memberships", "legends", "tier", "tiers"]):
                if "membership" in title_lower or "legends" in title_lower or "membership" in it["knowledge_id"].lower():
                    score += 50
                    if "tier" in it["knowledge_id"].lower() or "resource_type\":\"membership_tier\"" in content_lower:
                        score += 30
                    if "canonical_url" in content_lower:
                        score += 15
            if any(w in q_lower for w in ["class", "classes", "course", "courses", "growing", "cooking", "culinary", "formal"]):
                if "course" in it["knowledge_id"].lower() or "class" in title_lower or "culinary" in title_lower or "grow" in title_lower:
                    score += 40
                    
            if is_destination and "canonical_url" in content_lower:
                score += 25

            return score

        matches.sort(key=_score_item, reverse=True)
        return matches[: context.max_results]

    def _retrieve_live_catalog(self, context: AdapterContext) -> list[dict[str, Any]]:
        allowed = {item["knowledge_id"].split(":", 1)[1] for item in self._items if item["domain"] == "product_catalog"}
        with self.opener(self.commerce_url, timeout=8) as response:
            products = json.loads(response.read().decode("utf-8"))
        if not isinstance(products, list):
            raise RuntimeError("WooCommerce catalog response is invalid")
        
        stop_words = {
            "what", "which", "have", "available", "carry", "show", "your", "products",
            "product", "catalog", "please", "do", "you", "sell", "get", "any", "cbd",
            "cannabis", "hemp", "tell", "me", "about", "the", "a", "an", "for", "i",
            "can", "buy", "are", "there", "give", "list", "with", "all", "is", "of",
            "need", "want", "looking", "like", "my", "something", "put", "on", "some",
            "just", "help", "options", "option", "offer", "much", "many", "how", "to", "order",
            "check", "let", "lets", "targeted", "item", "items", "good", "best",
            "those", "these", "that", "this", "them", "they", "we", "us", "one", "ones",
            "types", "type", "kind", "kinds",
        }
        synonyms = {
            "cream": {"cream", "butter", "topical", "creams", "butters", "topicals", "salve", "salves", "lotion"},
            "creams": {"cream", "butter", "topical", "creams", "butters", "topicals", "salve", "salves", "lotion"},
            "butter": {"cream", "butter", "topical", "creams", "butters", "topicals", "salve", "salves", "lotion"},
            "butters": {"cream", "butter", "topical", "creams", "butters", "topicals", "salve", "salves", "lotion"},
            "topical": {"cream", "butter", "topical", "creams", "butters", "topicals", "salve", "salves", "lotion"},
            "topicals": {"cream", "butter", "topical", "creams", "butters", "topicals", "salve", "salves", "lotion"},
            "salve": {"cream", "butter", "topical", "salve", "salves"},
            "salves": {"cream", "butter", "topical", "salve", "salves"},
            "lotion": {"cream", "butter", "topical", "lotion"},
            "oil": {"oil", "oils", "tincture", "tinctures", "drops", "spray"},
            "oils": {"oil", "oils", "tincture", "tinctures", "drops", "spray"},
            "tincture": {"oil", "oils", "tincture", "tinctures", "drops", "spray"},
            "tinctures": {"oil", "oils", "tincture", "tinctures", "drops", "spray"},
            "book": {"book", "books", "guide", "guides", "botanical", "collection", "coloring"},
            "books": {"book", "books", "guide", "guides", "botanical", "collection", "coloring"},
            "guide": {"book", "books", "guide", "guides", "botanical", "collection", "coloring"},
            "guides": {"book", "books", "guide", "guides", "botanical", "collection", "coloring"},
            "course": {"course", "courses", "class", "classes", "grow", "cooking", "culinary", "formal", "structured", "education"},
            "courses": {"course", "courses", "class", "classes", "grow", "cooking", "culinary", "formal", "structured", "education"},
            "class": {"course", "courses", "class", "classes", "grow", "cooking", "culinary", "formal", "structured", "education"},
            "classes": {"course", "courses", "class", "classes", "grow", "cooking", "culinary", "formal", "structured", "education"},
            "formal": {"course", "courses", "class", "classes", "grow", "cooking", "culinary", "formal", "structured", "education"},
            "structured": {"course", "courses", "class", "classes", "grow", "cooking", "culinary", "formal", "structured", "education"},
            "learn": {"book", "books", "guide", "guides", "course", "courses", "class", "classes", "education", "botanical"},
            "membership": {"membership", "memberships", "nft", "legends"},
            "memberships": {"membership", "memberships", "nft", "legends"},
            "nft": {"membership", "memberships", "nft", "legends"},
            "legends": {"membership", "memberships", "nft", "legends"},
            "newsletter": {"newsletter", "forum", "community", "updates", "email", "subscribe"},
            "forum": {"newsletter", "forum", "community", "updates", "email", "subscribe"},
            "lounge": {"wakenbake", "lounge", "find", "location", "address", "website", "platform", "online"},
            "balm": {"balm", "balms"},
            "balms": {"balm", "balms"},
            "wholesale": {"wholesale", "bulk", "white", "label"},
            "bulk": {"wholesale", "bulk", "white", "label"},
        }

        # Resolve customer lane from query
        query_text = context.query.lower()
        if re.search(r"\b(myself|personal\s*use|for\s*me|individual|retail|single\s*bottle|1\s*jar|home\s*use|just\s*want\s*something\s*for\s*myself)\b", query_text):
            lane = "RETAIL_CONSUMER"
        elif re.search(r"\b(white\s*label|private\s*label|my\s*brand|own\s*brand|branded\s*products?|custom\s*label(?:s|ing)?)\b", query_text):
            lane = "WHITE_LABEL"
        elif re.search(r"\b(wholesale|bulk|case\s*quantit(?:y|ies)|resale|reselling|distributor|50\s*bottles|commercial\s*order|my\s*shop|my\s*store|own\s*a\s*shop|own\s*a\s*store|retailer)\b", query_text):
            lane = "WHOLESALE"
        else:
            lane = "RETAIL_CONSUMER"

        channel_tokens = {"wholesale", "bulk", "white", "label", "brand", "bottles", "bottle", "store", "shop", "resale", "myself", "personal", "own"}
        raw_terms = set(re.findall(r"[a-z0-9]+", query_text))
        specific_terms = {t for t in raw_terms - stop_words if len(t) > 1 and not t.isdigit()}
        product_intent_terms = specific_terms - channel_tokens

        required_keywords: set[str] = set()
        for term in product_intent_terms:
            if term in synonyms:
                required_keywords.update(synonyms[term])
            else:
                required_keywords.add(term)

        results = []
        for product in products:
            slug = str(product.get("slug", ""))
            if slug not in allowed or not product.get("is_purchasable") or not product.get("is_in_stock"):
                continue
            name = str(product.get("name", ""))
            categories = [str(value.get("name", "")) for value in product.get("categories", []) if isinstance(value, dict)]
            
            # Product lane classification
            combined_desc = f"{slug} {name}".lower()
            if "white-label" in combined_desc or "white label" in combined_desc:
                prod_lane = "WHITE_LABEL"
            elif "bulk" in combined_desc or "wholesale" in combined_desc or "per-1oz" in combined_desc or "min-10oz" in combined_desc or "min-16oz" in combined_desc:
                prod_lane = "WHOLESALE"
            else:
                prod_lane = "RETAIL_CONSUMER"

            # Filter by customer lane
            if lane == "RETAIL_CONSUMER" and prod_lane != "RETAIL_CONSUMER":
                continue
            if lane == "WHITE_LABEL" and prod_lane != "WHITE_LABEL":
                continue
            if lane == "WHOLESALE" and prod_lane not in {"WHOLESALE", "WHITE_LABEL"}:
                continue

            searchable_tokens = set(re.findall(r"[a-z0-9]+", f"{name} {slug}".lower()))
            for cat in categories:
                if cat.lower() not in {"cbd", "cannabis", "hemp"}:
                    searchable_tokens.update(re.findall(r"[a-z0-9]+", cat.lower()))
            
            if required_keywords and not required_keywords.intersection(searchable_tokens):
                continue

            prices = product.get("prices", {})
            decimals = int(prices.get("currency_minor_unit", 2) or 2)
            price = int(prices.get("price", 0) or 0) / (10 ** decimals)
            record = {
                "resource_type": "PRODUCT", "product_id": str(product.get("id", "")),
                "slug": slug, "name": html.unescape(re.sub(r"<[^>]+>", "", str(product.get("name", "")))),
                "category": categories, "customer_lane": prod_lane,
                "short_description": html.unescape(re.sub(r"<[^>]+>", " ", str(product.get("short_description", "")))).strip()[:500],
                "canonical_url": str(product.get("permalink", "")), "current_price": price,
                "currency": str(prices.get("currency_code", "USD")), "availability": "in_stock",
                "approval_status": "approved_allowlist", "last_verified_at": "live_request",
            }
            results.append({
                "knowledge_id": f"product:{slug}", "title": record["name"], "version": "live",
                "domain": "product_catalog", "status": "Active", "classification": "Public",
                "source_reference": f"woocommerce-store-api://products/{record['product_id']}",
                "content": json.dumps(record, separators=(",", ":")),
            })

        def _rank_product_item(item: dict[str, Any]) -> int:
            data = json.loads(item["content"])
            prod_slug = data.get("slug", "").lower()
            prod_name = data.get("name", "").lower()
            cats = [c.lower() for c in data.get("category", [])]
            q = query_text.lower()
            q_words = set(re.findall(r"[a-z0-9]+", q))
            score = 0
            
            prod_tokens = set(re.findall(r"[a-z0-9]+", f"{prod_slug} {prod_name}"))
            matched = prod_tokens.intersection(q_words - stop_words)
            score += len(matched) * 10
            
            if any(w in q for w in ["class", "classes", "course", "courses", "formal", "structured", "learn", "growing", "cooking", "culinary"]):
                if any(w in q for w in ["cook", "cooking", "culinary", "edible", "edibles", "infuse", "infusion"]):
                    if "culinary-cannabis" in prod_slug:
                        score += 50
                    elif "cook-grow-with-me" in prod_slug:
                        score += 45
                    elif "grow-cannabis-home" in prod_slug:
                        score += 30
                    elif "basics" in prod_slug:
                        score += 25
                elif "grow" in q and "cook" not in q and "culinary" not in q:
                    if "grow-cannabis-home" in prod_slug:
                        score += 50
                    elif "cook-grow-with-me" in prod_slug:
                        score += 40
                    elif "culinary-cannabis" in prod_slug:
                        score += 30
                    elif "basics" in prod_slug:
                        score += 20
                else:
                    if "grow-cannabis-home" in prod_slug:
                        score += 35
                    elif "culinary-cannabis" in prod_slug:
                        score += 34
                    elif "cook-grow-with-me" in prod_slug:
                        score += 33
                    elif "basics" in prod_slug:
                        score += 20
            elif any(w in q for w in ["book", "books", "guide", "guides", "read", "coloring", "botanical"]):
                if "basics" in prod_slug:
                    score += 30
                elif "botanical" in prod_slug or "collection" in prod_slug:
                    score += 30
            elif any(w in q for w in ["oil", "oils", "cbd", "tincture", "tinctures", "drops"]):
                if "tincture" in prod_slug or "tincture" in prod_name:
                    score += 35
                elif "cooking-oil-4oz" in prod_slug:
                    score += 20
                elif "cooking-oil-8oz" in prod_slug:
                    score += 19
                elif "cooking-oil-12oz" in prod_slug:
                    score += 18
                elif "cooking-oil-16oz" in prod_slug:
                    score += 17
                elif "oil" in prod_slug:
                    score += 15
            elif any(w in q for w in ["cream", "creams", "butter", "topical", "topicals", "salve", "lotion"]):
                if "body-butter" in prod_slug or "topical" in prod_slug:
                    score += 30
            elif any(w in q for w in ["wholesale", "bulk", "white label"]):
                if "bulk" in prod_slug:
                    score += 30
                elif "white-label" in prod_slug:
                    score += 25
            elif any(w in q for w in ["membership", "legends", "all 3"]):
                if "membership" in prod_slug or "legends" in prod_slug or "chemist" in prod_slug:
                    score += 30
            if "education" in cats and ("book" in q or "learn" in q or "class" in q or "course" in q):
                score += 5
            if "cbd" in cats:
                score += 2
            return score

        results.sort(key=_rank_product_item, reverse=True)
        return results[: context.max_results]

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
            policy_record = {
                "resource_type": "POLICY",
                "policy_key": key,
                "summary": content[:2000],
                "canonical_url": "https://cccultivate.com/customer-policies/",
                "link_label": "Read customer policies",
            }
            items.append({
                "knowledge_id": f"policy:{key}", "title": key.replace("_", " ").title(),
                "version": approved_on, "domain": "customer_policy", "status": "Active",
                "classification": "Public", "source_reference": f"repository://config/policies.json#{key}",
                "content": json.dumps(policy_record, separators=(",", ":")),
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
        if self.commercial_path is not None:
            commercial = self._read_json(self.commercial_path)
            if commercial.get("approval_status") != "owner_approved":
                raise ValueError("commercial knowledge is not owner approved")
            for resource in commercial.get("resources", []):
                if resource.get("approval_status") != "approved" or resource.get("active_status") != "active":
                    continue
                items.append({
                    "knowledge_id": str(resource["resource_id"]), "title": str(resource["title"]),
                    "version": str(resource["last_verified_at"]), "domain": str(resource["knowledge_domain"]),
                    "status": "Active", "classification": "Public",
                    "source_reference": f"{resource['source_system']}://{resource['source_identifier']}",
                    "content": json.dumps(resource, separators=(",", ":"))[:4000],
                })
            for entity in commercial.get("ecosystem_entities", []):
                if entity.get("approval_status") != "approved" or entity.get("active_status") != "active":
                    continue
                entity_record = {
                    "resource_type": "ECOSYSTEM_ENTITY",
                    "entity_id": entity["entity_id"],
                    "brand_name": entity["brand_name"],
                    "canonical_url": entity["website_url"],
                    "link_label": f"Visit {entity['brand_name']}",
                    "physical_location_exists": entity.get("physical_location_exists", False),
                    "summary": entity.get("description", ""),
                }
                for dom in ("educational", "membership", "support", "product_catalog"):
                    items.append({
                        "knowledge_id": f"{entity['entity_id']}:{dom}",
                        "title": entity["brand_name"],
                        "version": str(entity["last_verified_at"]),
                        "domain": dom,
                        "status": "Active",
                        "classification": "Public",
                        "source_reference": f"brand_entity://{entity['entity_id']}",
                        "content": json.dumps(entity_record, separators=(",", ":")),
                    })
            for key, truth in commercial.get("feature_truth_status", {}).items():
                truth_record = {
                    "resource_type": "FEATURE_TRUTH",
                    "feature_key": key,
                    "status": truth.get("status"),
                    "summary": truth.get("detail", ""),
                }
                for dom in ("educational", "membership", "customer_policy"):
                    items.append({
                        "knowledge_id": f"truth:{key}:{dom}",
                        "title": f"Feature Truth: {key.replace('_', ' ').title()}",
                        "version": "1.0",
                        "domain": dom,
                        "status": "Active",
                        "classification": "Public",
                        "source_reference": f"feature_truth://{key}",
                        "content": json.dumps(truth_record, separators=(",", ":")),
                    })
            for rel in commercial.get("offer_relationships", []):
                if rel.get("approval_status") != "approved":
                    continue
                rel_record = {
                    "resource_type": "OFFER_RELATIONSHIP",
                    "offer_id": rel["offer_id"],
                    "related_offer_id": rel["related_offer_id"],
                    "relationship_type": rel["relationship_type"],
                    "summary": rel["benefit_scope"],
                    "canonical_url": rel.get("source"),
                    "link_label": "View offer details",
                }
                for dom in ("membership", "educational", "product_catalog"):
                    items.append({
                        "knowledge_id": f"relationship:{rel['offer_id']}:{rel['related_offer_id']}:{dom}",
                        "title": f"Offer Relationship: {rel['relationship_type']}",
                        "version": str(rel.get("last_verified_at", "1.0")),
                        "domain": dom,
                        "status": "Active",
                        "classification": "Public",
                        "source_reference": f"offer_rel://{rel['offer_id']}",
                        "content": json.dumps(rel_record, separators=(",", ":")),
                    })
        return items

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"knowledge source {path.name} is invalid")
        return value
