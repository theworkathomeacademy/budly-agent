"""Deterministic Recommendation Router for Budly Conversion Spine (STS-1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from .cta_registry import CTARecord, CTARegistry, CTAType
    from .intent_taxonomy import CommercialIntent, ProductTopic
    from .qualification import QualificationState
except (ImportError, ValueError):
    from cta_registry import CTARecord, CTARegistry, CTAType
    from intent_taxonomy import CommercialIntent, ProductTopic
    from qualification import QualificationState


@dataclass(frozen=True)
class RecommendationOutcome:
    cta_id: str
    cta_type: str
    display_label: str
    destination_url: str
    destination_type: str
    rationale: str
    suggested_dialogue: str
    is_approved: bool
    canonical_id: str | None = None
    catalog_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "cta_id": self.cta_id,
            "cta_type": self.cta_type,
            "display_label": self.display_label,
            "destination_url": self.destination_url,
            "destination_type": self.destination_type,
            "rationale": self.rationale,
            "suggested_dialogue": self.suggested_dialogue,
            "is_approved": self.is_approved,
            "canonical_id": self.canonical_id,
            "catalog_version": self.catalog_version,
        }

    def build_correlated_url(
        self,
        session_id: str | None = None,
        journey_id: str | None = None,
        source: str | None = None,
        platform: str | None = None,
        content_id: str | None = None,
        campaign_id: str | None = None,
    ) -> str:
        """Append safe non-PII correlation parameters to destination_url."""
        from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
        parsed = urlparse(self.destination_url)
        query = dict(parse_qsl(parsed.query))
        if session_id:
            query["_budly_session_id"] = str(session_id)[:64]
        if journey_id:
            query["_budly_journey_id"] = str(journey_id)[:64]
        if source:
            query["_budly_source"] = str(source)[:32]
        if platform:
            query["_budly_platform"] = str(platform)[:32]
        if content_id:
            query["_budly_content_id"] = str(content_id)[:64]
        if campaign_id:
            query["_budly_campaign_id"] = str(campaign_id)[:64]
        if self.cta_id:
            query["_budly_cta_id"] = str(self.cta_id)[:64]
        if self.canonical_id:
            query["_budly_canonical_id"] = str(self.canonical_id)[:128]
        if self.catalog_version:
            query["_budly_catalog_version"] = str(self.catalog_version)[:32]
        new_query = urlencode(query)
        return urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment,
        ))


class RecommendationRouter:
    """Maps (intent, product_or_topic, qualification_state) to verified CTAs from CTARegistry."""

    def __init__(self, registry: CTARegistry | None = None, snapshot_loader: Any | None = None) -> None:
        self.registry = registry or CTARegistry()
        self.snapshot_loader = snapshot_loader
        self._init_snapshot()

    def _init_snapshot(self) -> None:
        if self.snapshot_loader is None:
            try:
                from pathlib import Path
                from budly_runtime.commercial_snapshot.loader import CommercialSnapshotLoader
                root = Path(__file__).resolve().parents[1]
                catalog_dir = root / "config" / "commercial_catalog"
                if (catalog_dir / "Current" / "budly-commercial-catalog.json").exists():
                    self.snapshot_loader = CommercialSnapshotLoader(catalog_dir)
            except Exception:
                try:
                    from pathlib import Path
                    from src.budly_runtime.commercial_snapshot.loader import CommercialSnapshotLoader
                    root = Path(__file__).resolve().parents[1]
                    catalog_dir = root / "config" / "commercial_catalog"
                    if (catalog_dir / "Current" / "budly-commercial-catalog.json").exists():
                        self.snapshot_loader = CommercialSnapshotLoader(catalog_dir)
                except Exception:
                    self.snapshot_loader = None

    def route(
        self,
        intent: str,
        product_or_topic: str,
        qualification_state: str,
        platform: str = "web",
    ) -> RecommendationOutcome:
        cat_ver = getattr(self.snapshot_loader, "loaded_catalog_version", "1.0.0-public") if self.snapshot_loader else "1.0.0-public"

        # CCS-006 Fail Closed: Excluded community products must never be recommended as purchasable products
        excluded_topics = {"LOUNGE_MEMBER", "LOUNGE_PASS", "LOUNGE_ELITE", "wnb:community:lounge-member", "wnb:community:lounge-pass", "wnb:community:lounge-elite"}
        if product_or_topic in excluded_topics:
            raise ValueError(f"CCS-006: Product or topic '{product_or_topic}' is excluded from public commercial recommendation.")

        # 1. Purchase Intent + Botanical Collection
        if (
            intent == CommercialIntent.PURCHASE_INTENT.value
            and product_or_topic == ProductTopic.BOTANICAL_COLLECTION.value
        ):
            cta = self.registry.get_active_cta("CTA-BOTANICAL-VOL1-SHOP")
            if cta:
                cid = "ccc:book:wakenbake-lounge-cannabis-botanical-collection-volume-1"
                dest_url = cta.destination_url
                if self.snapshot_loader:
                    rec = self.snapshot_loader.get_by_canonical_id(cid)
                    if rec and rec.canonical_url:
                        dest_url = rec.canonical_url
                return RecommendationOutcome(
                    cta_id=cta.cta_id,
                    cta_type=cta.cta_type,
                    display_label=cta.display_label,
                    destination_url=dest_url,
                    destination_type=cta.destination_type,
                    rationale="Direct checkout/shop destination for Botanical Collection Volume 1",
                    suggested_dialogue=(
                        "You can review the format options and complete your order on the verified "
                        "CCCultivate product page here."
                    ),
                    is_approved=True,
                    canonical_id=cid,
                    catalog_version=cat_ver,
                )

        # 2. Product Interest + Botanical Collection
        if (
            intent == CommercialIntent.PRODUCT_INTEREST.value
            and product_or_topic == ProductTopic.BOTANICAL_COLLECTION.value
        ) or (
            qualification_state == QualificationState.QUALIFIED_PURCHASE_READY.value
            and product_or_topic == ProductTopic.BOTANICAL_COLLECTION.value
        ):
            cta = self.registry.get_active_cta("CTA-BOTANICAL-VOL1-EXPLORE") or self.registry.get_active_cta("CTA-BOTANICAL-VOL1-SHOP")
            if cta:
                return RecommendationOutcome(
                    cta_id=cta.cta_id,
                    cta_type=cta.cta_type,
                    display_label=cta.display_label,
                    destination_url=cta.destination_url,
                    destination_type=cta.destination_type,
                    rationale="Product exploration destination for Botanical Collection",
                    suggested_dialogue=(
                        "The Wake'n'Bake Lounge Cannabis Botanical Collection Volume 1 includes "
                        "detailed strain art and botanical education in print and digital formats."
                    ),
                    is_approved=True,
                    canonical_id="ccc:book:wakenbake-lounge-cannabis-botanical-collection-volume-1",
                    catalog_version=cat_ver,
                )

        # 3. Education Interest
        if (
            intent == CommercialIntent.EDUCATION_INTEREST.value
            or qualification_state == QualificationState.QUALIFIED_EDUCATION.value
        ):
            cta = self.registry.get_active_cta("CTA-INFUSED-BASICS-LEARN")
            if cta:
                return RecommendationOutcome(
                    cta_id=cta.cta_id,
                    cta_type=cta.cta_type,
                    display_label=cta.display_label,
                    destination_url=cta.destination_url,
                    destination_type=cta.destination_type,
                    rationale="Approved educational guide destination",
                    suggested_dialogue=(
                        "If you'd like to dive deeper into infusions and cooking methods, "
                        "the Infused Basics guide covers beginner-friendly techniques."
                    ),
                    is_approved=True,
                    canonical_id="ccc:book:infused-basics",
                    catalog_version=cat_ver,
                )

        # 4. Community Interest
        if (
            intent == CommercialIntent.COMMUNITY_INTEREST.value
            or qualification_state == QualificationState.QUALIFIED_COMMUNITY.value
        ):
            cta = self.registry.get_active_cta("CTA-COMMUNITY-001")
            if cta:
                return RecommendationOutcome(
                    cta_id=cta.cta_id,
                    cta_type=cta.cta_type,
                    display_label=cta.display_label,
                    destination_url=cta.destination_url,
                    destination_type=cta.destination_type,
                    rationale="Approved Wake'n'Bake Lounge community portal",
                    suggested_dialogue=(
                        "You're welcome to join the Wake'n'Bake Lounge community for upcoming "
                        "lounge sessions, discussions, and wellness conversations."
                    ),
                    is_approved=True,
                    canonical_id=None,
                    catalog_version=cat_ver,
                )

        # 5. General Product Shopping / Other approved products
        if intent in {CommercialIntent.PRODUCT_INTEREST.value, CommercialIntent.PURCHASE_INTENT.value}:
            cta = self.registry.get_active_cta("CTA-CATALOG-SHOP-001")
            if cta:
                return RecommendationOutcome(
                    cta_id=cta.cta_id,
                    cta_type=cta.cta_type,
                    display_label=cta.display_label,
                    destination_url=cta.destination_url,
                    destination_type=cta.destination_type,
                    rationale="General verified store catalog destination",
                    suggested_dialogue=(
                        "You can browse the current verified catalog on the CCCultivate shop."
                    ),
                    is_approved=True,
                    canonical_id=None,
                    catalog_version=cat_ver,
                )

        # 6. Fallback / General / Discovery: Continue Ask Budly Conversation
        cta = self.registry.get_active_cta("CTA-ASK-BUDLY-001")
        if cta:
            return RecommendationOutcome(
                cta_id=cta.cta_id,
                cta_type=cta.cta_type,
                display_label=cta.display_label,
                destination_url=cta.destination_url,
                destination_type=cta.destination_type,
                rationale="Continue guided discovery in Ask Budly",
                suggested_dialogue=(
                    "I'm here to help you explore products, education, or the lounge community. "
                    "What would you like to focus on?"
                ),
                is_approved=True,
                canonical_id=None,
                catalog_version=cat_ver,
            )

        # Guardrail fallback: If no active CTA found in registry, fail closed (never invent)
        raise RuntimeError("No approved CTA available in registry for routing")
