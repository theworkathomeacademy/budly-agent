"""Tests for Intent Taxonomy, Lead Thresholds, and Qualification."""

import sys
import unittest
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parents[1]
if str(PKG_DIR) not in sys.path:
    sys.path.insert(0, str(PKG_DIR))

from intent_taxonomy import CommercialIntent, IntentClassifier, ProductTopic
from lead_threshold import LeadPromotionReason, LeadThresholdEvaluator
from qualification import QualificationEngine, QualificationState


class TestIntentAndQualification(unittest.TestCase):
    def test_intent_classification_product_interest(self):
        res = IntentClassifier.classify("Tell me about the cannabis botanical coloring collection volume 1")
        self.assertEqual(res.intent, CommercialIntent.PRODUCT_INTEREST.value)
        self.assertEqual(res.product_or_topic, ProductTopic.BOTANICAL_COLLECTION.value)
        self.assertEqual(res.confidence, "high")

    def test_intent_classification_purchase_intent(self):
        res = IntentClassifier.classify("I want to buy the botanical book", initial_topic="BOTANICAL_COLLECTION")
        self.assertEqual(res.intent, CommercialIntent.PURCHASE_INTENT.value)
        self.assertEqual(res.product_or_topic, ProductTopic.BOTANICAL_COLLECTION.value)

    def test_qualification_transitions(self):
        # Product interest -> QUALIFIED_NURTURE (turn 1)
        q1 = QualificationEngine.evaluate(
            intent=CommercialIntent.PRODUCT_INTEREST.value,
            product_or_topic=ProductTopic.BOTANICAL_COLLECTION.value,
            turn_count=1,
        )
        self.assertEqual(q1.state, QualificationState.QUALIFIED_NURTURE.value)

        # Purchase intent -> QUALIFIED_PURCHASE_READY
        q2 = QualificationEngine.evaluate(
            intent=CommercialIntent.PURCHASE_INTENT.value,
            product_or_topic=ProductTopic.BOTANICAL_COLLECTION.value,
            turn_count=1,
        )
        self.assertEqual(q2.state, QualificationState.QUALIFIED_PURCHASE_READY.value)

        # Community interest -> QUALIFIED_COMMUNITY
        q3 = QualificationEngine.evaluate(
            intent=CommercialIntent.COMMUNITY_INTEREST.value,
            product_or_topic=ProductTopic.WAKE_N_BAKE_CONTENT.value,
            turn_count=1,
        )
        self.assertEqual(q3.state, QualificationState.QUALIFIED_COMMUNITY.value)

    def test_lead_promotion_threshold(self):
        # Anonymous general conversation -> No lead promotion
        l1 = LeadThresholdEvaluator.evaluate(
            intent=CommercialIntent.GENERAL_CONVERSATION.value,
            product_or_topic=ProductTopic.UNKNOWN.value,
            qualification_state=QualificationState.DISCOVERY.value,
            turn_count=1,
        )
        self.assertFalse(l1.is_promoted)
        self.assertIsNone(l1.reason)

        # Anonymous product interest without identity -> Remains unpromoted at lead level (retains qualification)
        l2 = LeadThresholdEvaluator.evaluate(
            intent=CommercialIntent.PRODUCT_INTEREST.value,
            product_or_topic=ProductTopic.BOTANICAL_COLLECTION.value,
            qualification_state=QualificationState.QUALIFIED_NURTURE.value,
            turn_count=1,
        )
        self.assertFalse(l2.is_promoted)
        self.assertIsNone(l2.reason)

        # User supplies email voluntarily -> Promoted to Lead
        l3 = LeadThresholdEvaluator.evaluate(
            intent=CommercialIntent.GENERAL_CONVERSATION.value,
            product_or_topic=ProductTopic.UNKNOWN.value,
            qualification_state=QualificationState.DISCOVERY.value,
            turn_count=1,
            user_message="My email is buyer@example.com, please send info",
        )
        self.assertTrue(l3.is_promoted)
        self.assertEqual(l3.reason, LeadPromotionReason.CONTACT_INFO_SUPPLIED.value)


if __name__ == "__main__":
    unittest.main()
