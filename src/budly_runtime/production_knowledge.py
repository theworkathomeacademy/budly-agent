from __future__ import annotations

import html
import json
import re
import gzip
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .commercial_snapshot.contract import CommercialCatalogRecord
from .commercial_snapshot.loader import CommercialSnapshotLoader
from .commercial_snapshot.resolver import DeterministicEntityResolver
from .eligibility import ProductEligibilityResolver, ProductEligibilityStatus
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
    affiliate_path: Path | None = None
    commercial_snapshot_path: Path | None = None
    commercial_snapshot_enabled: bool = False
    commerce_url: str = "https://cccultivate.com/wp-json/wc/store/v1/products?per_page=100"
    opener: Any = urllib.request.urlopen
    state: ToolHealth = ToolHealth.HEALTHY
    tool_id: str = "approved_repository_knowledge"
    tool_version: str = "1.0"
    last_context: AdapterContext | None = None
    _cached_live_products: list[dict[str, Any]] | None = None
    _cached_live_products_time: float = 0.0
    _cache_ttl_seconds: float = 300.0

    def __post_init__(self) -> None:
        self.commercial_snapshot_loader: CommercialSnapshotLoader | None = None
        self.commercial_resolver = DeterministicEntityResolver(public_only=True)
        if self.commercial_snapshot_enabled or self.commercial_snapshot_path:
            snap_dir = self.commercial_snapshot_path or (self.policies_path.parent / "commercial_catalog")
            if snap_dir.exists():
                self.commercial_snapshot_loader = CommercialSnapshotLoader(snap_dir)
        self.product_overrides: dict[str, dict[str, Any]] = {}
        self._items = self._load()
        self.eligibility_resolver = ProductEligibilityResolver(overrides_by_slug=self.product_overrides)

    def reload(self) -> bool:
        """Reload commercial snapshot and repository items from disk."""
        reloaded = False
        if self.commercial_snapshot_loader is not None:
            reloaded = self.commercial_snapshot_loader.load()
        elif self.commercial_snapshot_enabled or self.commercial_snapshot_path:
            snap_dir = self.commercial_snapshot_path or (self.policies_path.parent / "commercial_catalog")
            if snap_dir.exists():
                self.commercial_snapshot_loader = CommercialSnapshotLoader(snap_dir)
                reloaded = self.commercial_snapshot_loader.record_count > 0
        self._items = self._load()
        return reloaded

    def health(self) -> ToolHealth:
        return self.state

    def retrieve(self, context: AdapterContext) -> list[dict[str, Any]]:
        self.last_context = context
        if self.state is not ToolHealth.HEALTHY:
            raise RuntimeError("approved knowledge source unavailable")

        # 1. Authoritative Commercial Snapshot Retrieval when feature is enabled
        if self.commercial_snapshot_enabled and self.commercial_snapshot_loader and self.commercial_snapshot_loader.record_count > 0:
            q_lower = context.query.lower()
            is_commercial_domain = context.domain in {"product_catalog", "membership"}
            is_commercial_query = any(w in q_lower for w in [
                "product", "products", "available", "carry", "cream", "creams", "butter", "butters",
                "topical", "topicals", "oil", "oils", "tincture", "tinctures", "book", "books",
                "course", "courses", "class", "classes", "grow", "cooking", "culinary", "learn",
                "torque", "nft", "membership", "memberships", "payment plan", "payment plans",
                "financing", "installment", "installments", "infused basics", "cannabis right for me",
                "consultation", "service", "buy", "price", "cost", "lounge pass", "lounge member",
                "lounge elite", "silver", "gold", "legend og", "bronze", "copper", "titanium", "platinum"
            ])

            if is_commercial_domain or is_commercial_query:
                snapshot_results = self._retrieve_commercial_snapshot(context)
                if snapshot_results:
                    return snapshot_results
                if self._is_excluded_or_specific_lookup(context.query):
                    return []

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
            elif t in {"affiliate", "affiliates", "referral", "commission", "commissions", "payout", "payouts", "promote", "promotions", "applications", "application"}:
                terms.update({"affiliate", "affiliates", "program", "pilot", "commission", "commissions", "rate", "rates", "earn", "promote", "payout", "payouts", "apply", "application", "followers"})

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
                    
            if any(w in q_lower for w in ["affiliate", "commission", "referral", "promote", "payout", "earn", "application", "pilot"]):
                if "affiliate" in it.get("domain", ""):
                    score += 50
                if "affiliate" in title_lower:
                    score += 30
                if "canonical_url" in content_lower:
                    score += 20
                    
            if is_destination and "canonical_url" in content_lower:
                score += 25

            return score

        matches.sort(key=_score_item, reverse=True)
        return matches[: context.max_results]

    def _retrieve_commercial_snapshot(self, context: AdapterContext) -> list[dict[str, Any]]:
        if not self.commercial_snapshot_loader or self.commercial_snapshot_loader.record_count == 0:
            return []

        query = context.query.strip()
        q_lower = query.lower()

        # 1. Deterministic direct entity resolution
        res = self.commercial_resolver.resolve(query)
        if res.status == "EXACT_MATCH" and res.canonical_id:
            rec = self.commercial_snapshot_loader.get_by_canonical_id(res.canonical_id)
            if rec is not None:
                items = [self._format_snapshot_record(rec, context.domain)]
                # If variable NFT parent (e.g. Torque), include its tiers (Bronze, Copper, Titanium, Platinum)
                if rec.entity_type == "NFT_MEMBERSHIP_PARENT":
                    tiers = [r for r in self.commercial_snapshot_loader.records if r.canonical_id.startswith(f"{rec.canonical_id}:")]
                    for t in tiers:
                        items.append(self._format_snapshot_record(t, context.domain))
                # If course with payment plan, include payment plan record
                if rec.entity_type == "COURSE" and rec.payment_plan_available:
                    plan = self.commercial_snapshot_loader.get_by_canonical_id(f"{rec.canonical_id}:payment-plan")
                    if plan:
                        items.append(self._format_snapshot_record(plan, context.domain))
                return items[: context.max_results]

        # 2. Check if query is for an excluded community product (Fail Closed)
        if any(exc in q_lower for exc in ["lounge pass", "lounge member", "lounge elite", "wnb:community:"]):
            return []

        # 3. Category / Inventory Collection Queries
        matched_records: list[CommercialCatalogRecord] = []
        all_records = self.commercial_snapshot_loader.records

        # Classes / Courses
        if any(w in q_lower for w in ["class", "classes", "course", "courses", "growing", "grow", "cooking", "culinary", "learn how to cook", "learn to cook"]):
            if any(w in q_lower for w in ["payment plan", "financing", "installment", "monthly"]):
                matched_records.extend([r for r in all_records if r.entity_type == "COURSE_PAYMENT_PLAN"])
            else:
                matched_records.extend([r for r in all_records if r.entity_type == "COURSE"])
                if "cook" in q_lower or "culinary" in q_lower:
                    # Also include book basics for cooking recommendation context
                    book = self.commercial_snapshot_loader.get_by_canonical_id("ccc:book:infused-basics")
                    if book:
                        matched_records.append(book)

        # Payment plans specifically
        elif any(w in q_lower for w in ["payment plan", "payment plans", "financing", "installments", "installment", "monthly option"]):
            matched_records.extend([r for r in all_records if r.entity_type == "COURSE_PAYMENT_PLAN"])

        # Consultation Service & Appointments
        elif any(w in q_lower for w in ["is cannabis right for me", "consultation", "consultations", "consult", "consulting", "service", "services", "appointment", "appointments", "1-on-1", "one-on-one", "session", "sessions", "schedule", "scheduling", "book a consultation", "book consultation", "book an appointment", "book appointment", "booking a consultation"]):
            matched_records.extend([r for r in all_records if r.entity_type == "SERVICE"])

        # Books
        elif any(w in q_lower for w in ["book", "books", "guide", "guides", "reading", "botanical", "basics", "infused basics"]) and not any(w in q_lower for w in ["consultation", "consult", "appointment", "session", "service", "schedule", "scheduling", "1-on-1", "one-on-one"]):
            matched_records.extend([r for r in all_records if r.entity_type == "BOOK"])

        # Memberships / Legends / Torque & Characters / NFTs
        elif any(w in q_lower for w in [
            "membership", "memberships", "nft", "legends", "pass", "tier", "tiers",
            "torque", "chemist", "the chemist", "berry bliss", "the don", "gamma blaze",
            "original guardian", "the monarch", "monarch", "dizel", "cookie cutter",
            "azurea", "azurea skye"
        ]):
            character_slug_map = {
                "torque": "torque",
                "chemist": "the-chemist",
                "berry bliss": "berry-bliss",
                "strawberry banana": "berry-bliss",
                "the don": "the-don",
                "godfather": "the-don",
                "gamma blaze": "gamma-blaze",
                "bruce banner": "gamma-blaze",
                "original guardian": "the-original-guardian",
                "guardian": "the-original-guardian",
                "monarch": "the-monarch",
                "dizel": "dizel",
                "cookie cutter": "cookie-cutter",
                "azurea": "azurea-skye",
            }
            matched_char = None
            for char_term, char_id in character_slug_map.items():
                if char_term in q_lower:
                    matched_char = char_id
                    break
            if matched_char:
                matched_records.extend([r for r in all_records if f"wnb:nft:{matched_char}" in r.canonical_id])
            else:
                matched_records.extend([r for r in all_records if r.entity_type in ["NFT_MEMBERSHIP_PARENT", "NFT_MEMBERSHIP_TIER"]])

        # CBD Products / General product catalog
        elif any(w in q_lower for w in ["product", "products", "cream", "creams", "butter", "butters", "topical", "topicals", "oil", "oils", "tincture", "tinctures", "cbd", "salve", "catalog", "shop", "carry", "sell", "available"]):
            cbd_prods = [r for r in all_records if r.entity_type == "PRODUCT"]
            if any(w in q_lower for w in ["oil", "oils", "tincture", "tinctures"]):
                matched_records.extend([r for r in cbd_prods if "oil" in r.canonical_id or "tincture" in r.canonical_id])
            elif any(w in q_lower for w in ["cream", "butter", "topical"]):
                matched_records.extend([r for r in cbd_prods if "butter" in r.canonical_id or "cream" in r.canonical_id])
            else:
                matched_records.extend(cbd_prods)

        if not matched_records:
            # Fallback search over tokens
            raw_terms = set(re.findall(r"[a-z0-9]+", q_lower)) - {"what", "is", "the", "a", "an", "do", "you", "have", "for", "me", "how", "much", "tell", "about"}
            for r in all_records:
                rec_text = f"{r.name} {r.slug} {r.canonical_id} {r.short_summary} {r.description}".lower()
                if raw_terms and any(t in rec_text for t in raw_terms):
                    matched_records.append(r)

        seen_ids: set[str] = set()
        deduped: list[CommercialCatalogRecord] = []
        for r in matched_records:
            if r.canonical_id not in seen_ids:
                seen_ids.add(r.canonical_id)
                deduped.append(r)

        items = [self._format_snapshot_record(r, context.domain) for r in deduped]
        return items[: context.max_results]

    def _format_snapshot_record(self, record: CommercialCatalogRecord, domain: str) -> dict[str, Any]:
        dest_url = record.booking_url or record.checkout_url or record.canonical_url
        link_label = "Book consultation" if record.entity_type == "SERVICE" else ("Enroll now" if record.entity_type in ["COURSE", "COURSE_PAYMENT_PLAN"] else ("View membership" if "NFT" in record.entity_type else "View product"))
        data = {
            "resource_type": record.entity_type,
            "canonical_id": record.canonical_id,
            "sku": record.sku,
            "slug": record.slug,
            "name": record.name,
            "price_usd": record.price_usd,
            "current_price": record.price_usd,
            "currency": record.currency,
            "billing_model": record.billing_model,
            "category": record.category,
            "brand": record.brand,
            "status": record.status,
            "release_state": record.release_state,
            "customer_purchasable": record.customer_purchasable,
            "catalog_visibility": record.catalog_visibility,
            "short_summary": record.short_summary,
            "description": record.description,
            "benefits": record.benefits,
            "exclusions": record.exclusions,
            "canonical_url": record.canonical_url,
            "checkout_url": record.checkout_url,
            "booking_url": record.booking_url,
            "woo_product_id": record.woo_product_id,
            "payment_plan_available": record.payment_plan_available,
            "payment_plan_amount": record.payment_plan_amount,
            "payment_plan_url": record.payment_plan_url,
            "payment_processor": record.payment_processor,
            "link_label": link_label,
        }
        return {
            "knowledge_id": f"commercial:{record.canonical_id}",
            "title": record.name,
            "version": record.catalog_version,
            "domain": domain,
            "status": "Active",
            "classification": "Public",
            "source_reference": f"commercial_snapshot://{record.canonical_id}",
            "canonical_url": record.canonical_url,
            "content": json.dumps(data, separators=(",", ":")),
        }

    @staticmethod
    def _is_excluded_or_specific_lookup(query: str) -> bool:
        q_lower = query.lower()
        if any(exc in q_lower for exc in ["lounge pass", "lounge member", "lounge elite", "wnb:community:"]):
            return True
        specific_product_nouns = re.compile(
            r"\b(balms?|gumm(?:y|ies)|vapes?|chocolates?|edibles?|flowers?|pre-?rolls?|beverages?|capsules?|cartridges?|patches?)\b",
            re.I
        )
        return bool(specific_product_nouns.search(query))

    def _retrieve_live_catalog(self, context: AdapterContext) -> list[dict[str, Any]]:
        now = time.time()
        products = None
        if self._cached_live_products and (now - self._cached_live_products_time) < self._cache_ttl_seconds:
            products = self._cached_live_products
        else:
            try:
                req = self.commerce_url
                if isinstance(req, str):
                    req = urllib.request.Request(
                        self.commerce_url,
                        headers={
                            "User-Agent": "BudlyRuntime/1.8.10",
                            "Accept-Encoding": "gzip",
                        }
                    )
                with self.opener(req, timeout=15) as response:
                    raw_bytes = response.read()
                    if raw_bytes.startswith(b"\x1f\x8b") or (hasattr(response, "info") and response.info() and response.info().get("Content-Encoding") == "gzip"):
                        raw_bytes = gzip.decompress(raw_bytes)
                    data = json.loads(raw_bytes.decode("utf-8"))
                    if isinstance(data, list):
                        products = data
                        self._cached_live_products = products
                        self._cached_live_products_time = now
            except Exception as exc:
                if self._cached_live_products:
                    products = self._cached_live_products
                else:
                    raise RuntimeError(f"approved knowledge source unavailable: {exc}") from exc
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
            "spray": {"spray", "sprays", "tincture", "tinctures", "oil", "oils"},
            "sprays": {"spray", "sprays", "tincture", "tinctures", "oil", "oils"},
            "combo": {"combo", "bundle", "therapeutic", "package"},
            "botanical": {"botanical", "collection", "book", "books", "coloring", "guide"},
            "collection": {"botanical", "collection", "book", "books", "coloring", "guide"},
            "therapeutic": {"therapeutic", "spray", "butter", "oil", "tincture", "combo"},
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
            "consultation": {"consultation", "consultations", "consult", "consulting", "appointment", "appointments", "session", "schedule", "booking", "service"},
            "consultations": {"consultation", "consultations", "consult", "consulting", "appointment", "appointments", "session", "schedule", "booking", "service"},
            "consult": {"consultation", "consultations", "consult", "consulting", "appointment", "appointments", "session", "schedule", "booking", "service"},
            "consulting": {"consultation", "consultations", "consult", "consulting", "appointment", "appointments", "session", "schedule", "booking", "service"},
            "appointment": {"consultation", "consultations", "consult", "appointment", "appointments", "session", "schedule", "booking", "service"},
            "appointments": {"consultation", "consultations", "consult", "appointment", "appointments", "session", "schedule", "booking", "service"},
            "schedule": {"consultation", "consultations", "appointment", "appointments", "session", "schedule", "booking", "service"},
            "scheduling": {"consultation", "consultations", "appointment", "appointments", "session", "schedule", "booking", "service"},
            "booking": {"consultation", "consultations", "appointment", "appointments", "session", "schedule", "booking", "service"},
            "session": {"consultation", "consultations", "appointment", "appointments", "session", "schedule", "booking", "service"},
            "sessions": {"consultation", "consultations", "appointment", "appointments", "session", "schedule", "booking", "service"},
            "service": {"consultation", "consultations", "appointment", "appointments", "session", "schedule", "booking", "service"},
            "services": {"consultation", "consultations", "appointment", "appointments", "session", "schedule", "booking", "service"},
            "one-on-one": {"consultation", "consultations", "appointment", "session", "1-on-1", "one-on-one", "service"},
            "1-on-1": {"consultation", "consultations", "appointment", "session", "1-on-1", "one-on-one", "service"},
            "cookbook": {"book", "books", "guide", "guides", "botanical", "collection", "basics", "cookbook"},
            "cookbooks": {"book", "books", "guide", "guides", "botanical", "collection", "basics", "cookbook"},
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

        is_service_booking_action = bool(
            re.search(r"\b(book|booking|schedule|scheduling)\b", query_text)
            and re.search(r"\b(consultation|consultations|consult|appointment|appointments|session|sessions|service|services|call|1-on-1|one-on-one|right\s+for\s+me)\b", query_text)
        )

        required_keywords: set[str] = set()
        for term in product_intent_terms:
            if term in {"book", "booking"} and is_service_booking_action:
                required_keywords.update({"consultation", "consultations", "appointment", "appointments", "session", "schedule", "booking", "service"})
            elif term in synonyms:
                required_keywords.update(synonyms[term])
            else:
                required_keywords.add(term)

        results = []
        for product in products:
            decision = self.eligibility_resolver.resolve(product)
            if decision.status != ProductEligibilityStatus.PUBLIC_APPROVED:
                continue
            slug = decision.slug or str(product.get("slug", ""))
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
            service_descriptors = {"consultation", "consultations", "consult", "consulting", "appointment", "appointments", "session", "sessions", "service", "services", "booking", "schedule", "scheduling", "1-on-1", "one-on-one"}
            short_desc_raw = str(product.get("short_description", "")).lower()
            desc_raw = str(product.get("description", "")).lower()
            for kw in service_descriptors:
                if kw in short_desc_raw or kw in desc_raw:
                    searchable_tokens.add(kw)
            
            if required_keywords and not required_keywords.intersection(searchable_tokens):
                continue

            prices = product.get("prices", {})
            decimals = int(prices.get("currency_minor_unit", 2) or 2)
            price = int(prices.get("price", 0) or 0) / (10 ** decimals)
            price_range = prices.get("price_range")
            min_price = None
            max_price = None
            if isinstance(price_range, dict) and price_range.get("min_amount") is not None and price_range.get("max_amount") is not None:
                min_price = int(price_range["min_amount"]) / (10 ** decimals)
                max_price = int(price_range["max_amount"]) / (10 ** decimals)

            prod_type = str(product.get("type", "simple")).lower()
            variations_list = []
            if prod_type == "variable" or product.get("has_options"):
                for v in product.get("variations", []):
                    if isinstance(v, dict):
                        attrs = {a.get("name"): a.get("value") for a in v.get("attributes", []) if isinstance(a, dict)}
                        variations_list.append({"variation_id": v.get("id"), "attributes": attrs})

            is_service = (
                slug == "is-cannabis-right-for-me"
                or str(product.get("id")) == "1046"
                or "consultation" in slug
                or "service" in slug
                or any("service" in c.lower() or "consultation" in c.lower() for c in categories)
            )
            prod_res_type = "SERVICE" if is_service else "PRODUCT"

            booking_url = None
            if prod_res_type == "SERVICE":
                if str(product.get("id")) == "1046" or slug == "is-cannabis-right-for-me":
                    booking_url = "https://dmckenzies.wixsite.com/wakenbakelounge/service-page/is-cannabis-right-for-me"
                elif product.get("booking_url"):
                    booking_url = str(product["booking_url"])
                else:
                    desc_text = f"{product.get('short_description', '')} {product.get('description', '')}"
                    wix_match = re.search(r"https://(?:dmckenzies\.wixsite\.com|wakenbakelounge\.com)/service-page/[a-zA-Z0-9_\-]+", desc_text)
                    if wix_match:
                        booking_url = wix_match.group(0)

            record = {
                "resource_type": prod_res_type,
                "product_type": prod_type,
                "product_id": str(product.get("id", "")),
                "slug": slug,
                "canonical_id": decision.canonical_id,
                "name": html.unescape(re.sub(r"<[^>]+>", "", str(product.get("name", "")))),
                "category": categories,
                "customer_lane": prod_lane,
                "short_description": html.unescape(re.sub(r"<[^>]+>", " ", str(product.get("short_description", "")))).strip()[:500],
                "description": html.unescape(re.sub(r"<[^>]+>", " ", str(product.get("description", "")))).strip()[:2000],
                "canonical_url": str(product.get("permalink", "")),
                "current_price": price,
                "price_range_min": min_price,
                "price_range_max": max_price,
                "currency": str(prices.get("currency_code", "USD")),
                "availability": "in_stock" if product.get("is_in_stock") else "out_of_stock",
                "approval_status": "PUBLIC_APPROVED",
                "ingredient_evidence_type": "MARKETING_DESCRIPTION",
                "variations": variations_list,
                "last_verified_at": "live_request",
            }
            if booking_url:
                record["booking_url"] = booking_url
            results.append({
                "knowledge_id": f"product:{slug}", "title": record["name"], "version": "live",
                "domain": "product_catalog", "status": "Active", "classification": "Public",
                "source_reference": f"woocommerce-store-api://products/{record['product_id']}",
                "canonical_url": record["canonical_url"],
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
            if any(w in q for w in ["consultation", "consultations", "consult", "appointment", "appointments", "session", "sessions", "1-on-1", "one-on-one", "cannabis right for me", "cannabis-right-for-me"]):
                if data.get("resource_type") == "SERVICE":
                    score += 40
                if ("cannabis-right-for-me" in prod_slug) and any(term in q for term in ["right for me", "right-for-me", "cannabis", "budly"]):
                    score += 30
            elif any(w in q for w in ["cookbook", "infused basics", "reading", "recipe", "guide book"]) or (any(w in q for w in ["book", "books"]) and not any(w in q for w in ["consultation", "consult", "appointment", "session", "service", "schedule", "scheduling", "1-on-1", "one-on-one", "book a", "booking"])):
                if "basics" in prod_slug:
                    score += 30
                elif "botanical" in prod_slug or "collection" in prod_slug:
                    score += 30
            if any(w in q for w in ["spray", "sprays"]):
                if "spray" in prod_slug or "spray" in prod_name:
                    score += 60
            if any(w in q for w in ["combo", "bundle"]):
                if "combo" in prod_slug or "combo" in prod_name:
                    score += 60
            if any(w in q for w in ["botanical", "collection"]):
                if "botanical" in prod_slug or "botanical" in prod_name:
                    score += 50
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

            # Prefer standard one-time retail products over monthly subscription variants unless explicitly requested
            if any(sub_token in prod_slug for sub_token in ["monthly", "subscription"]):
                if not any(req_token in q for req_token in ["monthly", "subscription", "recurring", "auto-ship", "subscribe"]):
                    score -= 15
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
        self.product_overrides = {p['id']: p for p in products.get('products', []) if isinstance(p, dict) and p.get('id')}
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
        if not self.commercial_snapshot_enabled:
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
                if self.commercial_snapshot_enabled and resource.get("resource_type") in {"PRODUCT", "COURSE", "COURSE_PAYMENT_PLAN", "MEMBERSHIP_TIER"}:
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
            if not self.commercial_snapshot_enabled:
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

        commercial_truth_candidates = [
            self.policies_path.parent.parent / "deploy" / "wordpress" / "ccc-wnb-membership-entitlements" / "commercial-truth.json",
            self.policies_path.parent / "commercial-truth.json",
            Path("deploy/wordpress/ccc-wnb-membership-entitlements/commercial-truth.json"),
        ]
        truth_path = next((p for p in commercial_truth_candidates if p.exists()), None)
        if truth_path is not None:
            try:
                truth = self._read_json(truth_path)
                if truth.get("release_state") in {"AVAILABLE", "APPROVED_NOT_RELEASED"} and truth.get("publicly_available"):
                    items.append({
                        "knowledge_id": "commercial_truth:wakenbake_lounge:membership",
                        "title": "Wake'n'Bake Lounge Community Memberships",
                        "version": str(truth.get("schema_version", "2.0")),
                        "domain": "membership",
                        "status": "Active",
                        "classification": "Public",
                        "source_reference": f"repository://{truth_path.as_posix()}",
                        "content": json.dumps({
                            "resource_type": "MEMBERSHIP_FAMILY",
                            "membership_family": truth.get("membership_family"),
                            "release_state": truth.get("release_state"),
                            "public_response_rule": truth.get("public_response_rule"),
                            "hierarchy": truth.get("hierarchy"),
                            "discount_exclusions": truth.get("discount_exclusions"),
                            "canonical_url": "https://cccultivate.com/wakenbake-lounge-community/",
                            "link_label": "Explore Lounge Community",
                        }, separators=(",", ":")),
                    })
                    for plan in truth.get("plans", []):
                        level = str(plan.get("level", ""))
                        items.append({
                            "knowledge_id": f"commercial_truth:plan:{level}",
                            "title": f"Wake'n'Bake Lounge {level.title()}",
                            "version": str(truth.get("schema_version", "2.0")),
                            "domain": "membership",
                            "status": "Active",
                            "classification": "Public",
                            "source_reference": f"repository://{truth_path.as_posix()}#{level}",
                            "content": json.dumps({
                                "resource_type": "MEMBERSHIP_PLAN",
                                "level": level,
                                "price_usd": plan.get("price_usd"),
                                "billing": plan.get("billing"),
                                "benefits": plan.get("benefits"),
                                "canonical_url": "https://cccultivate.com/product/lounge-pass/" if level == "pass" else "https://cccultivate.com/wakenbake-lounge-community/",
                                "link_label": "Claim Free Lounge Pass" if level == "pass" else f"Wake'n'Bake Lounge {level.title()}",
                            }, separators=(",", ":")),
                        })
                    items.append({
                        "knowledge_id": "commercial_truth:wakenbake_lounge:discovery",
                        "title": "Wake'n'Bake Lounge Public Discovery & Exploration",
                        "version": str(truth.get("schema_version", "2.0")),
                        "domain": "educational",
                        "status": "Active",
                        "classification": "Public",
                        "source_reference": f"repository://{truth_path.as_posix()}#discovery",
                        "content": json.dumps({
                            "resource_type": "PUBLIC_DISCOVERY",
                            "summary": "Wake'n'Bake Lounge public discovery: Educational guides, botanical recipes, and plant science exhibits are currently in editorial preparation and planned for future release. Currently accessible today are the community hub orientation and membership passes.",
                            "canonical_url": "https://cccultivate.com/wakenbake-lounge-community/",
                            "link_label": "Explore Lounge Community",
                        }, separators=(",", ":")),
                    })
            except Exception:
                pass

        if self.affiliate_path is not None:
            affiliate = self._read_json(self.affiliate_path)
            if affiliate.get("approval_status") != "owner_approved" or affiliate.get("program_state") != "PRIVATE_PILOT":
                raise ValueError("affiliate knowledge is not owner approved private-pilot truth")
            for fact in affiliate.get("public_facts", []):
                if fact.get("classification") != "Public" or fact.get("status") != "Active":
                    continue
                items.append({
                    "knowledge_id": str(fact["fact_id"]), "title": str(fact["title"]),
                    "version": str(affiliate["version"]), "domain": "affiliate_program",
                    "status": "Active", "classification": "Public",
                    "source_reference": f"repository://config/budly_runtime/affiliate-public-knowledge-g9d-v1.json#{fact['fact_id']}",
                    "content": json.dumps(fact, separators=(",", ":"))[:4000],
                })
        return items

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"knowledge source {path.name} is invalid")
        return value
