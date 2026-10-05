"""G8 Financial Logic and Commission Verification Suite.

Tests ratified commercial policy, rounding mode (ROUND_HALF_UP), exact decimal types,
fail-closed and quarantine behaviors across:
1. Botanical Collection -> 25% (BOTANICAL_COLLECTION_25)
2. Infused Basics -> 25% (INFUSED_BASICS_25)
3. Legends -> 10% (LEGENDS_MEMBERSHIP_10)
4. Explicitly excluded product -> 0 commission (NO_COMMISSION)
5. Unknown/unmapped product -> 0 commission / fail closed
6. Affiliate-eligible + missing class -> STOP / quarantine
7. Affiliate-eligible + unknown class -> STOP / quarantine
8. HALF_UP boundary test proving governed rounding
9. No float use in commission calculation path
"""

import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP

from src.budly_runtime.affiliate.engine import (
    AffiliateEngine,
    DomainError,
    FeatureFlags,
    MONEY_QUANTUM,
    RATE_QUANTUM,
    money,
)

T0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)


class G8FinancialReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.flags = FeatureFlags(
            affiliate_referral_enabled=True,
            affiliate_attribution_enabled=True,
            affiliate_commission_processing_enabled=True,
            affiliate_portal_enabled=True,
            affiliate_payout_submission_enabled=False,
        )
        self.engine = AffiliateEngine(self.flags)
        
        # Setup active affiliate
        app = self.engine.submit_application(
            {"applicant_email": "pilot_affiliate@example.test", "desired_affiliate_class": "STANDARD"},
            "k-pilot",
        )
        self.affiliate = self.engine.review_application(app["id"], approved=True, actor_role="AFFILIATE_OPERATOR")
        self.engine.accept_terms(self.affiliate.id, "v1.0", "chk-v1")
        self.engine.activate(self.affiliate.id, "v1.0")

        # Register Governed Pilot Rules
        self.rule_botanical = self.engine.add_rule(
            rule_code="RULE_BOTANICAL_25",
            rate="0.25",
            product_class="BOTANICAL_COLLECTION_25",
            precedence=4,
        )
        self.rule_infused = self.engine.add_rule(
            rule_code="RULE_INFUSED_25",
            rate="0.25",
            product_class="INFUSED_BASICS_25",
            precedence=4,
        )
        self.rule_legends = self.engine.add_rule(
            rule_code="RULE_LEGENDS_10",
            rate="0.10",
            product_class="LEGENDS_MEMBERSHIP_10",
            precedence=4,
        )

        # Attributed referral decision
        ref = self.engine.create_referral(self.affiliate.id, "LINK", T0)
        self.decision = self.engine.resolve_attribution("ORD-G8-TEST", [ref.id], at=T0 + timedelta(hours=1))

    def _make_event(self, order_id, line_items):
        return {
            "event_id": f"EVT-{order_id}",
            "order_id": order_id,
            "currency": "USD",
            "occurred_at": T0.isoformat(),
            "line_items": line_items,
        }

    def test_01_botanical_collection_25_percent(self):
        """Case 1: Botanical Collection resolves to exact 25% commission."""
        products = {
            "88": {
                "canonical_id": "ccc:book:wakenbake-lounge-cannabis-botanical-collection-volume-1",
                "product_id": "88",
                "affiliate_eligibility": "ELIGIBLE",
                "affiliate_commission_class": "BOTANICAL_COLLECTION_25",
            }
        }
        event = self._make_event("ORD-BOTANICAL", [
            {"line_id": "L1", "product_id": "88", "merchandise_total": "14.99", "discount": "0", "refunded": "0"}
        ])
        result = self.engine.process_revenue_event(event, self.decision, products)
        self.assertEqual("COMMISSION_CREATED", result["status"])
        
        commission = self.engine.commissions[result["commission_id"]]
        # 14.99 * 0.25 = 3.747500 -> exact decimal money quantum 3.747500
        expected_commission = Decimal("14.99") * Decimal("0.25")
        self.assertEqual(money(expected_commission), commission.amount)
        self.assertEqual(Decimal("3.747500"), commission.amount)

    def test_02_infused_basics_25_percent(self):
        """Case 2: Infused Basics resolves to exact 25% commission."""
        products = {
            "87": {
                "canonical_id": "ccc:book:infused-basics",
                "product_id": "87",
                "affiliate_eligibility": "ELIGIBLE",
                "affiliate_commission_class": "INFUSED_BASICS_25",
            }
        }
        event = self._make_event("ORD-INFUSED", [
            {"line_id": "L1", "product_id": "87", "merchandise_total": "40.00", "discount": "0", "refunded": "0"}
        ])
        result = self.engine.process_revenue_event(event, self.decision, products)
        self.assertEqual("COMMISSION_CREATED", result["status"])
        
        commission = self.engine.commissions[result["commission_id"]]
        # 40.00 * 0.25 = 10.000000
        self.assertEqual(Decimal("10.000000"), commission.amount)

    def test_03_legends_membership_10_percent(self):
        """Case 3: Legends Membership NFT resolves to exact 10% commission."""
        products = {
            "212": {
                "canonical_id": "wnb:nft:azurea-skye",
                "product_id": "212",
                "affiliate_eligibility": "ELIGIBLE",
                "affiliate_commission_class": "LEGENDS_MEMBERSHIP_10",
            }
        }
        event = self._make_event("ORD-LEGENDS", [
            {"line_id": "L1", "product_id": "212", "merchandise_total": "100.00", "discount": "0", "refunded": "0"}
        ])
        result = self.engine.process_revenue_event(event, self.decision, products)
        self.assertEqual("COMMISSION_CREATED", result["status"])
        
        commission = self.engine.commissions[result["commission_id"]]
        # 100.00 * 0.10 = 10.000000
        self.assertEqual(Decimal("10.000000"), commission.amount)

    def test_04_explicitly_excluded_product_zero_commission(self):
        """Case 4: Explicitly excluded product -> 0 commission (NO_COMMISSION), normal processing continues."""
        products = {
            "1047": {
                "canonical_id": "ccc:product:lounge-pass",
                "product_id": "1047",
                "affiliate_eligibility": "EXCLUDED",
                "affiliate_commission_class": None,
            }
        }
        event = self._make_event("ORD-EXCLUDED", [
            {"line_id": "L1", "product_id": "1047", "merchandise_total": "50.00", "discount": "0", "refunded": "0"}
        ])
        result = self.engine.process_revenue_event(event, self.decision, products)
        self.assertEqual("NO_COMMISSION", result["status"])
        self.assertIsNone(result["commission_id"])

    def test_05_unknown_unmapped_product_fail_closed(self):
        """Case 5: Unknown/unmapped product -> 0 commission / fail closed."""
        products = {}  # Product 9999 is completely unmapped
        event = self._make_event("ORD-UNMAPPED", [
            {"line_id": "L1", "product_id": "9999", "merchandise_total": "75.00", "discount": "0", "refunded": "0"}
        ])
        result = self.engine.process_revenue_event(event, self.decision, products)
        self.assertEqual("NO_COMMISSION", result["status"])
        self.assertIsNone(result["commission_id"])

    def test_06_eligible_product_missing_class_quarantines(self):
        """Case 6: Affiliate-eligible product with missing commission class -> STOP / quarantine."""
        products = {
            "888": {
                "canonical_id": "ccc:book:defective-item-no-class",
                "product_id": "888",
                "affiliate_eligibility": "ELIGIBLE",
                "affiliate_commission_class": None,
            }
        }
        event = self._make_event("ORD-MISSING-CLASS", [
            {"line_id": "L1", "product_id": "888", "merchandise_total": "20.00", "discount": "0", "refunded": "0"}
        ])
        result = self.engine.process_revenue_event(event, self.decision, products)
        self.assertEqual("QUARANTINED", result["status"])
        self.assertEqual("MISSING_COMMISSION_RULE", result["reason"])
        self.assertIsNone(result["commission_id"])
        self.assertEqual(1, len(self.engine.quarantine))

    def test_07_eligible_product_unknown_class_quarantines(self):
        """Case 7: Affiliate-eligible product with unknown commission class -> STOP / quarantine."""
        products = {
            "777": {
                "canonical_id": "ccc:book:unknown-class-item",
                "product_id": "777",
                "affiliate_eligibility": "ELIGIBLE",
                "affiliate_commission_class": "NON_EXISTENT_CLASS_99",
            }
        }
        event = self._make_event("ORD-UNKNOWN-CLASS", [
            {"line_id": "L1", "product_id": "777", "merchandise_total": "30.00", "discount": "0", "refunded": "0"}
        ])
        result = self.engine.process_revenue_event(event, self.decision, products)
        self.assertEqual("QUARANTINED", result["status"])
        self.assertEqual("MISSING_COMMISSION_RULE", result["reason"])
        self.assertIsNone(result["commission_id"])

    def test_08_rounding_boundary_proof_round_half_up(self):
        """Case 8: ROUND_HALF_UP boundary test proving governed rounding."""
        # 0.0000005 quantized to 6 decimals with ROUND_HALF_UP must round UP to 0.000001
        # In ROUND_HALF_EVEN, 0.0000005 would round DOWN to 0.000000 (even neighbor 0)
        val_to_round_up = Decimal("0.0000005")
        quantized = money(val_to_round_up)
        self.assertEqual(Decimal("0.000001"), quantized, "Must round UP on exact half (.5) boundary")

        # 0.0000015 with ROUND_HALF_UP must round UP to 0.000002 (In HALF_EVEN it also rounds to 2)
        # 0.0000025 with ROUND_HALF_UP must round UP to 0.000003 (In HALF_EVEN it rounds to 2)
        val_to_round_up_2 = Decimal("0.0000025")
        quantized_2 = money(val_to_round_up_2)
        self.assertEqual(Decimal("0.000003"), quantized_2, "Must round UP on .5 boundary (distinguishes HALF_UP from HALF_EVEN)")

    def test_09_no_float_use_in_calculation_path(self):
        """Case 9: Verify all calculation outputs, rates, and amounts are exact Decimal instances."""
        products = {
            "88": {
                "canonical_id": "ccc:book:wakenbake-lounge-cannabis-botanical-collection-volume-1",
                "product_id": "88",
                "affiliate_eligibility": "ELIGIBLE",
                "affiliate_commission_class": "BOTANICAL_COLLECTION_25",
            }
        }
        event = self._make_event("ORD-TYPE-CHECK", [
            {"line_id": "L1", "product_id": "88", "merchandise_total": "14.99", "discount": "0", "refunded": "0"}
        ])
        result = self.engine.process_revenue_event(event, self.decision, products)
        commission = self.engine.commissions[result["commission_id"]]

        self.assertIsInstance(commission.qualifying_revenue, Decimal)
        self.assertIsInstance(commission.amount, Decimal)
        self.assertIsInstance(commission.balance, Decimal)
        self.assertIsInstance(self.rule_botanical.rate, Decimal)
        self.assertNotIsInstance(commission.amount, float)
        self.assertNotIsInstance(self.rule_botanical.rate, float)


if __name__ == "__main__":
    unittest.main()
