"""Commercial Intent and Product Topic Taxonomy for Budly Conversion Spine (STS-1)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class CommercialIntent(str, Enum):
    GENERAL_CONVERSATION = "GENERAL_CONVERSATION"
    EDUCATION_INTEREST = "EDUCATION_INTEREST"
    COMMUNITY_INTEREST = "COMMUNITY_INTEREST"
    PRODUCT_INTEREST = "PRODUCT_INTEREST"
    PURCHASE_INTENT = "PURCHASE_INTENT"
    SUPPORT_QUESTION = "SUPPORT_QUESTION"
    UNKNOWN = "UNKNOWN"


class ProductTopic(str, Enum):
    BOTANICAL_COLLECTION = "BOTANICAL_COLLECTION"
    COLORING_APP = "COLORING_APP"
    WAKE_N_BAKE_CONTENT = "WAKE_N_BAKE_CONTENT"
    OTHER_APPROVED_PRODUCT = "OTHER_APPROVED_PRODUCT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class IntentRecognitionResult:
    intent: str
    product_or_topic: str
    confidence: str  # "high", "medium", "low"
    matched_signals: list[str]

    def validate(self) -> None:
        if self.intent not in {i.value for i in CommercialIntent}:
            raise ValueError(f"Invalid intent: {self.intent}")
        if self.product_or_topic not in {t.value for t in ProductTopic}:
            raise ValueError(f"Invalid product_or_topic: {self.product_or_topic}")
        if self.confidence not in {"high", "medium", "low"}:
            raise ValueError(f"Invalid confidence level: {self.confidence}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "product_or_topic": self.product_or_topic,
            "confidence": self.confidence,
            "matched_signals": self.matched_signals,
        }


class IntentClassifier:
    """Deterministic intent and topic classifier for Budly conversations."""

    INTENT_PATTERNS: dict[CommercialIntent, tuple[str, ...]] = {
        CommercialIntent.PURCHASE_INTENT: (
            r"\b(buy|purchase|order|checkout|cart|price|pricing|cost|how much is|discount|coupon)\b",
            r"\b(want to get|i('ll| will) take|ready to buy|ready to purchase)\b",
        ),
        CommercialIntent.PRODUCT_INTEREST: (
            r"\b(botanical|collection|coloring|book|edition|volume 1|print|digital format|tincture|oil|body butter)\b",
            r"\b(interested in (the|your)|tell me about the book|tell me about the product|what products|merch)\b",
        ),
        CommercialIntent.EDUCATION_INTEREST: (
            r"\b(learn|education|how to|guide|cannabinoids|terpenes|endocannabinoid|ecs|infusion|recipe|cooking)\b",
            r"\b(study|research|course|training|curriculum|reading)\b",
        ),
        CommercialIntent.COMMUNITY_INTEREST: (
            r"\b(community|lounge|wake'?n'?bake|events?|meetup|hangout|discord|membership|club|session)\b",
            r"\b(join the lounge|join community|wake and bake lounge)\b",
        ),
        CommercialIntent.SUPPORT_QUESTION: (
            r"\b(help|support|shipping|return|refund|order status|tracking|broken|damaged|contact human)\b",
        ),
        CommercialIntent.GENERAL_CONVERSATION: (
            r"\b(hi|hello|hey|good morning|what's up|how are you|who are you|budly)\b",
        ),
    }

    TOPIC_PATTERNS: dict[ProductTopic, tuple[str, ...]] = {
        ProductTopic.BOTANICAL_COLLECTION: (
            r"\b(botanical collection|cannabis botanical|coloring collection|botanical book|volume 1|vol 1)\b",
            r"\b(botanical|coloring book|botanicals)\b",
        ),
        ProductTopic.COLORING_APP: (
            r"\b(coloring app|digital app|interactive coloring|mobile coloring|ipad coloring)\b",
        ),
        ProductTopic.WAKE_N_BAKE_CONTENT: (
            r"\b(wake'?n'?bake|lounge content|podcast|wake and bake show|lounge stream)\b",
        ),
        ProductTopic.OTHER_APPROVED_PRODUCT: (
            r"\b(infused basics|tincture|body butter|cooking oil|wholesale butter|nft)\b",
        ),
    }

    @classmethod
    def classify(cls, text: str, initial_topic: str | None = None) -> IntentRecognitionResult:
        if not text or not text.strip():
            topic = initial_topic if initial_topic in {t.value for t in ProductTopic} else ProductTopic.UNKNOWN.value
            return IntentRecognitionResult(
                intent=CommercialIntent.UNKNOWN.value,
                product_or_topic=topic,
                confidence="low",
                matched_signals=[],
            )

        clean_text = text.lower().strip()
        matched_signals: list[str] = []

        # 1. Detect Topic
        detected_topic = ProductTopic.UNKNOWN
        for topic, patterns in cls.TOPIC_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, clean_text):
                    detected_topic = topic
                    matched_signals.append(f"topic_match:{topic.value}:{pat}")
                    break
            if detected_topic != ProductTopic.UNKNOWN:
                break

        # If no explicit topic detected in message but initial_topic was passed from attribution
        if detected_topic == ProductTopic.UNKNOWN and initial_topic:
            if initial_topic in {t.value for t in ProductTopic}:
                detected_topic = ProductTopic(initial_topic)
                matched_signals.append(f"topic_inherited:{initial_topic}")

        # 2. Detect Intent (order of precedence: PURCHASE_INTENT > PRODUCT_INTEREST > COMMUNITY/EDUCATION > SUPPORT > GENERAL)
        detected_intent = CommercialIntent.UNKNOWN
        priority_order = [
            CommercialIntent.PURCHASE_INTENT,
            CommercialIntent.PRODUCT_INTEREST,
            CommercialIntent.EDUCATION_INTEREST,
            CommercialIntent.COMMUNITY_INTEREST,
            CommercialIntent.SUPPORT_QUESTION,
            CommercialIntent.GENERAL_CONVERSATION,
        ]

        for intent in priority_order:
            patterns = cls.INTENT_PATTERNS[intent]
            for pat in patterns:
                if re.search(pat, clean_text):
                    detected_intent = intent
                    matched_signals.append(f"intent_match:{intent.value}:{pat}")
                    break
            if detected_intent != CommercialIntent.UNKNOWN:
                break

        # Fallback if text exists but didn't match specific keyword
        if detected_intent == CommercialIntent.UNKNOWN:
            if len(clean_text.split()) > 0:
                detected_intent = CommercialIntent.GENERAL_CONVERSATION
                matched_signals.append("fallback:general_conversation")

        # Determine confidence
        if len(matched_signals) >= 2 or detected_intent == CommercialIntent.PURCHASE_INTENT:
            confidence = "high"
        elif len(matched_signals) == 1:
            confidence = "medium"
        else:
            confidence = "low"

        res = IntentRecognitionResult(
            intent=detected_intent.value,
            product_or_topic=detected_topic.value,
            confidence=confidence,
            matched_signals=matched_signals,
        )
        res.validate()
        return res
