"""Tests for Attribution Link Standard."""

import sys
import unittest
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parents[1]
if str(PKG_DIR) not in sys.path:
    sys.path.insert(0, str(PKG_DIR))

from attribution import AttributionContext, AttributionStandard


class TestAttributionStandard(unittest.TestCase):
    def test_build_and_parse_attribution_url(self):
        ctx = AttributionContext(
            source="social",
            platform="instagram",
            content_id="IG-20260906-0002",
            campaign_id="STS-PILOT-001",
            cta_id="CTA-ASK-BUDLY-001",
            product_or_topic="BOTANICAL_COLLECTION",
            published_post_id="POST-88123",
        )
        url = AttributionStandard.build_url("https://www.wakenbakelounge.com/ask-budly", ctx)
        self.assertIn("source=social", url)
        self.assertIn("platform=instagram", url)
        self.assertIn("content_id=IG-20260906-0002", url)
        self.assertIn("campaign_id=STS-PILOT-001", url)
        self.assertIn("cta_id=CTA-ASK-BUDLY-001", url)

        landing_route, parsed_ctx = AttributionStandard.parse_url(url)
        self.assertEqual(landing_route, "https://www.wakenbakelounge.com/ask-budly")
        self.assertEqual(parsed_ctx.source, "social")
        self.assertEqual(parsed_ctx.platform, "instagram")
        self.assertEqual(parsed_ctx.content_id, "IG-20260906-0002")
        self.assertEqual(parsed_ctx.campaign_id, "STS-PILOT-001")
        self.assertEqual(parsed_ctx.cta_id, "CTA-ASK-BUDLY-001")
        self.assertEqual(parsed_ctx.product_or_topic, "BOTANICAL_COLLECTION")
        self.assertEqual(parsed_ctx.published_post_id, "POST-88123")

    def test_pii_filtering_in_attribution(self):
        ctx_with_email = AttributionContext(
            source="social",
            platform="instagram",
            content_id="user@example.com",
            campaign_id="STS-PILOT-001",
            cta_id="CTA-ASK-BUDLY-001",
        )
        with self.assertRaises(ValueError):
            ctx_with_email.validate()

        # Parameter cleaner strips PII
        cleaned = AttributionStandard.clean_param("test.user@gmail.com")
        self.assertEqual(cleaned, "")

    def test_direct_attribution_fallback(self):
        ctx = AttributionContext.direct()
        self.assertEqual(ctx.source, "direct")
        self.assertEqual(ctx.platform, "web")
        self.assertEqual(ctx.cta_id, "CTA-ASK-BUDLY-001")


if __name__ == "__main__":
    unittest.main()
