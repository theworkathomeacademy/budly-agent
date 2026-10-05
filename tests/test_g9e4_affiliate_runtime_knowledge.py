from __future__ import annotations

import io
import json
import unittest
from pathlib import Path

from src.budly_runtime.production_knowledge import ApprovedRepositoryKnowledgeAdapter
from src.budly_runtime.production_runtime import ProductionConversationRuntime
from src.budly_runtime.tool_gateway import AdapterContext

ROOT = Path(__file__).resolve().parents[1]

MANDATED_QUESTIONS = [
    "Do you have an affiliate program?",
    "What is your affiliate program?",
    "Who can become an affiliate?",
    "Are applications open?",
    "How much can affiliates earn?",
    "What products can I promote?",
    "Do I need a certain number of followers?",
    "Do affiliates earn recurring commissions?",
    "How do payouts work?",
    "What can you help affiliates with?",
]


class G9E4AffiliateRuntimeKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.policies_path = ROOT / "config" / "policies.json"
        self.products_path = ROOT / "config" / "products.json"
        self.education_path = ROOT / "config" / "budly_runtime" / "education-corpus-v0.1.json"
        self.commercial_path = ROOT / "config" / "budly_runtime" / "commercial-knowledge-v1.0.json"
        self.affiliate_path = ROOT / "config" / "budly_runtime" / "affiliate-public-knowledge-g9d-v1.json"

        self.adapter = ApprovedRepositoryKnowledgeAdapter(
            policies_path=self.policies_path,
            products_path=self.products_path,
            education_path=self.education_path,
            commercial_path=self.commercial_path,
            affiliate_path=self.affiliate_path,
        )

    def context(self, query: str, domain: str = "affiliate_program") -> AdapterContext:
        return AdapterContext(query, domain, 5, ("Public",), "test_corr", "test_actor", "website_chat")

    def test_all_10_questions_route_to_affiliate_domain(self):
        for q in MANDATED_QUESTIONS:
            domain = ProductionConversationRuntime._knowledge_domain(q)
            self.assertEqual(
                domain,
                "affiliate_program",
                f"Question '{q}' routed to '{domain}' instead of 'affiliate_program'",
            )

    def test_all_10_questions_retrieve_approved_affiliate_knowledge(self):
        for q in MANDATED_QUESTIONS:
            domain = ProductionConversationRuntime._knowledge_domain(q)
            results = self.adapter.retrieve(self.context(q, domain))
            self.assertGreater(
                len(results),
                0,
                f"Question '{q}' returned 0 knowledge results",
            )
            # Must contain affiliate-related knowledge
            has_affiliate = any("affiliate" in item["title"].lower() or "affiliate" in item["content"].lower() for item in results)
            self.assertTrue(
                has_affiliate,
                f"Question '{q}' did not retrieve any affiliate records in {results}",
            )

    def test_approved_links_prioritizes_public_affiliate_page(self):
        for q in MANDATED_QUESTIONS:
            domain = ProductionConversationRuntime._knowledge_domain(q)
            results = self.adapter.retrieve(self.context(q, domain))
            links = ProductionConversationRuntime._approved_links(results, q)
            urls = [link["url"] for link in links]
            self.assertIn(
                "https://cccultivate.com/affiliate/",
                urls,
                f"Question '{q}' failed to produce https://cccultivate.com/affiliate/ in approved links: {urls}",
            )

    def test_governed_facts_coverage(self):
        # 1. Pilot Status & Closed applications
        q_open = "Are applications open?"
        results_open = self.adapter.retrieve(self.context(q_open, "affiliate_program"))
        content_open = " ".join(item["content"] for item in results_open)
        self.assertTrue("private five-person pilot" in content_open.lower() or "private pilot" in content_open.lower())
        self.assertTrue("closed" in content_open.lower())
        self.assertTrue("approval" in content_open.lower())

        # 2. No follower minimum
        q_followers = "Do I need a certain number of followers?"
        results_followers = self.adapter.retrieve(self.context(q_followers, "affiliate_program"))
        content_followers = " ".join(item["content"] for item in results_followers)
        self.assertTrue("no follower minimum" in content_followers.lower() or "no follower threshold" in content_followers.lower())

        # 3. Commission classes
        q_earn = "How much can affiliates earn?"
        results_earn = self.adapter.retrieve(self.context(q_earn, "affiliate_program"))
        content_earn = " ".join(item["content"] for item in results_earn)
        self.assertIn("30%", content_earn)
        self.assertIn("25%", content_earn)
        self.assertIn("15%", content_earn)
        self.assertIn("10%", content_earn)

        # 4. Recurring subscriptions
        q_sub = "Do affiliates earn recurring commissions?"
        results_sub = self.adapter.retrieve(self.context(q_sub, "affiliate_program"))
        content_sub = " ".join(item["content"] for item in results_sub)
        self.assertIn("30%", content_sub)
        self.assertIn("5%", content_sub)

        # 5. Payouts & threshold
        q_payout = "How do payouts work?"
        results_payout = self.adapter.retrieve(self.context(q_payout, "affiliate_program"))
        content_payout = " ".join(item["content"] for item in results_payout)
        self.assertIn("$50", content_payout)
        self.assertTrue("30-day" in content_payout or "refund" in content_payout)
        self.assertTrue("authorization" in content_payout.lower() or "owner" in content_payout.lower())

        # 6. Budly boundaries
        q_help = "What can you help affiliates with?"
        results_help = self.adapter.retrieve(self.context(q_help, "affiliate_program"))
        content_help = " ".join(item["content"] for item in results_help)
        self.assertTrue("cannot approve" in content_help.lower())
        self.assertTrue("modify commission rates" in content_help.lower() or "modify" in content_help.lower())
        self.assertTrue("authorize payouts" in content_help.lower() or "payout" in content_help.lower())

    def test_authoritative_g9_pilot_cohort(self):
        cohort_path = ROOT / "config" / "affiliate" / "pilot_cohort.json"
        self.assertTrue(cohort_path.exists(), "pilot_cohort.json must exist in config/affiliate/")
        cohort = json.loads(cohort_path.read_text(encoding="utf-8"))
        self.assertEqual(cohort.get("real_affiliates_count"), 0)
        self.assertEqual(cohort.get("real_outreach_count"), 0)

        candidates = cohort.get("candidates", [])
        self.assertEqual(len(candidates), 5)

        expected = {
            "@thecannabiscutie": ("Tammy Pettigrew", "tammy@thecannabiscutie.com"),
            "@sanzidaah": ("Sanzida Haider", "sanzidaahcollab@gmail.com"),
            "@celestefitt": ("Celeste", "Celestrefitt@tsptalent.co"),
            "@saleemarrm1": ("Saleema Mansur", "UNRESOLVED"),
            "@avi.babyyyy": ("Avi Rossum", "UNRESOLVED"),
        }

        stale_handles = [
            "@thestonedhousewife",
            "@cannabissomatics",
            "@chefcheri",
            "@loudgirlgoodies",
            "@iamcarlag",
        ]

        found_handles = set()
        for c in candidates:
            h = c["handle"]
            self.assertIn(h, expected, f"Unexpected candidate handle: {h}")
            expected_name, expected_email = expected[h]
            self.assertEqual(c["name"], expected_name)
            self.assertEqual(c["email"], expected_email)
            self.assertNotIn(h, stale_handles)
            found_handles.add(h)

        self.assertEqual(found_handles, set(expected.keys()))

        # Verify AdminPage.php does not contain stale handles
        admin_php = (ROOT / "deploy" / "wordpress" / "budly-sales-agent" / "includes" / "Affiliate" / "AdminPage.php").read_text(encoding="utf-8")
        for sh in stale_handles:
            self.assertNotIn(sh, admin_php, f"AdminPage.php must not contain stale handle {sh}")
        for fabricated_id in ["AFF-000001", "AFF-000002", "AFF-000003", "AFF-000004", "AFF-000005"]:
            self.assertNotIn(f"<td>{fabricated_id}</td>", admin_php)
            self.assertNotIn(f"<strong>{fabricated_id}</strong>", admin_php)


if __name__ == "__main__":
    unittest.main()

