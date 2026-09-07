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
        }


class RecommendationRouter:
    """Maps (intent, product_or_topic, qualification_state) to verified CTAs from CTARegistry."""

    def __init__(self, registry: CTARegistry | None = None) -> None:
        self.registry = registry or CTARegistry()

    def route(
        self,
        intent: str,
        product_or_topic: str,
        qualification_state: str,
        platform: str = "web",
    ) -> RecommendationOutcome:
        # 1. Purchase Intent + Botanical Collection
        if (
            intent == CommercialIntent.PURCHASE_INTENT.value
            and product_or_topic == ProductTopic.BOTANICAL_COLLECTION.value
        ):
            cta = self.registry.get_active_cta("CTA-BOTANICAL-VOL1-SHOP")
            if cta:
                return RecommendationOutcome(
                    cta_id=cta.cta_id,
                    cta_type=cta.cta_type,
                    display_label=cta.display_label,
                    destination_url=cta.destination_url,
                    destination_type=cta.destination_type,
                    rationale="Direct checkout/shop destination for Botanical Collection Volume 1",
                    suggested_dialogue=(
                        "You can review the format options and complete your order on the verified "
                        "CCCultivate product page here."
                    ),
                    is_approved=True,
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
            )

        # Guardrail fallback: If no active CTA found in registry, fail closed (never invent)
        raise RuntimeError("No approved CTA available in registry for routing")
