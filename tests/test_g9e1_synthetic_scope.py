import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.budly_runtime.affiliate.synthetic_scope import (
    DurableScopeAudit,
    PAYOUT_GATE,
    SYNTHETIC_CLASSIFICATION,
    ScopeRequest,
    SyntheticScopeGuard,
    SyntheticScopeRecord,
)


class G9E1SyntheticScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.audit = DurableScopeAudit(Path(self.tmp.name) / "scope-audit.sqlite3")
        self.scope = SyntheticScopeRecord(
            scope_id="g9e-scope-a", classification=SYNTHETIC_CLASSIFICATION,
            wordpress_user_id=990001, affiliate_id="affiliate-a-uuid", affiliate_code="AFF-990001",
            referral_token="G9ESYNTH990001", destination_key="SYNTH-WELLNESS",
            campaign_id="G9E-SYNTH-CAMPAIGN-001", event_id="G9E-SYNTH-EVENT-001",
            order_id="G9E-SYNTH-ORDER-001", expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        self.on = {
            "affiliate_portal_enabled": True, "affiliate_referral_enabled": True,
            "affiliate_attribution_enabled": True, "affiliate_commission_processing_enabled": True,
            PAYOUT_GATE: False,
        }

    def tearDown(self):
        self.audit.connection.close()
        self.tmp.cleanup()

    def guard(self, gates=None, scope="default"):
        return SyntheticScopeGuard(gates if gates is not None else self.on, self.scope if scope == "default" else scope, self.audit)

    def portal(self, **changes):
        values = dict(operation="portal", actor="wp:990001", wordpress_user_id=990001,
                      affiliate_id="affiliate-a-uuid", affiliate_code="AFF-990001")
        values.update(changes)
        return ScopeRequest(**values)

    def referral(self, **changes):
        values = dict(operation="referral", actor="service:g9e", affiliate_id="affiliate-a-uuid",
                      affiliate_code="AFF-990001", referral_token="G9ESYNTH990001",
                      destination_key="SYNTH-WELLNESS", campaign_id="G9E-SYNTH-CAMPAIGN-001",
                      trusted_event_classification=SYNTHETIC_CLASSIFICATION)
        values.update(changes)
        return ScopeRequest(**values)

    def event(self, operation="attribution", **changes):
        values = dict(operation=operation, actor="service:g9e", affiliate_id="affiliate-a-uuid",
                      affiliate_code="AFF-990001", event_id="G9E-SYNTH-EVENT-001",
                      order_id="G9E-SYNTH-ORDER-001", trusted_event_classification=SYNTHETIC_CLASSIFICATION,
                      upstream_attribution_allowed=operation == "commission")
        values.update(changes)
        return ScopeRequest(**values)

    def test_01_gate_off_plus_synthetic_denied(self):
        gates = dict(self.on); gates["affiliate_portal_enabled"] = False
        self.assertFalse(self.guard(gates).authorize(self.portal()).allowed)

    def test_02_gate_on_valid_synthetic_allowed(self):
        self.assertTrue(self.guard().authorize(self.portal()).allowed)

    def test_03_gate_on_normal_user_denied(self):
        self.assertFalse(self.guard().authorize(self.portal(wordpress_user_id=123)).allowed)

    def test_04_gate_on_unmapped_user_denied(self):
        self.assertFalse(self.guard(scope=None).authorize(self.portal()).allowed)

    def test_05_gate_on_wrong_affiliate_denied(self):
        self.assertFalse(self.guard().authorize(self.portal(affiliate_id="affiliate-b-uuid", affiliate_code="AFF-990002")).allowed)

    def test_06_synthetic_referral_allowed(self):
        self.assertTrue(self.guard().authorize(self.referral()).allowed)

    def test_07_real_referral_denied_without_record_creation_authority(self):
        result = self.guard().authorize(self.referral(destination_key="REAL-PRODUCT", trusted_event_classification=None))
        self.assertFalse(result.allowed)

    def test_08_synthetic_revenue_event_allowed_for_attribution(self):
        self.assertTrue(self.guard().authorize(self.event()).allowed)

    def test_09_real_revenue_event_denied(self):
        self.assertFalse(self.guard().authorize(self.event(event_id="wc-order-123", order_id="123", trusted_event_classification=None)).allowed)

    def test_10_synthetic_attribution_allowed(self):
        self.assertTrue(self.guard().authorize(self.event()).allowed)

    def test_11_non_synthetic_attribution_denied(self):
        self.assertFalse(self.guard().authorize(self.event(trusted_event_classification="PRODUCTION")).allowed)

    def test_12_synthetic_commission_allowed(self):
        self.assertTrue(self.guard().authorize(self.event("commission")).allowed)

    def test_13_real_commission_denied(self):
        self.assertFalse(self.guard().authorize(self.event("commission", event_id="real", order_id="real", trusted_event_classification=None, upstream_attribution_allowed=False)).allowed)

    def test_14_payout_gate_must_remain_off(self):
        gates = dict(self.on); gates[PAYOUT_GATE] = True
        with self.assertRaisesRegex(ValueError, "PAYOUT_GATE_MUST_REMAIN_OFF"):
            self.guard(gates)
        self.assertFalse(self.guard().payout_allowed())

    def test_15_duplicate_synthetic_replay_is_idempotent(self):
        request = self.event(idempotency_key="g9e-event-replay-001")
        first = self.guard().authorize(request)
        second = self.guard().authorize(request)
        self.assertTrue(first.allowed)
        self.assertTrue(second.allowed)
        self.assertTrue(second.idempotent_replay)
        self.assertEqual(len(self.audit.rows()), 1)

    def test_16_denials_are_durably_audited_and_immutable(self):
        self.guard().authorize(self.portal(wordpress_user_id=123))
        rows = self.audit.rows()
        self.assertEqual(rows[0]["decision"], "DENY")
        self.assertEqual(rows[0]["scope_result"], "NO_MATCH")
        self.assertTrue(rows[0]["occurred_at"])
        with self.assertRaisesRegex(sqlite3.DatabaseError, "SYNTHETIC_SCOPE_AUDIT_IMMUTABLE"):
            self.audit.connection.execute("update synthetic_scope_audit set reason='changed'")

    def test_owner_and_synthetic_b_are_denied_affiliate_portal(self):
        self.assertFalse(self.guard().authorize(self.portal(actor="owner:d-mac", wordpress_user_id=1)).allowed)
        self.assertFalse(self.guard().authorize(self.portal(actor="wp:990002", wordpress_user_id=990002, affiliate_id="affiliate-b-uuid", affiliate_code="AFF-990002")).allowed)

    def test_audit_does_not_store_request_secrets_or_cookies(self):
        self.guard().authorize(self.referral())
        evidence = self.audit.rows()[0]["evidence_json"]
        self.assertNotIn("cookie", evidence.lower())
        self.assertNotIn("invitation", evidence.lower())
        self.assertNotIn("credential", evidence.lower())

    def test_expired_authoritative_scope_is_denied(self):
        expired = SyntheticScopeRecord(**{**self.scope.__dict__, "expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)})
        self.assertFalse(self.guard(scope=expired).authorize(self.portal()).allowed)


if __name__ == "__main__":
    unittest.main()
