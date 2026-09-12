from __future__ import annotations

import io
import json
import unittest
from pathlib import Path

from src.budly_runtime.production_knowledge import ApprovedRepositoryKnowledgeAdapter
from src.budly_runtime.production_runtime import ProductionConversationRuntime
from src.budly_runtime.tool_gateway import AdapterContext

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "deploy/wordpress/budly-sales-agent"


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def product_payload(*, active=True, slug="therapeutic-body-butter"):
    return [{
        "id": 50, "slug": slug, "name": "Therapeutic Body Butter 1-time",
        "permalink": "https://cccultivate.com/product/therapeutic-body-butter/",
        "short_description": "<p>A topical body butter.</p>",
        "categories": [{"name": "CBD"}, {"name": "Selfcare"}],
        "is_purchasable": active, "is_in_stock": active,
        "prices": {"price": "7500", "currency_minor_unit": 2, "currency_code": "USD"},
    }]


class WebKnowledgeTests(unittest.TestCase):
    def adapter(self, payload=None):
        raw = json.dumps(product_payload() if payload is None else payload).encode()
        return ApprovedRepositoryKnowledgeAdapter(
            ROOT / "config/policies.json", ROOT / "config/products.json",
            ROOT / "config/budly_runtime/education-corpus-v0.1.json",
            ROOT / "config/budly_runtime/commercial-knowledge-v1.0.json",
            opener=lambda *_args, **_kwargs: Response(raw),
        )

    def context(self, query, domain="product_catalog"):
        return AdapterContext(query, domain, 5, ("Public",), "test", "test", "website_chat")

    def test_product_lookup_uses_live_woocommerce_truth(self):
        result = self.adapter().retrieve(self.context("Do you carry creams?"))
        self.assertEqual(len(result), 1)
        content = json.loads(result[0]["content"])
        self.assertEqual(content["current_price"], 75.0)
        self.assertEqual(content["availability"], "in_stock")
        self.assertEqual(content["canonical_url"], "https://cccultivate.com/product/therapeutic-body-butter/")

    def test_unavailable_and_unapproved_products_are_excluded(self):
        self.assertEqual(self.adapter(product_payload(active=False)).retrieve(self.context("cream")), [])
        self.assertEqual(self.adapter(product_payload(slug="invented-cream")).retrieve(self.context("cream")), [])

    def test_policy_membership_affiliate_and_education_retrieval(self):
        adapter = self.adapter()
        cases = [
            ("return policy", "customer_policy", "cccultivate.com/customer-policies/"),
            ("membership benefits", "membership", "cccultivate.com/legends/"),
            ("affiliate application", "affiliate_program", "wakenbakelounge/affiliates"),
            ("learn about CBD", "educational", "cultivation-resources"),
        ]
        for query, domain, expected in cases:
            results = adapter.retrieve(self.context(query, domain))
            self.assertTrue(any(expected in item["content"] for item in results), (query, results))

    def test_canonical_links_are_allowlisted_and_unavailable_links_drop(self):
        good = [{"content": json.dumps({"canonical_url":"https://cccultivate.com/shop/","link_label":"View catalog"})}]
        bad = [{"content": json.dumps({"canonical_url":"https://example.invalid/phish"})}, {"content":"not-json"}]
        self.assertEqual(ProductionConversationRuntime._approved_links(good)[0]["url"], "https://cccultivate.com/shop/")
        self.assertEqual(ProductionConversationRuntime._approved_links(bad), [])

    def test_registry_freshness_and_approval(self):
        registry = json.loads((ROOT / "config/budly_runtime/commercial-knowledge-v1.0.json").read_text(encoding="utf-8"))
        self.assertEqual(registry["approval_status"], "owner_approved")
        for item in registry["resources"]:
            self.assertEqual(item["approval_status"], "approved")
            self.assertEqual(item["active_status"], "active")
            self.assertRegex(item["last_verified_at"], r"^\d{4}-\d{2}-\d{2}")

    def test_customer_message_contrast_and_mobile_contract(self):
        css = (PLUGIN / "assets/budly-sales.css").read_text(encoding="utf-8")
        self.assertIn(".budly-experience .budly-message.budly-user", css)
        self.assertIn("background:#174b29!important", css)
        self.assertIn("color:#fff!important", css)
        self.assertIn("opacity:1!important", css)
        self.assertIn("@media(max-width:760px)", css)

    def test_frontend_renders_only_approved_safe_links(self):
        js = (PLUGIN / "assets/budly-sales.js").read_text(encoding="utf-8")
        proxy = (PLUGIN / "includes/Runtime/ConversationProxy.php").read_text(encoding="utf-8")
        for token in ("approvedLinkHosts", "noopener noreferrer", "renderApprovedLinks"):
            self.assertIn(token, js)
        self.assertIn("dmckenzies.wixsite.com", proxy)
        self.assertIn("count($response['links']) > 3", proxy)


    def test_cbd_oil_query_matches_only_oils_and_excludes_books_courses_memberships(self):
        catalog = [
            {"id": 1, "slug": "therapeutic-oil-tincture-1-time", "name": "Therapeutic Oil Tincture 1-time", "permalink": "https://cccultivate.com/product/therapeutic-oil-tincture-1-time/", "categories": [{"name": "CBD"}], "is_purchasable": True, "is_in_stock": True, "prices": {"price": "6000", "currency_minor_unit": 2, "currency_code": "USD"}},
            {"id": 2, "slug": "therapeutic-body-butter", "name": "Therapeutic Body Butter 1-time", "permalink": "https://cccultivate.com/product/therapeutic-body-butter/", "categories": [{"name": "CBD"}], "is_purchasable": True, "is_in_stock": True, "prices": {"price": "7500", "currency_minor_unit": 2, "currency_code": "USD"}},
            {"id": 3, "slug": "wakenbake-lounge-cannabis-botanical-collection-volume-1", "name": "Wake'n'Bake Lounge Botanical Collection Vol 1", "permalink": "https://cccultivate.com/product/wakenbake-lounge-cannabis-botanical-collection-volume-1/", "categories": [{"name": "CBD"}], "is_purchasable": True, "is_in_stock": True, "prices": {"price": "2500", "currency_minor_unit": 2, "currency_code": "USD"}},
            {"id": 4, "slug": "cook-grow-with-me", "name": "Cook & Grow With Me", "permalink": "https://cccultivate.com/product/cook-grow-with-me/", "categories": [{"name": "CBD"}], "is_purchasable": True, "is_in_stock": True, "prices": {"price": "5000", "currency_minor_unit": 2, "currency_code": "USD"}},
            {"id": 5, "slug": "the-monarch", "name": "The Monarch - NFT Membership", "permalink": "https://cccultivate.com/product/the-monarch/", "categories": [{"name": "CBD"}], "is_purchasable": True, "is_in_stock": True, "prices": {"price": "10000", "currency_minor_unit": 2, "currency_code": "USD"}},
            {"id": 6, "slug": "white-label-oil-per-1oz-min-10oz", "name": "Bulk Oil per 1oz min. 10oz", "permalink": "https://cccultivate.com/product/white-label-oil-per-1oz-min-10oz/", "categories": [{"name": "CBD"}], "is_purchasable": True, "is_in_stock": True, "prices": {"price": "3000", "currency_minor_unit": 2, "currency_code": "USD"}},
        ]
        results = self.adapter(catalog).retrieve(self.context("CBD oil"))
        slugs = [json.loads(item["content"])["slug"] for item in results]
        self.assertEqual(slugs, ["therapeutic-oil-tincture-1-time"])

    def test_retail_creams_query_excludes_wholesale_and_bulk(self):
        catalog = [
            {"id": 1, "slug": "therapeutic-body-butter", "name": "Therapeutic Body Butter 1-time", "permalink": "https://cccultivate.com/product/therapeutic-body-butter/", "categories": [{"name": "CBD"}], "is_purchasable": True, "is_in_stock": True, "prices": {"price": "7500", "currency_minor_unit": 2, "currency_code": "USD"}},
            {"id": 2, "slug": "bulk-butter", "name": "Bulk Butter", "permalink": "https://cccultivate.com/product/bulk-butter/", "categories": [{"name": "CBD"}], "is_purchasable": True, "is_in_stock": True, "prices": {"price": "20000", "currency_minor_unit": 2, "currency_code": "USD"}},
            {"id": 3, "slug": "white-label-butter-per-1oz-min-16oz", "name": "Bulk Butter per 1oz min 16oz", "permalink": "https://cccultivate.com/product/white-label-butter-per-1oz-min-16oz/", "categories": [{"name": "CBD"}], "is_purchasable": True, "is_in_stock": True, "prices": {"price": "3500", "currency_minor_unit": 2, "currency_code": "USD"}},
        ]
        results = self.adapter(catalog).retrieve(self.context("Do you carry creams?"))
        slugs = [json.loads(item["content"])["slug"] for item in results]
        self.assertEqual(slugs, ["therapeutic-body-butter"])

    def test_wholesale_and_white_label_channel_routing(self):
        catalog = [
            {"id": 1, "slug": "therapeutic-body-butter", "name": "Therapeutic Body Butter 1-time", "permalink": "https://cccultivate.com/product/therapeutic-body-butter/", "categories": [{"name": "CBD"}], "is_purchasable": True, "is_in_stock": True, "prices": {"price": "7500", "currency_minor_unit": 2, "currency_code": "USD"}},
            {"id": 2, "slug": "bulk-butter", "name": "Bulk Butter", "permalink": "https://cccultivate.com/product/bulk-butter/", "categories": [{"name": "CBD"}], "is_purchasable": True, "is_in_stock": True, "prices": {"price": "20000", "currency_minor_unit": 2, "currency_code": "USD"}},
            {"id": 3, "slug": "white-label-butter-per-1oz-min-16oz", "name": "Bulk Butter per 1oz min 16oz", "permalink": "https://cccultivate.com/product/white-label-butter-per-1oz-min-16oz/", "categories": [{"name": "CBD"}], "is_purchasable": True, "is_in_stock": True, "prices": {"price": "3500", "currency_minor_unit": 2, "currency_code": "USD"}},
        ]
        adapter = self.adapter(catalog)
        
        # Wholesale query
        ws_results = adapter.retrieve(self.context("Do you offer bulk butter?"))
        ws_slugs = [json.loads(item["content"])["slug"] for item in ws_results]
        self.assertIn("bulk-butter", ws_slugs)
        self.assertIn("white-label-butter-per-1oz-min-16oz", ws_slugs)

        # White-label query
        wl_results = adapter.retrieve(self.context("Can I put my own brand on your products?"))
        wl_slugs = [json.loads(item["content"])["slug"] for item in wl_results]
        self.assertEqual(wl_slugs, ["white-label-butter-per-1oz-min-16oz"])

        # Explicit retail consumer query
        retail_results = adapter.retrieve(self.context("I just want something for myself"))
        retail_slugs = [json.loads(item["content"])["slug"] for item in retail_results]
        self.assertEqual(retail_slugs, ["therapeutic-body-butter"])

    def test_balm_query_returns_safe_empty_results(self):
        catalog = [
            {"id": 1, "slug": "therapeutic-oil-tincture-1-time", "name": "Therapeutic Oil Tincture 1-time", "permalink": "https://cccultivate.com/product/therapeutic-oil-tincture-1-time/", "categories": [{"name": "CBD"}], "is_purchasable": True, "is_in_stock": True, "prices": {"price": "6000", "currency_minor_unit": 2, "currency_code": "USD"}},
            {"id": 2, "slug": "therapeutic-body-butter", "name": "Therapeutic Body Butter 1-time", "permalink": "https://cccultivate.com/product/therapeutic-body-butter/", "categories": [{"name": "CBD"}], "is_purchasable": True, "is_in_stock": True, "prices": {"price": "7500", "currency_minor_unit": 2, "currency_code": "USD"}},
        ]
        results = self.adapter(catalog).retrieve(self.context("Do you have a balm?"))
        self.assertEqual(results, [])

    def test_turn2_pain_query_does_not_route_to_membership(self):
        query = "Benefits, I have a lot of pain in my leg and I want something for the pain. I heard CBD can help"
        domain = ProductionConversationRuntime._knowledge_domain(query)
        self.assertNotEqual(domain, "membership")
        self.assertEqual(domain, "educational")

    def test_approved_links_deduplication(self):
        dup_knowledge = [
            {"content": json.dumps({"canonical_url": "https://cccultivate.com/customer-policies/", "link_label": "Read customer policies"})},
            {"content": json.dumps({"canonical_url": "https://cccultivate.com/customer-policies/", "link_label": "Read customer policies"})},
            {"content": json.dumps({"canonical_url": "https://cccultivate.com/legends/", "link_label": "View memberships"})},
        ]
        links = ProductionConversationRuntime._approved_links(dup_knowledge)
        self.assertEqual(len(links), 2)
        self.assertEqual([link["url"] for link in links], [
            "https://cccultivate.com/customer-policies/",
            "https://cccultivate.com/legends/",
        ])


    def test_contextual_available_query_uses_session_history(self):
        from src.budly_runtime.config import ProductionSettings
        from src.budly_runtime.session import ConversationSession
        session = ConversationSession("test_session_1", "2026-09-11T00:00:00Z", "2026-09-11T00:00:00Z")
        session.recent_turns.append(type("Turn", (), {"role": "customer", "content": "Let’s check the targeted option. I like creams, do you carry those?"})())
        query = ProductionConversationRuntime._build_retrieval_query(session, "What do you have available?", "product_catalog")
        self.assertIn("cream", query)
        self.assertIn("topical", query)

    def test_exact_owner_six_turn_replay_execution(self):
        from src.budly_runtime.config import ProductionSettings
        settings = ProductionSettings(
            environment="development", bind_host="127.0.0.1", port=8791,
            shared_secret="a" * 32, model_provider="openai", model_name="gpt-4o-mini",
            model_api_key="mock-key", knowledge_path=Path("config"),
        )
        class MockReplayModel:
            def generate(self, req):
                msg = req.prompt_package["provider_input"][-1]["content"].lower()
                if "compare products" in msg:
                    t, i, j = "I can help you compare our topical, ingestible, or educational options.", "product_comparison", "wellness"
                elif "pain" in msg:
                    t, i, j = "For leg pain, please consult a healthcare professional. CBD is not a medical treatment.", "educational_health_guidance", "wellness"
                elif "muscle tension" in msg:
                    t, i, j = "For muscle tension, topicals provide direct targeted support without systemic effects.", "product_guidance", "wellness"
                elif "what is a topical" in msg:
                    t, i, j = "A topical is applied directly to the skin to interact locally with tissue receptors.", "educational_explanation", "wellness"
                elif "creams" in msg:
                    t, i, j = "We carry Therapeutic Body Butter for targeted topical care.", "product_inquiry", "wellness"
                else:
                    t, i, j = "In retail topicals, we offer the Therapeutic Body Butter 1-time purchase ($75.00).", "catalog_inquiry", "wellness"
                return type("Resp", (), {"payload": {"text": t, "intent": i, "journey": j, "resulting_action": "continue_conversation", "selected_product_id": None, "requires_human": False}})()
        
        runtime = ProductionConversationRuntime(settings, ROOT, model_adapter=MockReplayModel())
        conv = "conv_exact_owner_test_123"
        turns = [
            "Help me compare products",
            "Benefits, I have a lot of pain in my leg and I want something for the pain. I heard CBD can help",
            "Nope. Just muscle tension. I just want something to help me relax",
            "Thank you for your concern, thats nice of you. What is a topical?",
            "Let’s check the targeted option. I like creams, do you carry those?",
            "What do you have available?",
        ]
        results = []
        for q in turns:
            res = runtime.turn({"conversation_id": conv, "message": q, "correlation_id": "11111111-1111-1111-1111-111111111111", "channel": "ccc_website"})
            results.append(res["response"])
        
        # Turn 1: natural continuation
        self.assertEqual(results[0]["resulting_action"], "continue_conversation")
        self.assertEqual(results[0]["links"], [])
        
        # Turn 2: safety / no irrelevant link
        self.assertEqual(results[1]["resulting_action"], "continue_conversation")
        self.assertEqual(results[1]["links"], [])
        
        # Turn 5: retail topical link emitted
        self.assertEqual(results[4]["resulting_action"], "continue_conversation")
        t5_links = [link["url"] for link in results[4]["links"]]
        self.assertEqual(t5_links, ["https://cccultivate.com/product/therapeutic-body-butter/"])
        
        # Turn 6: contextual continuation
        self.assertEqual(results[5]["resulting_action"], "continue_conversation")
        self.assertNotIn("Combo", results[5]["text"])
        self.assertNotIn("third-party lab tested", results[5]["text"])
        self.assertNotIn("crafted in small batches", results[5]["text"])
        self.assertIn("Therapeutic Body Butter", results[5]["text"])
        t6_links = [link["url"] for link in results[5]["links"]]
        self.assertEqual(t6_links, ["https://cccultivate.com/product/therapeutic-body-butter/"])

    def test_grounding_prompt_rules_enforce_retrieved_evidence_constraints(self):
        from src.budly_runtime.config import ProductionSettings
        settings = ProductionSettings(
            environment="development", bind_host="127.0.0.1", port=8791,
            shared_secret="a" * 32, model_provider="openai", model_name="gpt-4o-mini",
            model_api_key="mock-key", knowledge_path=Path("config"),
        )
        captured_requests = []
        class CaptureModel:
            def generate(self, req):
                captured_requests.append(req)
                return type("Resp", (), {"payload": {"text": "Grounded answer.", "intent": "inquiry", "journey": "wellness", "resulting_action": "continue_conversation", "selected_product_id": None, "requires_human": False}})()
        
        runtime = ProductionConversationRuntime(settings, ROOT, model_adapter=CaptureModel())
        runtime.turn({"conversation_id": "conv_grounding_test", "message": "Do you carry creams?", "correlation_id": "11111111-1111-1111-1111-111111111111", "channel": "ccc_website"})
        self.assertEqual(len(captured_requests), 1)
        raw_system = captured_requests[0].prompt_package["provider_input"][0]["content"]
        system_data = json.loads(raw_system)
        rules = system_data.get("rules", [])
        self.assertTrue(any("Only mention specific products that are present in RETRIEVED KNOWLEDGE" in r for r in rules))
        self.assertTrue(any("Only state product attributes" in r for r in rules))
        self.assertTrue(any("selected_product_id must exactly match" in r for r in rules))

    def test_books_ranking_and_link_consistency(self):
        adapter = ApprovedRepositoryKnowledgeAdapter(
            ROOT / "config/policies.json", ROOT / "config/products.json",
            ROOT / "config/budly_runtime/education-corpus-v0.1.json",
            ROOT / "config/budly_runtime/commercial-knowledge-v1.0.json",
            opener=lambda *_args, **_kwargs: Response(json.dumps([
                {"id": 1, "slug": "infused-basics", "name": "Infused Basics: The Beginner&#8217;s Guide to Infuse Everything Edible",
                 "permalink": "https://cccultivate.com/product/infused-basics/", "short_description": "Book", "categories": [{"name": "Education"}],
                 "is_purchasable": True, "is_in_stock": True, "prices": {"price": "4000", "currency_minor_unit": 2, "currency_code": "USD"}},
                {"id": 2, "slug": "wakenbake-lounge-cannabis-botanical-collection-volume-1", "name": "Wake&#8217;n&#8217;Bake Lounge&#8230; Cannabis Botanical Collection &#8211; Volume 1",
                 "permalink": "https://cccultivate.com/product/wakenbake-lounge-cannabis-botanical-collection-volume-1/", "short_description": "Book", "categories": [{"name": "Education"}],
                 "is_purchasable": True, "is_in_stock": True, "prices": {"price": "1499", "currency_minor_unit": 2, "currency_code": "USD"}}
            ]).encode())
        )
        res = adapter.retrieve(self.context("What books do you have?"))
        self.assertEqual(len(res), 2)
        # Check titles are unescaped
        self.assertNotIn("&#8217;", res[0]["title"])
        self.assertNotIn("&#8211;", res[1]["title"])
        
        links = ProductionConversationRuntime._approved_links(res)
        self.assertEqual(len(links), 2)
        urls = [l["url"] for l in links]
        self.assertIn("https://cccultivate.com/product/infused-basics/", urls)
        self.assertIn("https://cccultivate.com/product/wakenbake-lounge-cannabis-botanical-collection-volume-1/", urls)

    def test_cbd_oils_tincture_priority_ranking(self):
        adapter = ApprovedRepositoryKnowledgeAdapter(
            ROOT / "config/policies.json", ROOT / "config/products.json",
            ROOT / "config/budly_runtime/education-corpus-v0.1.json",
            ROOT / "config/budly_runtime/commercial-knowledge-v1.0.json",
            opener=lambda *_args, **_kwargs: Response(json.dumps([
                {"id": 10, "slug": "infused-cooking-oil-4oz", "name": "Infused Cooking Oil 4oz", "permalink": "https://cccultivate.com/product/infused-cooking-oil-4oz/", "short_description": "", "categories": [{"name": "Culinary"}], "is_purchasable": True, "is_in_stock": True, "prices": {"price": "30000", "currency_minor_unit": 2, "currency_code": "USD"}},
                {"id": 11, "slug": "infused-cooking-oil-8oz", "name": "Infused Cooking Oil 8oz", "permalink": "https://cccultivate.com/product/infused-cooking-oil-8oz/", "short_description": "", "categories": [{"name": "Culinary"}], "is_purchasable": True, "is_in_stock": True, "prices": {"price": "50000", "currency_minor_unit": 2, "currency_code": "USD"}},
                {"id": 12, "slug": "infused-cooking-oil-12oz", "name": "Infused Cooking Oil 12oz", "permalink": "https://cccultivate.com/product/infused-cooking-oil-12oz/", "short_description": "", "categories": [{"name": "Culinary"}], "is_purchasable": True, "is_in_stock": True, "prices": {"price": "65000", "currency_minor_unit": 2, "currency_code": "USD"}},
                {"id": 13, "slug": "infused-cooking-oil-16oz", "name": "Infused Cooking Oil 16oz", "permalink": "https://cccultivate.com/product/infused-cooking-oil-16oz/", "short_description": "", "categories": [{"name": "Culinary"}], "is_purchasable": True, "is_in_stock": True, "prices": {"price": "75000", "currency_minor_unit": 2, "currency_code": "USD"}},
                {"id": 14, "slug": "therapeutic-oil-tincture-1-time", "name": "Therapeutic Oil Tincture 1-time", "permalink": "https://cccultivate.com/product/therapeutic-oil-tincture-1-time/", "short_description": "", "categories": [{"name": "CBD"}], "is_purchasable": True, "is_in_stock": True, "prices": {"price": "5500", "currency_minor_unit": 2, "currency_code": "USD"}},
            ]).encode())
        )
        res = adapter.retrieve(self.context("What CBD oils do you sell?"))
        self.assertEqual(len(res), 5)
        # Therapeutic tincture MUST be ranked #1
        self.assertEqual(res[0]["knowledge_id"], "product:therapeutic-oil-tincture-1-time")
        
        links = ProductionConversationRuntime._approved_links(res)
        self.assertEqual(len(links), 3)
        self.assertEqual(links[0]["url"], "https://cccultivate.com/product/therapeutic-oil-tincture-1-time/")


if __name__ == "__main__":
    unittest.main()
