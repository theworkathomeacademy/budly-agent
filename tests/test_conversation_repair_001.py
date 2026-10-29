from __future__ import annotations

import json
import unittest
from pathlib import Path
from uuid import uuid4

from src.budly_runtime.config import FeatureFlags, ProductionSettings, RuntimeConfig
from src.budly_runtime.model import ProviderResult
from src.budly_runtime.production_runtime import (
    EphemeralSessionStore,
    ProductionConversationRuntime,
    ProductionResponseValidator,
    RuntimeTurnRequest,
)

ROOT = Path(__file__).resolve().parents[1]


class ConversationRepairModel:
    def __init__(self, responses: list[dict] | None = None, default_behavior: str = "normal") -> None:
        self.responses = list(responses or [])
        self.default_behavior = default_behavior
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if self.default_behavior == "timeout":
            raise TimeoutError("Model timed out")
        if self.default_behavior == "connection_error":
            raise ConnectionError("Model unreachable")
        if self.responses:
            payload = self.responses.pop(0)
            return ProviderResult(payload, "test-provider", "test-model")

        prompt = json.loads(request.prompt_package["provider_input"][0]["content"])
        user_msg = request.prompt_package["provider_input"][1]["content"]
        deterministic = prompt.get("deterministic_authority", {})
        selected = deterministic.get("selected_product_id")
        active_task = deterministic.get("active_task")

        # Default compliant mock response
        payload = {
            "text": f"Budly helpful response to: {user_msg}",
            "intent": "product_guidance",
            "journey": deterministic.get("journey"),
            "resulting_action": "continue_conversation",
            "selected_product_id": selected,
            "requires_human": False,
        }
        return ProviderResult(payload, "test-provider", "test-model")


def make_settings(environment: str = "production") -> ProductionSettings:
    return ProductionSettings(
        environment, "127.0.0.1", 8791, "s" * 32, "openai", "candidate-model", "test-key", ROOT / "config"
    )


class TestConversationRepair001(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime_settings = make_settings()

    def make_runtime(self, model=None, knowledge=None):
        return ProductionConversationRuntime(
            self.runtime_settings, ROOT, model_adapter=model or ConversationRepairModel(), knowledge_adapter=knowledge
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
    # MANDATORY REGRESSION FIXTURE: EXACT CUSTOMER REPLAY (Turns 1 - 4)
    # =========================================================================
    def test_exact_customer_replay_regression(self):
        """
        Replays exact 4-turn customer defect conversation:
        Turn 1: "What are the ingredients in your body butter"
        Turn 2: "My name is d-Mac, and yes please confirm the ingredients if you can"
        Turn 3: "Yes please"
        Turn 4: "Sure"

        Verifies:
        - Active task contract preserved throughout (active_entity, active_request, task_state=UNRESOLVED)
        - Name correctly parsed as "d-Mac" (hyphen preserved, not truncated)
        - No contact channel inferred (email and phone remain None)
        - Action-truth preserved (crm_write_state=NOT_ATTEMPTED, human_followup_state=NOT_CREATED)
        - Follow-up consent accurately captured (requested=True, consent=True)
        - After Turn 4:
            * focused on Therapeutic Body Butter
            * asks for contact channel
            * NOT dumped into Consumer Wellness journey or qualification question
            * zero internal labels (GUIDED MODE, CONSUMER WELLNESS)
            * no unverified ingredient guessing
        """
        model_responses = [
            # Turn 1: Product description retrieval with listed ingredients and canonical URL
            {
                "text": "The product description lists cocoa, kokum, and shea butters, coconut and hemp seed oils, and CBD distillate for the Therapeutic Body Butter. Those are the ingredients specifically highlighted in the product description, though it is not a full regulatory ingredient declaration. It’s currently listed at $75. You can see the product details here: https://cccultivate.com/product/therapeutic-body-butter/. Would you like me to help get the full ingredients confirmed? By the way, what should I call you?",
                "intent": "product_guidance",
                "journey": None,
                "resulting_action": "continue_conversation",
                "selected_product_id": "ccc:product:therapeutic-body-butter",
                "requires_human": False,
            },
            # Turn 2: Retains d-Mac, acknowledges ingredient confirmation request, notes interest for records
            {
                "text": "Thanks, d-Mac. I’ve noted your interest in getting the full Therapeutic Body Butter ingredients confirmed for the team. Would you like the team to contact you once they confirm the ingredients?",
                "intent": "product_guidance",
                "journey": None,
                "resulting_action": "continue_conversation",
                "selected_product_id": None,
                "requires_human": False,
            },
            # Turn 3: Notes consent, does not claim contact info exists, asks for email/phone
            {
                "text": "Thanks, d-Mac. I’ve noted that you’d like follow-up once the full Therapeutic Body Butter ingredients are confirmed. To have the team reach out to you, what email address or phone number should they use?",
                "intent": "product_guidance",
                "journey": None,
                "resulting_action": "continue_conversation",
                "selected_product_id": None,
                "requires_human": False,
            },
            # Turn 4: Continues with task-bound focus, asks for contact method
            {
                "text": "Thanks, d-Mac! Please provide your preferred email address or phone number so our team can follow up with you directly regarding the Therapeutic Body Butter ingredients.",
                "intent": "product_guidance",
                "journey": None,
                "resulting_action": "continue_conversation",
                "selected_product_id": None,
                "requires_human": False,
            },
        ]

        model = ConversationRepairModel(model_responses)
        runtime = self.make_runtime(model)
        cid = f"conv_regression_{uuid4().hex[:12]}"

        # Turn 1
        r1 = runtime.turn(self.request(cid, "What are the ingredients in your body butter"))
        self.assertTrue(r1["success"])
        task1 = r1["active_task"]
        self.assertEqual(task1["active_entity"], "Therapeutic Body Butter")
        self.assertEqual(task1["active_request"], "verified ingredient list")
        self.assertEqual(task1["task_state"], "UNRESOLVED")

        # Turn 2
        r2 = runtime.turn(self.request(cid, "My name is d-Mac, and yes please confirm the ingredients if you can"))
        self.assertTrue(r2["success"])
        task2 = r2["active_task"]
        self.assertEqual(task2["customer_name"], "d-Mac")
        self.assertTrue(task2["follow_up_requested"])
        self.assertIsNone(task2["contact_email"])
        self.assertIsNone(task2["contact_phone"])

        # Turn 3
        r3 = runtime.turn(self.request(cid, "Yes please"))
        self.assertTrue(r3["success"])
        task3 = r3["active_task"]
        self.assertEqual(task3["customer_name"], "d-Mac")

        # Turn 4
        r4 = runtime.turn(self.request(cid, "Sure"))
        self.assertTrue(r4["success"])
        task4 = r4["active_task"]
        resp4 = r4["response"]

        # Assertions on Turn 4 outcome
        self.assertEqual(task4["active_entity"], "Therapeutic Body Butter")
        self.assertEqual(task4["active_request"], "verified ingredient list")
        self.assertEqual(task4["task_state"], "UNRESOLVED")
        self.assertEqual(task4["customer_name"], "d-Mac")
        self.assertTrue(task4["follow_up_requested"])
        self.assertTrue(task4["follow_up_consent"])
        self.assertIsNone(task4["contact_email"])
        self.assertIsNone(task4["contact_phone"])
        self.assertEqual(task4["crm_write_state"], "NOT_ATTEMPTED")
        self.assertEqual(task4["human_followup_state"], "NOT_CREATED")

        # Content assertions
        self.assertEqual(resp4["resulting_action"], "continue_conversation")
        self.assertNotEqual(resp4["resulting_action"], "legacy_guided_flow")
        self.assertNotIn("GUIDED MODE", resp4["text"])
        self.assertNotIn("CONSUMER WELLNESS", resp4["text"])
        self.assertNotIn("Are you comparing a topical, oil, or bundle?", resp4["text"])
        self.assertIn("d-Mac", resp4["text"])
        self.assertIn("Therapeutic Body Butter", resp4["text"])

    # =========================================================================
    # 15 ADDITIONAL REQUIRED TEST CASES
    # =========================================================================

    def test_case_01_name_only_no_email_or_phone(self):
        """Case 1: Name only, no email or phone. Budly recognizes the name but does not claim usable contact details exist."""
        validator = ProductionResponseValidator()
        session_data = type("SessionMock", (), {
            "crm_write_state": "NOT_ATTEMPTED",
            "human_followup_state": "NOT_CREATED",
            "customer_email": None,
            "contact_phone": None,
            "task_state": "UNRESOLVED",
            "active_entity": "Therapeutic Body Butter",
        })()
        
        # Claiming we have contact info when no phone or email exists must be rejected
        bad_payload = {
            "text": "Thanks, d-Mac! I've noted your contact information and interest for our records.",
            "intent": "product_guidance",
            "journey": None,
            "resulting_action": "continue_conversation",
            "selected_product_id": None,
            "requires_human": False,
        }
        valid, reasons = validator.validate(bad_payload, {}, session=session_data)
        self.assertFalse(valid)
        self.assertIn("unsupported_action_claim", reasons)

    def test_case_02_verified_email_from_prechat_form(self):
        """Case 2: Verified email from approved pre-chat form. Budly may use the verified email state without asking again."""
        runtime = self.make_runtime()
        cid = f"conv_prechat_{uuid4().hex[:12]}"
        req = self.request(
            cid,
            "What are the ingredients in your body butter",
            active_task={
                "customer_name": "Alice",
                "contact_email": "alice@example.com",
                "task_state": "UNRESOLVED",
            },
        )
        res = runtime.turn(req)
        self.assertTrue(res["success"])
        self.assertEqual(res["active_task"]["customer_name"], "Alice")
        self.assertEqual(res["active_task"]["contact_email"], "alice@example.com")

    def test_case_03_crm_followup_write_succeeds(self):
        """Case 3: CRM/follow-up write succeeds. Budly may truthfully confirm it."""
        validator = ProductionResponseValidator()
        session_data = type("SessionMock", (), {
            "crm_write_state": "SUCCESS",
            "human_followup_state": "CREATED",
            "customer_email": "dmac@example.com",
            "contact_phone": None,
            "task_state": "UNRESOLVED",
            "active_entity": "Therapeutic Body Butter",
        })()
        payload = {
            "text": "Thanks, d-Mac! I've noted your contact information and flagged your request for the team.",
            "intent": "product_guidance",
            "journey": None,
            "resulting_action": "continue_conversation",
            "selected_product_id": None,
            "requires_human": False,
        }
        valid, reasons = validator.validate(payload, {"crm_write_state": "SUCCESS", "human_followup_state": "CREATED"}, session=session_data)
        self.assertTrue(valid)

    def test_case_04_crm_followup_write_fails(self):
        """Case 4: CRM/follow-up write fails. Budly does not claim success."""
        validator = ProductionResponseValidator()
        session_data = type("SessionMock", (), {
            "crm_write_state": "FAILED",
            "human_followup_state": "FAILED",
            "customer_email": "dmac@example.com",
            "contact_phone": None,
            "task_state": "UNRESOLVED",
            "active_entity": "Therapeutic Body Butter",
        })()
        payload = {
            "text": "Thanks, d-Mac! I saved that and flagged your request for the team.",
            "intent": "product_guidance",
            "journey": None,
            "resulting_action": "continue_conversation",
            "selected_product_id": None,
            "requires_human": False,
        }
        valid, reasons = validator.validate(payload, {"crm_write_state": "FAILED"}, session=session_data)
        self.assertFalse(valid)
        self.assertIn("unsupported_action_claim", reasons)

    def test_case_05_runtime_healthy_throughout(self):
        """Case 5: Runtime healthy throughout. No unexpected guided fallback."""
        runtime = self.make_runtime()
        cid = f"conv_healthy_{uuid4().hex[:12]}"
        res = runtime.turn(self.request(cid, "What is the price of the body butter?"))
        self.assertTrue(res["success"])
        self.assertEqual(res["response"]["resulting_action"], "continue_conversation")
        self.assertNotEqual(res["response"]["resulting_action"], "legacy_guided_flow")

    def test_case_06_runtime_fails_mid_conversation(self):
        """Case 6: Runtime fails mid-conversation. Context-preserving safe fallback."""
        model = ConversationRepairModel(default_behavior="timeout")
        runtime = self.make_runtime(model)
        cid = f"conv_midfail_{uuid4().hex[:12]}"
        # Set active task first
        session = runtime.sessions.acquire(cid)
        session.active_entity = "Therapeutic Body Butter"
        session.active_request = "verified ingredient list"
        session.task_state = "UNRESOLVED"
        runtime.sessions.record(cid, session, "What are the ingredients?", "I don't have them yet.")

        res = runtime.turn(self.request(cid, "Sure"))
        self.assertTrue(res["success"])
        text = res["response"]["text"]
        self.assertIn("Therapeutic Body Butter", text)
        self.assertIn("verified ingredient list", text)
        self.assertEqual(res["response"]["resulting_action"], "continue_conversation")
        self.assertNotIn("GUIDED MODE", text)

    def test_case_07_fallback_activates_active_task_intact(self):
        """Case 7: Fallback activates. Active task remains intact."""
        model = ConversationRepairModel(default_behavior="connection_error")
        runtime = self.make_runtime(model)
        cid = f"conv_fallback_{uuid4().hex[:12]}"

        res = runtime.turn(self.request(cid, "Hello", active_task={
            "active_entity": "Therapeutic Body Butter",
            "active_request": "verified ingredient list",
            "task_state": "UNRESOLVED",
        }))
        self.assertEqual(res["active_task"]["active_entity"], "Therapeutic Body Butter")
        self.assertEqual(res["active_task"]["active_request"], "verified ingredient list")
        self.assertEqual(res["active_task"]["task_state"], "UNRESOLVED")

    def test_case_08_customer_explicitly_changes_topic(self):
        """Case 8: Customer explicitly changes topic. Task transition occurs cleanly."""
        runtime = self.make_runtime()
        cid = f"conv_topic_{uuid4().hex[:12]}"
        # Establish active task on body butter
        r1 = runtime.turn(self.request(cid, "What are the ingredients in your body butter?"))
        self.assertEqual(r1["active_task"]["task_state"], "UNRESOLVED")

        # Explicitly switch to culinary cannabis course
        r2 = runtime.turn(self.request(cid, "Instead of that, let's talk about something else. Tell me about the culinary cannabis course."))
        self.assertEqual(r2["active_task"]["task_state"], "SUPERSEDED")

    def test_case_09_customer_refuses_follow_up(self):
        """Case 9: Customer refuses follow-up. No follow-up task created."""
        runtime = self.make_runtime()
        cid = f"conv_refuse_{uuid4().hex[:12]}"
        r1 = runtime.turn(self.request(cid, "What are the ingredients in your body butter"))
        r2 = runtime.turn(self.request(cid, "My name is d-Mac, and yes please confirm the ingredients if you can"))
        session = runtime.sessions.acquire(cid)
        runtime.sessions.record(cid, session, "Sure", "Would you like the team to contact you?")

        res = runtime.turn(self.request(cid, "No thanks, please don't follow up"))
        self.assertFalse(res["active_task"]["follow_up_consent"])
        session = runtime.sessions.acquire(cid)
        self.assertEqual(session.follow_up_permission, "denied")

    def test_case_10_customer_revokes_consent(self):
        """Case 10: Customer revokes consent. Follow-up stops."""
        runtime = self.make_runtime()
        cid = f"conv_revoke_{uuid4().hex[:12]}"
        r1 = runtime.turn(self.request(cid, "What are the ingredients in your body butter"))
        r2 = runtime.turn(self.request(cid, "My name is d-Mac, and yes please confirm the ingredients if you can"))

        res = runtime.turn(self.request(cid, "Cancel that and do not contact me or save anything"))
        self.assertFalse(res["active_task"]["follow_up_consent"])
        self.assertEqual(res["active_task"]["task_state"], "CANCELLED")
        session = runtime.sessions.acquire(cid)
        self.assertEqual(session.crm_context_consent, "denied")
        self.assertEqual(session.follow_up_permission, "denied")

    def test_case_11_customer_asks_for_human(self):
        """Case 11: Customer asks for a human. Human support route offered/preserved."""
        model = ConversationRepairModel(responses=[{
            "text": "I will connect you with a team member who can help.",
            "intent": "support",
            "journey": "support",
            "resulting_action": "human_handoff",
            "selected_product_id": None,
            "requires_human": True,
        }])
        runtime = self.make_runtime(model)
        cid = f"conv_human_{uuid4().hex[:12]}"
        res = runtime.turn(self.request(cid, "Can I speak to a real person?", deterministic_context={"outcome": "human_review", "journey": "support"}))
        self.assertTrue(res["response"]["requires_human"])
        self.assertEqual(res["response"]["resulting_action"], "human_handoff")

    def test_case_12_generic_journey_classifier_active_task_wins(self):
        """Case 12: Generic journey classifier recognizes Consumer Wellness while a specific active task exists. Active task wins."""
        runtime = self.make_runtime()
        cid = f"conv_task_wins_{uuid4().hex[:12]}"

        # Turn passes deterministic context with wellness journey, but active task is UNRESOLVED
        res = runtime.turn(self.request(cid, "Sure", active_task={
            "active_entity": "Therapeutic Body Butter",
            "active_request": "verified ingredient list",
            "task_state": "UNRESOLVED",
        }, deterministic_context={"journey": "wellness", "outcome": "conversation"}))
        self.assertEqual(res["active_task"]["active_entity"], "Therapeutic Body Butter")
        self.assertEqual(res["active_task"]["task_state"], "UNRESOLVED")

    def test_case_13_internal_routing_labels_rejected(self):
        """Case 13: Internal routing labels. Zero internal labels displayed to customer."""
        validator = ProductionResponseValidator()
        session_data = type("SessionMock", (), {
            "crm_write_state": "NOT_ATTEMPTED",
            "human_followup_state": "NOT_CREATED",
            "customer_email": None,
            "contact_phone": None,
            "task_state": "UNRESOLVED",
            "active_entity": "Therapeutic Body Butter",
        })()

        for bad_label in ["GUIDED MODE", "CONSUMER WELLNESS", "HUMAN REVIEW"]:
            payload = {
                "text": f"{bad_label}\n\nI’m currently operating in guided mode.",
                "intent": "product_guidance",
                "journey": None,
                "resulting_action": "continue_conversation",
                "selected_product_id": None,
                "requires_human": False,
            }
            valid, reasons = validator.validate(payload, {}, session=session_data)
            self.assertFalse(valid, f"Expected validator to reject label disclosure: {bad_label}")
            self.assertIn("internal_label_disclosure", reasons)

    def test_case_14_duplicate_followup_request(self):
        """Case 14: Duplicate follow-up request. No duplicate business action if already recorded."""
        runtime = self.make_runtime()
        cid = f"conv_dup_{uuid4().hex[:12]}"

        res = runtime.turn(self.request(cid, "Please confirm the ingredients", active_task={
            "active_entity": "Therapeutic Body Butter",
            "active_request": "verified ingredient list",
            "task_state": "UNRESOLVED",
            "crm_write_state": "SUCCESS",
            "human_followup_state": "CREATED",
            "follow_up_requested": True,
            "follow_up_consent": True,
        }))
        self.assertEqual(res["active_task"]["crm_write_state"], "SUCCESS")
        self.assertEqual(res["active_task"]["human_followup_state"], "CREATED")

    def test_case_15_missing_product_knowledge_no_guessing(self):
        """Case 15: Missing product knowledge. No guessing."""
        validator = ProductionResponseValidator()
        session_data = type("SessionMock", (), {
            "crm_write_state": "NOT_ATTEMPTED",
            "human_followup_state": "NOT_CREATED",
            "customer_email": None,
            "contact_phone": None,
            "task_state": "UNRESOLVED",
            "active_entity": "Therapeutic Body Butter",
        })()
        
        # If model hallucinates ingredients for Therapeutic Body Butter, validator rejects it
        bad_payload = {
            "text": "The Therapeutic Body Butter ingredients include shea butter, cocoa butter, and jojoba oil.",
            "intent": "product_guidance",
            "journey": None,
            "resulting_action": "continue_conversation",
            "selected_product_id": None,
            "requires_human": False,
        }
        valid, reasons = validator.validate(bad_payload, {}, session=session_data)
        self.assertFalse(valid)
        self.assertIn("unverified_ingredient_claim", reasons)

    def test_case_16_body_butter_knowledge_retrieval(self):
        """Case 16: Rich product description retrieval for Therapeutic Body Butter.
        Verifies knowledge adapter returns published Woo description naming cocoa, kokum, shea, coconut oil,
        hemp seed oil, CBD distillate, price $75, and canonical URL.
        """
        runtime = self.make_runtime()
        from src.budly_runtime.tool_gateway import AdapterContext
        ctx = AdapterContext("What are the ingredients in your body butter", "product_catalog", 5, frozenset({"Public"}), "req1", "corr1")
        results = runtime.knowledge.retrieve(ctx)
        self.assertTrue(len(results) > 0)
        match = next((r for r in results if "Therapeutic Body Butter" in r.get("title", "") or "therapeutic-body-butter" in r.get("title", "").lower()), None)
        self.assertIsNotNone(match)
        content = match["content"].lower()
        self.assertIn("cocoa", content)
        self.assertIn("kokum", content)
        self.assertIn("shea", content)
        self.assertIn("coconut", content)
        self.assertIn("hemp seed", content)
        self.assertIn("cbd distillate", content)
        self.assertIn("https://cccultivate.com/product/therapeutic-body-butter/", match["canonical_url"])

    def test_case_17_distinguish_product_description_from_complete_inci(self):
        """Case 17: Distinguishing product description ingredients vs complete INCI formulation.
        Validator allows ingredients listed in description but blocks claims that it is 'complete' or unlisted ingredients.
        """
        validator = ProductionResponseValidator()
        session_data = type("SessionMock", (), {
            "crm_write_state": "NOT_ATTEMPTED",
            "human_followup_state": "NOT_CREATED",
            "customer_email": None,
            "contact_phone": None,
            "task_state": "UNRESOLVED",
            "active_entity": "Therapeutic Body Butter",
        })()

        # Valid: Product description listed ingredients
        good_payload = {
            "text": "The product description lists cocoa, kokum, and shea butters, coconut and hemp seed oils, and CBD distillate.",
            "intent": "product_guidance",
            "journey": None,
            "resulting_action": "continue_conversation",
            "selected_product_id": None,
            "requires_human": False,
        }
        valid, reasons = validator.validate(good_payload, {}, session=session_data)
        self.assertTrue(valid, f"Expected good_payload to pass, got: {reasons}")

        # Invalid: Claiming complete ingredient list / formulation
        complete_claim = {
            "text": "The complete ingredient list for Therapeutic Body Butter is cocoa butter, shea butter, coconut oil, and CBD distillate.",
            "intent": "product_guidance",
            "journey": None,
            "resulting_action": "continue_conversation",
            "selected_product_id": None,
            "requires_human": False,
        }
        valid, reasons = validator.validate(complete_claim, {}, session=session_data)
        self.assertFalse(valid)
        self.assertIn("unverified_ingredient_claim", reasons)

        # Invalid: Hallucinated / unverified ingredient (e.g. aloe, lavender, jojoba)
        hallucinated = {
            "text": "Therapeutic Body Butter contains lavender and aloe vera.",
            "intent": "product_guidance",
            "journey": None,
            "resulting_action": "continue_conversation",
            "selected_product_id": None,
            "requires_human": False,
        }
        valid, reasons = validator.validate(hallucinated, {}, session=session_data)
        self.assertFalse(valid)
        self.assertIn("unverified_ingredient_claim", reasons)

    def test_case_18_contact_truth_consent_not_contact_info(self):
        """Case 18: Contact truth: Name only + consent does NOT claim contact info exists; prompts for email/phone."""
        runtime = self.make_runtime()
        cid = f"conv_contact_truth_{uuid4().hex[:12]}"
        # Turn 1
        r1 = runtime.turn(self.request(cid, "What are the ingredients in your body butter"))
        # Turn 2: Name provided
        r2 = runtime.turn(self.request(cid, "My name is d-Mac, please confirm them"))
        # Turn 3: Consent provided
        r3 = runtime.turn(self.request(cid, "Yes please"))
        task = r3["active_task"]
        self.assertEqual(task["customer_name"], "d-Mac")
        self.assertTrue(task["follow_up_consent"])
        self.assertIsNone(task["contact_email"])
        self.assertIsNone(task["contact_phone"])
        self.assertEqual(task["action_truth_state"], "CONSENT_CAPTURED")

        # Validator rejects false claim that contact info is on file
        validator = ProductionResponseValidator()
        session = runtime.sessions.acquire(cid)
        bad_response = {
            "text": "Thanks, d-Mac. I’ve noted your contact information and interest in the Therapeutic Body Butter for the team records.",
            "intent": "product_guidance",
            "journey": None,
            "resulting_action": "continue_conversation",
            "selected_product_id": None,
            "requires_human": False,
        }
        valid, reasons = validator.validate(bad_response, {}, session=session)
        self.assertFalse(valid)
        self.assertIn("unsupported_contact_claim", reasons)

    def test_case_19_follow_up_subject_bound_to_active_task(self):
        """Case 19: Follow-up subject bound to Therapeutic Body Butter (blocks class schedules / unrelated topics)."""
        runtime = self.make_runtime()
        cid = f"conv_fubound_{uuid4().hex[:12]}"
        r1 = runtime.turn(self.request(cid, "What are the ingredients in your body butter"))
        self.assertEqual(r1["active_task"]["follow_up_subject"], "Therapeutic Body Butter ingredient information")

        session = runtime.sessions.acquire(cid)
        self.assertEqual(session.follow_up_subject, "Therapeutic Body Butter ingredient information")

        # Validator blocks class schedule contamination
        validator = ProductionResponseValidator()
        contaminated_response = {
            "text": "Would you also like the team to contact you when new class schedules or updates are added?",
            "intent": "product_guidance",
            "journey": None,
            "resulting_action": "continue_conversation",
            "selected_product_id": None,
            "requires_human": False,
        }
        valid, reasons = validator.validate(contaminated_response, {}, session=session)
        self.assertFalse(valid)
        self.assertIn("followup_topic_contamination", reasons)

    def test_case_20_action_truth_state_lifecycle(self):
        """Case 20: Action truth states: INITIAL -> CONSENT_CAPTURED -> CONTACT_CHANNEL_CAPTURED -> REQUEST_PERSISTED."""
        runtime = self.make_runtime()
        cid = f"conv_lifecycle_{uuid4().hex[:12]}"
        # Turn 1: Initial inquiry
        r1 = runtime.turn(self.request(cid, "What are the ingredients in your body butter"))
        self.assertEqual(r1["active_task"]["action_truth_state"], "INITIAL")

        # Turn 2: Name + consent
        r2 = runtime.turn(self.request(cid, "My name is d-Mac, please confirm the ingredients"))
        r3 = runtime.turn(self.request(cid, "Yes please"))
        self.assertEqual(r3["active_task"]["action_truth_state"], "CONSENT_CAPTURED")

        # Turn 4: Contact channel provided
        r4 = runtime.turn(self.request(cid, "You can email me at dmac@example.com"))
        self.assertEqual(r4["active_task"]["action_truth_state"], "CONTACT_CHANNEL_CAPTURED")
        self.assertEqual(r4["active_task"]["contact_email"], "dmac@example.com")

        # If CRM write is performed successfully
        session = runtime.sessions.acquire(cid)
        session.crm_write_state = "SUCCESS"
        session.action_truth_state = "REQUEST_PERSISTED"
        runtime.sessions.record(cid, session, "dmac@example.com", "Saved")
        r5 = runtime.turn(self.request(cid, "Thanks"))
        self.assertEqual(r5["active_task"]["action_truth_state"], "REQUEST_PERSISTED")

    def test_case_21_ecosystem_retrieval_approved_sources(self):
        """Case 21: Ecosystem retrieval across approved sources (WooCommerce, policies, courses, books, memberships)."""
        runtime = self.make_runtime()
        from src.budly_runtime.tool_gateway import AdapterContext

        # 1. Product (WooCommerce / CCSS)
        ctx_prod = AdapterContext("body butter", "product_catalog", 5, frozenset({"Public"}), "req1", "corr1")
        res_prod = runtime.knowledge.retrieve(ctx_prod)
        self.assertTrue(any("Body Butter" in r.get("title", "") for r in res_prod))

        # 2. Policies
        ctx_pol = AdapterContext("refund policy cancellation", "customer_policy", 5, frozenset({"Public"}), "req2", "corr2")
        res_pol = runtime.knowledge.retrieve(ctx_pol)
        self.assertTrue(len(res_pol) > 0)
        self.assertTrue(any(any(k in r.get("title", "").lower() for k in ["polic", "refund", "order", "return"]) for r in res_pol))

        # 3. Education / Courses
        ctx_edu = AdapterContext("Infused Basics culinary cannabis course", "educational", 5, frozenset({"Public"}), "req3", "corr3")
        res_edu = runtime.knowledge.retrieve(ctx_edu)
        self.assertTrue(len(res_edu) > 0)

        # 4. Botanical / Books
        ctx_book = AdapterContext("Botanical Collection", "educational", 5, frozenset({"Public"}), "req4", "corr4")
        res_book = runtime.knowledge.retrieve(ctx_book)
        self.assertTrue(len(res_book) > 0)

        # 5. Memberships
        ctx_mem = AdapterContext("Silver Legend Gold Legend OG", "membership", 5, frozenset({"Public"}), "req5", "corr5")
        res_mem = runtime.knowledge.retrieve(ctx_mem)
        self.assertTrue(len(res_mem) > 0)

    def test_case_22_publication_and_access_filters(self):
        """Case 22: Publication/access filters (Public vs Authenticated vs Entitlement-Protected)."""
        runtime = self.make_runtime()
        from src.budly_runtime.tool_gateway import AdapterContext

        # Public query with Public access
        ctx_pub = AdapterContext("privacy policy", "customer_policy", 5, frozenset({"Public"}), "req1", "corr1")
        res_pub = runtime.knowledge.retrieve(ctx_pub)
        self.assertTrue(all(r.get("classification") == "Public" for r in res_pub))

        # Private or draft items are never included in self._items for public retrieval
        for item in runtime.knowledge._items:
            self.assertIn(item.get("classification"), {"Public", "Authenticated", "Entitlement-Protected"})
            self.assertNotIn(item.get("status", "").lower(), {"draft", "trash", "private"})

    def test_case_23_unknown_source_fact_vs_retrieval_failure(self):
        """Case 23: Differentiating UNKNOWN_SOURCE_FACT vs RETRIEVAL_FAILURE.
        When fact is absent from approved source -> UNKNOWN_SOURCE_FACT (Budly truthfully acknowledges lack of verified info).
        When knowledge adapter encounters internal error/failure -> RETRIEVAL_FAILURE (raises error/safe fallback, does not claim business lacks info).
        """
        runtime = self.make_runtime()
        from src.budly_runtime.tool_gateway import AdapterContext, ToolHealth

        # UNKNOWN_SOURCE_FACT: Query for completely non-existent entity returns empty list
        ctx_unknown = AdapterContext("xyz_nonexistent_widget_99999", "product_catalog", 5, frozenset({"Public"}), "req1", "corr1")
        results = runtime.knowledge.retrieve(ctx_unknown)
        self.assertEqual(len(results), 0)

        # RETRIEVAL_FAILURE: Adapter unhealthy / broken raises RuntimeError
        runtime.knowledge.state = ToolHealth.UNAVAILABLE
        with self.assertRaises(RuntimeError) as cm:
            runtime.knowledge.retrieve(ctx_unknown)
        self.assertIn("approved knowledge source unavailable", str(cm.exception))


if __name__ == "__main__":
    unittest.main()

