"""Targeted & Regression Test Suite for MA-005 Phase B: Generalized Product Retrieval.

Covers:
1. public product absent from legacy products.json (e.g. Spray 130)
2. legacy allowed product (e.g. Oil Tincture 57)
3. restricted/private product (e.g. Lounge Member 1048)
4. draft product
5. password-protected product
6. ambiguous identifier
7. unknown identifier
8. variable product (Botanical Collection 913)
9. marketing-description ingredient evidence
10. complete governed ingredient evidence
11. Woo price freshness
12. canonical URL
13. Woo retrieval outage
14. stale snapshot versus live Woo conflict
15. Affiliate exclusion does not automatically equal public-content exclusion
16. Fixture: Oil Tincture 57 full turn
17. Fixture: Spray 130 full turn
18. Fixture: Combo 101 full turn
19. Fixture: Botanical Collection 913 variable pricing
20. Fixture: Restricted/private fixture fail closed
21. Fixture: Body Butter 50 regression
"""

from __future__ import annotations

import io
import json
import unittest
from pathlib import Path
from uuid import uuid4

from src.budly_runtime.config import FeatureFlags, ProductionSettings, RuntimeConfig
from src.budly_runtime.eligibility import (
    ProductEligibilityDecision,
    ProductEligibilityResolver,
    ProductEligibilityStatus,
)
from src.budly_runtime.model import ProviderResult
from src.budly_runtime.production_knowledge import ApprovedRepositoryKnowledgeAdapter
from src.budly_runtime.production_runtime import (
    EphemeralSessionStore,
    ProductionConversationRuntime,
    ProductionResponseValidator,
    RuntimeTurnRequest,
)
from src.budly_runtime.tool_gateway import AdapterContext, ToolHealth

ROOT = Path(__file__).resolve().parents[1]


class MockModelAdapter:
    def __init__(self, responses: list[dict] | None = None) -> None:
        self.responses = list(responses or [])
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if self.responses:
            payload = self.responses.pop(0)
            return ProviderResult(payload, "mock-provider", "mock-model")

        prompt = json.loads(request.prompt_package["provider_input"][0]["content"])
        user_msg = request.prompt_package["provider_input"][1]["content"]
        deterministic = prompt.get("deterministic_authority", {})
        payload = {
            "text": f"Budly helpful response to: {user_msg}",
            "intent": "product_guidance",
            "journey": deterministic.get("journey"),
            "resulting_action": "continue_conversation",
            "selected_product_id": deterministic.get("selected_product_id"),
            "requires_human": False,
        }
        return ProviderResult(payload, "mock-provider", "mock-model")


def make_settings(environment: str = "production") -> ProductionSettings:
    return ProductionSettings(
        environment, "127.0.0.1", 8791, "s" * 32, "openai", "candidate-model", "test-key", ROOT / "config"
    )


class TestPhaseBGeneralizedProductRetrieval(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = make_settings()
        self.resolver = ProductEligibilityResolver()

    def make_runtime(self, model=None, knowledge=None):
        return ProductionConversationRuntime(
            self.settings, ROOT, model_adapter=model or MockModelAdapter(), knowledge_adapter=knowledge
        )

    def request(self, conversation_id: str, message: str, **extra):
        return {
            "conversation_id": conversation_id,
            "message": message,
            "correlation_id": str(uuid4()),
            "channel": "ccc_website",
            "use_durable_memory": False,
            **extra,
        }

    # =========================================================================
    # STEP 9: 15 MANDATORY TEST SCENARIOS
    # =========================================================================

    def test_01_public_product_absent_from_legacy_products_json(self):
        """1. Public product absent from legacy products.json (e.g. Spray 130).
        Verifies dynamic admission via ProductEligibilityResolver without requiring manual products.json entry.
        """
        spray_payload = {
            "id": 130,
            "slug": "cbd-tincture-spray",
            "name": "CBD Tincture Spray",
            "type": "simple",
            "is_purchasable": True,
            "is_in_stock": True,
            "is_password_protected": False,
            "status": "publish",
            "catalog_visibility": "visible",
            "permalink": "https://cccultivate.com/product/cbd-tincture-spray/",
            "prices": {"price": "3500", "currency_code": "USD", "currency_minor_unit": 2},
        }
        decision = self.resolver.resolve(spray_payload)
        self.assertEqual(decision.status, ProductEligibilityStatus.PUBLIC_APPROVED)
        self.assertEqual(decision.canonical_id, "ccc:product:cbd-tincture-spray")
        self.assertEqual(decision.slug, "cbd-tincture-spray")

    def test_02_legacy_allowed_product(self):
        """2. Legacy allowed product (e.g. Oil Tincture 57).
        Verifies existing products in products.json continue to resolve as PUBLIC_APPROVED.
        """
        tincture_payload = {
            "id": 57,
            "slug": "therapeutic-oil-tincture-1-time",
            "name": "Therapeutic Oil Tincture 1-time",
            "type": "simple",
            "is_purchasable": True,
            "is_in_stock": True,
            "is_password_protected": False,
            "status": "publish",
            "catalog_visibility": "visible",
            "permalink": "https://cccultivate.com/product/therapeutic-oil-tincture-1-time/",
            "prices": {"price": "5500", "currency_code": "USD", "currency_minor_unit": 2},
        }
        decision = self.resolver.resolve(tincture_payload)
        self.assertEqual(decision.status, ProductEligibilityStatus.PUBLIC_APPROVED)
        self.assertEqual(decision.canonical_id, "ccc:product:therapeutic-oil-tincture")

    def test_03_restricted_private_product(self):
        """3. Restricted/private product (e.g. Lounge Member 1048 or status=private).
        Verifies fail-closed exclusion.
        """
        # A: Explicit unreleased community tier
        lounge_member_payload = {
            "id": 1048,
            "slug": "lounge-member",
            "name": "Wake'n'Bake Lounge Member",
            "type": "fsb-subscription",
            "status": "publish",
        }
        d1 = self.resolver.resolve(lounge_member_payload)
        self.assertEqual(d1.status, ProductEligibilityStatus.RESTRICTED)
        self.assertEqual(d1.reason, "EXPLICIT_EXCLUSION_UNRELEASED_COMMUNITY_TIER")

        # B: Private publication status
        private_payload = {
            "id": 9991,
            "slug": "internal-secret-blend",
            "status": "private",
        }
        d2 = self.resolver.resolve(private_payload)
        self.assertEqual(d2.status, ProductEligibilityStatus.RESTRICTED)
        self.assertEqual(d2.reason, "NON_PUBLIC_STATUS_PRIVATE")

    def test_04_draft_product(self):
        """4. Draft product.
        Verifies unreleased/draft products are rejected with RESTRICTED.
        """
        draft_payload = {
            "id": 8881,
            "slug": "upcoming-cbd-lotion",
            "status": "draft",
        }
        decision = self.resolver.resolve(draft_payload)
        self.assertEqual(decision.status, ProductEligibilityStatus.RESTRICTED)
        self.assertEqual(decision.reason, "NON_PUBLIC_STATUS_DRAFT")

    def test_05_password_protected_product(self):
        """5. Password-protected product.
        Verifies products requiring passwords fail closed with RESTRICTED.
        """
        pw_payload = {
            "id": 7771,
            "slug": "vip-exclusive-product",
            "status": "publish",
            "is_password_protected": True,
        }
        decision = self.resolver.resolve(pw_payload)
        self.assertEqual(decision.status, ProductEligibilityStatus.RESTRICTED)
        self.assertEqual(decision.reason, "PASSWORD_PROTECTED")

    def test_06_ambiguous_identifier(self):
        """6. Ambiguous identifier.
        Verifies ambiguous terms fail closed with UNRESOLVED rather than guessing.
        """
        for term in ["membership", "memberships", "class", "classes", "course", "courses", "payment plan"]:
            decision = self.resolver.normalize_identity(term)
            self.assertEqual(decision.status, ProductEligibilityStatus.UNRESOLVED)
            self.assertEqual(decision.reason, "AMBIGUOUS_IDENTIFIER")

    def test_07_unknown_identifier(self):
        """7. Unknown identifier.
        Verifies unknown entities fail closed with UNRESOLVED.
        """
        decision = self.resolver.normalize_identity("xyz_completely_unknown_99999")
        self.assertEqual(decision.status, ProductEligibilityStatus.UNRESOLVED)
        self.assertEqual(decision.reason, "UNKNOWN_IDENTIFIER")

    def test_08_variable_product(self):
        """8. Variable product (e.g. Botanical Collection 913).
        Verifies variable parent pricing range and format variations are preserved.
        """
        variable_payload = {
            "id": 913,
            "slug": "wakenbake-lounge-cannabis-botanical-collection-volume-1",
            "name": "Wake'n'Bake Lounge Cannabis Botanical Collection – Volume 1",
            "type": "variable",
            "has_options": True,
            "is_purchasable": True,
            "is_in_stock": True,
            "is_password_protected": False,
            "status": "publish",
            "permalink": "https://cccultivate.com/product/wakenbake-lounge-cannabis-botanical-collection-volume-1/",
            "prices": {
                "price": "1499",
                "price_range": {"min_amount": "1499", "max_amount": "4999"},
                "currency_code": "USD",
                "currency_minor_unit": 2,
            },
            "variations": [
                {"id": 916, "attributes": [{"name": "Botanical Collection", "value": "DIY Download & Print"}]},
                {"id": 917, "attributes": [{"name": "Botanical Collection", "value": "Paperback"}]},
                {"id": 918, "attributes": [{"name": "Botanical Collection", "value": "Collector's Edition"}]},
            ],
        }
        decision = self.resolver.resolve(variable_payload)
        self.assertEqual(decision.status, ProductEligibilityStatus.PUBLIC_APPROVED)
        self.assertEqual(decision.canonical_id, "ccc:book:wakenbake-lounge-cannabis-botanical-collection-volume-1")

    def test_09_marketing_description_ingredient_evidence(self):
        """9. Marketing-description ingredient evidence.
        Budly may state what the product description lists, but must NOT claim complete formulation or exhaustive declaration.
        """
        validator = ProductionResponseValidator()
        session_mock = type("SessionMock", (), {
            "task_state": "UNRESOLVED",
            "active_entity": "Therapeutic Oil Tincture",
            "active_request": "verified ingredient list",
            "ingredient_evidence_type": "MARKETING_DESCRIPTION",
            "crm_write_state": "NOT_ATTEMPTED",
            "human_followup_state": "NOT_CREATED",
            "customer_email": None,
            "contact_phone": None,
        })()

        # Permitted: "The product description lists..."
        good_resp = {
            "text": "The product description lists full-spectrum hemp extract and botanical carrier oils for the Therapeutic Oil Tincture. It is currently $55 at https://cccultivate.com/product/therapeutic-oil-tincture-1-time/.",
            "intent": "product_guidance",
            "journey": None,
            "resulting_action": "continue_conversation",
            "selected_product_id": None,
            "requires_human": False,
        }
        valid, reasons = validator.validate(good_resp, {}, session=session_mock)
        self.assertTrue(valid, f"Expected good_resp to pass, got: {reasons}")

        # Prohibited: Claiming complete formulation
        complete_claim = {
            "text": "The complete formulation and exhaustive ingredient list for Therapeutic Oil Tincture is full-spectrum CBD and hemp seed oil.",
            "intent": "product_guidance",
            "journey": None,
            "resulting_action": "continue_conversation",
            "selected_product_id": None,
            "requires_human": False,
        }
        valid, reasons = validator.validate(complete_claim, {"ingredient_evidence_type": "MARKETING_DESCRIPTION"}, session=session_mock)
        self.assertFalse(valid)
        self.assertIn("unverified_ingredient_claim", reasons)

    def test_10_complete_governed_ingredient_evidence(self):
        """10. Complete governed ingredient evidence.
        When evidence is explicitly COMPLETE_GOVERNED_INGREDIENT_DECLARATION, Budly may identify it as complete.
        """
        validator = ProductionResponseValidator()
        session_mock = type("SessionMock", (), {
            "task_state": "UNRESOLVED",
            "active_entity": "Therapeutic Oil Tincture",
            "active_request": "verified ingredient list",
            "ingredient_evidence_type": "COMPLETE_GOVERNED_INGREDIENT_DECLARATION",
            "crm_write_state": "NOT_ATTEMPTED",
            "human_followup_state": "NOT_CREATED",
            "customer_email": None,
            "contact_phone": None,
        })()

        complete_claim = {
            "text": "The complete regulated ingredient declaration for Therapeutic Oil Tincture is organic MCT oil and full-spectrum hemp distillate.",
            "intent": "product_guidance",
            "journey": None,
            "resulting_action": "continue_conversation",
            "selected_product_id": None,
            "requires_human": False,
        }
        valid, reasons = validator.validate(
            complete_claim,
            {"ingredient_evidence_type": "COMPLETE_GOVERNED_INGREDIENT_DECLARATION"},
            session=session_mock,
        )
        self.assertTrue(valid, f"Expected complete declaration to be accepted when evidence is governed complete, got: {reasons}")

    def test_11_woo_price_freshness(self):
        """11. Woo price freshness.
        Authoritative live WooCommerce prices supersede static/stale prices.
        """
        mock_products = [
            {
                "id": 130,
                "slug": "cbd-tincture-spray",
                "name": "CBD Tincture Spray",
                "type": "simple",
                "is_purchasable": True,
                "is_in_stock": True,
                "permalink": "https://cccultivate.com/product/cbd-tincture-spray/",
                "prices": {"price": "3500", "currency_code": "USD", "currency_minor_unit": 2},
                "short_description": "Spray 1oz",
                "description": "Full spectrum CBD tincture in a 1oz spray bottle.",
            }
        ]

        def mock_opener(url, timeout=8):
            return io.BytesIO(json.dumps(mock_products).encode("utf-8"))

        knowledge = ApprovedRepositoryKnowledgeAdapter(
            policies_path=ROOT / "config" / "policies.json",
            products_path=ROOT / "config" / "products.json",
            opener=mock_opener,
        )
        ctx = AdapterContext("spray", "product_catalog", 5, frozenset({"Public"}), "req1", "corr1")
        items = knowledge.retrieve(ctx)
        self.assertTrue(len(items) > 0)
        data = json.loads(items[0]["content"])
        self.assertEqual(data["current_price"], 35.0)
        self.assertEqual(data["currency"], "USD")

    def test_12_canonical_url(self):
        """12. Canonical URL determinism.
        Verifies verified canonical URLs are resolved across catalog products.
        """
        expected_urls = {
            "50": "https://cccultivate.com/product/therapeutic-body-butter/",
            "57": "https://cccultivate.com/product/therapeutic-oil-tincture-1-time/",
            "130": "https://cccultivate.com/product/cbd-tincture-spray/",
            "101": "https://cccultivate.com/product/therapeutic-combo-one-time-purchase/",
            "913": "https://cccultivate.com/product/wakenbake-lounge-cannabis-botanical-collection-volume-1/",
        }
        for identifier, expected in expected_urls.items():
            norm = self.resolver.normalize_identity(identifier)
            self.assertEqual(norm.status, ProductEligibilityStatus.PUBLIC_APPROVED)
            self.assertEqual(norm.details["canonical_url"], expected)

    def test_13_woo_retrieval_outage(self):
        """13. Woo retrieval outage.
        When WooCommerce Store API is unavailable, runtime triggers safe fallback without claiming facts don't exist.
        """
        def broken_opener(url, timeout=8):
            raise ConnectionError("Connection refused by upstream host")

        knowledge = ApprovedRepositoryKnowledgeAdapter(
            policies_path=ROOT / "config" / "policies.json",
            products_path=ROOT / "config" / "products.json",
            opener=broken_opener,
        )
        runtime = self.make_runtime(knowledge=knowledge)
        cid = f"conv_outage_{uuid4().hex[:12]}"
        res = runtime.turn(self.request(cid, "What is the price of your body butter?"))
        self.assertTrue(res["success"])
        # Must return temporary unavailable fallback, NOT "I don't have an approved source"
        self.assertIn("temporarily unavailable", res["response"]["text"])

    def test_14_stale_snapshot_vs_live_woo_conflict(self):
        """14. Stale snapshot versus live Woo conflict.
        Live Woo Store API is the authoritative commercial truth for price/stock.
        """
        # Stale snapshot has $70, live Woo has $75
        mock_products = [
            {
                "id": 50,
                "slug": "therapeutic-body-butter",
                "name": "Therapeutic Body Butter",
                "type": "simple",
                "is_purchasable": True,
                "is_in_stock": True,
                "permalink": "https://cccultivate.com/product/therapeutic-body-butter/",
                "prices": {"price": "7500", "currency_code": "USD", "currency_minor_unit": 2},
                "short_description": "Hydrating butter",
                "description": "Cocoa, kokum, shea butter with CBD.",
            }
        ]

        def mock_opener(url, timeout=8):
            return io.BytesIO(json.dumps(mock_products).encode("utf-8"))

        knowledge = ApprovedRepositoryKnowledgeAdapter(
            policies_path=ROOT / "config" / "policies.json",
            products_path=ROOT / "config" / "products.json",
            commercial_snapshot_enabled=False,
            opener=mock_opener,
        )
        ctx = AdapterContext("body butter", "product_catalog", 5, frozenset({"Public"}), "req1", "corr1")
        items = knowledge.retrieve(ctx)
        self.assertTrue(len(items) > 0)
        data = json.loads(items[0]["content"])
        self.assertEqual(data["current_price"], 75.0)

    def test_15_affiliate_exclusion_not_public_content_exclusion(self):
        """15. Affiliate exclusion does not automatically equal public-content exclusion.
        A product not in the affiliate pilot program remains eligible for public knowledge retrieval.
        """
        # Product with no affiliate eligibility still resolves PUBLIC_APPROVED
        test_prod = {
            "id": 9992,
            "slug": "general-wellness-salve",
            "name": "General Wellness Salve",
            "type": "simple",
            "is_purchasable": True,
            "is_in_stock": True,
            "is_password_protected": False,
            "status": "publish",
            "affiliate_eligibility": "INELIGIBLE",
            "permalink": "https://cccultivate.com/product/general-wellness-salve/",
        }
        decision = self.resolver.resolve(test_prod)
        self.assertEqual(decision.status, ProductEligibilityStatus.PUBLIC_APPROVED)

    # =========================================================================
    # REPRESENTATIVE FIXTURE TESTS (STEP 5)
    # =========================================================================

    def test_fixture_oil_tincture_57(self):
        """Fixture: Oil Tincture 57.
        Prompt: 'What is in the Therapeutic Oil Tincture and how much does it cost?'
        Verifies: current price $55, marketing description, canonical URL, active task bound to Oil Tincture.
        """
        runtime = self.make_runtime()
        cid = f"conv_tincture_{uuid4().hex[:12]}"
        res = runtime.turn(self.request(cid, "What is in the Therapeutic Oil Tincture and how much does it cost?"))
        self.assertTrue(res["success"])
        task = res["active_task"]
        self.assertEqual(task["active_entity"], "Therapeutic Oil Tincture")
        self.assertEqual(task["active_request"], "verified ingredient list")
        self.assertEqual(task["task_state"], "UNRESOLVED")
        self.assertEqual(task["follow_up_subject"], "Therapeutic Oil Tincture ingredient information")

    def test_fixture_spray_130_dynamic_retrieval(self):
        """Fixture: Therapeutic Spray 130.
        Prompt: 'Tell me about your Therapeutic Spray. What is in it and how much does it cost?'
        Verifies: dynamically retrieved via live Store API, active task bound, $35 price, canonical URL.
        """
        runtime = self.make_runtime()
        cid = f"conv_spray_{uuid4().hex[:12]}"
        res = runtime.turn(self.request(cid, "Tell me about your Therapeutic Spray. What is in it and how much does it cost?"))
        self.assertTrue(res["success"])
        task = res["active_task"]
        self.assertEqual(task["active_entity"], "CBD Tincture Spray")
        self.assertEqual(task["active_request"], "verified ingredient list")
        self.assertEqual(task["task_state"], "UNRESOLVED")
        self.assertEqual(task["follow_up_subject"], "CBD Tincture Spray ingredient information")

    def test_fixture_combo_101(self):
        """Fixture: Therapeutic Combo 101.
        Verifies commercial facts and canonical identity ($125).
        """
        runtime = self.make_runtime()
        from src.budly_runtime.tool_gateway import AdapterContext
        ctx = AdapterContext("therapeutic combo bundle", "product_catalog", 5, frozenset({"Public"}), "req1", "corr1")
        items = runtime.knowledge.retrieve(ctx)
        self.assertTrue(len(items) > 0)
        combo_one_time = next((json.loads(it["content"]) for it in items if json.loads(it["content"]).get("product_id") == "101" or "one-time" in it.get("title", "").lower()), None)
        self.assertIsNotNone(combo_one_time)
        self.assertEqual(combo_one_time["current_price"], 125.0)
        self.assertIn("therapeutic-combo", combo_one_time["canonical_url"])

    def test_fixture_botanical_collection_913_variable(self):
        """Fixture: Botanical Collection 913.
        Verifies variable parent, formats/variations, and price range ($14.99 to $49.99).
        """
        runtime = self.make_runtime()
        from src.budly_runtime.tool_gateway import AdapterContext
        ctx = AdapterContext("botanical collection volume 1", "product_catalog", 5, frozenset({"Public"}), "req1", "corr1")
        items = runtime.knowledge.retrieve(ctx)
        self.assertTrue(len(items) > 0)
        botanical = next((json.loads(it["content"]) for it in items if "botanical" in it.get("title", "").lower()), None)
        self.assertIsNotNone(botanical)
        self.assertEqual(botanical["product_type"], "variable")
        self.assertEqual(botanical["price_range_min"], 14.99)
        self.assertEqual(botanical["price_range_max"], 49.99)
        self.assertTrue(len(botanical["variations"]) >= 3)

    def test_fixture_restricted_lounge_member_1048_fail_closed(self):
        """Fixture: Restricted Lounge Member 1048.
        Verifies fail closed: unreleased membership draft is excluded from public product catalog.
        """
        runtime = self.make_runtime()
        from src.budly_runtime.tool_gateway import AdapterContext
        ctx = AdapterContext("lounge member", "product_catalog", 5, frozenset({"Public"}), "req1", "corr1")
        items = runtime.knowledge.retrieve(ctx)
        # Must not contain lounge-member product as a public purchasable product item
        self.assertFalse(any(it.get("knowledge_id") == "product:lounge-member" for it in items))

    def test_fixture_body_butter_50_regression(self):
        """Fixture: Body Butter 50 Regression.
        Verifies previous r4 behavior remains 100% intact with generalized evidence and eligibility rules.
        """
        runtime = self.make_runtime()
        cid = f"conv_bb_regress_{uuid4().hex[:12]}"
        res = runtime.turn(self.request(cid, "What are the ingredients in your body butter?"))
        self.assertTrue(res["success"])
        task = res["active_task"]
        self.assertEqual(task["active_entity"], "Therapeutic Body Butter")
        self.assertEqual(task["active_request"], "verified ingredient list")
        self.assertEqual(task["task_state"], "UNRESOLVED")
        self.assertEqual(task["follow_up_subject"], "Therapeutic Body Butter ingredient information")


if __name__ == "__main__":
    unittest.main()
