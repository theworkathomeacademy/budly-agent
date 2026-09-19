"""Lead promotion threshold rules for Budly Conversion Spine (STS-1)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}")
PHONE_RE = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")


class LeadPromotionReason(str, Enum):
    CONTACT_INFO_SUPPLIED = "CONTACT_INFO_SUPPLIED"
    REQUESTED_FOLLOWUP = "REQUESTED_FOLLOWUP"


@dataclass(frozen=True)
class LeadPromotionDecision:
    is_promoted: bool
    reason: str | None
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_promoted": self.is_promoted,
            "reason": self.reason,
            "rationale": self.rationale,
        }


class LeadThresholdEvaluator:
    """Evaluates whether a conversation session has met the governed known-visitor threshold for CRM Lead promotion.
    
    In accordance with ratified BROS customer lifecycle architecture:
    Anonymous visitors may have commercial intent and be QUALIFIED_PURCHASE_READY without becoming CRM Leads.
    A CRM Lead is ONLY created when approved voluntary identifying/contact information is provided.
    """

    @classmethod
    def evaluate(
        cls,
        intent: str,
        product_or_topic: str,
        qualification_state: str,
        turn_count: int = 1,
        user_message: str = "",
        contact_info_provided: dict[str, str] | None = None,
    ) -> LeadPromotionDecision:
        # 1. Contact info supplied explicitly via structured input
        if contact_info_provided and (contact_info_provided.get("email") or contact_info_provided.get("phone")):
            return LeadPromotionDecision(
                is_promoted=True,
                reason=LeadPromotionReason.CONTACT_INFO_SUPPLIED.value,
                rationale="User voluntarily supplied approved identity/contact information",
            )

        # 2. Contact info included voluntarily in message
        if user_message:
            if EMAIL_RE.search(user_message) or PHONE_RE.search(user_message):
                return LeadPromotionDecision(
                    is_promoted=True,
                    reason=LeadPromotionReason.CONTACT_INFO_SUPPLIED.value,
                    rationale="User included contact information in message",
                )

        # Anonymous visitor: Remains unpromoted regardless of purchase intent or commercial conversation depth
        return LeadPromotionDecision(
            is_promoted=False,
            reason=None,
            rationale="User is an anonymous visitor; identity/contact threshold not met",
        )
