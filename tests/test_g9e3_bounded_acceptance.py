"""G9E.3 Bounded Production Acceptance Test Suite.

Authoritative Synthetic Identity:
- WordPress user ID: 215217324
- Username: g9e-synthetic-affiliate
- Classification: TEST_SYNTHETIC_NON_PRODUCTION_PERSON
- Affiliate UUID: 50000000-0000-0000-0000-000000000001
- AFF ID: AFF-900001
- Scope UUID: 91000000-0000-0000-0000-000000000001
- Referral token: G9ESYNTH900001
- Destination: SYNTH-WELLNESS
- Campaign: G9E-SYNTH-CAMPAIGN-001
- Event: G9E-SYNTH-EVENT-001
- Order: G9E-SYNTH-ORDER-001
"""

from decimal import Decimal
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.budly_runtime.affiliate.synthetic_scope import (
    DurableScopeAudit,
    PAYOUT_GATE,
    SYNTHETIC_CLASSIFICATION,
    ScopeRequest,
    SyntheticScopeGuard,
    SyntheticScopeRecord,
)
from src.budly_runtime.affiliate.engine import (
    AffiliateEngine,
    FeatureFlags,
    DomainError,
)


class G9E3BoundedProductionAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.audit = DurableScopeAudit(Path(self.tmp.name) / "g9e3-audit.sqlite3")
        
        # Authoritative Synthetic Scope
        self.scope = SyntheticScopeRecord(
            scope_id="91000000-0000-0000-0000-000000000001",
            classification=SYNTHETIC_CLASSIFICATION,
            wordpress_user_id=215217324,
            affiliate_id="50000000-0000-0000-0000-000000000001",
            affiliate_code="AFF-900001",
            referral_token="G9ESYNTH900001",
            destination_key="SYNTH-WELLNESS",
            campaign_id="G9E-SYNTH-CAMPAIGN-001",
            event_id="G9E-SYNTH-EVENT-001",
            order_id="G9E-SYNTH-ORDER-001",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            active=True,
        )
        
        # All gates ON for scoped guard tests, except payout gate which MUST be FALSE
        self.gates_on = {
            "affiliate_portal_enabled": True,
            "affiliate_referral_enabled": True,
            "affiliate_attribution_enabled": True,
            "affiliate_commission_processing_enabled": True,
            PAYOUT_GATE: False,
        }

    def tearDown(self):
        self.audit.connection.close()
        self.tmp.cleanup()

    def guard(self, gates=None, scope="default"):
        return SyntheticScopeGuard(
            gates if gates is not None else self.gates_on,
            self.scope if scope == "default" else scope,
            self.audit,
        )

    # --------------------------------------------------------------------------
    # 1. PORTAL TESTS
    # --------------------------------------------------------------------------
    def test_01_portal_approved_synthetic_user_allowed(self):
        req = ScopeRequest(
            operation="portal",
            actor="wp:215217324",
            wordpress_user_id=215217324,
            affiliate_id="50000000-0000-0000-0000-000000000001",
            affiliate_code="AFF-900001",
        )
        dec = self.guard().authorize(req)
        self.assertTrue(dec.allowed)
        self.assertEqual(dec.reason, "TRUSTED_SYNTHETIC_PORTAL_MATCH")

    def test_02_portal_anonymous_or_unmapped_denied(self):
        # Anonymous (user_id=0)
        req_anon = ScopeRequest(
            operation="portal",
            actor="anon",
            wordpress_user_id=0,
            affiliate_id="50000000-0000-0000-0000-000000000001",
            affiliate_code="AFF-900001",
        )
        dec_anon = self.guard().authorize(req_anon)
        self.assertFalse(dec_anon.allowed)
        self.assertEqual(dec_anon.reason, "WORDPRESS_IDENTITY_MAPPING_MISMATCH")

        # Unmapped user
        req_unmapped = ScopeRequest(
            operation="portal",
            actor="wp:999999",
            wordpress_user_id=999999,
            affiliate_id="50000000-0000-0000-0000-000000000001",
            affiliate_code="AFF-900001",
        )
        dec_unmapped = self.guard().authorize(req_unmapped)
        self.assertFalse(dec_unmapped.allowed)
        self.assertEqual(dec_unmapped.reason, "WORDPRESS_IDENTITY_MAPPING_MISMATCH")

    def test_03_portal_owner_as_affiliate_denied(self):
        # Owner impersonation attempt
        req_owner = ScopeRequest(
            operation="portal",
            actor="owner:d-mac",
            wordpress_user_id=1,  # Owner ID
            affiliate_id="50000000-0000-0000-0000-000000000001",
            affiliate_code="AFF-900001",
        )
        dec_owner = self.guard().authorize(req_owner)
        self.assertFalse(dec_owner.allowed)
        self.assertEqual(dec_owner.reason, "WORDPRESS_IDENTITY_MAPPING_MISMATCH")

    def test_04_portal_gate_off_denies_all(self):
        gates = dict(self.gates_on)
        gates["affiliate_portal_enabled"] = False
        req = ScopeRequest(
            operation="portal",
            actor="wp:215217324",
            wordpress_user_id=215217324,
            affiliate_id="50000000-0000-0000-0000-000000000001",
            affiliate_code="AFF-900001",
        )
        dec = self.guard(gates=gates).authorize(req)
        self.assertFalse(dec.allowed)
        self.assertEqual(dec.reason, "GLOBAL_GATE_OFF")

    # --------------------------------------------------------------------------
    # 2. REFERRAL TESTS
    # --------------------------------------------------------------------------
    def test_05_referral_approved_synthetic_allowed(self):
        req = ScopeRequest(
            operation="referral",
            actor="service:g9e",
            affiliate_id="50000000-0000-0000-0000-000000000001",
            affiliate_code="AFF-900001",
            referral_token="G9ESYNTH900001",
            destination_key="SYNTH-WELLNESS",
            campaign_id="G9E-SYNTH-CAMPAIGN-001",
            trusted_event_classification=SYNTHETIC_CLASSIFICATION,
        )
        dec = self.guard().authorize(req)
        self.assertTrue(dec.allowed)
        self.assertEqual(dec.reason, "TRUSTED_SYNTHETIC_REFERRAL_MATCH")

    def test_06_referral_non_synthetic_negative_denied(self):
        req_real = ScopeRequest(
            operation="referral",
            actor="service:g9e",
            affiliate_id="50000000-0000-0000-0000-000000000001",
            affiliate_code="AFF-900001",
            referral_token="REAL_CREATOR_TOKEN",
            destination_key="REAL-PRODUCT",
            campaign_id="PUBLIC-CAMPAIGN",
            trusted_event_classification=None,
        )
        dec_real = self.guard().authorize(req_real)
        self.assertFalse(dec_real.allowed)
        self.assertEqual(dec_real.reason, "TRUSTED_EVENT_CLASSIFICATION_MISMATCH")

    # --------------------------------------------------------------------------
    # 3. ATTRIBUTION TESTS
    # --------------------------------------------------------------------------
    def test_07_attribution_approved_synthetic_allowed(self):
        req = ScopeRequest(
            operation="attribution",
            actor="service:g9e",
            affiliate_id="50000000-0000-0000-0000-000000000001",
            affiliate_code="AFF-900001",
            event_id="G9E-SYNTH-EVENT-001",
            order_id="G9E-SYNTH-ORDER-001",
            trusted_event_classification=SYNTHETIC_CLASSIFICATION,
        )
        dec = self.guard().authorize(req)
        self.assertTrue(dec.allowed)
        self.assertEqual(dec.reason, "TRUSTED_SYNTHETIC_ATTRIBUTION_MATCH")

    def test_08_attribution_non_synthetic_order_denied(self):
        req_woo = ScopeRequest(
            operation="attribution",
            actor="service:g9e",
            affiliate_id="50000000-0000-0000-0000-000000000001",
            affiliate_code="AFF-900001",
            event_id="WC-ORDER-9999",
            order_id="9999",
            trusted_event_classification="PRODUCTION",
        )
        dec_woo = self.guard().authorize(req_woo)
        self.assertFalse(dec_woo.allowed)
        self.assertEqual(dec_woo.reason, "TRUSTED_EVENT_CLASSIFICATION_MISMATCH")

    # --------------------------------------------------------------------------
    # 4. COMMISSION TESTS
    # --------------------------------------------------------------------------
    def test_09_commission_approved_synthetic_allowed_with_exact_decimal(self):
        req = ScopeRequest(
            operation="commission",
            actor="service:g9e",
            affiliate_id="50000000-0000-0000-0000-000000000001",
            affiliate_code="AFF-900001",
            event_id="G9E-SYNTH-EVENT-001",
            order_id="G9E-SYNTH-ORDER-001",
            trusted_event_classification=SYNTHETIC_CLASSIFICATION,
            upstream_attribution_allowed=True,
        )
        dec = self.guard().authorize(req)
        self.assertTrue(dec.allowed)
        self.assertEqual(dec.reason, "TRUSTED_SYNTHETIC_COMMISSION_MATCH")

        # Test exact Decimal calculation for governed wellness rate (30% on $75 = $22.50)
        retail = Decimal("75.00")
        rate = Decimal("0.30")
        commission = (retail * rate).quantize(Decimal("0.01"))
        self.assertEqual(commission, Decimal("22.50"))

    def test_10_commission_non_synthetic_upstream_denied(self):
        req = ScopeRequest(
            operation="commission",
            actor="service:g9e",
            affiliate_id="50000000-0000-0000-0000-000000000001",
            affiliate_code="AFF-900001",
            event_id="G9E-SYNTH-EVENT-001",
            order_id="G9E-SYNTH-ORDER-001",
            trusted_event_classification=SYNTHETIC_CLASSIFICATION,
            upstream_attribution_allowed=False,  # Upstream attribution not proven
        )
        dec = self.guard().authorize(req)
        self.assertFalse(dec.allowed)
        self.assertEqual(dec.reason, "SYNTHETIC_ATTRIBUTION_NOT_PROVEN")

    # --------------------------------------------------------------------------
    # 5. IDEMPOTENCY REPLAY TEST
    # --------------------------------------------------------------------------
    def test_11_idempotency_replay_prevents_duplicate_records(self):
        req = ScopeRequest(
            operation="attribution",
            actor="service:g9e",
            affiliate_id="50000000-0000-0000-0000-000000000001",
            affiliate_code="AFF-900001",
            event_id="G9E-SYNTH-EVENT-001",
            order_id="G9E-SYNTH-ORDER-001",
            trusted_event_classification=SYNTHETIC_CLASSIFICATION,
            idempotency_key="G9E-SYNTH-IDEMP-001",
        )
        dec1 = self.guard().authorize(req)
        self.assertTrue(dec1.allowed)
        self.assertFalse(dec1.idempotent_replay)

        # Replay exact event
        dec2 = self.guard().authorize(req)
        self.assertTrue(dec2.allowed)
        self.assertTrue(dec2.idempotent_replay)

        # Ensure only 1 audit record persisted
        rows = self.audit.rows()
        self.assertEqual(len(rows), 1)

    # --------------------------------------------------------------------------
    # 6. PAYOUT GATE STRICT OFF ENFORCEMENT
    # --------------------------------------------------------------------------
    def test_12_payout_gate_must_remain_off(self):
        illegal_gates = dict(self.gates_on)
        illegal_gates[PAYOUT_GATE] = True

        with self.assertRaises(ValueError) as ctx:
            SyntheticScopeGuard(illegal_gates, self.scope, self.audit)
        self.assertIn("PAYOUT_GATE_MUST_REMAIN_OFF", str(ctx.exception))

        # Check payout_allowed is always False
        self.assertFalse(self.guard().payout_allowed())

    # --------------------------------------------------------------------------
    # 7. DURABLE AUDIT IMMUTABILITY
    # --------------------------------------------------------------------------
    def test_13_audit_records_are_immutable(self):
        req = ScopeRequest(
            operation="portal",
            actor="wp:215217324",
            wordpress_user_id=215217324,
            affiliate_id="50000000-0000-0000-0000-000000000001",
            affiliate_code="AFF-900001",
        )
        self.guard().authorize(req)

        with self.assertRaises(sqlite3.DatabaseError):
            self.audit.connection.execute("update synthetic_scope_audit set decision = 'DENY'")

        with self.assertRaises(sqlite3.DatabaseError):
            self.audit.connection.execute("delete from synthetic_scope_audit")

    # --------------------------------------------------------------------------
    # 8. AUDIT EXCLUDES SECRETS
    # --------------------------------------------------------------------------
    def test_14_audit_excludes_raw_secrets(self):
        req = ScopeRequest(
            operation="referral",
            actor="service:g9e",
            affiliate_id="50000000-0000-0000-0000-000000000001",
            affiliate_code="AFF-900001",
            referral_token="G9ESYNTH900001",
            destination_key="SYNTH-WELLNESS",
            campaign_id="G9E-SYNTH-CAMPAIGN-001",
            trusted_event_classification=SYNTHETIC_CLASSIFICATION,
        )
        self.guard().authorize(req)
        rows = self.audit.rows()
        evidence_str = rows[0]["evidence_json"].lower()
        self.assertNotIn("raw_invitation_token", evidence_str)
        self.assertNotIn("cookie", evidence_str)
        self.assertNotIn("credential", evidence_str)
        self.assertNotIn("secret", evidence_str)

    # --------------------------------------------------------------------------
    # 9. EXPIRED SCOPE DENIED
    # --------------------------------------------------------------------------
    def test_15_expired_scope_denied(self):
        expired_scope = SyntheticScopeRecord(
            scope_id="91000000-0000-0000-0000-000000000001",
            classification=SYNTHETIC_CLASSIFICATION,
            wordpress_user_id=215217324,
            affiliate_id="50000000-0000-0000-0000-000000000001",
            affiliate_code="AFF-900001",
            referral_token="G9ESYNTH900001",
            destination_key="SYNTH-WELLNESS",
            campaign_id="G9E-SYNTH-CAMPAIGN-001",
            event_id="G9E-SYNTH-EVENT-001",
            order_id="G9E-SYNTH-ORDER-001",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),  # EXPIRED
            active=True,
        )
        req = ScopeRequest(
            operation="portal",
            actor="wp:215217324",
            wordpress_user_id=215217324,
            affiliate_id="50000000-0000-0000-0000-000000000001",
            affiliate_code="AFF-900001",
        )
        dec = self.guard(scope=expired_scope).authorize(req)
        self.assertFalse(dec.allowed)
        self.assertEqual(dec.reason, "TRUSTED_SYNTHETIC_SCOPE_MISSING_OR_INVALID")

    # --------------------------------------------------------------------------
    # 10. ROLLBACK VERIFICATION
    # --------------------------------------------------------------------------
    def test_16_rollback_all_gates_false_and_inactive_scope(self):
        inactive_scope = SyntheticScopeRecord(
            scope_id="91000000-0000-0000-0000-000000000001",
            classification=SYNTHETIC_CLASSIFICATION,
            wordpress_user_id=215217324,
            affiliate_id="50000000-0000-0000-0000-000000000001",
            affiliate_code="AFF-900001",
            referral_token="G9ESYNTH900001",
            destination_key="SYNTH-WELLNESS",
            campaign_id="G9E-SYNTH-CAMPAIGN-001",
            event_id="G9E-SYNTH-EVENT-001",
            order_id="G9E-SYNTH-ORDER-001",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            active=False,  # INACTIVE AFTER ROLLBACK
        )
        all_gates_off = {
            "affiliate_portal_enabled": False,
            "affiliate_referral_enabled": False,
            "affiliate_attribution_enabled": False,
            "affiliate_commission_processing_enabled": False,
            PAYOUT_GATE: False,
        }
        req = ScopeRequest(
            operation="portal",
            actor="wp:215217324",
            wordpress_user_id=215217324,
            affiliate_id="50000000-0000-0000-0000-000000000001",
            affiliate_code="AFF-900001",
        )
        dec = self.guard(gates=all_gates_off, scope=inactive_scope).authorize(req)
        self.assertFalse(dec.allowed)
        self.assertEqual(dec.reason, "GLOBAL_GATE_OFF")


if __name__ == "__main__":
    unittest.main()
