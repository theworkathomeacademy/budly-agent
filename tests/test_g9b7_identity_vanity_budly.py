"""Acceptance Test Suite for G9B.7A & G9B.7B:
Catalog Policy, Canonical Identity, Referral Tokens, Vanity Links, Preferences, Tenant Isolation & Budly Management.

Proves all 30 required governance and functional test points:
1. Canonical Affiliate ID immutability
2. Canonical token uniqueness
3. Canonical token immutability
4. Instagram-derived initial alias
5. Alias normalization
6. Alias uniqueness
7. Reserved slug rejection
8. Impersonation / conflict rejection
9. Primary alias replacement
10. Historical redirect preservation
11. 30-day cooldown
12. 3-day rollback
13. Third-alias rejection during rollback
14. Alias audit history
15. Canonical attribution through old alias
16. Canonical attribution through new alias
17. Campaign-specific routing
18. QR canonical reconciliation
19. Unified analytics across alias changes
20. Preference create/update
21. Preference audit
22. Affiliate tenant isolation
23. Unauthenticated private-data rejection
24. Unauthorized Affiliate-to-Affiliate lookup rejection
25. Owner-authorized lookup
26. Unknown identity fail closed
27. Ambiguous canonical mapping fail closed
28. Catalog state reconciliation
29. ELIGIBLE_RATE_REQUIRED fail closed
30. Mixed-order line-item commission behavior
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import pytest

from src.budly_runtime.affiliate.identity import (
    CanonicalIdentity,
    IdentityError,
    generate_canonical_id,
    generate_referral_token,
    normalize_slug,
    validate_slug,
)
from src.budly_runtime.affiliate.vanity import VanityLinkManager
from src.budly_runtime.affiliate.preferences import AffiliatePreferenceStore
from src.budly_runtime.affiliate.routing import CanonicalRouter
from src.budly_runtime.affiliate.analytics import AnalyticsEngine
from src.budly_runtime.affiliate.budly_service import (
    AccessControlError,
    ActorContext,
    BudlyAffiliateService,
)
from src.budly_runtime.affiliate.engine import (
    Affiliate,
    AffiliateEngine,
    AttributionDecision,
    Commission,
    DomainError,
    FeatureFlags,
    money,
)
from src.budly_runtime.commercial_snapshot.loader import CommercialSnapshotLoader

ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT / "config" / "commercial_catalog"


@pytest.fixture
def base_environment():
    vanity_mgr = VanityLinkManager()
    pref_store = AffiliatePreferenceStore()
    router = CanonicalRouter(vanity_mgr)
    analytics_eng = AnalyticsEngine()
    budly_svc = BudlyAffiliateService(router, vanity_mgr, pref_store, analytics_eng)

    flags = FeatureFlags(
        affiliate_referral_enabled=True,
        affiliate_attribution_enabled=True,
        affiliate_commission_processing_enabled=True,
        affiliate_portal_enabled=True,
        affiliate_payout_submission_enabled=False,
    )
    engine = AffiliateEngine(flags=flags)

    # Standard rules
    engine.add_rule(
        rule_code="R-BOTANICAL-25",
        rate="0.25000000",
        precedence=10,
        product_class="BOTANICAL_COLLECTION_25",
    )
    engine.add_rule(
        rule_code="R-INFUSED-BASICS-25",
        rate="0.25000000",
        precedence=10,
        product_class="INFUSED_BASICS_25",
    )
    engine.add_rule(
        rule_code="R-LEGENDS-10",
        rate="0.10000000",
        precedence=10,
        product_class="LEGENDS_MEMBERSHIP_10",
    )
    engine.add_rule(
        rule_code="R-WELLNESS-PHYSICAL-30",
        rate="0.30000000",
        precedence=10,
        product_class="WELLNESS_PHYSICAL_30",
    )

    return {
        "vanity": vanity_mgr,
        "preferences": pref_store,
        "router": router,
        "analytics": analytics_eng,
        "budly": budly_svc,
        "engine": engine,
    }


# ---------------------------------------------------------------------------
# Test 1: Canonical Affiliate ID Immutability & Format
# ---------------------------------------------------------------------------
def test_01_canonical_id_format_and_immutability():
    aff_id = generate_canonical_id(123)
    assert aff_id == "AFF-000123"

    identity = CanonicalIdentity(
        affiliate_id=aff_id,
        referral_token="7KQ9M2TX",
        email="tammy@example.com",
        public_display_name="Tammy Pettigrew",
    )
    assert identity.affiliate_id == "AFF-000123"

    with pytest.raises(Exception):
        identity.affiliate_id = "AFF-999999"  # frozen dataclass prevents mutation


# ---------------------------------------------------------------------------
# Test 2: Canonical Token Uniqueness
# ---------------------------------------------------------------------------
def test_02_canonical_token_uniqueness():
    tokens = {generate_referral_token() for _ in range(1000)}
    assert len(tokens) == 1000  # 1000 unique cryptographic tokens


# ---------------------------------------------------------------------------
# Test 3: Canonical Token Immutability
# ---------------------------------------------------------------------------
def test_03_canonical_token_immutability():
    identity = CanonicalIdentity(
        affiliate_id="AFF-000001",
        referral_token="ABCDEF23",
        email="creator@example.com",
        public_display_name="Creator One",
    )
    assert identity.referral_token == "ABCDEF23"
    with pytest.raises(Exception):
        identity.referral_token = "NEWTOKEN99"


# ---------------------------------------------------------------------------
# Test 4: Instagram-Derived Initial Alias
# ---------------------------------------------------------------------------
def test_04_instagram_derived_initial_alias(base_environment):
    vanity = base_environment["vanity"]
    alias = vanity.register_initial_alias(
        affiliate_id="AFF-000001",
        raw_slug="@thecannabiscutie",
    )
    assert alias.slug == "thecannabiscutie"
    assert alias.status == "PRIMARY"
    assert alias.affiliate_id == "AFF-000001"


# ---------------------------------------------------------------------------
# Test 5: Alias Normalization
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("@TheCannabisCutie", "thecannabiscutie"),
        ("  tammy_pettigrew  ", "tammy-pettigrew"),
        ("tammy...cutie", "tammy-cutie"),
        ("@Kathryn.Celestre ", "kathryn-celestre"),
    ],
)
def test_05_alias_normalization(raw, expected):
    assert normalize_slug(raw) == expected


# ---------------------------------------------------------------------------
# Test 6: Alias Uniqueness
# ---------------------------------------------------------------------------
def test_06_alias_uniqueness(base_environment):
    vanity = base_environment["vanity"]
    vanity.register_initial_alias("AFF-000001", "thecannabiscutie")
    with pytest.raises(IdentityError) as exc:
        vanity.register_initial_alias("AFF-000002", "thecannabiscutie")
    assert exc.value.code == "SLUG_ALREADY_CLAIMED"


# ---------------------------------------------------------------------------
# Test 7: Reserved Slug Rejection
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad_slug", ["admin", "api", "checkout", "budly", "shop", "login", "r", "go"])
def test_07_reserved_slug_rejection(bad_slug):
    with pytest.raises(IdentityError) as exc:
        validate_slug(bad_slug)
    assert exc.value.code == "RESERVED_SLUG"


# ---------------------------------------------------------------------------
# Test 8: Impersonation / Conflict Rejection
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("prohibited", ["official-support", "verified-badge", "billing-help"])
def test_08_impersonation_conflict_rejection(prohibited):
    with pytest.raises(IdentityError) as exc:
        validate_slug(prohibited)
    assert exc.value.code in ["PROHIBITED_SLUG_TERM", "RESERVED_SLUG"]


# ---------------------------------------------------------------------------
# Test 9: Primary Alias Replacement
# ---------------------------------------------------------------------------
def test_09_primary_alias_replacement(base_environment):
    vanity = base_environment["vanity"]
    t0 = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    vanity.register_initial_alias("AFF-000001", "thecannabiscutie", now=t0)

    # Update to 'tammy'
    new_alias = vanity.update_vanity_slug("AFF-000001", "tammy", now=t0)
    assert new_alias.slug == "tammy"
    assert new_alias.status == "PRIMARY"
    assert vanity.affiliate_primary["AFF-000001"] == "tammy"


# ---------------------------------------------------------------------------
# Test 10: Historical Redirect Preservation
# ---------------------------------------------------------------------------
def test_10_historical_redirect_preservation(base_environment):
    vanity = base_environment["vanity"]
    t0 = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    vanity.register_initial_alias("AFF-000001", "thecannabiscutie", now=t0)
    vanity.update_vanity_slug("AFF-000001", "tammy", now=t0)

    # Check old slug resolves as HISTORICAL_REDIRECT
    aff_id, status = vanity.resolve_slug("thecannabiscutie")
    assert aff_id == "AFF-000001"
    assert status == "HISTORICAL_REDIRECT"

    # Check new slug resolves as PRIMARY
    aff_id2, status2 = vanity.resolve_slug("tammy")
    assert aff_id2 == "AFF-000001"
    assert status2 == "PRIMARY"


# ---------------------------------------------------------------------------
# Test 11: 30-Day Cooldown Enforcement
# ---------------------------------------------------------------------------
def test_11_thirty_day_cooldown(base_environment):
    vanity = base_environment["vanity"]
    t0 = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    vanity.register_initial_alias("AFF-000001", "thecannabiscutie", now=t0)
    vanity.update_vanity_slug("AFF-000001", "tammy", now=t0)

    # Attempt second edit at Day 10 (cooldown active, outside 3-day rollback)
    t_day10 = t0 + timedelta(days=10)
    with pytest.raises(IdentityError) as exc:
        vanity.update_vanity_slug("AFF-000001", "tammy-p", now=t_day10)
    assert exc.value.code == "COOLDOWN_ACTIVE"

    # Attempt at Day 31 (cooldown complete)
    t_day31 = t0 + timedelta(days=31)
    updated = vanity.update_vanity_slug("AFF-000001", "tammy-p", now=t_day31)
    assert updated.slug == "tammy-p"
    assert updated.status == "PRIMARY"


# ---------------------------------------------------------------------------
# Test 12: 3-Day Rollback Window
# ---------------------------------------------------------------------------
def test_12_three_day_rollback(base_environment):
    vanity = base_environment["vanity"]
    t0 = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    vanity.register_initial_alias("AFF-000001", "thecannabiscutie", now=t0)
    vanity.update_vanity_slug("AFF-000001", "tammy", now=t0)

    # Rollback at Day 2 (within 3-day rollback window)
    t_day2 = t0 + timedelta(days=2)
    reverted = vanity.rollback_vanity_slug("AFF-000001", now=t_day2)
    assert reverted.slug == "thecannabiscutie"
    assert reverted.status == "PRIMARY"
    assert vanity.affiliate_primary["AFF-000001"] == "thecannabiscutie"


# ---------------------------------------------------------------------------
# Test 13: Third-Alias Rejection During Rollback Window
# ---------------------------------------------------------------------------
def test_13_third_alias_rejection_during_rollback(base_environment):
    vanity = base_environment["vanity"]
    t0 = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    vanity.register_initial_alias("AFF-000001", "thecannabiscutie", now=t0)
    vanity.update_vanity_slug("AFF-000001", "tammy", now=t0)

    # Attempt to pick a 3rd slug 'tammy-third' at Day 2 (blocked by cooldown)
    t_day2 = t0 + timedelta(days=2)
    with pytest.raises(IdentityError) as exc:
        vanity.update_vanity_slug("AFF-000001", "tammy-third", now=t_day2)
    assert exc.value.code == "COOLDOWN_ACTIVE_ROLLBACK_MISMATCH"


# ---------------------------------------------------------------------------
# Test 14: Alias Audit History
# ---------------------------------------------------------------------------
def test_14_alias_audit_history(base_environment):
    vanity = base_environment["vanity"]
    t0 = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    vanity.register_initial_alias("AFF-000001", "thecannabiscutie", now=t0)
    vanity.update_vanity_slug("AFF-000001", "tammy", now=t0)
    vanity.rollback_vanity_slug("AFF-000001", now=t0 + timedelta(days=1))

    assert len(vanity.audit_log) == 3
    assert vanity.audit_log[0].event_type == "INITIAL_CREATION"
    assert vanity.audit_log[1].event_type == "SLUG_UPDATE"
    assert vanity.audit_log[2].event_type == "SLUG_ROLLBACK"


# ---------------------------------------------------------------------------
# Test 15 & 16: Canonical Attribution Through Old and New Alias
# ---------------------------------------------------------------------------
def test_15_and_16_canonical_attribution_through_old_and_new_alias(base_environment):
    router = base_environment["router"]
    vanity = base_environment["vanity"]

    identity = CanonicalIdentity("AFF-000001", "7KQ9M2TX", "tammy@example.com", "Tammy Pettigrew")
    router.register_identity(identity)
    vanity.register_initial_alias("AFF-000001", "thecannabiscutie")
    vanity.update_vanity_slug("AFF-000001", "tammy")

    # Route through old alias
    res_old = router.resolve_path("/go/thecannabiscutie")
    assert res_old is not None
    assert res_old.affiliate_id == "AFF-000001"
    assert res_old.routing_method == "HISTORICAL_REDIRECT"

    # Route through new alias
    res_new = router.resolve_path("/go/tammy")
    assert res_new is not None
    assert res_new.affiliate_id == "AFF-000001"
    assert res_new.routing_method == "PRIMARY_VANITY"


# ---------------------------------------------------------------------------
# Test 17: Campaign-Specific Routing
# ---------------------------------------------------------------------------
def test_17_campaign_specific_routing(base_environment):
    router = base_environment["router"]
    vanity = base_environment["vanity"]

    identity = CanonicalIdentity("AFF-000001", "7KQ9M2TX", "tammy@example.com", "Tammy Pettigrew")
    router.register_identity(identity)
    router.register_campaign("CAMP-INFUSED-01", "infused-basics", "ccc:book:infused-basics", "Infused Basics Promo")
    vanity.register_initial_alias("AFF-000001", "thecannabiscutie")

    res = router.resolve_path("/go/thecannabiscutie/infused-basics")
    assert res is not None
    assert res.affiliate_id == "AFF-000001"
    assert res.routing_method == "CAMPAIGN_VANITY"
    assert res.campaign_id == "CAMP-INFUSED-01"
    assert res.product_id == "ccc:book:infused-basics"


# ---------------------------------------------------------------------------
# Test 18: QR Canonical Reconciliation
# ---------------------------------------------------------------------------
def test_18_qr_canonical_reconciliation(base_environment):
    router = base_environment["router"]
    identity = CanonicalIdentity("AFF-000001", "7KQ9M2TX", "tammy@example.com", "Tammy Pettigrew")
    router.register_identity(identity)

    res = router.resolve_path("/qr/7KQ9M2TX")
    assert res is not None
    assert res.affiliate_id == "AFF-000001"
    assert res.routing_method == "PERMANENT_QR"


# ---------------------------------------------------------------------------
# Test 19: Unified Analytics Across Alias Changes
# ---------------------------------------------------------------------------
def test_19_unified_analytics_across_alias_changes(base_environment):
    analytics = base_environment["analytics"]
    vanity = base_environment["vanity"]

    vanity.register_initial_alias("AFF-000001", "thecannabiscutie")
    # Record clicks under old alias
    analytics.record_click("clk-1", "AFF-000001", "7KQ9M2TX", "PRIMARY_VANITY", "thecannabiscutie", visitor_id="v1")

    # Change alias
    vanity.update_vanity_slug("AFF-000001", "tammy")
    # Record clicks under new alias
    analytics.record_click("clk-2", "AFF-000001", "7KQ9M2TX", "PRIMARY_VANITY", "tammy", visitor_id="v2")
    # Record clicks under historical redirect
    analytics.record_click("clk-3", "AFF-000001", "7KQ9M2TX", "HISTORICAL_REDIRECT", "thecannabiscutie", visitor_id="v3")

    comm = Commission("comm-1", "AFF-000001", "ord-1", "USD", Decimal("40.00"), Decimal("10.00"), Decimal("10.00"), "PENDING", datetime.now(timezone.utc), "corr-1", ["R-1"])
    summary = analytics.get_affiliate_analytics("AFF-000001", [comm])

    assert summary.total_clicks == 3
    assert summary.unique_visitors == 3
    assert summary.total_orders == 1
    assert summary.commission_total == Decimal("10.000000")


# ---------------------------------------------------------------------------
# Test 20 & 21: Preference Create/Update & Audit
# ---------------------------------------------------------------------------
def test_20_and_21_preference_create_update_audit(base_environment):
    prefs = base_environment["preferences"]
    prefs.set_preference("AFF-000001", "PUBLIC_NAME", "display_format", "Tammy Pettigrew")
    assert prefs.get_preference("AFF-000001", "PUBLIC_NAME", "display_format") == "Tammy Pettigrew"

    prefs.set_preference("AFF-000001", "PUBLIC_NAME", "display_format", "Tammy")
    assert prefs.get_preference("AFF-000001", "PUBLIC_NAME", "display_format") == "Tammy"
    assert len(prefs.audit_log) == 2


# ---------------------------------------------------------------------------
# Test 22: Affiliate Tenant Isolation
# ---------------------------------------------------------------------------
def test_22_affiliate_tenant_isolation(base_environment):
    budly = base_environment["budly"]
    id1 = CanonicalIdentity("AFF-000001", "7KQ9M2TX", "tammy@example.com", "Tammy Pettigrew")
    id2 = CanonicalIdentity("AFF-000002", "8LR2N3UY", "sanzidah@example.com", "Sanzidah")
    budly.register_affiliate(id1, "thecannabiscutie")
    budly.register_affiliate(id2, "sanzidah")

    # Actor is Affiliate 1
    actor1 = ActorContext(actor_id="usr-1", role="AFFILIATE", affiliate_id="AFF-000001", authenticated=True)

    # Access own profile -> OK
    prof1 = budly.get_profile("AFF-000001", actor1)
    assert prof1["affiliate_id"] == "AFF-000001"

    # Attempt to access Affiliate 2 profile -> BLOCKED
    with pytest.raises(AccessControlError) as exc:
        budly.get_profile("AFF-000002", actor1)
    assert exc.value.code == "TENANT_ISOLATION_VIOLATION"


# ---------------------------------------------------------------------------
# Test 23: Unauthenticated Private-Data Rejection
# ---------------------------------------------------------------------------
def test_23_unauthenticated_private_data_rejection(base_environment):
    budly = base_environment["budly"]
    id1 = CanonicalIdentity("AFF-000001", "7KQ9M2TX", "tammy@example.com", "Tammy Pettigrew")
    budly.register_affiliate(id1, "thecannabiscutie")

    unauth_actor = ActorContext(actor_id="anon", role="ANONYMOUS", authenticated=False)
    with pytest.raises(AccessControlError) as exc:
        budly.get_profile("AFF-000001", unauth_actor)
    assert exc.value.code == "UNAUTHENTICATED"


# ---------------------------------------------------------------------------
# Test 24: Unauthorized Affiliate-to-Affiliate Lookup Rejection
# ---------------------------------------------------------------------------
def test_24_unauthorized_affiliate_to_affiliate_lookup(base_environment):
    budly = base_environment["budly"]
    id1 = CanonicalIdentity("AFF-000001", "7KQ9M2TX", "tammy@example.com", "Tammy Pettigrew")
    id2 = CanonicalIdentity("AFF-000002", "8LR2N3UY", "sanzidah@example.com", "Sanzidah")
    budly.register_affiliate(id1, "thecannabiscutie")
    budly.register_affiliate(id2, "sanzidah")

    actor2 = ActorContext(actor_id="usr-2", role="AFFILIATE", affiliate_id="AFF-000002", authenticated=True)
    with pytest.raises(AccessControlError) as exc:
        budly.get_profile("thecannabiscutie", actor2)
    assert exc.value.code == "TENANT_ISOLATION_VIOLATION"


# ---------------------------------------------------------------------------
# Test 25: Owner-Authorized Lookup
# ---------------------------------------------------------------------------
def test_25_owner_authorized_lookup(base_environment):
    budly = base_environment["budly"]
    id1 = CanonicalIdentity("AFF-000001", "7KQ9M2TX", "tammy@example.com", "Tammy Pettigrew")
    budly.register_affiliate(id1, "thecannabiscutie")

    owner_actor = ActorContext(actor_id="owner-1", role="PROJECT_OWNER", authenticated=True)
    res = budly.handle_owner_query("Pull up Tammy", owner_actor)
    assert res.get("status") != "UNRESOLVED"
    assert res["affiliate_id"] == "AFF-000001"
    assert res["name"] == "Tammy Pettigrew"


# ---------------------------------------------------------------------------
# Test 26: Unknown Identity Fails Closed
# ---------------------------------------------------------------------------
def test_26_unknown_identity_fails_closed(base_environment):
    budly = base_environment["budly"]
    owner_actor = ActorContext(actor_id="owner-1", role="PROJECT_OWNER", authenticated=True)
    with pytest.raises(IdentityError) as exc:
        budly.get_profile("AFF-999999", owner_actor)
    assert exc.value.code == "AFFILIATE_NOT_FOUND"


# ---------------------------------------------------------------------------
# Test 27: Ambiguous Canonical Mapping Fails Closed
# ---------------------------------------------------------------------------
def test_27_ambiguous_canonical_mapping_fails_closed(base_environment):
    budly = base_environment["budly"]
    owner_actor = ActorContext(actor_id="owner-1", role="PROJECT_OWNER", authenticated=True)
    res = budly.handle_owner_query("How is nonexistent performing?", owner_actor)
    assert res["status"] == "UNRESOLVED"


# ---------------------------------------------------------------------------
# Test 28: Catalog State Reconciliation
# ---------------------------------------------------------------------------
def test_28_catalog_state_reconciliation():
    loader = CommercialSnapshotLoader(CATALOG_DIR)
    assert loader.record_count == 73

    eligible = [r for r in loader.records if r.affiliate_eligibility == "AFFILIATE_ELIGIBLE"]
    rate_required = [r for r in loader.records if r.affiliate_eligibility == "ELIGIBLE_RATE_REQUIRED"]
    attributable_only = [r for r in loader.records if r.affiliate_eligibility == "ATTRIBUTABLE_ONLY"]
    excluded = [r for r in loader.records if r.affiliate_eligibility == "EXCLUDED"]

    assert len(eligible) == 52
    assert len(rate_required) == 0
    assert len(attributable_only) == 10
    assert len(excluded) == 11


# ---------------------------------------------------------------------------
# Test 29: ELIGIBLE_RATE_REQUIRED Fails Closed ($0 Commission)
# ---------------------------------------------------------------------------
def test_29_eligible_rate_required_fails_closed(base_environment):
    engine = base_environment["engine"]
    aff = engine.review_application(
        engine.submit_application({"applicant_email": "test@example.com", "desired_affiliate_class": "STANDARD"}, "idemp-t29")["id"],
        approved=True,
    )
    engine.accept_terms(aff.id, "v1.0", "h")
    engine.activate(aff.id, "v1.0")

    decision = AttributionDecision("dec-29", "ord-29", aff.id, "ATTRIBUTED", "REFERRAL_LINK", "LAST_QUALIFIED_REFERRAL", "ref-29", "corr-29")
    products = {
        "ccc:course:culinary-cannabis": {
            "canonical_id": "ccc:course:culinary-cannabis",
            "affiliate_eligibility": "ELIGIBLE_RATE_REQUIRED",
            "affiliate_commission_class": None,
        }
    }
    event = {
        "event_id": "rev-29",
        "order_id": "ord-29",
        "currency": "USD",
        "occurred_at": "2026-10-02T12:00:00Z",
        "line_items": [
            {
                "product_id": "ccc:course:culinary-cannabis",
                "merchandise_total": "1000.00",
                "discount": "0.00",
                "refunded": "0.00",
            }
        ],
    }
    res = engine.process_revenue_event(event, decision, products)
    assert res["status"] == "NO_COMMISSION"
    assert res["commission_id"] is None


# ---------------------------------------------------------------------------
# Test 30: Mixed-Order Line-Item Commission Behavior
# ---------------------------------------------------------------------------
def test_30_mixed_order_line_item_behavior(base_environment):
    engine = base_environment["engine"]
    aff = engine.review_application(
        engine.submit_application({"applicant_email": "test30@example.com", "desired_affiliate_class": "STANDARD"}, "idemp-t30")["id"],
        approved=True,
    )
    engine.accept_terms(aff.id, "v1.0", "h")
    engine.activate(aff.id, "v1.0")

    decision = AttributionDecision("dec-30", "ord-30", aff.id, "ATTRIBUTED", "REFERRAL_LINK", "LAST_QUALIFIED_REFERRAL", "ref-30", "corr-30")
    products = {
        "ccc:product:therapeutic-body-butter": {
            "canonical_id": "ccc:product:therapeutic-body-butter",
            "affiliate_eligibility": "AFFILIATE_ELIGIBLE",
            "affiliate_commission_class": "WELLNESS_PHYSICAL_30",
        },
        "ccc:course:culinary-cannabis": {
            "canonical_id": "ccc:course:culinary-cannabis",
            "affiliate_eligibility": "ELIGIBLE_RATE_REQUIRED",
            "affiliate_commission_class": None,
        },
        "ccc:product:bulk-butter": {
            "canonical_id": "ccc:product:bulk-butter",
            "affiliate_eligibility": "EXCLUDED",
            "affiliate_commission_class": None,
        },
    }
    event = {
        "event_id": "rev-30",
        "order_id": "ord-30",
        "currency": "USD",
        "occurred_at": "2026-10-02T12:00:00Z",
        "line_items": [
            {
                "product_id": "ccc:product:therapeutic-body-butter",
                "merchandise_total": "75.00",
                "discount": "0.00",
                "refunded": "0.00",
            },
            {
                "product_id": "ccc:course:culinary-cannabis",
                "merchandise_total": "1000.00",
                "discount": "0.00",
                "refunded": "0.00",
            },
            {
                "product_id": "ccc:product:bulk-butter",
                "merchandise_total": "1000.00",
                "discount": "0.00",
                "refunded": "0.00",
            },
        ],
    }
    res = engine.process_revenue_event(event, decision, products)
    assert res["status"] == "COMMISSION_CREATED"
    comm = engine.commissions[res["commission_id"]]
    # Only eligible Body Butter earns commission: $75 * 0.30 = $22.50
    assert comm.amount == Decimal("22.500000")
    assert comm.qualifying_revenue == Decimal("75.000000")


# ---------------------------------------------------------------------------
# Test 31: Public Display Name Is NOT a Canonical Resolution Key
# ---------------------------------------------------------------------------
def test_31_public_display_name_not_canonical_key(base_environment):
    budly = base_environment["budly"]
    id1 = CanonicalIdentity("AFF-000001", "7KQ9M2TX", "tammy@example.com", "Tammy Pettigrew")
    budly.register_affiliate(id1, "thecannabiscutie")

    # 1. resolve_canonical_id with display name MUST return None
    assert budly.resolve_canonical_id("Tammy Pettigrew") is None
    assert budly.resolve_canonical_id("Tammy") is None

    # 2. get_profile with display name MUST fail closed (AFFILIATE_NOT_FOUND)
    owner_actor = ActorContext(actor_id="owner-1", role="PROJECT_OWNER", authenticated=True)
    with pytest.raises(IdentityError) as exc:
        budly.get_profile("Tammy Pettigrew", owner_actor)
    assert exc.value.code == "AFFILIATE_NOT_FOUND"


# ---------------------------------------------------------------------------
# Test 32: Ambiguous Name Search Requires Disambiguation (Fail Closed)
# ---------------------------------------------------------------------------
def test_32_ambiguous_name_disambiguation(base_environment):
    budly = base_environment["budly"]
    id1 = CanonicalIdentity("AFF-000001", "7KQ9M2TX", "tammy1@example.com", "Tammy Pettigrew")
    id2 = CanonicalIdentity("AFF-000002", "8LR2N3UY", "tammy2@example.com", "Tammy Smith")
    budly.register_affiliate(id1, "thecannabiscutie")
    budly.register_affiliate(id2, "tammysmith")

    owner_actor = ActorContext(actor_id="owner-1", role="PROJECT_OWNER", authenticated=True)
    res = budly.handle_owner_query("Pull up Tammy", owner_actor)
    assert res["status"] == "AMBIGUOUS_MATCH"
    assert len(res["matching_candidates"]) == 2
    assert {c["affiliate_id"] for c in res["matching_candidates"]} == {"AFF-000001", "AFF-000002"}


# ---------------------------------------------------------------------------
# Test 33: Owner Commands Restricted Strictly to PROJECT_OWNER
# ---------------------------------------------------------------------------
def test_33_owner_commands_restricted_to_project_owner(base_environment):
    budly = base_environment["budly"]
    id1 = CanonicalIdentity("AFF-000001", "7KQ9M2TX", "tammy@example.com", "Tammy Pettigrew")
    budly.register_affiliate(id1, "thecannabiscutie")

    # AFFILIATE_OPERATOR is NOT authorized without separate ratified governance
    operator_actor = ActorContext(actor_id="op-1", role="AFFILIATE_OPERATOR", authenticated=True)
    with pytest.raises(AccessControlError) as exc:
        budly.handle_owner_query("Pull up Tammy", operator_actor)
    assert exc.value.code == "OWNER_ROLE_REQUIRED"

    with pytest.raises(AccessControlError) as exc:
        budly.get_profile("AFF-000001", operator_actor)
    assert exc.value.code == "UNAUTHORIZED_ROLE"


# ---------------------------------------------------------------------------
# Test 34: Name Hint Search Helper (Search/Lookup Aid Only)
# ---------------------------------------------------------------------------
def test_34_name_hint_search_helper(base_environment):
    budly = base_environment["budly"]
    id1 = CanonicalIdentity("AFF-000001", "7KQ9M2TX", "tammy@example.com", "Tammy Pettigrew")
    budly.register_affiliate(id1, "thecannabiscutie")

    matches = budly.search_by_name_hint("Tammy")
    assert len(matches) == 1
    assert matches[0].affiliate_id == "AFF-000001"

    empty_matches = budly.search_by_name_hint("UnknownPerson")
    assert len(empty_matches) == 0
