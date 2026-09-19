"""Targeted Tests for COMMERCIAL-CATALOG-SNAPSHOT-001.

Implements all 7 Mandatory Commercial Tests and all 8 Mandatory Returning Customer Tests.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from src.budly_runtime.commercial_snapshot.contract import CommercialCatalogRecord
from src.budly_runtime.commercial_snapshot.loader import CommercialSnapshotLoader
from src.budly_runtime.commercial_snapshot.rebuild import rebuild_catalog
from src.budly_runtime.commercial_snapshot.resolver import DeterministicEntityResolver
from src.budly_runtime.commercial_snapshot.returning_customer import (
    CustomerVerificationState,
    EntitlementRecord,
    ReturningCustomerRetrievalService,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT / "config" / "commercial_catalog"


@pytest.fixture(scope="module")
def snapshot_loader() -> CommercialSnapshotLoader:
    # Ensure current snapshot is built
    rebuild_catalog(
        event_reason="TEST_INITIALIZATION",
        triggering_entity="TEST_SUITE",
        root_dir=CATALOG_DIR,
        canonical_source_path=ROOT / "config" / "canonical_catalog.json",
        catalog_version="1.9.0-test",
    )
    loader = CommercialSnapshotLoader(CATALOG_DIR)
    assert loader.record_count > 0
    return loader


@pytest.fixture(scope="module")
def returning_customer_service(snapshot_loader: CommercialSnapshotLoader) -> ReturningCustomerRetrievalService:
    return ReturningCustomerRetrievalService(snapshot_loader)


# =============================================================================
# MANDATORY COMMERCIAL TESTS (1 TO 7)
# =============================================================================

def test_commercial_01_what_is_infused_basics(snapshot_loader: CommercialSnapshotLoader):
    """Test 1: What is Infused Basics?

    Expected: book, not course, correct current commercial data ($40).
    """
    resolver = DeterministicEntityResolver()
    res = resolver.resolve("What is Infused Basics?")
    assert res.status == "EXACT_MATCH"
    assert res.canonical_id == "ccc:book:infused-basics"

    rec = snapshot_loader.get_by_canonical_id(res.canonical_id)
    assert rec is not None
    assert rec.entity_type == "BOOK"
    assert rec.entity_type != "COURSE"
    assert rec.price_usd == 40.0
    assert rec.status == "ACTIVE"
    assert rec.customer_purchasable is True
    assert "https://cccultivate.com/product/infused-basics/" in rec.canonical_url


def test_commercial_02_what_is_lounge_member(snapshot_loader: CommercialSnapshotLoader):
    """Test 2: What is Lounge Member?
    
    CCS-006 Rule:
    - In Public Mode: Must FAIL CLOSED (NO_MATCH / None in public snapshot).
    - In Internal Mode / Canonical Inventory: Preserved as unreleased Community Membership with approved benefits.
    """
    # 1. Public Resolver & Public Snapshot Exclusion
    public_resolver = DeterministicEntityResolver(public_only=True)
    res_pub = public_resolver.resolve("What is Lounge Member?")
    assert res_pub.status == "NO_MATCH"
    assert res_pub.canonical_id is None
    assert snapshot_loader.get_by_canonical_id("wnb:community:lounge-member") is None

    # 2. Internal Resolver & Canonical Inventory Preservation
    internal_resolver = DeterministicEntityResolver(public_only=False)
    res_int = internal_resolver.resolve("What is Lounge Member?")
    assert res_int.status == "EXACT_MATCH"
    assert res_int.canonical_id == "wnb:community:lounge-member"
    assert not res_int.canonical_id.startswith("wnb:nft:")

    internal_inv_path = CATALOG_DIR / "Internal" / "budly-canonical-inventory.json"
    assert internal_inv_path.exists()
    with open(internal_inv_path, "r", encoding="utf-8") as f:
        internal_records = {r["canonical_id"]: r for r in json.load(f)}

    rec = internal_records.get("wnb:community:lounge-member")
    assert rec is not None
    assert rec["entity_type"] == "COMMUNITY_MEMBERSHIP"
    assert rec["release_state"] == "APPROVED_NOT_RELEASED"
    assert rec["customer_purchasable"] is False
    assert rec["budly_visibility"] == "EXCLUDED"
    assert rec["price_usd"] == 9.99
    assert rec["billing_model"] == "RECURRING_MONTHLY"
    assert rec["coupon_relationship"] == "LOUNGEMEMBER10"
    assert len(rec["benefits"]) == 6
    assert "Community access" in rec["benefits"]
    assert "10% off all Lounge Collection products" in rec["benefits"]


def test_commercial_03_what_do_i_get_with_lounge_elite(snapshot_loader: CommercialSnapshotLoader):
    """Test 3: What do I get with Lounge Elite?
    
    CCS-006 Rule:
    - In Public Mode: Must FAIL CLOSED (NO_MATCH / None in public snapshot).
    - In Internal Mode / Canonical Inventory: Preserved with exact approved Lounge Elite benefits (6 benefits).
    """
    # Public isolation
    public_resolver = DeterministicEntityResolver(public_only=True)
    res_pub = public_resolver.resolve("What do I get with Lounge Elite?")
    assert res_pub.status == "NO_MATCH"
    assert res_pub.canonical_id is None
    assert snapshot_loader.get_by_canonical_id("wnb:community:lounge-elite") is None

    # Internal preservation
    internal_resolver = DeterministicEntityResolver(public_only=False)
    res_int = internal_resolver.resolve("What do I get with Lounge Elite?")
    assert res_int.status == "EXACT_MATCH"
    assert res_int.canonical_id == "wnb:community:lounge-elite"

    internal_inv_path = CATALOG_DIR / "Internal" / "budly-canonical-inventory.json"
    with open(internal_inv_path, "r", encoding="utf-8") as f:
        internal_records = {r["canonical_id"]: r for r in json.load(f)}

    rec = internal_records.get("wnb:community:lounge-elite")
    assert rec is not None
    assert rec["entity_type"] == "COMMUNITY_MEMBERSHIP"
    assert rec["price_usd"] == 24.99
    assert rec["billing_model"] == "RECURRING_MONTHLY"
    assert rec["coupon_relationship"] == "LOUNGEELITE25"
    assert rec["budly_visibility"] == "EXCLUDED"
    assert len(rec["benefits"]) == 6


def test_commercial_04_can_i_buy_lounge_elite(snapshot_loader: CommercialSnapshotLoader):
    """Test 4: Can I buy Lounge Elite?
    
    CCS-006 Rule:
    - In Public Mode: Must FAIL CLOSED (not customer purchasable, not in public snapshot).
    - In Internal Mode: release_state is APPROVED_NOT_RELEASED, customer_purchasable is False.
    """
    public_resolver = DeterministicEntityResolver(public_only=True)
    res_pub = public_resolver.resolve("Can I buy Lounge Elite?")
    assert res_pub.status == "NO_MATCH"
    assert res_pub.canonical_id is None

    internal_inv_path = CATALOG_DIR / "Internal" / "budly-canonical-inventory.json"
    with open(internal_inv_path, "r", encoding="utf-8") as f:
        internal_records = {r["canonical_id"]: r for r in json.load(f)}

    rec = internal_records.get("wnb:community:lounge-elite")
    assert rec is not None
    assert rec["release_state"] == "APPROVED_NOT_RELEASED"
    assert rec["customer_purchasable"] is False
    assert rec["catalog_visibility"] == "hidden"


def test_commercial_05_what_classes_do_you_offer(snapshot_loader: CommercialSnapshotLoader):
    """Test 5: What classes do you offer?

    Expected: current canonical classes, current prices.
    """
    classes = snapshot_loader.get_by_entity_type("COURSE")
    assert len(classes) >= 3

    class_dict = {c.canonical_id: c for c in classes}
    
    # Culinary Cannabis
    assert "ccc:course:culinary-cannabis" in class_dict
    cul = class_dict["ccc:course:culinary-cannabis"]
    assert cul.price_usd == 1000.0
    assert cul.customer_purchasable is True

    # Grow Cannabis @ Home
    assert "ccc:course:grow-cannabis-home" in class_dict
    grow = class_dict["ccc:course:grow-cannabis-home"]
    assert grow.price_usd == 1500.0
    assert grow.customer_purchasable is True

    # Cook & Grow With Me
    assert "ccc:course:grow-cook-with-me" in class_dict
    dual = class_dict["ccc:course:grow-cook-with-me"]
    assert dual.price_usd == 2500.0
    assert dual.customer_purchasable is True


def test_commercial_06_do_you_have_payment_plans(snapshot_loader: CommercialSnapshotLoader):
    """Test 6: Do you have payment plans?

    Expected: only verified payment-plan relationships/routes.
    """
    plans = snapshot_loader.get_by_entity_type("COURSE_PAYMENT_PLAN")
    assert len(plans) == 3

    plan_dict = {p.canonical_id: p for p in plans}
    
    # Culinary Cannabis Payment Plan ($300/mo via Stripe)
    assert "ccc:course:culinary-cannabis:payment-plan" in plan_dict
    cul_plan = plan_dict["ccc:course:culinary-cannabis:payment-plan"]
    assert cul_plan.price_usd == 300.0
    assert cul_plan.payment_processor == "STRIPE"
    assert "https://buy.stripe.com/cNi3cugI527OeoS9BleIw0J" in str(cul_plan.checkout_url)

    # Grow Cannabis @ Home Payment Plan ($425/mo via Stripe)
    assert "ccc:course:grow-cannabis-home:payment-plan" in plan_dict
    grow_plan = plan_dict["ccc:course:grow-cannabis-home:payment-plan"]
    assert grow_plan.price_usd == 425.0
    assert grow_plan.payment_processor == "STRIPE"
    assert "https://buy.stripe.com/14A7sKfE113KbcG14PeIw0K" in str(grow_plan.checkout_url)

    # Cook & Grow With Me Payment Plan ($675/mo via Stripe)
    assert "ccc:course:grow-cook-with-me:payment-plan" in plan_dict
    dual_plan = plan_dict["ccc:course:grow-cook-with-me:payment-plan"]
    assert dual_plan.price_usd == 675.0
    assert dual_plan.payment_processor == "STRIPE"
    assert "https://buy.stripe.com/9B6dR81Nb8wc5Sm14PeIw0L" in str(dual_plan.checkout_url)


def test_commercial_07_is_cannabis_right_for_me(snapshot_loader: CommercialSnapshotLoader):
    """Test 7: Is Cannabis Right For Me?

    Expected: $75 consultation, approved customer destination, appropriate safety framing.
    """
    resolver = DeterministicEntityResolver()
    res = resolver.resolve("Is Cannabis Right For Me?")
    assert res.status == "EXACT_MATCH"
    assert res.canonical_id == "ccc:service:is-cannabis-right-for-me"

    rec = snapshot_loader.get_by_canonical_id(res.canonical_id)
    assert rec is not None
    assert rec.entity_type == "SERVICE"
    assert rec.price_usd == 75.0
    assert rec.canonical_url == "https://wakenbakelounge.com/service-page/is-cannabis-right-for-me"
    assert rec.booking_url == "https://wakenbakelounge.com/service-page/is-cannabis-right-for-me"
    assert rec.payment_processor == "WIX_BOOKINGS"
    assert any("not medical advice" in exc.lower() for exc in rec.exclusions)


# =============================================================================
# MANDATORY RETURNING CUSTOMER TESTS (1 TO 8)
# =============================================================================

def test_returning_customer_01_anonymous_asks_what_did_i_buy(returning_customer_service: ReturningCustomerRetrievalService):
    """Returning Test 1: Anonymous asks: 'What did I buy?'

    Expected: no disclosure, identity verification required.
    """
    state = CustomerVerificationState(
        customer_id=None,
        email=None,
        is_verified=False,
        consent_scope=set(),
    )
    context = returning_customer_service.evaluate_customer_turn(
        verification=state,
        crm_record=None,
        crm_available=True,
    )
    assert context.verification_status in {"ANONYMOUS", "UNVERIFIED"}
    assert context.can_disclose_history is False
    assert len(context.past_purchases) == 0
    assert "identity verification is required" in context.guidance_message.lower()


def test_returning_customer_02_verified_customer_asks_purchase_history(returning_customer_service: ReturningCustomerRetrievalService):
    """Returning Test 2: Verified customer asks purchase history.

    Expected: only verified authorized relationship history, canonical products resolve correctly.
    """
    state = CustomerVerificationState(
        customer_id="cust_12345",
        email="jane.doe@example.com",
        is_verified=True,
        consent_scope={"crm_storage", "purchase_history_access"},
    )
    crm_record = {
        "customer_id": "cust_12345",
        "purchased_canonical_ids": [
            "ccc:book:infused-basics",
            "ccc:course:culinary-cannabis",
        ],
        "entitlements": [],
    }
    context = returning_customer_service.evaluate_customer_turn(
        verification=state,
        crm_record=crm_record,
        crm_available=True,
    )
    assert context.verification_status == "VERIFIED"
    assert context.can_disclose_history is True
    assert "ccc:book:infused-basics" in context.past_purchases
    assert "ccc:course:culinary-cannabis" in context.past_purchases


def test_returning_customer_03_verified_active_community_member_asks_benefits(
    returning_customer_service: ReturningCustomerRetrievalService,
):
    """Returning Test 3: Verified active Community member asks benefits.

    Expected: active entitlement required, current snapshot benefits returned.
    """
    state = CustomerVerificationState(
        customer_id="cust_elite_99",
        email="vip@example.com",
        is_verified=True,
        consent_scope={"crm_storage", "purchase_history_access"},
    )
    crm_record = {
        "customer_id": "cust_elite_99",
        "purchased_canonical_ids": ["wnb:community:lounge-elite"],
        "entitlements": [
            {
                "canonical_id": "wnb:community:lounge-elite",
                "entity_type": "COMMUNITY_MEMBERSHIP",
                "status": "ACTIVE",
            }
        ],
    }
    context = returning_customer_service.evaluate_customer_turn(
        verification=state,
        crm_record=crm_record,
        crm_available=True,
    )
    assert context.verification_status == "VERIFIED"
    assert len(context.active_entitlements) == 1
    assert "25% off all Lounge Collection products" in context.available_benefits
    assert "VIP forum badge" in context.available_benefits


def test_returning_customer_04_former_cancelled_member_asks_benefits(
    returning_customer_service: ReturningCustomerRetrievalService,
):
    """Returning Test 4: Former/cancelled member asks benefits.

    Expected: no active entitlement claim.
    """
    state = CustomerVerificationState(
        customer_id="cust_former_01",
        email="cancelled@example.com",
        is_verified=True,
        consent_scope={"crm_storage", "purchase_history_access"},
    )
    crm_record = {
        "customer_id": "cust_former_01",
        "purchased_canonical_ids": ["wnb:community:lounge-elite"],
        "entitlements": [
            {
                "canonical_id": "wnb:community:lounge-elite",
                "entity_type": "COMMUNITY_MEMBERSHIP",
                "status": "CANCELLED",
            }
        ],
    }
    context = returning_customer_service.evaluate_customer_turn(
        verification=state,
        crm_record=crm_record,
        crm_available=True,
    )
    assert context.verification_status == "VERIFIED"
    assert len(context.active_entitlements) == 0
    assert len(context.available_benefits) == 0


def test_returning_customer_05_crm_unavailable(returning_customer_service: ReturningCustomerRetrievalService):
    """Returning Test 5: CRM unavailable.

    Expected: general commercial assistance only, no fabricated history.
    """
    state = CustomerVerificationState(
        customer_id="cust_999",
        email="test@example.com",
        is_verified=True,
        consent_scope={"crm_storage"},
    )
    context = returning_customer_service.evaluate_customer_turn(
        verification=state,
        crm_record=None,
        crm_available=False,
    )
    assert context.crm_healthy is False
    assert context.can_disclose_history is False
    assert len(context.past_purchases) == 0
    assert "general product information" in context.guidance_message


def test_returning_customer_06_duplicate_identity_candidate(returning_customer_service: ReturningCustomerRetrievalService):
    """Returning Test 6: Duplicate identity candidate.

    Expected: review/escalation, no automatic merge.
    """
    state = CustomerVerificationState(
        customer_id="cust_dup_01",
        email="ambiguous@example.com",
        is_verified=True,
        consent_scope={"crm_storage"},
        is_duplicate_candidate=True,
    )
    context = returning_customer_service.evaluate_customer_turn(
        verification=state,
        crm_record={"purchased_canonical_ids": ["ccc:book:infused-basics"]},
        crm_available=True,
    )
    assert context.verification_status == "DUPLICATE_ESCALATION"
    assert context.can_disclose_history is False
    assert "multiple records" in context.guidance_message


def test_returning_customer_07_customer_opted_out(returning_customer_service: ReturningCustomerRetrievalService):
    """Returning Test 7: Customer opted out.

    Expected: no marketing/follow-up.
    """
    state = CustomerVerificationState(
        customer_id="cust_optout_01",
        email="optout@example.com",
        is_verified=True,
        consent_scope={"crm_storage"},  # marketing_followup is NOT in consent scope
    )
    crm_record = {
        "customer_id": "cust_optout_01",
        "purchased_canonical_ids": [],
    }
    context = returning_customer_service.evaluate_customer_turn(
        verification=state,
        crm_record=crm_record,
        crm_available=True,
    )
    assert context.can_market_follow_up is False


def test_returning_customer_08_existing_ownership_suppression(
    returning_customer_service: ReturningCustomerRetrievalService,
):
    """Returning Test 8: Existing ownership.

    Expected: recommendation logic should not unknowingly resell the same non-repeat item.
    """
    state = CustomerVerificationState(
        customer_id="cust_owner_01",
        email="owner@example.com",
        is_verified=True,
        consent_scope={"crm_storage", "purchase_history_access"},
    )
    crm_record = {
        "customer_id": "cust_owner_01",
        "purchased_canonical_ids": ["ccc:course:grow-cannabis-home"],
        "entitlements": [
            {
                "canonical_id": "ccc:course:grow-cannabis-home",
                "entity_type": "COURSE",
                "status": "ACTIVE",
            }
        ],
    }
    context = returning_customer_service.evaluate_customer_turn(
        verification=state,
        crm_record=crm_record,
        crm_available=True,
    )

    candidates = [
        "ccc:course:grow-cannabis-home",  # Already owned course -> should be filtered out
        "ccc:course:culinary-cannabis",   # Not owned -> should remain
        "ccc:product:therapeutic-body-butter", # Consumable -> should remain
    ]

    filtered = returning_customer_service.filter_recommendations_for_ownership(candidates, context)
    filtered_ids = [r.canonical_id for r in filtered]

    assert "ccc:course:grow-cannabis-home" not in filtered_ids
    assert "ccc:course:culinary-cannabis" in filtered_ids
    assert "ccc:product:therapeutic-body-butter" in filtered_ids


# =============================================================================
# PHASE 13 ADDITIONAL PUBLIC VISIBILITY & EXCLUSION TESTS
# =============================================================================

def test_commercial_08_torque_nft_parent_and_variations(snapshot_loader: CommercialSnapshotLoader):
    """Test 8: Torque NFT Parent and Variations in Public Catalog.

    Expected: Parent is variable product, 4 tier variations (Bronze, Copper, Titanium, Platinum), all active and purchasable.
    """
    resolver = DeterministicEntityResolver(public_only=True)
    res = resolver.resolve("Torque")
    assert res.status == "EXACT_MATCH"
    assert res.canonical_id == "wnb:nft:torque"

    parent = snapshot_loader.get_by_canonical_id("wnb:nft:torque")
    assert parent is not None
    assert parent.entity_type == "NFT_MEMBERSHIP_PARENT"
    assert parent.customer_purchasable is True
    assert parent.status == "ACTIVE"
    assert "Torque" in parent.name

    # Variations / Tiers
    variations = snapshot_loader.get_by_entity_type("NFT_MEMBERSHIP_TIER")
    torque_vars = [v for v in variations if v.canonical_id.startswith("wnb:nft:torque:")]
    assert len(torque_vars) == 4
    for var in torque_vars:
        assert var.price_usd in {5000.0, 10000.0, 20000.0, 40000.0}
        assert var.customer_purchasable is True
        assert var.status == "ACTIVE"


def test_commercial_09_community_memberships_public_exclusion(snapshot_loader: CommercialSnapshotLoader):
    """Test 9: All 3 unreleased Community Memberships are absent from the public snapshot."""
    excluded_ids = [
        "wnb:community:lounge-pass",
        "wnb:community:lounge-member",
        "wnb:community:lounge-elite",
    ]
    for cid in excluded_ids:
        assert snapshot_loader.get_by_canonical_id(cid) is None
        assert snapshot_loader.get_by_sku(f"WNB-MBR-{cid.split(':')[-1].upper()}") is None


def test_commercial_10_public_resolver_fail_closed_on_excluded_ids():
    """Test 10: Public resolver fails closed on excluded IDs and unknown queries."""
    resolver = DeterministicEntityResolver(public_only=True)

    # Excluded entities fail closed
    assert resolver.resolve("What is Lounge Pass?").status == "NO_MATCH"
    assert resolver.resolve("What is Lounge Member?").status == "NO_MATCH"
    assert resolver.resolve("What is Lounge Elite?").status == "NO_MATCH"
    assert resolver.resolve("wnb:community:lounge-pass").status == "NO_MATCH"

    # Unknown / garbage queries fail closed
    assert resolver.resolve("XYZ non-existent product 12345").status == "NO_MATCH"
    assert resolver.resolve("").status == "NO_MATCH"


def test_commercial_11_internal_canonical_inventory_preserves_76_records():
    """Test 11: Internal canonical inventory preserves all 76 source records."""
    internal_inv_path = CATALOG_DIR / "Internal" / "budly-canonical-inventory.json"
    assert internal_inv_path.exists()
    with open(internal_inv_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    assert len(records) == 76
    cids = {r["canonical_id"] for r in records}
    assert "wnb:community:lounge-pass" in cids
    assert "wnb:community:lounge-member" in cids
    assert "wnb:community:lounge-elite" in cids
    assert "ccc:book:infused-basics" in cids
    assert "wnb:nft:torque" in cids


def test_commercial_12_no_planned_coupons_in_public_snapshot(snapshot_loader: CommercialSnapshotLoader):
    """Test 12: No unreleased/internal coupons (e.g. LOUNGEMEMBER10, LOUNGEELITE25) in public snapshot."""
    for record in snapshot_loader.records:
        if record.coupon_relationship:
            assert record.coupon_relationship not in {"LOUNGEMEMBER10", "LOUNGEELITE25"}
        # All public records must have PUBLIC visibility
        assert record.budly_visibility == "PUBLIC"
        assert record.release_state == "RELEASED"
        assert record.status in {"ACTIVE", "ACTIVE_CATALOG_GAP"}


def test_commercial_13_catalog_manifest_ccs006_audit():
    """Test 13: Catalog manifest declares CCS-006 visibility metrics and sha256 checksums."""
    manifest_path = CATALOG_DIR / "Current" / "catalog-manifest.json"
    assert manifest_path.exists()
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["source_inventory_count"] == 76
    assert manifest["public_record_count"] == 73
    assert manifest["output_record_count"] == 73
    assert manifest["excluded_record_count"] == 3
    assert manifest["pre_release_record_count"] == 0
    assert manifest["internal_only_record_count"] == 0
    assert manifest["visibility_policy"] == "CCS-006"
    assert manifest["visibility_policy_version"] == "0.1"
    assert manifest["validation_status"] == "PASSED"
    assert len(manifest["json_sha256"]) == 64
    assert len(manifest["csv_sha256"]) == 64

