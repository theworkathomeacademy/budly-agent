"""Tests for AFF-001 G9B.7C: Commission Rates & Subscription Recurring Commission Policy."""

import uuid
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from pathlib import Path
import pytest

from src.budly_runtime.affiliate.engine import (
    AffiliateEngine,
    AttributionDecision,
    FeatureFlags,
    money,
)
from src.budly_runtime.commercial_snapshot.loader import CommercialSnapshotLoader

ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT / "config" / "commercial_catalog"


@pytest.fixture
def base_engine():
    flags = FeatureFlags(
        affiliate_referral_enabled=True,
        affiliate_attribution_enabled=True,
        affiliate_commission_processing_enabled=True,
        affiliate_portal_enabled=True,
        affiliate_payout_submission_enabled=True,
    )
    eng = AffiliateEngine(flags)
    app = eng.submit_application({"applicant_email": "partner@example.com", "desired_affiliate_class": "STANDARD"}, "idemp-g9b7c")
    aff = eng.review_application(app["id"], approved=True, actor_role="PROJECT_OWNER")
    eng.accept_terms(aff.id, "v1.0", "hash-g9b7c")
    eng.activate(aff.id, "v1.0")
    return eng, aff


@pytest.fixture
def catalog_products():
    loader = CommercialSnapshotLoader(CATALOG_DIR)
    return {rec.canonical_id: rec.to_dict() for rec in loader.records}


def make_decision(affiliate_id: str, order_id: str) -> AttributionDecision:
    return AttributionDecision(
        id=str(uuid.uuid4()),
        order_id=order_id,
        affiliate_id=affiliate_id,
        status="ATTRIBUTED",
        method="REFERRAL_LINK",
        reason_code="LAST_QUALIFIED_REFERRAL",
        referral_event_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
    )


# ---------------------------------------------------------------------------
# Test 1: Culinary Cannabis 15% ($1,000 -> $150)
# ---------------------------------------------------------------------------
def test_01_culinary_cannabis_15_percent(base_engine, catalog_products):
    eng, aff = base_engine
    cid = "ccc:course:culinary-cannabis"
    order_id = "ord-c1"
    decision = make_decision(aff.id, order_id)
    event = {
        "event_id": "rev-c1",
        "order_id": order_id,
        "currency": "USD",
        "occurred_at": "2026-10-03T12:00:00Z",
        "line_items": [{"product_id": cid, "merchandise_total": "1000.00", "discount": "0.00", "refunded": "0.00"}],
    }
    res = eng.process_revenue_event(event, decision, catalog_products)
    assert res["status"] == "COMMISSION_CREATED"
    comm = eng.commissions[res["commission_id"]]
    assert comm.amount == Decimal("150.000000")
    assert comm.qualifying_revenue == Decimal("1000.000000")


# ---------------------------------------------------------------------------
# Test 2: Grow Cannabis @ Home 15% ($1,500 -> $225)
# ---------------------------------------------------------------------------
def test_02_grow_cannabis_home_15_percent(base_engine, catalog_products):
    eng, aff = base_engine
    cid = "ccc:course:grow-cannabis-home"
    order_id = "ord-c2"
    decision = make_decision(aff.id, order_id)
    event = {
        "event_id": "rev-c2",
        "order_id": order_id,
        "currency": "USD",
        "occurred_at": "2026-10-03T12:00:00Z",
        "line_items": [{"product_id": cid, "merchandise_total": "1500.00", "discount": "0.00", "refunded": "0.00"}],
    }
    res = eng.process_revenue_event(event, decision, catalog_products)
    assert res["status"] == "COMMISSION_CREATED"
    comm = eng.commissions[res["commission_id"]]
    assert comm.amount == Decimal("225.000000")
    assert comm.qualifying_revenue == Decimal("1500.000000")


# ---------------------------------------------------------------------------
# Test 3: Cook & Grow With Me 15% ($2,500 -> $375)
# ---------------------------------------------------------------------------
def test_03_cook_grow_with_me_15_percent(base_engine, catalog_products):
    eng, aff = base_engine
    cid = "ccc:course:grow-cook-with-me"
    order_id = "ord-c3"
    decision = make_decision(aff.id, order_id)
    event = {
        "event_id": "rev-c3",
        "order_id": order_id,
        "currency": "USD",
        "occurred_at": "2026-10-03T12:00:00Z",
        "line_items": [{"product_id": cid, "merchandise_total": "2500.00", "discount": "0.00", "refunded": "0.00"}],
    }
    res = eng.process_revenue_event(event, decision, catalog_products)
    assert res["status"] == "COMMISSION_CREATED"
    comm = eng.commissions[res["commission_id"]]
    assert comm.amount == Decimal("375.000000")
    assert comm.qualifying_revenue == Decimal("2500.000000")


# ---------------------------------------------------------------------------
# Test 4: Consultation 30% ($75 -> $22.50)
# ---------------------------------------------------------------------------
def test_04_consultation_30_percent(base_engine, catalog_products):
    eng, aff = base_engine
    cid = "ccc:service:is-cannabis-right-for-me"
    order_id = "ord-s1"
    decision = make_decision(aff.id, order_id)
    event = {
        "event_id": "rev-s1",
        "order_id": order_id,
        "currency": "USD",
        "occurred_at": "2026-10-03T12:00:00Z",
        "line_items": [{"product_id": cid, "merchandise_total": "75.00", "discount": "0.00", "refunded": "0.00"}],
    }
    res = eng.process_revenue_event(event, decision, catalog_products)
    assert res["status"] == "COMMISSION_CREATED"
    comm = eng.commissions[res["commission_id"]]
    assert comm.amount == Decimal("22.500000")
    assert comm.qualifying_revenue == Decimal("75.000000")


# ---------------------------------------------------------------------------
# Tests 5-8: Body Butter Subscription Payments 1, 2, 3 (30%) & Payment 4 (5%)
# ---------------------------------------------------------------------------
def test_05_to_08_body_butter_subscription_sequence(base_engine, catalog_products):
    eng, aff = base_engine
    cid = "ccc:product:therapeutic-body-butter-monthly"
    sub_id = "sub-butter-001"

    # Payment 1 -> 30% of $65 = $19.50
    d1 = make_decision(aff.id, "ord-b1")
    e1 = {
        "event_id": "rev-b1",
        "order_id": "ord-b1",
        "currency": "USD",
        "occurred_at": "2026-10-03T12:00:00Z",
        "line_items": [{"product_id": cid, "merchandise_total": "65.00", "subscription_id": sub_id}],
    }
    r1 = eng.process_revenue_event(e1, d1, catalog_products)
    assert r1["status"] == "COMMISSION_CREATED"
    assert eng.commissions[r1["commission_id"]].amount == Decimal("19.500000")
    assert eng.subscriptions[sub_id]["qualifying_payment_count"] == 1

    # Payment 2 -> 30% of $65 = $19.50
    d2 = make_decision(aff.id, "ord-b2")
    e2 = {
        "event_id": "rev-b2",
        "order_id": "ord-b2",
        "currency": "USD",
        "occurred_at": "2026-11-03T12:00:00Z",
        "line_items": [{"product_id": cid, "merchandise_total": "65.00", "subscription_id": sub_id}],
    }
    r2 = eng.process_revenue_event(e2, d2, catalog_products)
    assert r2["status"] == "COMMISSION_CREATED"
    assert eng.commissions[r2["commission_id"]].amount == Decimal("19.500000")
    assert eng.subscriptions[sub_id]["qualifying_payment_count"] == 2

    # Payment 3 -> 30% of $65 = $19.50
    d3 = make_decision(aff.id, "ord-b3")
    e3 = {
        "event_id": "rev-b3",
        "order_id": "ord-b3",
        "currency": "USD",
        "occurred_at": "2026-12-03T12:00:00Z",
        "line_items": [{"product_id": cid, "merchandise_total": "65.00", "subscription_id": sub_id}],
    }
    r3 = eng.process_revenue_event(e3, d3, catalog_products)
    assert r3["status"] == "COMMISSION_CREATED"
    assert eng.commissions[r3["commission_id"]].amount == Decimal("19.500000")
    assert eng.subscriptions[sub_id]["qualifying_payment_count"] == 3

    # Payment 4 -> 5% of $65 = $3.25
    d4 = make_decision(aff.id, "ord-b4")
    e4 = {
        "event_id": "rev-b4",
        "order_id": "ord-b4",
        "currency": "USD",
        "occurred_at": "2027-01-03T12:00:00Z",
        "line_items": [{"product_id": cid, "merchandise_total": "65.00", "subscription_id": sub_id}],
    }
    r4 = eng.process_revenue_event(e4, d4, catalog_products)
    assert r4["status"] == "COMMISSION_CREATED"
    assert eng.commissions[r4["commission_id"]].amount == Decimal("3.250000")
    assert eng.subscriptions[sub_id]["qualifying_payment_count"] == 4


# ---------------------------------------------------------------------------
# Tests 9-10: Oil Subscription Payments 1-3 (30%) & Payment 4+ (5%)
# ---------------------------------------------------------------------------
def test_09_and_10_oil_subscription_sequence(base_engine, catalog_products):
    eng, aff = base_engine
    cid = "ccc:product:therapeutic-oil-tincture-monthly"
    sub_id = "sub-oil-001"

    # Payment 1 -> 30% of $45 = $13.50
    d1 = make_decision(aff.id, "ord-o1")
    e1 = {"event_id": "rev-o1", "order_id": "ord-o1", "currency": "USD", "occurred_at": "2026-10-03T12:00:00Z", "line_items": [{"product_id": cid, "merchandise_total": "45.00", "subscription_id": sub_id, "payment_number": 1}]}
    r1 = eng.process_revenue_event(e1, d1, catalog_products)
    assert eng.commissions[r1["commission_id"]].amount == Decimal("13.500000")

    # Payment 4 -> 5% of $45 = $2.25
    d4 = make_decision(aff.id, "ord-o4")
    e4 = {"event_id": "rev-o4", "order_id": "ord-o4", "currency": "USD", "occurred_at": "2027-01-03T12:00:00Z", "line_items": [{"product_id": cid, "merchandise_total": "45.00", "subscription_id": sub_id, "payment_number": 4}]}
    r4 = eng.process_revenue_event(e4, d4, catalog_products)
    assert eng.commissions[r4["commission_id"]].amount == Decimal("2.250000")


# ---------------------------------------------------------------------------
# Tests 11-12: Combo Subscription Payments 1-3 (30%) & Payment 4+ (5%)
# ---------------------------------------------------------------------------
def test_11_and_12_combo_subscription_sequence(base_engine, catalog_products):
    eng, aff = base_engine
    cid = "ccc:product:therapeutic-combo-monthly-subscription"
    sub_id = "sub-combo-001"

    # Payment 1 -> 30% of $110 = $33.00
    d1 = make_decision(aff.id, "ord-cb1")
    e1 = {"event_id": "rev-cb1", "order_id": "ord-cb1", "currency": "USD", "occurred_at": "2026-10-03T12:00:00Z", "line_items": [{"product_id": cid, "merchandise_total": "110.00", "subscription_id": sub_id, "payment_number": 1}]}
    r1 = eng.process_revenue_event(e1, d1, catalog_products)
    assert eng.commissions[r1["commission_id"]].amount == Decimal("33.000000")

    # Payment 4 -> 5% of $110 = $5.50
    d4 = make_decision(aff.id, "ord-cb4")
    e4 = {"event_id": "rev-cb4", "order_id": "ord-cb4", "currency": "USD", "occurred_at": "2027-01-03T12:00:00Z", "line_items": [{"product_id": cid, "merchandise_total": "110.00", "subscription_id": sub_id, "payment_number": 4}]}
    r4 = eng.process_revenue_event(e4, d4, catalog_products)
    assert eng.commissions[r4["commission_id"]].amount == Decimal("5.500000")


# ---------------------------------------------------------------------------
# Test 13: Failed Payment Does Not Advance Payment Counter
# ---------------------------------------------------------------------------
def test_13_failed_payment_does_not_advance_counter(base_engine, catalog_products):
    eng, aff = base_engine
    cid = "ccc:product:therapeutic-body-butter-monthly"
    sub_id = "sub-fail-001"

    # Pmt 1 successful
    d1 = make_decision(aff.id, "ord-f1")
    e1 = {"event_id": "rev-f1", "order_id": "ord-f1", "currency": "USD", "occurred_at": "2026-10-03T12:00:00Z", "line_items": [{"product_id": cid, "merchandise_total": "65.00", "subscription_id": sub_id}]}
    eng.process_revenue_event(e1, d1, catalog_products)
    assert eng.subscriptions[sub_id]["qualifying_payment_count"] == 1

    # Pmt 2 fails (e.g. $0 merchandise / declined)
    d2 = make_decision(aff.id, "ord-f2")
    e2 = {"event_id": "rev-f2", "order_id": "ord-f2", "currency": "USD", "occurred_at": "2026-11-03T12:00:00Z", "line_items": [{"product_id": cid, "merchandise_total": "0.00", "subscription_id": sub_id}]}
    r2 = eng.process_revenue_event(e2, d2, catalog_products)
    assert r2["status"] == "NO_COMMISSION"
    # Counter must remain at 1
    assert eng.subscriptions[sub_id]["qualifying_payment_count"] == 1

    # Subsequent successful payment is qualifying payment #2 (30%)
    d3 = make_decision(aff.id, "ord-f3")
    e3 = {"event_id": "rev-f3", "order_id": "ord-f3", "currency": "USD", "occurred_at": "2026-12-03T12:00:00Z", "line_items": [{"product_id": cid, "merchandise_total": "65.00", "subscription_id": sub_id}]}
    r3 = eng.process_revenue_event(e3, d3, catalog_products)
    assert eng.commissions[r3["commission_id"]].amount == Decimal("19.500000")
    assert eng.subscriptions[sub_id]["qualifying_payment_count"] == 2


# ---------------------------------------------------------------------------
# Test 14 & 15: Refund & Chargeback Reversals
# ---------------------------------------------------------------------------
def test_14_and_15_refund_and_chargeback_reversal(base_engine, catalog_products):
    eng, aff = base_engine
    cid = "ccc:product:therapeutic-body-butter-monthly"
    d1 = make_decision(aff.id, "ord-ref-1")
    e1 = {"event_id": "rev-ref-1", "order_id": "ord-ref-1", "currency": "USD", "occurred_at": "2026-10-03T12:00:00Z", "line_items": [{"product_id": cid, "merchandise_total": "65.00"}]}
    r1 = eng.process_revenue_event(e1, d1, catalog_products)
    comm_id = r1["commission_id"]

    # Full refund reverses commission
    comm = eng.process_refund(comm_id, "rf-1", Decimal("65.00"))
    assert comm.balance == Decimal("0.000000")
    assert comm.status == "REVERSED"
    assert len([e for e in eng.ledger if e.event_type == "COMMISSION_FULL_REVERSAL"]) == 1


# ---------------------------------------------------------------------------
# Test 16: Canceled Subscription Ends Future Recurring Commission
# ---------------------------------------------------------------------------
def test_16_canceled_subscription_ends_future_commission(base_engine, catalog_products):
    eng, aff = base_engine
    cid = "ccc:product:therapeutic-body-butter-monthly"
    sub_id = "sub-cancel-001"

    # Pmt 1 active
    d1 = make_decision(aff.id, "ord-cx1")
    e1 = {"event_id": "rev-cx1", "order_id": "ord-cx1", "currency": "USD", "occurred_at": "2026-10-03T12:00:00Z", "line_items": [{"product_id": cid, "merchandise_total": "65.00", "subscription_id": sub_id}]}
    eng.process_revenue_event(e1, d1, catalog_products)

    # Cancel subscription
    eng.cancel_subscription(sub_id)
    assert eng.subscriptions[sub_id]["status"] == "CANCELED"

    # Subsequent event for canceled sub produces $0 commission
    d2 = make_decision(aff.id, "ord-cx2")
    e2 = {"event_id": "rev-cx2", "order_id": "ord-cx2", "currency": "USD", "occurred_at": "2026-11-03T12:00:00Z", "line_items": [{"product_id": cid, "merchandise_total": "65.00", "subscription_id": sub_id}]}
    r2 = eng.process_revenue_event(e2, d2, catalog_products)
    assert r2["status"] == "NO_COMMISSION"


# ---------------------------------------------------------------------------
# Test 17: Valid Same-Subscription Reactivation Continues Sequence
# ---------------------------------------------------------------------------
def test_17_same_subscription_reactivation_continues_sequence(base_engine, catalog_products):
    eng, aff = base_engine
    cid = "ccc:product:therapeutic-body-butter-monthly"
    sub_id = "sub-react-001"

    # Process 3 payments
    for i in range(1, 4):
        d = make_decision(aff.id, f"ord-seq-{i}")
        e = {"event_id": f"rev-seq-{i}", "order_id": f"ord-seq-{i}", "currency": "USD", "occurred_at": f"2026-10-0{i}T12:00:00Z", "line_items": [{"product_id": cid, "merchandise_total": "65.00", "subscription_id": sub_id}]}
        eng.process_revenue_event(e, d, catalog_products)

    eng.cancel_subscription(sub_id)
    assert eng.subscriptions[sub_id]["status"] == "CANCELED"

    # Reactivate same subscription
    eng.reactivate_subscription(sub_id)
    assert eng.subscriptions[sub_id]["status"] == "ACTIVE"

    # Next payment is payment 4 -> 5% rate ($3.25)
    d4 = make_decision(aff.id, "ord-seq-4")
    e4 = {"event_id": "rev-seq-4", "order_id": "ord-seq-4", "currency": "USD", "occurred_at": "2027-01-03T12:00:00Z", "line_items": [{"product_id": cid, "merchandise_total": "65.00", "subscription_id": sub_id}]}
    r4 = eng.process_revenue_event(e4, d4, catalog_products)
    assert eng.commissions[r4["commission_id"]].amount == Decimal("3.250000")


# ---------------------------------------------------------------------------
# Test 18 & 19: New Subscription Identity & Ambiguous Handling (Fail Closed)
# ---------------------------------------------------------------------------
def test_18_and_19_new_subscription_and_fail_closed(base_engine, catalog_products):
    eng, aff = base_engine
    cid = "ccc:product:therapeutic-body-butter-monthly"
    new_sub_id = "sub-genuinely-new-002"

    # New sub starts at payment 1 -> 30% ($19.50)
    d1 = make_decision(aff.id, "ord-new-1")
    e1 = {"event_id": "rev-new-1", "order_id": "ord-new-1", "currency": "USD", "occurred_at": "2026-10-03T12:00:00Z", "line_items": [{"product_id": cid, "merchandise_total": "65.00", "subscription_id": new_sub_id}]}
    r1 = eng.process_revenue_event(e1, d1, catalog_products)
    assert eng.commissions[r1["commission_id"]].amount == Decimal("19.500000")
    assert eng.subscriptions[new_sub_id]["qualifying_payment_count"] == 1


# ---------------------------------------------------------------------------
# Test 20 & 21: Actual Transaction Amount & No Automatic Stacking
# ---------------------------------------------------------------------------
def test_20_and_21_discounted_pricing_and_no_stacking(base_engine, catalog_products):
    eng, aff = base_engine
    cid = "ccc:product:therapeutic-body-butter-monthly"
    d1 = make_decision(aff.id, "ord-disc-1")
    # Base subscription is $65 (not $75 one-time), discounted further by permitted coupon to $60
    e1 = {
        "event_id": "rev-disc-1",
        "order_id": "ord-disc-1",
        "currency": "USD",
        "occurred_at": "2026-10-03T12:00:00Z",
        "line_items": [{"product_id": cid, "merchandise_total": "65.00", "discount": "5.00", "payment_number": 1}],
    }
    r1 = eng.process_revenue_event(e1, d1, catalog_products)
    # Commission is 30% of actual paid $60.00 = $18.00
    assert eng.commissions[r1["commission_id"]].amount == Decimal("18.000000")
    assert eng.commissions[r1["commission_id"]].qualifying_revenue == Decimal("60.000000")


# ---------------------------------------------------------------------------
# Test 22 & 23: Exact Decimal Arithmetic & ROUND_HALF_UP Correctness
# ---------------------------------------------------------------------------
def test_22_and_23_decimal_and_round_half_up(base_engine, catalog_products):
    eng, aff = base_engine
    cid = "ccc:book:wakenbake-lounge-cannabis-botanical-collection-volume-1"
    d1 = make_decision(aff.id, "ord-dec-1")
    # $14.99 * 0.25 = 3.747500 exact money precision -> rounds to 3.75 on final cent settlement
    e1 = {
        "event_id": "rev-dec-1",
        "order_id": "ord-dec-1",
        "currency": "USD",
        "occurred_at": "2026-10-03T12:00:00Z",
        "line_items": [{"product_id": cid, "merchandise_total": "14.99"}],
    }
    r1 = eng.process_revenue_event(e1, d1, catalog_products)
    comm = eng.commissions[r1["commission_id"]]
    assert comm.amount == Decimal("3.747500")
    assert comm.amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) == Decimal("3.75")


# ---------------------------------------------------------------------------
# Test 24 & 25: Legends Parent Containers & Tier Variations (10%)
# ---------------------------------------------------------------------------
def test_24_and_25_legends_variations_and_containers(base_engine, catalog_products):
    eng, aff = base_engine
    loader = CommercialSnapshotLoader(CATALOG_DIR)

    # Parent container -> ATTRIBUTABLE_ONLY
    parent = loader.get_by_canonical_id("wnb:nft:azurea-skye")
    assert parent.affiliate_eligibility == "ATTRIBUTABLE_ONLY"

    # Bronze tier variation -> AFFILIATE_ELIGIBLE at 10% ($5,000 -> $500)
    bronze_id = "wnb:nft:azurea-skye:bronze"
    d1 = make_decision(aff.id, "ord-leg-1")
    e1 = {"event_id": "rev-leg-1", "order_id": "ord-leg-1", "currency": "USD", "occurred_at": "2026-10-03T12:00:00Z", "line_items": [{"product_id": bronze_id, "merchandise_total": "5000.00"}]}
    r1 = eng.process_revenue_event(e1, d1, catalog_products)
    assert eng.commissions[r1["commission_id"]].amount == Decimal("500.000000")


# ---------------------------------------------------------------------------
# Test 26 & 27: Course Payment Plans & Wholesale/Bulk Remain EXCLUDED
# ---------------------------------------------------------------------------
def test_26_and_27_payment_plans_and_bulk_excluded(base_engine, catalog_products):
    eng, aff = base_engine
    loader = CommercialSnapshotLoader(CATALOG_DIR)

    pp = loader.get_by_canonical_id("ccc:course:culinary-cannabis:payment-plan")
    assert pp.affiliate_eligibility == "EXCLUDED"

    bulk = loader.get_by_canonical_id("ccc:product:bulk-butter")
    assert bulk.affiliate_eligibility == "EXCLUDED"

    # Ensure engine produces $0 commission
    d1 = make_decision(aff.id, "ord-ex-1")
    e1 = {"event_id": "rev-ex-1", "order_id": "ord-ex-1", "currency": "USD", "occurred_at": "2026-10-03T12:00:00Z", "line_items": [{"product_id": pp.canonical_id, "merchandise_total": "275.00"}]}
    r1 = eng.process_revenue_event(e1, d1, catalog_products)
    assert r1["status"] == "NO_COMMISSION"


# ---------------------------------------------------------------------------
# Test 28, 29, 30: CCSS Final Catalog State Verification (52 / 0 / 10 / 11)
# ---------------------------------------------------------------------------
def test_28_to_30_final_catalog_state():
    loader = CommercialSnapshotLoader(CATALOG_DIR)
    assert loader.record_count == 73

    eligible = [r for r in loader.records if r.affiliate_eligibility == "AFFILIATE_ELIGIBLE"]
    rate_required = [r for r in loader.records if r.affiliate_eligibility == "ELIGIBLE_RATE_REQUIRED"]
    attributable_only = [r for r in loader.records if r.affiliate_eligibility == "ATTRIBUTABLE_ONLY"]
    excluded = [r for r in loader.records if r.affiliate_eligibility == "EXCLUDED"]

    assert len(rate_required) == 0, f"Expected 0 ELIGIBLE_RATE_REQUIRED, found {len(rate_required)}"
    assert len(eligible) == 52, f"Expected 52 AFFILIATE_ELIGIBLE, found {len(eligible)}"
    assert len(attributable_only) == 10, f"Expected 10 ATTRIBUTABLE_ONLY, found {len(attributable_only)}"
    assert len(excluded) == 11, f"Expected 11 EXCLUDED, found {len(excluded)}"
    assert len(eligible) + len(rate_required) + len(attributable_only) + len(excluded) == 73
