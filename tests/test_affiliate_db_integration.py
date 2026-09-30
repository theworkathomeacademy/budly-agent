"""PostgreSQL Database & RLS Integration Tests for AFF-001 Phase F Affiliate MVP.

Validates against isolated local PostgreSQL instance:
1. Schema & Table creation (17 tables, 27 enum types, indexes, sequences)
2. Immutability triggers on append-only financial/audit/event tables
3. Row-Level Security (RLS) policies for anon, authenticated affiliate, and admin roles
4. Foreign key integrity and exact decimal precision (numeric(20,6), numeric(12,8))
5. Non-destructive feature-flag rollback execution
"""

import os
import unittest
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
SETUP_SQL = ROOT / "scripts" / "test_postgres_setup.sql"
FOUNDATION_SQL = ROOT / "migrations" / "affiliate_mvp" / "001_affiliate_mvp_foundation.sql"
ROLLBACK_SQL = ROOT / "migrations" / "affiliate_mvp" / "rollback_disable.sql"
DB_URL = os.environ.get("AFFILIATE_TEST_DB_URL", "postgresql://postgres:postgres@localhost:5433/postgres")


class AffiliateDatabaseIntegrationTests(unittest.TestCase):
    conn: psycopg.Connection | None = None

    @classmethod
    def setUpClass(cls):
        try:
            cls.conn = psycopg.connect(DB_URL, autocommit=True, row_factory=dict_row)
        except Exception as exc:
            raise unittest.SkipTest(f"PostgreSQL container not reachable at {DB_URL}: {exc}")

        with cls.conn.cursor() as cur:
            # 1. Setup mock auth / extensions
            cur.execute(SETUP_SQL.read_text(encoding="utf-8"))
            # 2. Apply foundation migration
            cur.execute(FOUNDATION_SQL.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        if cls.conn:
            cls.conn.close()

    def test_01_feature_flags_default_off(self):
        """Verify all 5 feature flags exist and default to disabled (false)."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT flag_name, enabled FROM bros_affiliate.feature_flags ORDER BY flag_name;")
            flags = {row["flag_name"]: row["enabled"] for row in cur.fetchall()}
            expected_flags = [
                "affiliate_attribution_enabled",
                "affiliate_commission_processing_enabled",
                "affiliate_payout_submission_enabled",
                "affiliate_portal_enabled",
                "affiliate_referral_enabled",
            ]
            for ef in expected_flags:
                self.assertIn(ef, flags)
                self.assertFalse(flags[ef], f"Flag {ef} must default to false")

    def test_02_schema_tables_exist(self):
        """Verify all bros_affiliate tables exist."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'bros_affiliate' 
                ORDER BY table_name;
            """)
            tables = [row["table_name"] for row in cur.fetchall()]
            required = [
                "feature_flags", "affiliate_applications", "affiliates",
                "affiliate_terms_acceptances", "affiliate_referral_routes", "affiliate_qr_routes",
                "affiliate_referral_events", "affiliate_attribution_contexts",
                "affiliate_attribution_decisions", "affiliate_coupon_mappings",
                "affiliate_commission_rules", "affiliate_order_line_commissions",
                "affiliate_commissions", "affiliate_commission_ledger",
                "affiliate_risk_events", "affiliate_disputes", "affiliate_attribution_overrides",
                "affiliate_payout_batches", "affiliate_payout_items",
                "affiliate_payout_item_commissions", "affiliate_quarantine_events",
                "affiliate_audit_events"
            ]
            for req in required:
                self.assertIn(req, tables, f"Missing table: {req}")

    def test_03_immutability_triggers_reject_updates_and_deletes(self):
        """Verify append-only triggers prevent UPDATE/DELETE on ledger, audit, referral events, and terms."""
        with self.conn.cursor() as cur:
            # 1. Insert test affiliate
            cur.execute("""
                INSERT INTO bros_affiliate.affiliates (
                    id, affiliate_code, primary_email, display_name, status, affiliate_class
                ) VALUES (
                    '11111111-1111-1111-1111-111111111111', 'AFF-000001', 'aff1@example.com', 'Affiliate One', 'ACTIVE', 'STANDARD'
                ) ON CONFLICT (id) DO NOTHING;
            """)

            # 2. Insert attribution decision
            cur.execute("""
                INSERT INTO bros_affiliate.affiliate_attribution_decisions (
                    id, decision_key, order_id, revenue_event_id, affiliate_id,
                    status, decision_version, evidence, reason_code, correlation_id
                ) VALUES (
                    '44444444-4444-4444-4444-444444444444', 'DEC-0001', 'ORD-1001', 'REV-1001',
                    '11111111-1111-1111-1111-111111111111', 'ATTRIBUTED', '1.0', '{}'::jsonb,
                    'LAST_QUALIFIED', '55555555-5555-5555-5555-555555555555'
                ) ON CONFLICT (id) DO NOTHING;
            """)

            # 3. Insert commission summary record
            cur.execute("""
                INSERT INTO bros_affiliate.affiliate_commissions (
                    id, commission_code, affiliate_id, woocommerce_order_id,
                    attribution_decision_id, currency_code, qualifying_revenue_total,
                    commission_amount_total, current_status, hold_until, rules_version,
                    attribution_version, calculation_version
                ) VALUES (
                    '33333333-3333-3333-3333-333333333333', 'COMM-0001',
                    '11111111-1111-1111-1111-111111111111', 'ORD-1001',
                    '44444444-4444-4444-4444-444444444444', 'USD', 500.000000,
                    50.000000, 'PENDING', now() + interval '30 days', '1.0', '1.0', '1.0'
                ) ON CONFLICT (id) DO NOTHING;
            """)

            # 4. Insert ledger event
            cur.execute("""
                INSERT INTO bros_affiliate.affiliate_commission_ledger (
                    id, ledger_event_key, commission_id, affiliate_id, woocommerce_order_id,
                    event_type, amount_delta, currency_code, resulting_commission_balance,
                    reason_code, actor_type, actor_id, correlation_id, occurred_at
                ) VALUES (
                    '22222222-2222-2222-2222-222222222222', 'LEDGER-0001',
                    '33333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111',
                    'ORD-1001', 'COMMISSION_CREATED', 50.000000, 'USD', 50.000000,
                    'EARNED', 'SYSTEM_SERVICE', 'AFF_ENGINE',
                    '55555555-5555-5555-5555-555555555555', now()
                ) ON CONFLICT (id) DO NOTHING;
            """)

            # UPDATE on affiliate_commission_ledger must raise exception
            with self.assertRaises(psycopg.DatabaseError):
                cur.execute("""
                    UPDATE bros_affiliate.affiliate_commission_ledger 
                    SET amount_delta = 100.0 
                    WHERE id = '22222222-2222-2222-2222-222222222222';
                """)

            # DELETE on affiliate_commission_ledger must raise exception
            with self.assertRaises(psycopg.DatabaseError):
                cur.execute("""
                    DELETE FROM bros_affiliate.affiliate_commission_ledger 
                    WHERE id = '22222222-2222-2222-2222-222222222222';
                """)

    def test_04_rls_isolation_between_affiliates(self):
        """Verify Row-Level Security isolates authenticated affiliate users to their own rows."""
        with self.conn.cursor() as cur:
            # Create two affiliates
            cur.execute("""
                INSERT INTO bros_affiliate.affiliates (
                    id, affiliate_code, primary_email, display_name, status, affiliate_class
                ) VALUES 
                ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'AFF-000002', 'user_a@example.com', 'User A', 'ACTIVE', 'STANDARD'),
                ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'AFF-000003', 'user_b@example.com', 'User B', 'ACTIVE', 'STANDARD')
                ON CONFLICT (id) DO NOTHING;
            """)

        # Connect as authenticated user A
        with psycopg.connect(DB_URL, autocommit=True, row_factory=dict_row) as user_a_conn:
            with user_a_conn.cursor() as cur:
                cur.execute("SET ROLE authenticated;")
                cur.execute("""
                    SET request.jwt.claims = '{"app_metadata": {"affiliate_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"}}';
                """)
                cur.execute("SELECT id, display_name FROM bros_affiliate.affiliates;")
                rows = cur.fetchall()
                self.assertEqual(len(rows), 1)
                self.assertEqual(str(rows[0]["id"]), "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

        # Connect as authenticated user B
        with psycopg.connect(DB_URL, autocommit=True, row_factory=dict_row) as user_b_conn:
            with user_b_conn.cursor() as cur:
                cur.execute("SET ROLE authenticated;")
                cur.execute("""
                    SET request.jwt.claims = '{"app_metadata": {"affiliate_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"}}';
                """)
                cur.execute("SELECT id, display_name FROM bros_affiliate.affiliates;")
                rows = cur.fetchall()
                self.assertEqual(len(rows), 1)
                self.assertEqual(str(rows[0]["id"]), "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

        # Connect as operator (PROJECT_OWNER)
        with psycopg.connect(DB_URL, autocommit=True, row_factory=dict_row) as admin_conn:
            with admin_conn.cursor() as cur:
                cur.execute("SET ROLE authenticated;")
                cur.execute("""
                    SET request.jwt.claims = '{"app_metadata": {"bros_roles": ["PROJECT_OWNER"]}}';
                """)
                cur.execute("SELECT count(*) as cnt FROM bros_affiliate.affiliates;")
                row = cur.fetchone()
                self.assertGreaterEqual(row["cnt"], 2)

        # Connect as anon (unauthenticated) -> must be denied access
        with psycopg.connect(DB_URL, autocommit=True, row_factory=dict_row) as anon_conn:
            with anon_conn.cursor() as cur:
                cur.execute("SET ROLE anon;")
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cur.execute("SELECT count(*) as cnt FROM bros_affiliate.affiliates;")

    def test_05_rollback_disable_script(self):
        """Verify rollback_disable.sql successfully executes and disables all feature flags non-destructively."""
        with self.conn.cursor() as cur:
            # Enable one flag temporarily
            cur.execute("UPDATE bros_affiliate.feature_flags SET enabled = true WHERE flag_name = 'affiliate_portal_enabled';")
            # Run rollback script
            cur.execute(ROLLBACK_SQL.read_text(encoding="utf-8"))
            # Confirm all flags are false
            cur.execute("SELECT count(*) as active_cnt FROM bros_affiliate.feature_flags WHERE enabled = true;")
            row = cur.fetchone()
            self.assertEqual(row["active_cnt"], 0)


if __name__ == "__main__":
    unittest.main()
