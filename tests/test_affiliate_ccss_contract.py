from __future__ import annotations

import unittest

from src.budly_runtime.commercial_snapshot.contract import CommercialCatalogRecord


def record(**overrides):
    values = dict(
        canonical_id="ccc:product:test", sku="TEST", slug="test", name="Test", entity_type="PRODUCT",
        category=[], brand="CCC", status="ACTIVE", approval_status="OWNER_APPROVED", release_state="RELEASED",
        customer_purchasable=True, catalog_visibility="visible", stock_status="instock", price_usd=10.0,
        currency="USD", billing_model="ONE_TIME", short_summary="Test", description="Test", benefits=[], audience=[],
        customer_goals=[], eligibility_rules=[], exclusions=[], fulfillment_type="PHYSICAL_SHIPPING",
        fulfillment_platform="WOOCOMMERCE", canonical_url="https://example.test/p/test", checkout_url=None,
        booking_url=None, payment_plan_available=False, payment_plan_amount=None, payment_plan_url=None,
        payment_processor="WOOCOMMERCE", coupon_relationship=None, wix_plan_id=None, wordpress_page_id=1,
        source_authority="woocommerce", source_ids={}, source_updated_at=None, snapshot_generated_at="2026-01-01T00:00:00Z",
        catalog_version="test",
    )
    values.update(overrides)
    return CommercialCatalogRecord(**values)


class AffiliateCCSSContractTests(unittest.TestCase):
    def test_absence_fails_closed(self):
        self.assertEqual("MISSING_AFFILIATE_ELIGIBILITY", record().affiliate_policy()["reason"])

    def test_explicit_eligible(self):
        self.assertTrue(record(affiliate_eligibility="ELIGIBLE", affiliate_commission_class="PHYSICAL").affiliate_policy()["eligible"])

    def test_unknown_value_invalid(self):
        self.assertTrue(any("Unknown affiliate_eligibility" in e for e in record(affiliate_eligibility="MAYBE").validate()))

    def test_campaign_only_requires_restriction(self):
        self.assertIn("CAMPAIGN_ONLY requires affiliate_campaign_restriction", record(affiliate_eligibility="CAMPAIGN_ONLY").validate())

    def test_affiliate_configuration_changes_checksum(self):
        self.assertNotEqual(record().compute_checksum(), record(affiliate_eligibility="EXCLUDED").compute_checksum())


if __name__ == "__main__":
    unittest.main()
