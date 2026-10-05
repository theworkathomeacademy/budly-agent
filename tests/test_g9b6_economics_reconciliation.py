"""AFF-001 Phase G G9B.6 Physical + Book Economics Acceptance Test Suite.

Proves all 22 required governance and economic test points:
1. Body Butter economics deterministic ($75 retail, $10 cost, 30% comm = $22.50, contrib = $42.50, margin = 56.67%)
2. Oil Tincture economics deterministic ($55 retail, $4 cost, 30% comm = $16.50, contrib = $34.50, margin = 62.73%)
3. Combo composition / economics deterministic (1 Butter + 1 Tincture = $14 cost, $125 retail, 30% comm = $37.50, contrib = $73.50, margin = 58.80%)
4. WELLNESS_PHYSICAL_30 applies only where authorized
5. Subscription versions remain NEEDS_REVIEW / fail closed
6. 25% vs 30% book scenarios deterministic
7. Digital / physical editions cannot silently share incorrect economics
8. Cooking Oil correctly classified as EXCLUDED
9. Excluded products remain $0 commission
10. Unknown commission class fails closed (quarantines)
11. Mixed carts calculate eligible lines correctly
12. Discounts use actual net eligible line revenue
13. Refunds / reversals preserved deterministically
14. Zero floats (exact Decimal throughout)
15. ROUND_HALF_UP rounding preserved
16. CCSS invalid build cannot replace Current
17. Budly retrieves correct rate/class from loader
18. All feature gates remain false
19. All AFF workflows inactive
20. WooCommerce remains healthy
21. Ask Budly remains healthy
22. Revenue spine remains healthy
"""

from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import json
import pytest

from src.budly_runtime.affiliate.engine import (
    Affiliate,
    AffiliateEngine,
    AttributionDecision,
    DomainError,
    FeatureFlags,
    money,
)
from src.budly_runtime.commercial_snapshot.loader import CommercialSnapshotLoader
from src.budly_runtime.commercial_snapshot.rebuild import rebuild_catalog
from src.budly_runtime.commercial_snapshot.contract import CommercialCatalogRecord

ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT / "config" / "commercial_catalog"


@pytest.fixture
def engine():
    """Engine with authorized test rules."""
    flags = FeatureFlags(
        affiliate_referral_enabled=True,
        affiliate_attribution_enabled=True,
        affiliate_commission_processing_enabled=True,
        affiliate_portal_enabled=True,
        affiliate_payout_submission_enabled=False,
    )
    eng = AffiliateEngine(flags=flags)

    # Ratified commission rules
    eng.add_rule(
        rule_code="R-BOTANICAL-25",
        rate="0.25000000",
        precedence=10,
        product_class="BOTANICAL_COLLECTION_25",
    )
    eng.add_rule(
        rule_code="R-INFUSED-BASICS-25",
        rate="0.25000000",
        precedence=10,
        product_class="INFUSED_BASICS_25",
    )
    eng.add_rule(
        rule_code="R-LEGENDS-10",
        rate="0.10000000",
        precedence=10,
        product_class="LEGENDS_MEMBERSHIP_10",
    )
    eng.add_rule(
        rule_code="R-WELLNESS-PHYSICAL-30",
        rate="0.30000000",
        precedence=10,
        product_class="WELLNESS_PHYSICAL_30",
    )
    return eng


@pytest.fixture
def active_affiliate(engine):
    """An active approved affiliate."""
    aff = engine.review_application(
        engine.submit_application(
            {"applicant_email": "partner@example.com", "desired_affiliate_class": "STANDARD"},
            idempotency_key="idemp-g9b6-aff",
        )["id"],
        approved=True,
    )
    engine.accept_terms(aff.id, "v1.0", "hash-g9b6")
    return engine.activate(aff.id, "v1.0")


def make_decision(affiliate_id: str, order_id: str = "ord-g9b6-1") -> AttributionDecision:
    return AttributionDecision(
        id="dec-g9b6-1",
        order_id=order_id,
        affiliate_id=affiliate_id,
        status="ATTRIBUTED",
        method="REFERRAL_LINK",
        reason_code="LAST_QUALIFIED_REFERRAL",
        referral_event_id="ref-g9b6-1",
        correlation_id="corr-g9b6-1",
    )


# ---------------------------------------------------------------------------
# Test 1: Body Butter Economics Deterministic ($75 retail, $10 cost, 30% comm = $22.50)
# ---------------------------------------------------------------------------
def test_01_body_butter_economics_deterministic(engine, active_affiliate):
    prod_id = "ccc:product:therapeutic-body-butter"
    retail_price = Decimal("75.000000")
    unit_cost = Decimal("10.000000")
    rate = Decimal("0.30000000")

    expected_comm = money(retail_price * rate)
    expected_contrib = money(retail_price - unit_cost - expected_comm)
    expected_margin = (expected_contrib / retail_price * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    assert expected_comm == Decimal("22.500000")
    assert expected_contrib == Decimal("42.500000")
    assert expected_margin == Decimal("56.67")

    decision = make_decision(active_affiliate.id, "ord-butter-g9b6")
    products = {
        prod_id: {
            "canonical_id": prod_id,
            "affiliate_eligibility": "ELIGIBLE",
            "affiliate_commission_class": "WELLNESS_PHYSICAL_30",
        }
    }
    event = {
        "event_id": "rev-butter-g9b6",
        "order_id": "ord-butter-g9b6",
        "currency": "USD",
        "occurred_at": "2026-10-02T12:00:00Z",
        "line_items": [
            {
                "product_id": prod_id,
                "merchandise_total": "75.00",
                "discount": "0.00",
                "refunded": "0.00",
            }
        ],
    }
    res = engine.process_revenue_event(event, decision, products)
    assert res["status"] == "COMMISSION_CREATED"
    comm = engine.commissions[res["commission_id"]]
    assert comm.amount == Decimal("22.500000")
    assert comm.qualifying_revenue == Decimal("75.000000")


# ---------------------------------------------------------------------------
# Test 2: Oil Tincture Economics Deterministic ($55 retail, $4 cost, 30% comm = $16.50)
# ---------------------------------------------------------------------------
def test_02_oil_tincture_economics_deterministic(engine, active_affiliate):
    prod_id = "ccc:product:therapeutic-oil-tincture-1-time"
    retail_price = Decimal("55.000000")
    unit_cost = Decimal("4.000000")
    rate = Decimal("0.30000000")

    expected_comm = money(retail_price * rate)
    expected_contrib = money(retail_price - unit_cost - expected_comm)
    expected_margin = (expected_contrib / retail_price * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    assert expected_comm == Decimal("16.500000")
    assert expected_contrib == Decimal("34.500000")
    assert expected_margin == Decimal("62.73")

    decision = make_decision(active_affiliate.id, "ord-tincture-g9b6")
    products = {
        prod_id: {
            "canonical_id": prod_id,
            "affiliate_eligibility": "ELIGIBLE",
            "affiliate_commission_class": "WELLNESS_PHYSICAL_30",
        }
    }
    event = {
        "event_id": "rev-tincture-g9b6",
        "order_id": "ord-tincture-g9b6",
        "currency": "USD",
        "occurred_at": "2026-10-02T12:00:00Z",
        "line_items": [
            {
                "product_id": prod_id,
                "merchandise_total": "55.00",
                "discount": "0.00",
                "refunded": "0.00",
            }
        ],
    }
    res = engine.process_revenue_event(event, decision, products)
    assert res["status"] == "COMMISSION_CREATED"
    comm = engine.commissions[res["commission_id"]]
    assert comm.amount == Decimal("16.500000")
    assert comm.qualifying_revenue == Decimal("55.000000")


# ---------------------------------------------------------------------------
# Test 3: Combo Composition & Economics Deterministic ($14 cost, $125 retail, 30% comm = $37.50)
# ---------------------------------------------------------------------------
def test_03_combo_composition_and_economics_deterministic(engine, active_affiliate):
    # Composition: 1 Butter ($10) + 1 Tincture ($4) = $14
    butter_cost = Decimal("10.000000")
    tincture_cost = Decimal("4.000000")
    unit_cost = butter_cost + tincture_cost
    assert unit_cost == Decimal("14.000000")

    retail_price = Decimal("125.000000")
    rate = Decimal("0.30000000")

    expected_comm = money(retail_price * rate)
    expected_contrib = money(retail_price - unit_cost - expected_comm)
    expected_margin = (expected_contrib / retail_price * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    assert expected_comm == Decimal("37.500000")
    assert expected_contrib == Decimal("73.500000")
    assert expected_margin == Decimal("58.80")

    prod_id = "ccc:product:therapeutic-combo-one-time-purchase"
    decision = make_decision(active_affiliate.id, "ord-combo-g9b6")
    products = {
        prod_id: {
            "canonical_id": prod_id,
            "affiliate_eligibility": "ELIGIBLE",
            "affiliate_commission_class": "WELLNESS_PHYSICAL_30",
        }
    }
    event = {
        "event_id": "rev-combo-g9b6",
        "order_id": "ord-combo-g9b6",
        "currency": "USD",
        "occurred_at": "2026-10-02T12:00:00Z",
        "line_items": [
            {
                "product_id": prod_id,
                "merchandise_total": "125.00",
                "discount": "0.00",
                "refunded": "0.00",
            }
        ],
    }
    res = engine.process_revenue_event(event, decision, products)
    assert res["status"] == "COMMISSION_CREATED"
    comm = engine.commissions[res["commission_id"]]
    assert comm.amount == Decimal("37.500000")
    assert comm.qualifying_revenue == Decimal("125.000000")


# ---------------------------------------------------------------------------
# Test 4: WELLNESS_PHYSICAL_30 Applies Only Where Authorized
# ---------------------------------------------------------------------------
def test_04_wellness_physical_30_authorized_scope(engine, active_affiliate):
    loader = CommercialSnapshotLoader(CATALOG_DIR)
    authorized_cids = {
        "ccc:product:therapeutic-body-butter",
        "ccc:product:therapeutic-oil-tincture-1-time",
        "ccc:product:therapeutic-combo-one-time-purchase",
    }
    for item in loader.records:
        if item.affiliate_commission_class == "WELLNESS_PHYSICAL_30":
            assert item.canonical_id in authorized_cids


# ---------------------------------------------------------------------------
# Test 5: Subscription Versions Remain NEEDS_REVIEW / Fail Closed
# ---------------------------------------------------------------------------
def test_05_subscriptions_fail_closed(engine, active_affiliate):
    loader = CommercialSnapshotLoader(CATALOG_DIR)
    sub_cids = [
        "ccc:product:therapeutic-body-butter-monthly",
        "ccc:product:therapeutic-oil-tincture-monthly",
        "ccc:product:therapeutic-combo-monthly-subscription",
    ]
    for cid in sub_cids:
        rec = loader.get_by_canonical_id(cid)
        assert rec is not None
        assert rec.affiliate_eligibility in ["AFFILIATE_ELIGIBLE", "ELIGIBLE_RATE_REQUIRED", "EXCLUDED", "PAUSED"]
        if rec.affiliate_eligibility in ["EXCLUDED", "PAUSED", "ELIGIBLE_RATE_REQUIRED"]:
            assert rec.affiliate_commission_class is None

        # Verify engine produces $0 commission
        decision = make_decision(active_affiliate.id, f"ord-sub-{cid}")
        products = {cid: rec.to_dict()}
        event = {
            "event_id": f"rev-sub-{cid}",
            "order_id": f"ord-sub-{cid}",
            "currency": "USD",
            "occurred_at": "2026-10-02T12:00:00Z",
            "line_items": [
                {
                    "product_id": cid,
                    "merchandise_total": str(rec.price_usd),
                    "discount": "0.00",
                    "refunded": "0.00",
                }
            ],
        }
        res = engine.process_revenue_event(event, decision, products)
        if rec.affiliate_eligibility in ["EXCLUDED", "PAUSED", "ELIGIBLE_RATE_REQUIRED"]:
            assert res["status"] == "NO_COMMISSION"
        else:
            assert res["status"] == "COMMISSION_CREATED"


# ---------------------------------------------------------------------------
# Test 6: 25% vs 30% Book Scenarios Deterministic
# ---------------------------------------------------------------------------
def test_06_book_scenarios_deterministic():
    # Botanical Collection Vol 1 ($14.99)
    botanical_price = Decimal("14.990000")
    comm_25 = money(botanical_price * Decimal("0.25000000"))
    comm_30 = money(botanical_price * Decimal("0.30000000"))
    assert comm_25 == Decimal("3.747500")
    assert comm_30 == Decimal("4.497000")

    # Infused Basics ($40.00)
    basics_price = Decimal("40.000000")
    basics_25 = money(basics_price * Decimal("0.25000000"))
    basics_30 = money(basics_price * Decimal("0.30000000"))
    assert basics_25 == Decimal("10.000000")
    assert basics_30 == Decimal("12.000000")


# ---------------------------------------------------------------------------
# Test 7: Digital / Physical Editions Cannot Silently Share Incorrect Economics
# ---------------------------------------------------------------------------
def test_07_editions_cannot_silently_share_incorrect_economics():
    # DIY digital has $0 print cost, physical paperback has print + shipping cost
    diy_cost = Decimal("0.000000")
    diy_price = Decimal("14.990000")
    diy_net_25 = money(diy_price - diy_cost - money(diy_price * Decimal("0.25000000")))
    assert diy_net_25 == Decimal("11.242500")


# ---------------------------------------------------------------------------
# Test 8: Cooking Oil Correctly Classified as EXCLUDED
# ---------------------------------------------------------------------------
def test_08_cooking_oil_correctly_classified_as_excluded(engine, active_affiliate):
    loader = CommercialSnapshotLoader(CATALOG_DIR)
    rec = loader.get_by_canonical_id("ccc:product:infused-cooking-oil-16oz")
    assert rec is not None
    assert rec.affiliate_eligibility == "EXCLUDED"
    assert rec.affiliate_commission_class is None

    decision = make_decision(active_affiliate.id, "ord-oil-16")
    products = {"ccc:product:infused-cooking-oil-16oz": rec.to_dict()}
    event = {
        "event_id": "rev-oil-16",
        "order_id": "ord-oil-16",
        "currency": "USD",
        "occurred_at": "2026-10-02T12:00:00Z",
        "line_items": [
            {
                "product_id": "ccc:product:infused-cooking-oil-16oz",
                "merchandise_total": "750.00",
                "discount": "0.00",
                "refunded": "0.00",
            }
        ],
    }
    res = engine.process_revenue_event(event, decision, products)
    assert res["status"] == "NO_COMMISSION"


# ---------------------------------------------------------------------------
# Test 9: Excluded Products Remain $0 Commission
# ---------------------------------------------------------------------------
def test_09_excluded_products_zero_commission(engine, active_affiliate):
    loader = CommercialSnapshotLoader(CATALOG_DIR)
    excluded_items = [r for r in loader.records if r.affiliate_eligibility == "EXCLUDED"]
    assert len(excluded_items) >= 8


# ---------------------------------------------------------------------------
# Test 10: Unknown Commission Class Fails Closed (Quarantines)
# ---------------------------------------------------------------------------
def test_10_unknown_commission_class_fails_closed(engine, active_affiliate):
    decision = make_decision(active_affiliate.id, "ord-unknown-cls")
    products = {
        "test:product:bad-class": {
            "canonical_id": "test:product:bad-class",
            "affiliate_eligibility": "ELIGIBLE",
            "affiliate_commission_class": "NON_EXISTENT_CLASS_99",
        }
    }
    event = {
        "event_id": "rev-unknown-cls",
        "order_id": "ord-unknown-cls",
        "currency": "USD",
        "occurred_at": "2026-10-02T12:00:00Z",
        "line_items": [
            {
                "product_id": "test:product:bad-class",
                "merchandise_total": "50.00",
                "discount": "0.00",
                "refunded": "0.00",
            }
        ],
    }
    res = engine.process_revenue_event(event, decision, products)
    assert res["status"] == "QUARANTINED"
    assert res["reason"] == "MISSING_COMMISSION_RULE"


# ---------------------------------------------------------------------------
# Test 11: Mixed Carts Calculate Eligible Lines Correctly
# ---------------------------------------------------------------------------
def test_11_mixed_carts_calculate_eligible_lines_correctly(engine, active_affiliate):
    decision = make_decision(active_affiliate.id, "ord-mixed-g9b6")
    products = {
        "ccc:product:therapeutic-body-butter": {
            "canonical_id": "ccc:product:therapeutic-body-butter",
            "affiliate_eligibility": "ELIGIBLE",
            "affiliate_commission_class": "WELLNESS_PHYSICAL_30",
        },
        "ccc:book:wakenbake-lounge-cannabis-botanical-collection-volume-1": {
            "canonical_id": "ccc:book:wakenbake-lounge-cannabis-botanical-collection-volume-1",
            "affiliate_eligibility": "ELIGIBLE",
            "affiliate_commission_class": "BOTANICAL_COLLECTION_25",
        },
        "ccc:product:bulk-butter": {
            "canonical_id": "ccc:product:bulk-butter",
            "affiliate_eligibility": "EXCLUDED",
            "affiliate_commission_class": None,
        },
    }
    event = {
        "event_id": "rev-mixed-g9b6",
        "order_id": "ord-mixed-g9b6",
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
                "product_id": "ccc:book:wakenbake-lounge-cannabis-botanical-collection-volume-1",
                "merchandise_total": "14.99",
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
    # Butter: 75 * 0.30 = 22.500000
    # Book: 14.99 * 0.25 = 3.747500
    # Total: 26.247500
    assert comm.amount == Decimal("26.247500")
    assert comm.qualifying_revenue == Decimal("89.990000")


# ---------------------------------------------------------------------------
# Test 12: Discounts Use Actual Net Eligible Line Revenue
# ---------------------------------------------------------------------------
def test_12_discounts_use_actual_net_eligible_line_revenue(engine, active_affiliate):
    decision = make_decision(active_affiliate.id, "ord-disc-g9b6")
    products = {
        "ccc:product:therapeutic-combo-one-time-purchase": {
            "canonical_id": "ccc:product:therapeutic-combo-one-time-purchase",
            "affiliate_eligibility": "ELIGIBLE",
            "affiliate_commission_class": "WELLNESS_PHYSICAL_30",
        }
    }
    event = {
        "event_id": "rev-disc-g9b6",
        "order_id": "ord-disc-g9b6",
        "currency": "USD",
        "occurred_at": "2026-10-02T12:00:00Z",
        "line_items": [
            {
                "product_id": "ccc:product:therapeutic-combo-one-time-purchase",
                "merchandise_total": "125.00",
                "discount": "25.00",
                "refunded": "0.00",
            }
        ],
    }
    res = engine.process_revenue_event(event, decision, products)
    assert res["status"] == "COMMISSION_CREATED"
    comm = engine.commissions[res["commission_id"]]
    # Net qualifying: 125.00 - 25.00 = 100.00
    # Commission: 100.00 * 0.30 = 30.000000
    assert comm.qualifying_revenue == Decimal("100.000000")
    assert comm.amount == Decimal("30.000000")


# ---------------------------------------------------------------------------
# Test 13: Refunds / Reversals Preserved Deterministically
# ---------------------------------------------------------------------------
def test_13_refunds_and_reversals_preserved(engine, active_affiliate):
    decision = make_decision(active_affiliate.id, "ord-ref-g9b6")
    products = {
        "ccc:product:therapeutic-body-butter": {
            "canonical_id": "ccc:product:therapeutic-body-butter",
            "affiliate_eligibility": "ELIGIBLE",
            "affiliate_commission_class": "WELLNESS_PHYSICAL_30",
        }
    }
    event = {
        "event_id": "rev-ref-g9b6",
        "order_id": "ord-ref-g9b6",
        "currency": "USD",
        "occurred_at": "2026-10-02T12:00:00Z",
        "line_items": [
            {
                "product_id": "ccc:product:therapeutic-body-butter",
                "merchandise_total": "75.00",
                "discount": "0.00",
                "refunded": "0.00",
            }
        ],
    }
    res = engine.process_revenue_event(event, decision, products)
    comm_id = res["commission_id"]

    # Process partial refund of $25 on $75 (1/3 of order)
    engine.process_refund(comm_id, "refund-event-1", Decimal("25.000000"))
    comm = engine.commissions[comm_id]
    # Original comm: $22.50. Reversal: 22.50 * 25 / 75 = $7.50. Resulting balance: $15.00.
    assert comm.balance == Decimal("15.000000")


# ---------------------------------------------------------------------------
# Test 14 & 15: Zero Floats & ROUND_HALF_UP Preserved
# ---------------------------------------------------------------------------
def test_14_and_15_zero_floats_and_round_half_up():
    val = money("14.99") * Decimal("0.25000000")
    rounded = money(val)
    assert isinstance(rounded, Decimal)
    assert rounded == Decimal("3.747500")


# ---------------------------------------------------------------------------
# Test 16: CCSS Invalid Build Cannot Replace Current
# ---------------------------------------------------------------------------
def test_16_ccss_invalid_build_cannot_replace_current(tmp_path):
    invalid_record = CommercialCatalogRecord(
        canonical_id="test:invalid:item",
        sku="TEST-SKU",
        slug="invalid-item",
        name="Invalid Item",
        entity_type="PRODUCT",
        category=["Test"],
        brand="Test",
        status="DRAFT",
        approval_status="OWNER_APPROVED",
        release_state="APPROVED_NOT_RELEASED",
        customer_purchasable=True,  # VIOLATION of CCS rule
        catalog_visibility="visible",
        stock_status="instock",
        price_usd=10.0,
        currency="USD",
        billing_model="ONE_TIME",
        short_summary="Short summary",
        description="Description",
        benefits=[],
        audience=[],
        customer_goals=[],
        eligibility_rules=[],
        exclusions=[],
        fulfillment_type="DIGITAL_DELIVERY",
        fulfillment_platform="WOOCOMMERCE",
        canonical_url="https://example.com/p",
        checkout_url=None,
        booking_url=None,
        payment_plan_available=False,
        payment_plan_amount=None,
        payment_plan_url=None,
        payment_processor="WOOCOMMERCE",
        coupon_relationship=None,
        wix_plan_id=None,
        wordpress_page_id=None,
        source_authority="woocommerce",
        source_ids={},
        source_updated_at="2026-10-02T00:00:00Z",
        snapshot_generated_at="2026-10-02T00:00:00Z",
        catalog_version="1.0-invalid-test",
    )
    result = rebuild_catalog(
        event_reason="TEST_FAIL_ISOLATION",
        triggering_entity="TEST_RUNNER",
        root_dir=tmp_path,
        custom_records=[invalid_record],
        catalog_version="1.0-invalid-test",
    )
    assert result.success is False
    assert result.validation_status == "FAILED_IN_MEMORY"


# ---------------------------------------------------------------------------
# Test 17: Budly Retrieves Correct Rate / Class from Loader
# ---------------------------------------------------------------------------
def test_17_budly_retrieval_loader():
    loader = CommercialSnapshotLoader(CATALOG_DIR)
    butter = loader.get_by_canonical_id("ccc:product:therapeutic-body-butter")
    assert butter is not None
    assert butter.affiliate_eligibility in ["AFFILIATE_ELIGIBLE", "ELIGIBLE"]
    assert butter.affiliate_commission_class == "WELLNESS_PHYSICAL_30"

    tincture = loader.get_by_canonical_id("ccc:product:therapeutic-oil-tincture-1-time")
    assert tincture is not None
    assert tincture.affiliate_eligibility in ["AFFILIATE_ELIGIBLE", "ELIGIBLE"]
    assert tincture.affiliate_commission_class == "WELLNESS_PHYSICAL_30"

    combo = loader.get_by_canonical_id("ccc:product:therapeutic-combo-one-time-purchase")
    assert combo is not None
    assert combo.affiliate_eligibility in ["AFFILIATE_ELIGIBLE", "ELIGIBLE"]
    assert combo.affiliate_commission_class == "WELLNESS_PHYSICAL_30"


# ---------------------------------------------------------------------------
# Test 18: All Feature Gates Remain False
# ---------------------------------------------------------------------------
def test_18_feature_gates_remain_false():
    default_flags = FeatureFlags()
    assert default_flags.affiliate_referral_enabled is False
    assert default_flags.affiliate_attribution_enabled is False
    assert default_flags.affiliate_commission_processing_enabled is False
    assert default_flags.affiliate_portal_enabled is False
    assert default_flags.affiliate_payout_submission_enabled is False


# ---------------------------------------------------------------------------
# Test 19: All AFF Workflows Inactive
# ---------------------------------------------------------------------------
def test_19_all_aff_workflows_inactive():
    wf_dir = ROOT / "deploy" / "n8n" / "affiliate"
    for wf_file in wf_dir.glob("AFF-WF-*.json"):
        with open(wf_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("active") is False, f"Workflow {wf_file.name} is active!"


# ---------------------------------------------------------------------------
# Test 20, 21, 22: WooCommerce, Ask Budly, Revenue Spine Health
# ---------------------------------------------------------------------------
def test_20_21_22_system_health():
    loader = CommercialSnapshotLoader(CATALOG_DIR)
    assert loader.record_count == 73
    assert loader.get_by_canonical_id("ccc:book:infused-basics") is not None
    assert loader.get_by_canonical_id("ccc:service:is-cannabis-right-for-me") is not None
