from __future__ import annotations

import io
import json
import unittest
from pathlib import Path

from src.budly_runtime.config import ProductionSettings
from src.budly_runtime.events import EventLogger
from src.budly_runtime.model import ProviderResult
from src.budly_runtime.production_knowledge import ApprovedRepositoryKnowledgeAdapter
from src.budly_runtime.production_runtime import ProductionConversationRuntime
from src.budly_runtime.tool_gateway import AdapterContext

ROOT = Path(__file__).resolve().parents[1]


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def live_catalog_payload():
    return [
        {
            "id": 151, "slug": "grow-cannabis-home", "name": "Grow Cannabis @ Home",
            "permalink": "https://cccultivate.com/product/grow-cannabis-home/",
            "short_description": "Comprehensive home cultivation course.",
            "categories": [{"name": "Education"}],
            "is_purchasable": True, "is_in_stock": True,
            "prices": {"price": "150000", "regular_price": "150000", "sale_price": "150000", "currency_minor_unit": 2, "currency_code": "USD"},
        },
        {
            "id": 150, "slug": "culinary-cannabis", "name": "Culinary Cannabis",
            "permalink": "https://cccultivate.com/product/culinary-cannabis/",
            "short_description": "Comprehensive culinary infusion class.",
            "categories": [{"name": "Culinary"}, {"name": "Education"}],
            "is_purchasable": True, "is_in_stock": True,
            "prices": {"price": "100000", "regular_price": "100000", "sale_price": "100000", "currency_minor_unit": 2, "currency_code": "USD"},
        },
        {
            "id": 152, "slug": "cook-grow-with-me", "name": "Cook & Grow With Me",
            "permalink": "https://cccultivate.com/product/cook-grow-with-me/",
            "short_description": "Complete bundle combining both Grow Cannabis @ Home and Culinary Cannabis.",
            "categories": [{"name": "Culinary"}, {"name": "Education"}],
            "is_purchasable": True, "is_in_stock": True,
            "prices": {"price": "250000", "regular_price": "250000", "sale_price": "250000", "currency_minor_unit": 2, "currency_code": "USD"},
        },
        {
            "id": 87, "slug": "infused-basics", "name": "Infused Basics: The Beginner's Guide to Infuse Everything Edible",
            "permalink": "https://cccultivate.com/product/infused-basics/",
            "short_description": "Introductory guide to edible infusions.",
            "categories": [{"name": "Culinary"}, {"name": "Education"}],
            "is_purchasable": True, "is_in_stock": True,
            "prices": {"price": "4000", "regular_price": "4000", "sale_price": "4000", "currency_minor_unit": 2, "currency_code": "USD"},
        },
        {
            "id": 913, "slug": "wakenbake-lounge-cannabis-botanical-collection-volume-1",
            "name": "Wake'n'Bake Lounge Cannabis Botanical Collection - Volume 1",
            "permalink": "https://cccultivate.com/product/wakenbake-lounge-cannabis-botanical-collection-volume-1/",
            "short_description": "Botanical coloring and plant education collection.",
            "categories": [{"name": "Education"}],
            "is_purchasable": True, "is_in_stock": True,
            "prices": {"price": "1499", "currency_minor_unit": 2, "currency_code": "USD"},
        },
        {
            "id": 42, "slug": "therapeutic-oil-tincture-1-time",
            "name": "Therapeutic Oil Tincture 1-time",
            "permalink": "https://cccultivate.com/product/therapeutic-oil-tincture-1-time/",
            "short_description": "Therapeutic full spectrum CBD oil tincture drops.",
            "categories": [{"name": "CBD"}, {"name": "Wellness"}],
            "is_purchasable": True, "is_in_stock": True,
            "prices": {"price": "7500", "currency_minor_unit": 2, "currency_code": "USD"},
        },
        {
            "id": 61, "slug": "therapeutic-body-butter",
            "name": "Therapeutic Body Butter 1-time",
            "permalink": "https://cccultivate.com/product/therapeutic-body-butter/",
            "short_description": "Therapeutic CBD topical body butter cream.",
            "categories": [{"name": "CBD"}, {"name": "Selfcare"}],
            "is_purchasable": True, "is_in_stock": True,
            "prices": {"price": "4000", "currency_minor_unit": 2, "currency_code": "USD"},
        },
        {
            "id": 114, "slug": "infused-cooking-oil-4oz",
            "name": "Infused Cooking Oil 4oz",
            "permalink": "https://cccultivate.com/product/infused-cooking-oil-4oz/",
            "short_description": "Infused cooking oil 4oz.",
            "categories": [{"name": "Culinary"}, {"name": "CBD"}],
            "is_purchasable": True, "is_in_stock": True,
            "prices": {"price": "4500", "currency_minor_unit": 2, "currency_code": "USD"},
        },
        {
            "id": 115, "slug": "infused-cooking-oil-8oz",
            "name": "Infused Cooking Oil 8oz",
            "permalink": "https://cccultivate.com/product/infused-cooking-oil-8oz/",
            "short_description": "Infused cooking oil 8oz.",
            "categories": [{"name": "Culinary"}, {"name": "CBD"}],
            "is_purchasable": True, "is_in_stock": True,
            "prices": {"price": "8000", "currency_minor_unit": 2, "currency_code": "USD"},
        },
        {
            "id": 116, "slug": "infused-cooking-oil-12oz",
            "name": "Infused Cooking Oil 12oz",
            "permalink": "https://cccultivate.com/product/infused-cooking-oil-12oz/",
            "short_description": "Infused cooking oil 12oz.",
            "categories": [{"name": "Culinary"}, {"name": "CBD"}],
            "is_purchasable": True, "is_in_stock": True,
            "prices": {"price": "11500", "currency_minor_unit": 2, "currency_code": "USD"},
        },
        {
            "id": 882, "slug": "the-chemist-nft-membership", "name": "The Chemist - NFT Membership",
            "permalink": "https://cccultivate.com/product/the-chemist-nft-membership/",
            "short_description": "Legends digital collectible NFT membership pass.",
            "categories": [{"name": "Membership"}],
            "is_purchasable": True, "is_in_stock": True,
            "prices": {"price": "300000", "currency_minor_unit": 2, "currency_code": "USD"},
        },
    ]


class MockModelAdapter:
    def __init__(self, canned_responses=None):
        self.canned = canned_responses or {}
        self.call_count = 0
        self.history = []

    def generate(self, request):
        self.call_count += 1
        self.history.append(request)
        pkg = request.prompt_package
        user_msg = pkg['provider_input'][-1]['content'] if 'provider_input' in pkg else pkg.get('message', '')
        
        for pattern, resp in self.canned.items():
            if pattern.lower() in user_msg.lower():
                return ProviderResult(resp, 'mock', 'mock-model')
        
        payload = {
            'text': f'Here is helpful information regarding: {user_msg}',
            'intent': 'customer_education',
            'journey': 'education',
            'resulting_action': 'continue_conversation',
            'selected_product_id': None,
            'requires_human': False
        }
        return ProviderResult(payload, 'mock', 'mock-model')


class OfferRelationship001Tests(unittest.TestCase):
    def setUp(self):
        raw_catalog = json.dumps(live_catalog_payload()).encode()
        self.knowledge = ApprovedRepositoryKnowledgeAdapter(
            ROOT / 'config/policies.json',
            ROOT / 'config/products.json',
            ROOT / 'config/budly_runtime/education-corpus-v0.1.json',
            ROOT / 'config/budly_runtime/commercial-knowledge-v1.0.json',
            opener=lambda *_args, **_kwargs: Response(raw_catalog),
        )
        self.events = EventLogger()
        self.settings = ProductionSettings(
            environment='development',
            bind_host='127.0.0.1',
            port=8791,
            shared_secret='0'*32,
            model_provider='openai',
            model_name='mock-model',
            model_api_key='mock-key',
            knowledge_path=Path('config'),
            request_timeout_seconds=10.0,
            provider_retry_count=1,
        )

    def context(self, query, domain='product_catalog'):
        return AdapterContext(query, domain, 5, ('Public',), 'test', 'test', 'website_chat')

    def test_01_cbd_commercial_query_routes_to_product_catalog(self):
        commercial_queries = [
            'What CBD oils do you sell?',
            'Do you sell CBD?',
            'What CBD products are available?',
            'How much is your CBD oil?',
            'Where can I buy CBD tinctures?',
        ]
        for q in commercial_queries:
            domain = ProductionConversationRuntime._knowledge_domain(q)
            self.assertEqual(domain, 'product_catalog', f'Query {q} should route to product_catalog')

    def test_02_cbd_educational_query_routes_to_educational(self):
        educational_queries = [
            'What is CBD?',
            'How does the endocannabinoid system work?',
            'What are the parts that people smoke or use for medicine?',
            'General safety and the different parts of the plant',
        ]
        for q in educational_queries:
            domain = ProductionConversationRuntime._knowledge_domain(q)
            self.assertEqual(domain, 'educational', f'Query {q} should route to educational')

    def test_03_therapeutic_oil_tincture_top_card_priority(self):
        results = self.knowledge.retrieve(self.context('What CBD oils do you sell?'))
        self.assertGreater(len(results), 0)
        top_item = json.loads(results[0]['content'])
        self.assertIn('tincture', top_item.get('slug', '').lower())
        self.assertIn('Therapeutic Oil Tincture', top_item.get('name', ''))

    def test_04_books_prose_and_card_count_equality(self):
        results = self.knowledge.retrieve(self.context('What books do you have?'))
        slugs = [json.loads(r['content']).get('slug') for r in results]
        self.assertIn('infused-basics', slugs)
        self.assertIn('wakenbake-lounge-cannabis-botanical-collection-volume-1', slugs)
        self.assertEqual(len([s for s in slugs if s in {'infused-basics', 'wakenbake-lounge-cannabis-botanical-collection-volume-1'}]), 2)

    def test_05_wakenbake_lounge_canonical_homepage_precedence(self):
        knowledge_results = self.knowledge.retrieve(self.context("How do I get to Wake'n'Bake Lounge?", domain='educational'))
        links = ProductionConversationRuntime._approved_links(knowledge_results, "How do I get to Wake'n'Bake Lounge?")
        self.assertGreater(len(links), 0)
        self.assertEqual(links[0]['url'], 'https://dmckenzies.wixsite.com/wakenbakelounge')

    def test_06_class_inventory_list_completeness(self):
        results = self.knowledge.retrieve(self.context('What classes do you offer?'))
        slugs = [json.loads(r['content']).get('slug') for r in results]
        self.assertIn('grow-cannabis-home', slugs)
        self.assertIn('culinary-cannabis', slugs)
        self.assertIn('cook-grow-with-me', slugs)
        self.assertIn('infused-basics', slugs)

    def test_07_class_recommendation_ranking(self):
        grow_res = self.knowledge.retrieve(self.context('Which class is best if I want to learn to grow cannabis?'))
        top_grow = json.loads(grow_res[0]['content']).get('slug')
        self.assertEqual(top_grow, 'grow-cannabis-home')

        cook_res = self.knowledge.retrieve(self.context('Which class is best for cooking with cannabis?'))
        top_cook = json.loads(cook_res[0]['content']).get('slug')
        self.assertEqual(top_cook, 'culinary-cannabis')

    def test_08_membership_inventory_list_completeness(self):
        results = self.knowledge.retrieve(self.context('What memberships do you have?', domain='membership'))
        titles = [r['title'] for r in results]
        self.assertTrue(any('Bronze' in t for t in titles))
        self.assertTrue(any('Copper' in t for t in titles))
        self.assertTrue(any('Titanium' in t for t in titles))
        self.assertTrue(any('Platinum' in t for t in titles))

    def test_09_membership_recommendation_ranking(self):
        results = self.knowledge.retrieve(self.context('Which membership would fit someone looking for education and community?', domain='membership'))
        self.assertGreater(len(results), 0)
        all_content = ' '.join(r['content'] for r in results)
        self.assertIn('community', all_content.lower())
        self.assertTrue('course' in all_content.lower() or 'education' in all_content.lower() or 'ebook' in all_content.lower())

    def test_10_exact_membership_tier_names_and_prices(self):
        commercial = json.loads((ROOT / 'config/budly_runtime/commercial-knowledge-v1.0.json').read_text('utf-8'))
        resources = {r['resource_id']: r for r in commercial.get('resources', []) if r.get('resource_type') == 'MEMBERSHIP_TIER'}
        
        bronze = resources.get('ccc:membership:tier:bronze')
        self.assertIsNotNone(bronze)
        self.assertEqual(bronze['title'], 'Bronze Tier')
        self.assertIn('$5,000', bronze['summary'])
        self.assertEqual(bronze['canonical_url'], 'https://cccultivate.com/legends/')
        self.assertEqual(bronze['active_status'], 'active')

        copper = resources.get('ccc:membership:tier:copper')
        self.assertIsNotNone(copper)
        self.assertEqual(copper['title'], 'Copper Tier')
        self.assertIn('$10,000', copper['summary'])
        self.assertEqual(copper['canonical_url'], 'https://cccultivate.com/legends/')
        self.assertEqual(copper['active_status'], 'active')

        titanium = resources.get('ccc:membership:tier:titanium')
        self.assertIsNotNone(titanium)
        self.assertEqual(titanium['title'], 'Titanium Tier')
        self.assertIn('$20,000', titanium['summary'])
        self.assertEqual(titanium['canonical_url'], 'https://cccultivate.com/legends/')
        self.assertEqual(titanium['active_status'], 'active')

        platinum = resources.get('ccc:membership:tier:platinum')
        self.assertIsNotNone(platinum)
        self.assertEqual(platinum['title'], 'Platinum Tier')
        self.assertIn('$40,000', platinum['summary'])
        self.assertEqual(platinum['canonical_url'], 'https://cccultivate.com/legends/')
        self.assertEqual(platinum['active_status'], 'active')

        self.assertNotIn('ccc:membership:tier:legend-silver', resources)
        self.assertNotIn('ccc:membership:tier:legend-gold', resources)
        self.assertNotIn('ccc:membership:tier:legend-og', resources)

    def test_11_proactive_name_capture(self):
        model = MockModelAdapter()
        runtime = ProductionConversationRuntime(
            self.settings, ROOT, model_adapter=model,
            knowledge_adapter=self.knowledge, events=self.events
        )
        cid = 'conv_name_cap_01'
        runtime.turn({
            'conversation_id': cid,
            'message': 'Hi, I am Alex',
            'correlation_id': '00000000-0000-0000-0000-000000000101',
            'channel': 'ccc_website',
            'reset': True,
            'use_durable_memory': False
        })
        session = runtime.sessions.acquire(cid)
        self.assertEqual(session.customer_name, 'Alex')

        cid_dec = 'conv_name_dec_01'
        runtime.turn({
            'conversation_id': cid_dec,
            'message': "I'd rather not share my name",
            'correlation_id': '00000000-0000-0000-0000-000000000102',
            'channel': 'ccc_website',
            'reset': True,
            'use_durable_memory': False
        })
        session_dec = runtime.sessions.acquire(cid_dec)
        self.assertTrue(session_dec.name_capture_declined)
        self.assertIsNone(session_dec.customer_name)

    def test_12_proactive_email_capture(self):
        model = MockModelAdapter()
        runtime = ProductionConversationRuntime(
            self.settings, ROOT, model_adapter=model,
            knowledge_adapter=self.knowledge, events=self.events
        )
        cid = 'conv_email_cap_01'
        runtime.turn({
            'conversation_id': cid,
            'message': 'My email is alex@example.com',
            'correlation_id': '00000000-0000-0000-0000-000000000111',
            'channel': 'ccc_website',
            'reset': True,
            'use_durable_memory': False
        })
        session = runtime.sessions.acquire(cid)
        self.assertEqual(session.customer_email, 'alex@example.com')

        cid_dec = 'conv_email_dec_01'
        runtime.turn({
            'conversation_id': cid_dec,
            'message': 'No thanks, I do not want to provide my email',
            'correlation_id': '00000000-0000-0000-0000-000000000112',
            'channel': 'ccc_website',
            'reset': True,
            'use_durable_memory': False
        })
        session_dec = runtime.sessions.acquire(cid_dec)
        self.assertTrue(session_dec.email_capture_declined)
        self.assertIsNone(session_dec.customer_email)

    def test_13_crm_consent_independence(self):
        model = MockModelAdapter()
        runtime = ProductionConversationRuntime(
            self.settings, ROOT, model_adapter=model,
            knowledge_adapter=self.knowledge, events=self.events
        )
        cid = 'conv_crm_indep_01'
        runtime.turn({
            'conversation_id': cid,
            'message': 'Yes, please save my contact info and interests for your records.',
            'correlation_id': '00000000-0000-0000-0000-000000000121',
            'channel': 'ccc_website',
            'reset': True,
            'use_durable_memory': False
        })
        session = runtime.sessions.acquire(cid)
        self.assertEqual(session.crm_context_consent, 'granted')
        self.assertEqual(session.follow_up_permission, 'none')

    def test_14_followup_consent_independence(self):
        model = MockModelAdapter()
        runtime = ProductionConversationRuntime(
            self.settings, ROOT, model_adapter=model,
            knowledge_adapter=self.knowledge, events=self.events
        )
        cid = 'conv_followup_indep_01'
        runtime.turn({
            'conversation_id': cid,
            'message': 'Yes, please follow up with me when new classes are added.',
            'correlation_id': '00000000-0000-0000-0000-000000000131',
            'channel': 'ccc_website',
            'reset': True,
            'use_durable_memory': False
        })
        session = runtime.sessions.acquire(cid)
        self.assertEqual(session.follow_up_permission, 'granted')
        self.assertEqual(session.crm_context_consent, 'none')

    def test_15_explicit_denial_precedence(self):
        model = MockModelAdapter()
        runtime = ProductionConversationRuntime(
            self.settings, ROOT, model_adapter=model,
            knowledge_adapter=self.knowledge, events=self.events
        )
        cid_a = 'conv_denial_01'
        runtime.turn({
            'conversation_id': cid_a,
            'message': "Save my information, but don't contact me.",
            'correlation_id': '00000000-0000-0000-0000-000000000141',
            'channel': 'ccc_website',
            'reset': True,
            'use_durable_memory': False
        })
        session_a = runtime.sessions.acquire(cid_a)
        self.assertEqual(session_a.crm_context_consent, 'granted')
        self.assertEqual(session_a.follow_up_permission, 'denied')

        cid_b = 'conv_denial_02'
        runtime.turn({
            'conversation_id': cid_b,
            'message': "You can contact me, but don't save anything else.",
            'correlation_id': '00000000-0000-0000-0000-000000000142',
            'channel': 'ccc_website',
            'reset': True,
            'use_durable_memory': False
        })
        session_b = runtime.sessions.acquire(cid_b)
        self.assertEqual(session_b.follow_up_permission, 'granted')
        self.assertEqual(session_b.crm_context_consent, 'denied')

    def test_16_body_butter_regression(self):
        results = self.knowledge.retrieve(self.context('Do you carry creams?'))
        self.assertGreater(len(results), 0)
        slugs = [json.loads(r['content']).get('slug') for r in results]
        self.assertIn('therapeutic-body-butter', slugs)
        content = json.loads(results[0]['content'])
        self.assertEqual(content['current_price'], 40.0)

    def test_17_return_policy_regression(self):
        results = self.knowledge.retrieve(self.context('What is your return policy?', domain='customer_policy'))
        self.assertGreater(len(results), 0)
        self.assertTrue(any('customer-policies' in r['content'] for r in results))

    def test_18_affiliate_regression(self):
        results = self.knowledge.retrieve(self.context('How do I become an affiliate?', domain='affiliate_program'))
        self.assertGreater(len(results), 0)
        self.assertTrue(any('affiliate' in r['content'].lower() for r in results))

    def test_19_closing_regression(self):
        model = MockModelAdapter()
        runtime = ProductionConversationRuntime(
            self.settings, ROOT, model_adapter=model,
            knowledge_adapter=self.knowledge, events=self.events
        )
        res = runtime.turn({
            'conversation_id': 'conv_closing_regression_01',
            'message': 'No thanks, I have what I need',
            'correlation_id': '00000000-0000-0000-0000-000000000191',
            'channel': 'ccc_website',
            'reset': True,
            'use_durable_memory': False
        })
        self.assertEqual(res['response']['intent'], 'conversation_closing')
        self.assertEqual(res['response']['resulting_action'], 'continue_conversation')
        self.assertIn('welcome', res['response']['text'].lower())

    def test_tier_specific_membership_relationships(self):
        commercial = json.loads((ROOT / 'config/budly_runtime/commercial-knowledge-v1.0.json').read_text('utf-8'))
        rels = commercial.get('offer_relationships', [])
        
        tier_bronze_rels = [r for r in rels if r['offer_id'] == 'ccc:membership:tier:bronze']
        tier_copper_rels = [r for r in rels if r['offer_id'] == 'ccc:membership:tier:copper']
        tier_titanium_rels = [r for r in rels if r['offer_id'] == 'ccc:membership:tier:titanium']
        tier_platinum_rels = [r for r in rels if r['offer_id'] == 'ccc:membership:tier:platinum']
        
        self.assertEqual(len(tier_bronze_rels), 2)
        self.assertEqual(len(tier_copper_rels), 2)
        self.assertEqual(len(tier_titanium_rels), 3)
        self.assertEqual(len(tier_platinum_rels), 4)
        
        for tier_rels in [tier_bronze_rels, tier_copper_rels, tier_titanium_rels, tier_platinum_rels]:
            types = {r['relationship_type'] for r in tier_rels}
            self.assertIn('INCLUDES_COMMUNITY_ACCESS', types)
            related_ids = {r['related_offer_id'] for r in tier_rels}
            self.assertIn('wnb:community:hub', related_ids)

    def test_live_course_price_grounding_woocommerce(self):
        res = self.knowledge.retrieve(self.context('How much are Grow Cannabis @ Home, Culinary Cannabis, and Cook & Grow With Me?'))
        slug_to_price = {}
        for r in res:
            try:
                c = json.loads(r['content'])
                slug = c.get('slug')
                slug_to_price[slug] = float(c.get('current_price', 0.0))
            except Exception:
                pass
        
        self.assertEqual(slug_to_price.get('grow-cannabis-home'), 1500.00)
        self.assertEqual(slug_to_price.get('culinary-cannabis'), 1000.00)
        self.assertEqual(slug_to_price.get('cook-grow-with-me'), 2500.00)
        self.assertEqual(slug_to_price.get('infused-basics'), 40.00)

    def test_membership_destination_persistence_across_turns(self):
        model = MockModelAdapter()
        runtime = ProductionConversationRuntime(
            self.settings, ROOT, model_adapter=model,
            knowledge_adapter=self.knowledge, events=self.events
        )
        cid = 'conv_dest_persist_01'
        runtime.turn({
            'conversation_id': cid,
            'message': "Maybe a free membership until I decide it's worth paying for",
            'correlation_id': '00000000-0000-0000-0000-000000000081',
            'channel': 'ccc_website',
            'reset': True,
            'use_durable_memory': False
        })
        res9 = runtime.turn({
            'conversation_id': cid,
            'message': "Ok thanks. I'll look into that. How do I find them?",
            'correlation_id': '00000000-0000-0000-0000-000000000082',
            'channel': 'ccc_website',
            'reset': False,
            'use_durable_memory': False
        })
        links9 = [l['url'] for l in res9['response']['links']]
        self.assertTrue(any('cccultivate.com/legends' in u for u in links9))


if __name__ == '__main__':
    unittest.main()
