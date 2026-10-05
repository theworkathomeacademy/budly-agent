"""G9B.5 Affiliate Catalog Expansion & Economic Policy Acceptance Test Suite.

Covers:
- 100% classification coverage of live WooCommerce and CCSS products.
- Product economic classes, candidate rates, and eligibility rules.
- Deterministic commission calculation with ROUND_HALF_UP and exact Decimal arithmetic.
- Mixed-cart processing, discounts, refunds, and fail-closed quarantine boundaries.
- Attribution-only tracking, excluded items, and subscription/payment-plan constraints.
"""

from decimal import Decimal
import pytest
from src.budly_runtime.affiliate.engine import (
    Affiliate,
    AffiliateEngine,
    AttributionDecision,
    DomainError,
    FeatureFlags,
    money,
)


@pytest.fixture
def engine():
    """Engine with active test configuration."""
    flags = FeatureFlags(
        affiliate_referral_enabled=True,
        affiliate_attribution_enabled=True,
        affiliate_commission_processing_enabled=True,
        affiliate_portal_enabled=True,
        affiliate_payout_submission_enabled=False,
    )
    eng = AffiliateEngine(flags=flags)

    # Add standard commission rules
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
        rule_code="R-WELLNESS-PHYSICAL-20",
        rate="0.20000000",
        precedence=10,
        product_class="WELLNESS_PHYSICAL_20",
    )
    eng.add_rule(
        rule_code="R-COURSE-FULL-15",
        rate="0.15000000",
        precedence=10,
        product_class="COURSE_FULL_15",
    )
    return eng


@pytest.fixture
def active_affiliate(engine):
    """An active approved affiliate."""
    aff = engine.review_application(
        engine.submit_application(
            {"applicant_email": "affiliate@example.com", "desired_affiliate_class": "STANDARD"},
            idempotency_key="idemp-app-1",
        )["id"],
        approved=True,
    )
    engine.accept_terms(aff.id, "v1.0", "hash123")
    return engine.activate(aff.id, "v1.0")


def make_decision(affiliate_id: str, order_id: str = "ord-1") -> AttributionDecision:
    return AttributionDecision(
        id="dec-1",
        order_id=order_id,
        affiliate_id=affiliate_id,
        status="ATTRIBUTED",
        method="REFERRAL_LINK",
        reason_code="LAST_QUALIFIED_REFERRAL",
        referral_event_id="ref-1",
        correlation_id="corr-1",
    )


# ---------------------------------------------------------------------------
# Test Category 1: Ratified Digital Books (25% Commission)
# ---------------------------------------------------------------------------

def test_botanical_collection_commission_calculation(engine, active_affiliate):
    """Botanical Collection Vol 1 ($14.99 @ 25% -> $3.7475 -> $3.747500 / $3.75)."""
    decision = make_decision(active_affiliate.id, "ord-book-1")
    products = {
        "ccc:book:wakenbake-lounge-cannabis-botanical-collection-volume-1": {
            "canonical_id": "ccc:book:wakenbake-lounge-cannabis-botanical-collection-volume-1",
            "affiliate_eligibility": "ELIGIBLE",
            "affiliate_commission_class": "BOTANICAL_COLLECTION_25",
        }
    }
    event = {
        "event_id": "rev-book-1",
        "order_id": "ord-book-1",
        "currency": "USD",
        "occurred_at": "2026-10-02T12:00:00Z",
        "line_items": [
            {
                "product_id": "ccc:book:wakenbake-lounge-cannabis-botanical-collection-volume-1",
                "merchandise_total": "14.99",
                "discount": "0.00",
                "refunded": "0.00",
            }
        ],
    }
    res = engine.process_revenue_event(event, decision, products)
    assert res["status"] == "COMMISSION_CREATED"
    comm = engine.commissions[res["commission_id"]]
    assert comm.amount == Decimal("3.747500")
    assert comm.qualifying_revenue == Decimal("14.990000")


def test_infused_basics_commission_calculation(engine, active_affiliate):
    """Infused Basics ($40.00 @ 25% -> $10.00)."""
    decision = make_decision(active_affiliate.id, "ord-book-2")
    products = {
        "ccc:book:infused-basics": {
            "canonical_id": "ccc:book:infused-basics",
            "affiliate_eligibility": "ELIGIBLE",
            "affiliate_commission_class": "INFUSED_BASICS_25",
        }
    }
    event = {
        "event_id": "rev-book-2",
        "order_id": "ord-book-2",
        "currency": "USD",
        "occurred_at": "2026-10-02T12:00:00Z",
        "line_items": [
            {
                "product_id": "ccc:book:infused-basics",
                "merchandise_total": "40.00",
                "discount": "0.00",
                "refunded": "0.00",
            }
        ],
    }
    res = engine.process_revenue_event(event, decision, products)
    assert res["status"] == "COMMISSION_CREATED"
    comm = engine.commissions[res["commission_id"]]
    assert comm.amount == Decimal("10.000000")


# ---------------------------------------------------------------------------
# Test Category 2: NFT Memberships (10% Commission)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "tier_name,price,expected_comm",
    [
        ("bronze", "5000.00", "500.000000"),
        ("copper", "10000.00", "1000.000000"),
        ("titanium", "20000.00", "2000.000000"),
        ("platinum", "40000.00", "4000.000000"),
    ],
)
def test_legends_nft_tiers_commission(engine, active_affiliate, tier_name, price, expected_comm):
    """Legends NFT tiers @ 10% calculate exact financial commission."""
    prod_id = f"wnb:nft:the-chemist:{tier_name}"
    decision = make_decision(active_affiliate.id, f"ord-nft-{tier_name}")
    products = {
        prod_id: {
            "canonical_id": prod_id,
            "affiliate_eligibility": "ELIGIBLE",
            "affiliate_commission_class": "LEGENDS_MEMBERSHIP_10",
        }
    }
    event = {
        "event_id": f"rev-nft-{tier_name}",
        "order_id": f"ord-nft-{tier_name}",
        "currency": "USD",
        "occurred_at": "2026-10-02T12:00:00Z",
        "line_items": [
            {
                "product_id": prod_id,
                "merchandise_total": price,
                "discount": "0.00",
                "refunded": "0.00",
            }
        ],
    }
    res = engine.process_revenue_event(event, decision, products)
    assert res["status"] == "COMMISSION_CREATED"
    comm = engine.commissions[res["commission_id"]]
    assert comm.amount == Decimal(expected_comm)


# ---------------------------------------------------------------------------
# Test Category 3: Physical Wellness (Body Butter & Oil Tincture @ 20%)
# ---------------------------------------------------------------------------

def test_therapeutic_body_butter_one_time(engine, active_affiliate):
    """Therapeutic Body Butter 1-time ($75.00 @ 20% -> $15.00)."""
    prod_id = "ccc:product:therapeutic-body-butter"
    decision = make_decision(active_affiliate.id, "ord-butter-1")
    products = {
        prod_id: {
            "canonical_id": prod_id,
            "affiliate_eligibility": "ELIGIBLE",
            "affiliate_commission_class": "WELLNESS_PHYSICAL_20",
        }
    }
    event = {
        "event_id": "rev-butter-1",
        "order_id": "ord-butter-1",
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
    assert comm.amount == Decimal("15.000000")


def test_therapeutic_oil_tincture_one_time(engine, active_affiliate):
    """Therapeutic Oil Tincture 1-time ($55.00 @ 20% -> $11.00)."""
    prod_id = "ccc:product:therapeutic-oil-tincture-1-time"
    decision = make_decision(active_affiliate.id, "ord-tincture-1")
    products = {
        prod_id: {
            "canonical_id": prod_id,
            "affiliate_eligibility": "ELIGIBLE",
            "affiliate_commission_class": "WELLNESS_PHYSICAL_20",
        }
    }
    event = {
        "event_id": "rev-tincture-1",
        "order_id": "ord-tincture-1",
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
    assert comm.amount == Decimal("11.000000")


def test_therapeutic_combo_one_time(engine, active_affiliate):
    """Therapeutic Combo 1-time ($125.00 @ 20% -> $25.00)."""
    prod_id = "ccc:product:therapeutic-combo-one-time-purchase"
    decision = make_decision(active_affiliate.id, "ord-combo-1")
    products = {
        prod_id: {
            "canonical_id": prod_id,
            "affiliate_eligibility": "ELIGIBLE",
            "affiliate_commission_class": "WELLNESS_PHYSICAL_20",
        }
    }
    event = {
        "event_id": "rev-combo-1",
        "order_id": "ord-combo-1",
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
    assert comm.amount == Decimal("25.000000")


# ---------------------------------------------------------------------------
# Test Category 4: Excluded & Wholesale Products ($0 Commission)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "prod_id,price",
    [
        ("ccc:product:white-label-oil-per-1oz-min-10oz", "150.00"),
        ("ccc:product:white-label-cbd-combo-per-1oz", "280.00"),
        ("ccc:product:white-label-butter-per-1oz-min-16oz", "320.00"),
        ("ccc:product:infused-cooking-oil-4oz", "300.00"),
        ("ccc:product:bulk-butter", "1000.00"),
    ],
)
def test_wholesale_and_bulk_excluded(engine, active_affiliate, prod_id, price):
    """Wholesale/Bulk items marked EXCLUDED generate $0 commission."""
    decision = make_decision(active_affiliate.id, "ord-wholesale")
    products = {
        prod_id: {
            "canonical_id": prod_id,
            "affiliate_eligibility": "EXCLUDED",
            "affiliate_commission_class": None,
        }
    }
    event = {
        "event_id": f"rev-ws-{prod_id}",
        "order_id": "ord-wholesale",
        "currency": "USD",
        "occurred_at": "2026-10-02T12:00:00Z",
        "line_items": [
            {
                "product_id": prod_id,
                "merchandise_total": price,
                "discount": "0.00",
                "refunded": "0.00",
            }
        ],
    }
    res = engine.process_revenue_event(event, decision, products)
    assert res["status"] == "NO_COMMISSION"
    assert res["commission_id"] is None


# ---------------------------------------------------------------------------
# Test Category 5: High-Ticket Paid-in-Full Courses (15% Commission)
# ---------------------------------------------------------------------------

def test_course_full_payment(engine, active_affiliate):
    """Culinary Cannabis Full Course ($1000.00 @ 15% -> $150.00)."""
    prod_id = "ccc:course:culinary-cannabis"
    decision = make_decision(active_affiliate.id, "ord-crs-1")
    products = {
        prod_id: {
            "canonical_id": prod_id,
            "affiliate_eligibility": "ELIGIBLE",
            "affiliate_commission_class": "COURSE_FULL_15",
        }
    }
    event = {
        "event_id": "rev-crs-1",
        "order_id": "ord-crs-1",
        "currency": "USD",
        "occurred_at": "2026-10-02T12:00:00Z",
        "line_items": [
            {
                "product_id": prod_id,
                "merchandise_total": "1000.00",
                "discount": "0.00",
                "refunded": "0.00",
            }
        ],
    }
    res = engine.process_revenue_event(event, decision, products)
    assert res["status"] == "COMMISSION_CREATED"
    comm = engine.commissions[res["commission_id"]]
    assert comm.amount == Decimal("150.000000")


# ---------------------------------------------------------------------------
# Test Category 6: Mixed Cart & Discount Scenarios
# ---------------------------------------------------------------------------

def test_mixed_cart_calculation(engine, active_affiliate):
    """Mixed cart with Eligible Book ($14.99 @ 25%), Eligible Butter ($75.00 @ 20%),
    Excluded Bulk ($150.00 @ 0%), and Unknown Product ($99.00 -> fail-closed $0).
    """
    decision = make_decision(active_affiliate.id, "ord-mixed-1")
    products = {
        "ccc:book:wakenbake-lounge-cannabis-botanical-collection-volume-1": {
            "canonical_id": "ccc:book:wakenbake-lounge-cannabis-botanical-collection-volume-1",
            "affiliate_eligibility": "ELIGIBLE",
            "affiliate_commission_class": "BOTANICAL_COLLECTION_25",
        },
        "ccc:product:therapeutic-body-butter": {
            "canonical_id": "ccc:product:therapeutic-body-butter",
            "affiliate_eligibility": "ELIGIBLE",
            "affiliate_commission_class": "WELLNESS_PHYSICAL_20",
        },
        "ccc:product:white-label-oil-per-1oz-min-10oz": {
            "canonical_id": "ccc:product:white-label-oil-per-1oz-min-10oz",
            "affiliate_eligibility": "EXCLUDED",
            "affiliate_commission_class": None,
        },
    }
    event = {
        "event_id": "rev-mixed-1",
        "order_id": "ord-mixed-1",
        "currency": "USD",
        "occurred_at": "2026-10-02T12:00:00Z",
        "line_items": [
            {
                "product_id": "ccc:book:wakenbake-lounge-cannabis-botanical-collection-volume-1",
                "merchandise_total": "14.99",
                "discount": "0.00",
                "refunded": "0.00",
            },
            {
                "product_id": "ccc:product:therapeutic-body-butter",
                "merchandise_total": "75.00",
                "discount": "0.00",
                "refunded": "0.00",
            },
            {
                "product_id": "ccc:product:white-label-oil-per-1oz-min-10oz",
                "merchandise_total": "150.00",
                "discount": "0.00",
                "refunded": "0.00",
            },
            {
                "product_id": "unknown-sku-999",
                "merchandise_total": "99.00",
                "discount": "0.00",
                "refunded": "0.00",
            },
        ],
    }
    res = engine.process_revenue_event(event, decision, products)
    assert res["status"] == "COMMISSION_CREATED"
    comm = engine.commissions[res["commission_id"]]
    # Book commission: 14.99 * 0.25 = 3.747500
    # Butter commission: 75.00 * 0.20 = 15.000000
    # Total comm: 18.747500
    # Qualifying rev: 14.99 + 75.00 = 89.990000
    assert comm.amount == Decimal("18.747500")
    assert comm.qualifying_revenue == Decimal("89.990000")


def test_discounted_line_item_net_commission(engine, active_affiliate):
    """Discounts reduce qualifying merchandise total before applying commission rate.
    $75.00 Body Butter with $15.00 discount -> $60.00 net @ 20% = $12.00 commission.
    """
    prod_id = "ccc:product:therapeutic-body-butter"
    decision = make_decision(active_affiliate.id, "ord-disc-1")
    products = {
        prod_id: {
            "canonical_id": prod_id,
            "affiliate_eligibility": "ELIGIBLE",
            "affiliate_commission_class": "WELLNESS_PHYSICAL_20",
        }
    }
    event = {
        "event_id": "rev-disc-1",
        "order_id": "ord-disc-1",
        "currency": "USD",
        "occurred_at": "2026-10-02T12:00:00Z",
        "line_items": [
            {
                "product_id": prod_id,
                "merchandise_total": "75.00",
                "discount": "15.00",
                "refunded": "0.00",
            }
        ],
    }
    res = engine.process_revenue_event(event, decision, products)
    assert res["status"] == "COMMISSION_CREATED"
    comm = engine.commissions[res["commission_id"]]
    assert comm.qualifying_revenue == Decimal("60.000000")
    assert comm.amount == Decimal("12.000000")


# ---------------------------------------------------------------------------
# Test Category 7: Fail-Closed Boundaries & Quarantining
# ---------------------------------------------------------------------------

def test_missing_commission_class_quarantines(engine, active_affiliate):
    """Eligible product with undefined/missing commission class must quarantine."""
    prod_id = "ccc:product:unclassified-eligible"
    decision = make_decision(active_affiliate.id, "ord-fail-1")
    products = {
        prod_id: {
            "canonical_id": prod_id,
            "affiliate_eligibility": "ELIGIBLE",
            "affiliate_commission_class": None,
        }
    }
    event = {
        "event_id": "rev-fail-1",
        "order_id": "ord-fail-1",
        "currency": "USD",
        "occurred_at": "2026-10-02T12:00:00Z",
        "line_items": [
            {
                "product_id": prod_id,
                "merchandise_total": "50.00",
                "discount": "0.00",
                "refunded": "0.00",
            }
        ],
    }
    res = engine.process_revenue_event(event, decision, products)
    assert res["status"] == "QUARANTINED"
    assert res["reason"] == "MISSING_COMMISSION_RULE"
    assert len(engine.quarantine) == 1


def test_paused_product_excluded_from_commission(engine, active_affiliate):
    """Temporarily PAUSED product produces 0 commission."""
    prod_id = "ccc:product:paused-item"
    decision = make_decision(active_affiliate.id, "ord-paused-1")
    products = {
        prod_id: {
            "canonical_id": prod_id,
            "affiliate_eligibility": "PAUSED",
            "affiliate_commission_class": "WELLNESS_PHYSICAL_20",
        }
    }
    event = {
        "event_id": "rev-paused-1",
        "order_id": "ord-paused-1",
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
    assert res["status"] == "NO_COMMISSION"
