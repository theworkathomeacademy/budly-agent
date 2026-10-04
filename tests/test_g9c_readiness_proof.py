"""Deterministic acceptance evidence for G9C readiness R1-R15."""

from __future__ import annotations

import json
import hashlib
import unittest
from dataclasses import replace
from pathlib import Path

from src.budly_runtime.affiliate.engine import AffiliateEngine, DomainError, FeatureFlags
from src.budly_runtime.affiliate.g9c_readiness import (
    G9COperatingExperience,
    PublicAffiliateKnowledge,
    ReadinessActor,
    ReadinessError,
    governed_test_facts,
    run_synthetic_round_trip,
)


class G9CReadinessProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_synthetic_round_trip()
        cls.service_result = cls.result

    def test_r1_public_budly_affiliate_ux(self):
        knowledge = PublicAffiliateKnowledge(governed_test_facts())
        questions = [
            "What is your affiliate program?", "Who can become an affiliate?",
            "How much can affiliates earn?", "What products can I promote?",
            "Do I need a certain number of followers?", "Do you have recurring commissions?",
            "How do I apply?", "Are applications open?", "What can Budly help me with?",
        ]
        answers = [knowledge.answer(q) for q in questions]
        self.assertTrue(all(a["program_state"] == "PRIVATE_PILOT" for a in answers))
        self.assertTrue(all(a["public_applications_open"] is False for a in answers))
        self.assertFalse(any(a.get("private_token_exposed") for a in answers))
        compensation = knowledge.answer("How much can affiliates earn?")
        self.assertEqual(compensation["rates"], governed_test_facts()["rates"])

    def test_r2_private_invitation_application(self):
        app = self.result["application"]
        self.assertEqual(app["classification"], "TEST_SYNTHETIC_NON_PRODUCTION_PERSON")
        self.assertEqual(app["status"], "PENDING_REVIEW")

    def test_r3_owner_application_review_ux(self):
        owner_view = self.result["owner_view"]
        self.assertEqual(owner_view["applications"][0]["status"], "APPROVED_PENDING_TERMS")
        self.assertTrue(any(e["event_type"] == "APPLICATION_DECIDED" for e in owner_view["audit"]))

    def test_r4_affiliate_authenticated_ux(self):
        view = self.result["affiliate_view"]
        self.assertEqual(view["identity"]["status"], "ACTIVE")
        self.assertIn("canonical_referral_token", view["assets"])
        self.assertIn("commissions", view["performance"])

    def test_r5_referral_asset_creation(self):
        assets = self.result["activation"]["assets"]
        self.assertRegex(assets["canonical_referral_path"], r"^/r/[A-Z0-9]+$")
        self.assertEqual(assets["current_vanity_path"], "/go/g9c-synthetic")
        self.assertTrue(assets["qr_asset"].startswith("synthetic://qr/"))

    def test_r6_ccss_product_and_rate_retrieval(self):
        products = self.result["affiliate_view"]["products"]
        self.assertTrue(products)
        self.assertTrue(all(p["affiliate_eligibility"] == "AFFILIATE_ELIGIBLE" for p in products))
        self.assertEqual(products[0]["rate"], "0.30000000")

    def test_r7_referral_event(self):
        self.assertTrue(self.result["referral_id"])
        self.assertEqual(self.result["affiliate_view"]["performance"]["referral_events"], 1)

    def test_r8_attribution(self):
        decision = self.result["attribution"]
        self.assertEqual(decision["status"], "ATTRIBUTED")
        self.assertEqual(decision["reason_code"], "LAST_QUALIFIED_REFERRAL")

    def test_r9_commission_creation(self):
        commission = self.result["commission"]
        self.assertEqual(commission["amount"], "60.000000")
        self.assertEqual(commission["pending_state"], "PENDING")

    def test_r10_hold_and_maturity(self):
        commission = self.result["commission"]
        self.assertEqual(commission["pending_state"], "PENDING")
        self.assertEqual(commission["final_state"], "PAYABLE")

    def test_r11_owner_commission_visibility(self):
        commissions = self.result["owner_view"]["commissions"]
        self.assertEqual(len(commissions), 1)
        self.assertEqual(commissions[0]["amount"], "60.000000")
        self.assertEqual(commissions[0]["status"], "PAYABLE")

    def test_r12_payout_readiness_visibility_without_submission(self):
        self.assertEqual(self.result["payout_readiness"]["status"], "UNDER_REVIEW")
        self.assertEqual(self.result["payout_readiness"]["items"][0]["amount"], "60.000000")
        self.assertEqual(self.result["payout_readiness"]["items"][0]["status"], "PREPARED")
        self.assertFalse(self.result["payout_submitted"])
        self.assertFalse(self.result["owner_view"]["payout_readiness"]["actual_payout_authorized"])

    def test_r13_role_and_privacy_isolation(self):
        view = self.result["affiliate_view"]
        self.assertNotIn("applications", view)
        self.assertNotIn("audit", view)
        self.assertIn("authorize_payout", view["support"]["prohibited"])
        service = G9COperatingExperience(AffiliateEngine(), PublicAffiliateKnowledge(governed_test_facts()))
        with self.assertRaises(ReadinessError) as anonymous:
            service._require_affiliate_self(ReadinessActor("anon", "ANONYMOUS"), "aff-a")
        self.assertEqual(anonymous.exception.code, "AUTHENTICATION_REQUIRED")
        with self.assertRaises(ReadinessError) as cross_tenant:
            service._require_affiliate_self(ReadinessActor("user-a", "AFFILIATE", "aff-a", True), "aff-b")
        self.assertEqual(cross_tenant.exception.code, "TENANT_ISOLATION_VIOLATION")
        with self.assertRaises(ReadinessError) as owner_control:
            service.owner_experience(ReadinessActor("user-a", "AFFILIATE", "aff-a", True))
        self.assertEqual(owner_control.exception.code, "OWNER_AUTHORIZATION_REQUIRED")

    def test_r14_audit_trail(self):
        audit = self.result["owner_view"]["audit"]
        self.assertGreaterEqual(len(audit), 4)
        self.assertEqual([e["sequence"] for e in audit], list(range(1, len(audit) + 1)))
        self.assertTrue(all(e["actor_id"] and e["occurred_at"] and e["reason"] and e["evidence_ref"] for e in audit))

    def test_r15_complete_synthetic_round_trip(self):
        self.assertEqual(self.result["classification"], "TEST_SYNTHETIC_NON_PRODUCTION_PERSON")
        self.assertEqual(self.result["production_feature_flags_touched"], 0)
        self.assertEqual(self.result["external_calls"], 0)
        self.assertFalse(self.result["payout_submitted"])

    def test_production_feature_flags_remain_off(self):
        flags = json.loads(Path("config/affiliate/feature-flags.json").read_text(encoding="utf-8"))
        gate_names = [key for key in flags if key.startswith("affiliate_") and key.endswith("_enabled")]
        self.assertEqual(len(gate_names), 5)
        self.assertTrue(all(flags[name] is False for name in gate_names))

    def test_budly_cannot_self_authorize_financial_operations(self):
        prohibited = self.result["affiliate_view"]["support"]["prohibited"]
        self.assertIn("change_commission_rate", prohibited)
        self.assertIn("rewrite_attribution", prohibited)
        self.assertIn("authorize_payout", prohibited)

    def test_payout_submission_is_disabled_in_synthetic_proof(self):
        engine = AffiliateEngine(FeatureFlags(True, True, True, True, False))
        engine.payout_batches.append({"id": "synthetic", "human_approved": True, "status": "APPROVED", "items": []})
        with self.assertRaises(DomainError) as ctx:
            engine.submit_payout_batch("synthetic")
        self.assertEqual(ctx.exception.code, "PAYOUT_SUBMISSION_DISABLED")

    def test_preserved_outreach_packages_are_hash_verified_and_not_sendable(self):
        manifest = json.loads(Path("docs/affiliate/pilot/g9c-outreach-packages-v1.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["package_state"], "READY_COPY")
        self.assertEqual(manifest["authorization_state"], "NOT_AUTHORIZED_FOR_SEND")
        self.assertEqual(manifest["real_outreach_count"], 0)
        self.assertEqual(len(manifest["candidates"]), 5)
        for candidate in manifest["candidates"]:
            email_hash = hashlib.sha256(candidate["email_copy"].encode("utf-8")).hexdigest()
            dm_hash = hashlib.sha256(candidate["dm_copy"].encode("utf-8")).hexdigest()
            self.assertEqual(candidate["email_message_hash"], email_hash)
            self.assertEqual(candidate["dm_message_hash"], dm_hash)
            self.assertEqual(candidate["send_state"], "NOT_AUTHORIZED_FOR_SEND")


if __name__ == "__main__":
    unittest.main()
