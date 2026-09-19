"""Qualification state transitions for Budly Conversion Spine (STS-1)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

try:
    from .intent_taxonomy import CommercialIntent, ProductTopic
except (ImportError, ValueError):
    from intent_taxonomy import CommercialIntent, ProductTopic


class QualificationState(str, Enum):
    UNQUALIFIED = "UNQUALIFIED"
    DISCOVERY = "DISCOVERY"
    QUALIFIED_EDUCATION = "QUALIFIED_EDUCATION"
    QUALIFIED_COMMUNITY = "QUALIFIED_COMMUNITY"
    QUALIFIED_NURTURE = "QUALIFIED_NURTURE"
    QUALIFIED_PURCHASE_READY = "QUALIFIED_PURCHASE_READY"
    NOT_CURRENT_FIT = "NOT_CURRENT_FIT"


@dataclass(frozen=True)
class QualificationDecision:
    state: str
    rationale: str
    confidence: str

    def validate(self) -> None:
        if self.state not in {s.value for s in QualificationState}:
            raise ValueError(f"Invalid qualification state: {self.state}")
        if self.confidence not in {"high", "medium", "low"}:
            raise ValueError(f"Invalid confidence: {self.confidence}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "rationale": self.rationale,
            "confidence": self.confidence,
        }


class QualificationEngine:
    """Deterministic, lightweight qualification state evaluator for Sprint to 100."""

    STATE_RANK: dict[str, int] = {
        QualificationState.NOT_CURRENT_FIT.value: -1,
        QualificationState.UNQUALIFIED.value: 0,
        QualificationState.DISCOVERY.value: 1,
        QualificationState.QUALIFIED_COMMUNITY.value: 2,
        QualificationState.QUALIFIED_EDUCATION.value: 2,
        QualificationState.QUALIFIED_NURTURE.value: 3,
        QualificationState.QUALIFIED_PURCHASE_READY.value: 4,
    }

    @classmethod
    def evaluate(
        cls,
        intent: str,
        product_or_topic: str,
        turn_count: int = 1,
        has_contact_info: bool = False,
        is_risk_or_prohibited: bool = False,
        prior_state: str | None = None,
    ) -> QualificationDecision:
        if is_risk_or_prohibited:
            return QualificationDecision(
                state=QualificationState.NOT_CURRENT_FIT.value,
                rationale="Flagged for medical/safety/prohibited claim risk",
                confidence="high",
            )

        # 1. Purchase intent on known product
        if intent == CommercialIntent.PURCHASE_INTENT.value:
            if product_or_topic in {ProductTopic.BOTANICAL_COLLECTION.value, ProductTopic.OTHER_APPROVED_PRODUCT.value}:
                return QualificationDecision(
                    state=QualificationState.QUALIFIED_PURCHASE_READY.value,
                    rationale=f"Explicit purchase intent expressed for approved topic {product_or_topic}",
                    confidence="high",
                )
            return QualificationDecision(
                state=QualificationState.QUALIFIED_PURCHASE_READY.value,
                rationale="General purchase intent expressed; ready for product selection",
                confidence="medium",
            )

        # 2. Product interest
        if intent == CommercialIntent.PRODUCT_INTEREST.value:
            if turn_count >= 2 or has_contact_info:
                return QualificationDecision(
                    state=QualificationState.QUALIFIED_PURCHASE_READY.value,
                    rationale="Multi-turn product interest or identified interest",
                    confidence="high",
                )
            return QualificationDecision(
                state=QualificationState.QUALIFIED_NURTURE.value,
                rationale=f"Active commercial interest in {product_or_topic}",
                confidence="medium",
            )

        # 3. Education interest
        if intent == CommercialIntent.EDUCATION_INTEREST.value:
            return QualificationDecision(
                state=QualificationState.QUALIFIED_EDUCATION.value,
                rationale="Expressed interest in cannabis wellness education or guides",
                confidence="high",
            )

        # 4. Community interest
        if intent == CommercialIntent.COMMUNITY_INTEREST.value:
            return QualificationDecision(
                state=QualificationState.QUALIFIED_COMMUNITY.value,
                rationale="Expressed interest in Wake'n'Bake Lounge community or events",
                confidence="high",
            )

        # 5. Prior state preservation if user simply provided contact info or continuing chat
        if prior_state and prior_state in cls.STATE_RANK and cls.STATE_RANK[prior_state] >= cls.STATE_RANK[QualificationState.QUALIFIED_NURTURE.value]:
            return QualificationDecision(
                state=prior_state,
                rationale=f"Maintained prior qualification state {prior_state} across conversation",
                confidence="high",
            )

        # 6. Discovery vs Unqualified
        if intent == CommercialIntent.GENERAL_CONVERSATION.value:
            if product_or_topic != ProductTopic.UNKNOWN.value:
                return QualificationDecision(
                    state=QualificationState.DISCOVERY.value,
                    rationale="In conversation with social campaign topic context",
                    confidence="medium",
                )
            return QualificationDecision(
                state=QualificationState.DISCOVERY.value,
                rationale="General introductory conversation",
                confidence="low",
            )

        return QualificationDecision(
            state=QualificationState.UNQUALIFIED.value,
            rationale="No commercial or engagement intent identified yet",
            confidence="low",
        )
