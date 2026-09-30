from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from src.budly_runtime.affiliate.engine import AffiliateEngine, DomainError, FeatureFlags

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


class AffiliatePhaseEAcceptance(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = AffiliateEngine(FeatureFlags(True, True, True, True, False))

    def affiliate(self, email="affiliate@example.test", affiliate_class="STANDARD", verified=False):
        app = self.engine.submit_application({"applicant_email": email, "desired_affiliate_class": affiliate_class}, "app:" + email)
        aff = self.engine.review_application(app["id"], True, "PROJECT_OWNER")
        self.engine.accept_terms(aff.id, "terms-v1", "sha256:test")
        aff = self.engine.activate(aff.id, "terms-v1")
        if verified:
            aff = replace(aff, payout_profile_status="VERIFIED", tax_profile_status="VERIFIED")
            self.engine.affiliates[aff.id] = aff
        return aff

    def referral(self, aff, method="LINK", when=T0, campaign_id=None):
        if method == "QR":
            self.engine.register_qr("AQR-7M4D9X2KQP", aff.id)
            return self.engine.create_referral(aff.id, method, when, campaign_id, "AQR-7M4D9X2KQP")
        return self.engine.create_referral(aff.id, method, when, campaign_id)

    @staticmethod
    def product(product_id="P1", eligibility="ELIGIBLE", product_class="PHYSICAL", **extra):
        return {"product_id": product_id, "affiliate_eligibility": eligibility, "product_class": product_class, **extra}

    def rule(self, **overrides):
        values = {"rule_code": "RULE-" + str(len(self.engine.rules) + 1), "rate": "0.20", "precedence": 6}
        values.update(overrides)
        return self.engine.add_rule(**values)

    def decision(self, aff, order="O1", method="LINK", when=T0):
        ref = self.referral(aff, method, when)
        return self.engine.resolve_attribution(order, [ref.id], at=when + timedelta(hours=1))

    @staticmethod
    def event(event_id="REV-1", order_id="O1", total="100", refunded="0", product_id="P1", occurred=T0):
        return {"event_id": event_id, "order_id": order_id, "currency": "USD", "occurred_at": occurred.isoformat(), "line_items": [{"line_id": "L1", "product_id": product_id, "merchandise_total": total, "discount": "0", "refunded": refunded}]}

    def make_commission(self, total="250", aff=None, order="O1", event_id="REV-1", rate="0.20"):
        aff = aff or self.affiliate(verified=True)
        decision = self.decision(aff, order)
        self.rule(rate=rate)
        result = self.engine.process_revenue_event(self.event(event_id, order, total), decision, {"P1": self.product()})
        return aff, self.engine.commissions[result["commission_id"]]

    def test_01_valid_standard_application(self):
        app = self.engine.submit_application({"applicant_email": "a@example.test", "desired_affiliate_class": "STANDARD"}, "k1")
        self.assertEqual("SUBMITTED", app["status"])

    def test_02_declined_application_no_entitlement(self):
        app = self.engine.submit_application({"applicant_email": "a@example.test"}, "k1")
        self.assertIsNone(self.engine.review_application(app["id"], False))
        self.assertFalse(self.engine.affiliates)

    def test_03_approved_without_terms_not_active(self):
        app = self.engine.submit_application({"applicant_email": "a@example.test"}, "k1")
        aff = self.engine.review_application(app["id"], True)
        self.assertEqual("APPROVED_PENDING_TERMS", aff.status)
        with self.assertRaisesRegex(DomainError, "TERMS_REQUIRED"):
            self.engine.activate(aff.id, "terms-v1")

    def test_04_active_referral_gets_30_day_context(self):
        ref = self.referral(self.affiliate())
        self.assertEqual(timedelta(days=30), ref.expires_at - ref.occurred_at)

    def test_05_expired_referral_unattributed(self):
        aff = self.affiliate(); ref = self.referral(aff)
        decision = self.engine.resolve_attribution("O1", [ref.id], at=T0 + timedelta(days=31))
        self.assertEqual("UNATTRIBUTED", decision.status)

    def test_06_last_qualified_affiliate_wins(self):
        a = self.affiliate("a@example.test"); b = self.affiliate("b@example.test")
        ra = self.referral(a, when=T0); rb = self.referral(b, when=T0 + timedelta(hours=1))
        self.assertEqual(b.id, self.engine.resolve_attribution("O1", [ra.id, rb.id], at=T0 + timedelta(hours=2)).affiliate_id)

    def test_07_link_then_qr_qr_wins(self):
        a = self.affiliate("a@example.test"); b = self.affiliate("b@example.test")
        ra = self.referral(a, when=T0); rb = self.referral(b, "QR", T0 + timedelta(hours=1))
        decision = self.engine.resolve_attribution("O1", [ra.id, rb.id], at=T0 + timedelta(hours=2))
        self.assertEqual((b.id, "QR_REFERRAL"), (decision.affiliate_id, decision.method))

    def test_08_coupon_overrides_link(self):
        a = self.affiliate("a@example.test"); b = self.affiliate("b@example.test"); ref = self.referral(a)
        self.engine.add_coupon("SAVE", b.id)
        self.assertEqual(b.id, self.engine.resolve_attribution("O1", [ref.id], ["SAVE"], T0 + timedelta(hours=1)).affiliate_id)

    def test_09_invalid_coupon_preserves_referral(self):
        aff = self.affiliate(); ref = self.referral(aff)
        self.assertEqual(aff.id, self.engine.resolve_attribution("O1", [ref.id], ["NOPE"], T0 + timedelta(hours=1)).affiliate_id)

    def test_10_suspended_affiliate_cannot_refer(self):
        aff = self.affiliate(); self.engine.set_status(aff.id, "SUSPENDED")
        with self.assertRaisesRegex(DomainError, "INVALID_AFFILIATE_STATE"):
            self.referral(self.engine.affiliates[aff.id])

    def test_11_excluded_product_zero_commission(self):
        aff = self.affiliate(); decision = self.decision(aff); self.rule()
        result = self.engine.process_revenue_event(self.event(), decision, {"P1": self.product(eligibility="EXCLUDED")})
        self.assertEqual("NO_COMMISSION", result["status"])

    def test_12_mixed_cart_only_eligible_lines(self):
        aff = self.affiliate(); decision = self.decision(aff); self.rule()
        event = self.event(); event["line_items"].append({"line_id":"L2","product_id":"P2","merchandise_total":"900","discount":"0","refunded":"0"})
        result = self.engine.process_revenue_event(event, decision, {"P1":self.product(),"P2":self.product("P2","EXCLUDED")})
        self.assertEqual("20.000000", result["amount"])

    def test_13_digital_configured_rule(self):
        aff = self.affiliate(); decision = self.decision(aff); self.rule(rate="0.30", product_class="DIGITAL", precedence=5)
        result = self.engine.process_revenue_event(self.event(), decision, {"P1":self.product(product_class="DIGITAL")})
        self.assertEqual("30.000000", result["amount"])

    def test_14_physical_configured_rule(self):
        _, commission = self.make_commission(total="100", rate="0.20")
        self.assertEqual(Decimal("20.000000"), commission.amount)

    def test_15_product_override_precedence(self):
        aff = self.affiliate(); decision = self.decision(aff)
        self.rule(rate="0.10"); self.rule(rate="0.25", product_id="P1", precedence=1)
        result = self.engine.process_revenue_event(self.event(), decision, {"P1":self.product()})
        self.assertEqual("25.000000", result["amount"])

    def test_16_no_rule_quarantines(self):
        aff = self.affiliate(); decision = self.decision(aff)
        result = self.engine.process_revenue_event(self.event(), decision, {"P1":self.product()})
        self.assertEqual(("QUARANTINED", "MISSING_COMMISSION_RULE"), (result["status"], result["reason"]))

    def test_17_discounted_item_uses_collected_merchandise(self):
        aff = self.affiliate(); decision = self.decision(aff); self.rule()
        event = self.event(); event["line_items"][0]["discount"] = "25"
        result = self.engine.process_revenue_event(event, decision, {"P1":self.product()})
        self.assertEqual("15.000000", result["amount"])

    def test_18_full_refund_full_reversal(self):
        _, commission = self.make_commission(total="100")
        self.engine.process_refund(commission.id, "REF-1", "100")
        self.assertEqual(("REVERSED", Decimal("0.000000")), (commission.status, commission.balance))

    def test_19_partial_refund_exact_recalculation(self):
        _, commission = self.make_commission(total="100")
        self.engine.process_refund(commission.id, "REF-1", "25")
        self.assertEqual(Decimal("15.000000"), commission.balance)

    def test_20_post_paid_refund_is_debit_without_deleting_paid_event(self):
        _, commission = self.make_commission(); commission.status = "PAID"
        before = len(self.engine.ledger); self.engine.process_refund(commission.id, "REF-1", "50")
        self.assertEqual("COMMISSION_ADJUSTMENT_DEBIT", self.engine.ledger[-1].event_type)
        self.assertEqual(before + 1, len(self.engine.ledger))

    def test_21_duplicate_revenue_one_commission(self):
        aff = self.affiliate(); decision = self.decision(aff); self.rule(); event = self.event()
        a = self.engine.process_revenue_event(event, decision, {"P1":self.product()}); b = self.engine.process_revenue_event(event, decision, {"P1":self.product()})
        self.assertEqual(a["commission_id"], b["commission_id"]); self.assertEqual(1, len(self.engine.commissions))

    def test_22_duplicate_refund_one_reversal(self):
        _, commission = self.make_commission(); self.engine.process_refund(commission.id,"REF-1","25"); count=len(self.engine.ledger)
        self.engine.process_refund(commission.id,"REF-1","25"); self.assertEqual(count,len(self.engine.ledger))

    def test_23_self_referral_is_review_flag(self):
        aff=self.affiliate(); risk=self.engine.flag_self_referral(aff.id,"O1",{"email_match":True})
        self.assertEqual(("SELF_REFERRAL_SUSPECTED","OPEN"),(risk["risk_type"],risk["review_status"]))

    def test_24_budly_assist_does_not_erase_affiliate(self):
        aff=self.affiliate(); decision=self.decision(aff); self.assertEqual(aff.id,decision.affiliate_id)
        self.assertIn("intake_dispute",self.engine.budly_context(aff.id)["allowed_operations"])

    def test_25_existing_customer_may_have_new_valid_referral(self):
        aff=self.affiliate(); ref=self.referral(aff)
        self.assertEqual("ATTRIBUTED",self.engine.resolve_attribution("O1",[ref.id],at=T0+timedelta(hours=1),client_affiliate_id="customer-known").status)

    def test_26_dispute_within_window_open(self):
        aff,commission=self.make_commission(); dispute=self.engine.submit_dispute(aff.id,commission.id,T0,T0+timedelta(days=29))
        self.assertTrue(dispute["within_standard_window"]); self.assertEqual("OPEN",dispute["status"])

    def test_27_late_dispute_human_path(self):
        aff,commission=self.make_commission(); dispute=self.engine.submit_dispute(aff.id,commission.id,T0,T0+timedelta(days=31))
        self.assertFalse(dispute["within_standard_window"]); self.assertEqual("OPEN",dispute["status"])

    def test_28_balance_49_99_not_included(self):
        aff,commission=self.make_commission(total="249.95"); self.engine.mature(commission.id,T0+timedelta(days=31))
        self.assertEqual([],self.engine.prepare_payout_batch("USD")["items"])

    def test_29_balance_50_exactly_included(self):
        aff,commission=self.make_commission(total="250"); self.engine.mature(commission.id,T0+timedelta(days=31))
        self.assertEqual("50.000000",self.engine.prepare_payout_batch("USD")["items"][0]["amount"])

    def test_30_balance_over_50_included(self):
        aff,commission=self.make_commission(total="300"); self.engine.mature(commission.id,T0+timedelta(days=31))
        self.assertEqual(1,len(self.engine.prepare_payout_batch("USD")["items"]))

    def test_31_compliance_hold_blocks_payout(self):
        aff,commission=self.make_commission(); commission.compliance_hold=True
        self.assertEqual("PENDING",self.engine.mature(commission.id,T0+timedelta(days=31)).status)

    def test_32_provider_failure_does_not_mark_paid(self):
        aff,commission=self.make_commission(); self.engine.mature(commission.id,T0+timedelta(days=31)); batch=self.engine.prepare_payout_batch("USD"); self.engine.approve_payout_batch(batch["id"],"FINANCIAL_APPROVER")
        self.engine.reconcile_provider_callback(batch["id"],"CB1",True,False); self.assertEqual("PAYABLE",commission.status)

    def test_33_provider_success_marks_paid_with_ledger(self):
        aff,commission=self.make_commission(); self.engine.mature(commission.id,T0+timedelta(days=31)); batch=self.engine.prepare_payout_batch("USD"); self.engine.approve_payout_batch(batch["id"],"FINANCIAL_APPROVER")
        self.engine.reconcile_provider_callback(batch["id"],"CB1",True,True); self.assertEqual("PAID",commission.status); self.assertEqual("COMMISSION_PAID",self.engine.ledger[-1].event_type)

    def test_34_manual_override_preserves_original(self):
        a=self.affiliate("a@example.test"); b=self.affiliate("b@example.test"); original=self.decision(a)
        replacement=self.engine.manual_override(original,b.id,"AFFILIATE_OPERATOR"); self.assertIn(original.id,self.engine.decisions); self.assertEqual(b.id,replacement.affiliate_id)

    def test_35_client_affiliate_metadata_is_not_authority(self):
        a=self.affiliate("a@example.test"); b=self.affiliate("b@example.test"); ref=self.referral(a)
        decision=self.engine.resolve_attribution("O1",[ref.id],at=T0+timedelta(hours=1),client_affiliate_id=b.id); self.assertEqual(a.id,decision.affiliate_id)

    def test_36_missing_attribution_is_auditable_unattributed(self):
        decision=self.engine.resolve_attribution("O1",[],at=T0); self.assertEqual(("UNATTRIBUTED","NO_VALID_ATTRIBUTION"),(decision.status,decision.reason_code))

    def test_37_quarantine_reprocessing_is_exactly_once(self):
        aff=self.affiliate(); decision=self.decision(aff); event=self.event(); first=self.engine.process_revenue_event(event,decision,{"P1":self.product()}); second=self.engine.process_revenue_event(event,decision,{"P1":self.product()})
        self.assertEqual("QUARANTINED",first["status"]); self.assertTrue(second["idempotent_replay"]); self.assertEqual(1,len(self.engine.quarantine))

    def test_38_rls_cross_affiliate_policy_present(self):
        sql=(Path("migrations/affiliate_mvp/001_affiliate_mvp_foundation.sql").read_text(encoding="utf-8"))
        self.assertIn("id=(select private.bros_affiliate_id())",sql)

    def test_39_affiliate_pii_access_not_granted(self):
        sql=Path("migrations/affiliate_mvp/001_affiliate_mvp_foundation.sql").read_text(encoding="utf-8")
        self.assertNotIn("grant select on public.revenue_events to authenticated",sql.lower())

    def test_40_complete_controlled_round_trip(self):
        aff,commission=self.make_commission(); self.engine.mature(commission.id,T0+timedelta(days=31)); batch=self.engine.prepare_payout_batch("USD"); self.engine.approve_payout_batch(batch["id"],"PROJECT_OWNER")
        self.engine.flags.affiliate_payout_submission_enabled=True; self.engine.submit_payout_batch(batch["id"]); self.engine.reconcile_provider_callback(batch["id"],"CB1",True,True)
        self.assertEqual("PAID",commission.status); self.assertGreaterEqual(len(self.engine.ledger),3)

    def test_41_unknown_ccss_eligibility_fails_closed(self):
        aff=self.affiliate(); self.rule()
        with self.assertRaisesRegex(DomainError,"UNKNOWN_OR_MISSING_CCSS_ELIGIBILITY"): self.engine.resolve_rule(aff,self.product(eligibility="MAYBE"),None)

    def test_42_missing_ccss_eligibility_fails_closed(self):
        aff=self.affiliate(); self.rule()
        with self.assertRaisesRegex(DomainError,"UNKNOWN_OR_MISSING_CCSS_ELIGIBILITY"): self.engine.resolve_rule(aff,{"product_id":"P1","product_class":"PHYSICAL"},None)

    def test_43_duplicate_payout_callback_is_idempotent(self):
        aff,commission=self.make_commission(); self.engine.mature(commission.id,T0+timedelta(days=31)); batch=self.engine.prepare_payout_batch("USD"); self.engine.reconcile_provider_callback(batch["id"],"CB1",True,True); count=len(self.engine.ledger)
        replay=self.engine.reconcile_provider_callback(batch["id"],"CB1",True,True); self.assertTrue(replay["idempotent_replay"]); self.assertEqual(count,len(self.engine.ledger))

    def test_44_equal_priority_rules_quarantine(self):
        aff=self.affiliate(); decision=self.decision(aff); self.rule(); self.rule()
        result=self.engine.process_revenue_event(self.event(),decision,{"P1":self.product()}); self.assertEqual("CONFLICTING_COMMISSION_RULES",result["reason"])

    def test_45_invalid_affiliate_id_format(self):
        self.assertIsNone(__import__("re").match(r"^AFF-[0-9]{6}$","AFF-1"))

    def test_46_qr_affiliate_mismatch(self):
        a=self.affiliate("a@example.test"); b=self.affiliate("b@example.test"); self.engine.register_qr("AQR-7M4D9X2KQP",a.id)
        with self.assertRaisesRegex(DomainError,"QR_AFFILIATE_MISMATCH"): self.engine.create_referral(b.id,"QR",T0,None,"AQR-7M4D9X2KQP")

    def test_47_expired_campaign_not_attributed(self):
        aff=self.affiliate(); self.engine.register_campaign("C1",T0,T0+timedelta(days=1)); ref=self.referral(aff,when=T0,campaign_id="C1")
        self.assertEqual("UNATTRIBUTED",self.engine.resolve_attribution("O1",[ref.id],at=T0+timedelta(days=2)).status)

    def test_48_invalid_payout_callback_authenticity(self):
        batch={"id":"B1","status":"SUBMITTED","items":[]}; self.engine.payout_batches.append(batch)
        with self.assertRaisesRegex(DomainError,"INVALID_SIGNATURE"): self.engine.reconcile_provider_callback("B1","CB1",False,True)

    def test_49_impossible_state_transition(self):
        _,commission=self.make_commission(); commission.status="PAID"
        with self.assertRaisesRegex(DomainError,"IMPOSSIBLE_STATE_TRANSITION"): self.engine.mature(commission.id,T0+timedelta(days=31))

    def test_50_disabled_affiliate_system_preserves_normal_sale(self):
        engine=AffiliateEngine(); decision=type("Decision",(),{"status":"UNATTRIBUTED","affiliate_id":None,"correlation_id":"c"})()
        result=engine.process_revenue_event(self.event(),decision,{})
        self.assertEqual("PRESERVED_PROCESSING_DISABLED",result["status"])


if __name__ == "__main__":
    unittest.main()
