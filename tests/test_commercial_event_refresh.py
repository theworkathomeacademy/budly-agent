"""
Targeted test suite for Commercial Catalog Snapshot Event-Driven Refresh Layer (CCS-001 / CCS-003).
Validates:
- Phase 14: Event Refresh Test Matrix (Tests A through N)
- Phase 15: Staged End-to-End Refresh Test
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from budly_runtime.config import ProductionSettings
from budly_runtime.events import EventLogger
from budly_runtime.model import ProviderResult
from budly_runtime.production_knowledge import ApprovedRepositoryKnowledgeAdapter
from budly_runtime.production_runtime import ProductionConversationRuntime
from budly_runtime.commercial_snapshot.contract import CommercialCatalogRecord
from budly_runtime.commercial_snapshot.events import (
    CommercialRefreshEvent,
    EventRefreshController,
    EventIntakeResult,
)
from budly_runtime.commercial_snapshot.loader import CommercialSnapshotLoader
from budly_runtime.commercial_snapshot.rebuild import rebuild_catalog

ROOT = Path(__file__).resolve().parents[1]


class StagedCommercialMockModel:
    """Mock model that reflects current active knowledge prices."""

    def generate(self, request: Any) -> ProviderResult:
        pkg = getattr(request, "prompt_package", request)
        provider_input = pkg.get("provider_input", [])
        system_content = provider_input[0]["content"] if provider_input else ""
        user_msg = provider_input[1]["content"] if len(provider_input) > 1 else ""
        msg_lower = user_msg.lower()

        price_str = "$1,000"
        try:
            sys_data = json.loads(system_content)
            for layer in sys_data.get("layers", []):
                if layer.get("name") == "RETRIEVED KNOWLEDGE":
                    untrusted = layer.get("content", {}).get("untrusted_data", [])
                    for item in untrusted:
                        content_val = item.get("content", {})
                        if isinstance(content_val, str):
                            content_val = json.loads(content_val)
                        c_name = str(content_val.get("name", "")).strip()
                        c_id = str(content_val.get("canonical_id", "")).strip()
                        if c_name == "Culinary Cannabis" or c_id == "ccc:course:culinary-cannabis":
                            p = content_val.get("price_usd") or content_val.get("price")
                            if p:
                                price_str = f"${int(p):,}"
        except Exception:
            pass

        if "culinary" in msg_lower or "class" in msg_lower or "cooking" in msg_lower:
            payload = {
                "text": f"Our Culinary Cannabis class is currently {price_str}.",
                "intent": "product_guidance",
                "journey": "education",
                "resulting_action": "continue_conversation",
                "selected_product_id": None,
                "requires_human": False,
            }
        else:
            payload = {
                "text": f"Here is information on {user_msg}.",
                "intent": "customer_education",
                "journey": "education",
                "resulting_action": "continue_conversation",
                "selected_product_id": None,
                "requires_human": False,
            }

        return ProviderResult(payload, "staged-mock", "mock-model")


@pytest.fixture
def refresh_env(tmp_path: Path):
    """Setup a complete isolated catalog environment in tmp_path."""
    catalog_dir = tmp_path / "config" / "commercial_catalog"
    catalog_dir.mkdir(parents=True)

    # Initial build from canonical seed
    init_res = rebuild_catalog(
        event_reason="TEST_INIT",
        triggering_entity="TEST_SETUP",
        root_dir=catalog_dir,
        canonical_source_path=ROOT / "config" / "canonical_catalog.json",
        catalog_version="1.0.0-init",
    )
    assert init_res.success is True

    controller = EventRefreshController(
        root_dir=catalog_dir,
        webhook_secret="test-webhook-secret",
        debounce_seconds=0.0,  # Synchronous / immediate for tests
        canonical_source_path=ROOT / "config" / "canonical_catalog.json",
    )
    return catalog_dir, controller


# ==============================================================================
# Phase 14: Event Refresh Test Matrix (Tests A through N)
# ==============================================================================

def test_a_public_product_price_changes(refresh_env):
    """TEST A: Public product price changes → refresh → new price in public snapshot, new manifest version."""
    catalog_dir, controller = refresh_env
    loader = CommercialSnapshotLoader(catalog_dir)
    initial_version = loader.loaded_catalog_version

    # Modify Culinary Cannabis price from $1,000 to $1,200 and recompute checksum
    records = [CommercialCatalogRecord.from_dict(r.to_dict()) for r in loader.records]
    culinary = next(r for r in records if r.canonical_id == "ccc:course:culinary-cannabis")
    culinary.price_usd = 1200.0
    culinary.record_checksum = culinary.compute_checksum()

    event = CommercialRefreshEvent.create(
        event_type="product.updated",
        provider="WOOCOMMERCE",
        provider_entity_id=150,
        reason="PRICE_UPDATE_TO_1200",
        payload={"custom_records": records},
    )
    res = controller.ingest_event(event, synchronous=True)
    assert res.accepted is True
    assert res.rebuild_result is not None
    assert res.rebuild_result.success is True
    assert res.rebuild_result.catalog_version != initial_version

    # Verify loader sees new price
    loader.load()
    updated_rec = loader.get_by_canonical_id("ccc:course:culinary-cannabis")
    assert updated_rec is not None
    assert updated_rec.price_usd == 1200.0


def test_b_draft_product_changes_remains_excluded(refresh_env):
    """TEST B: Draft product changes → no public exposure, no public catalog contamination."""
    catalog_dir, controller = refresh_env
    loader = CommercialSnapshotLoader(catalog_dir)
    assert loader.get_by_canonical_id("wnb:community:lounge-pass") is None

    # Simulate draft product change
    event = CommercialRefreshEvent.create(
        event_type="product.updated",
        provider="WOOCOMMERCE",
        provider_entity_id=1047,  # Lounge Pass (draft)
        reason="DRAFT_EDIT",
    )
    res = controller.ingest_event(event, synchronous=True)
    assert res.accepted is True

    loader.load()
    assert loader.get_by_canonical_id("wnb:community:lounge-pass") is None
    assert loader.record_count == 73  # Remains exactly 73 public records


def test_c_public_product_becomes_hidden(refresh_env):
    """TEST C: Public product becomes hidden → removed from public snapshot after rebuild."""
    catalog_dir, controller = refresh_env
    loader = CommercialSnapshotLoader(catalog_dir)
    records = [CommercialCatalogRecord.from_dict(r.to_dict()) for r in loader.records]
    
    # Change Infused Basics to hidden
    infused = next(r for r in records if r.canonical_id == "ccc:book:infused-basics")
    infused.catalog_visibility = "hidden"
    infused.record_checksum = infused.compute_checksum()

    event = CommercialRefreshEvent.create(
        event_type="product.updated",
        provider="WOOCOMMERCE",
        provider_entity_id=87,
        reason="VISIBILITY_TO_HIDDEN",
        payload={"custom_records": records},
    )
    controller.ingest_event(event, synchronous=True)

    loader.load()
    assert loader.get_by_canonical_id("ccc:book:infused-basics") is None
    assert loader.record_count == 72


def test_d_hidden_product_becomes_published_and_visible(refresh_env):
    """TEST D: Hidden product becomes published + visible → enters public snapshot."""
    catalog_dir, controller = refresh_env
    loader = CommercialSnapshotLoader(catalog_dir)
    records = [CommercialCatalogRecord.from_dict(r.to_dict()) for r in loader.records]

    # Create a previously hidden item and make it visible + published
    new_product = CommercialCatalogRecord(
        canonical_id="ccc:product:wellness-salve",
        sku="CCC-SALVE-01",
        slug="wellness-salve",
        name="Wellness Herbal Salve",
        entity_type="PRODUCT",
        category=["CBD", "Topical"],
        brand="Canna Care Cultivation",
        status="ACTIVE",
        approval_status="OWNER_APPROVED",
        release_state="RELEASED",
        customer_purchasable=True,
        catalog_visibility="visible",
        stock_status="instock",
        price_usd=45.0,
        currency="USD",
        billing_model="ONE_TIME",
        short_summary="Natural CBD wellness herbal salve.",
        description="Full spectrum CBD herbal topical salve.",
        benefits=["Skin nourishment"],
        audience=["Adults"],
        customer_goals=["Topical relief"],
        eligibility_rules=["21+"],
        exclusions=["External use only"],
        fulfillment_type="PHYSICAL_SHIPPING",
        fulfillment_platform="WOOCOMMERCE",
        canonical_url="https://cccultivate.com/product/wellness-salve/",
        checkout_url="https://cccultivate.com/cart/?add-to-cart=999",
        booking_url=None,
        payment_plan_available=False,
        payment_plan_amount=None,
        payment_plan_url=None,
        payment_processor="WOOCOMMERCE",
        coupon_relationship=None,
        wix_plan_id=None,
        wordpress_page_id=None,
        source_authority="woocommerce",
        source_ids={"woocommerce": 999},
        source_updated_at="2026-09-15T15:00:00Z",
        snapshot_generated_at="2026-09-15T15:00:00Z",
        catalog_version="1.0.0",
        budly_visibility="PUBLIC",
    )
    new_product.record_checksum = new_product.compute_checksum()
    records.append(new_product)

    event = CommercialRefreshEvent.create(
        event_type="product.created",
        provider="WOOCOMMERCE",
        provider_entity_id=999,
        reason="PRODUCT_PUBLISHED",
        payload={"custom_records": records},
    )
    controller.ingest_event(event, synchronous=True)

    loader.load()
    rec = loader.get_by_canonical_id("ccc:product:wellness-salve")
    assert rec is not None
    assert rec.price_usd == 45.0
    assert loader.record_count == 74


def test_e_public_product_becomes_draft(refresh_env):
    """TEST E: Public product becomes draft/unpublished → removed from public catalog."""
    catalog_dir, controller = refresh_env
    loader = CommercialSnapshotLoader(catalog_dir)
    records = [CommercialCatalogRecord.from_dict(r.to_dict()) for r in loader.records]

    # Grow Cannabis at Home becomes draft
    grow = next(r for r in records if r.canonical_id == "ccc:course:grow-cannabis-home")
    grow.status = "DRAFT"
    grow.release_state = "APPROVED_NOT_RELEASED"
    grow.customer_purchasable = False
    grow.budly_visibility = "EXCLUDED"
    grow.record_checksum = grow.compute_checksum()

    event = CommercialRefreshEvent.create(
        event_type="product.updated",
        provider="WOOCOMMERCE",
        provider_entity_id=151,
        reason="STATUS_TO_DRAFT",
        payload={"custom_records": records},
    )
    controller.ingest_event(event, synchronous=True)

    loader.load()
    assert loader.get_by_canonical_id("ccc:course:grow-cannabis-home") is None
    assert loader.record_count == 72


def test_f_variation_price_changes(refresh_env):
    """TEST F: Variation price changes → parent/tier relationship retained, new price available (Torque Copper Woo 878)."""
    catalog_dir, controller = refresh_env
    loader = CommercialSnapshotLoader(catalog_dir)
    records = [CommercialCatalogRecord.from_dict(r.to_dict()) for r in loader.records]

    # Verify baseline state
    copper_baseline = next(r for r in records if r.canonical_id == "wnb:nft:torque:copper")
    assert copper_baseline.price_usd == 10000.0
    assert "Copper" in copper_baseline.name
    assert copper_baseline.woo_variation_id == 878
    assert copper_baseline.woo_parent_product_id == 875

    # Update Torque Copper (Woo 878, parent 875) from $10,000 to $11,000
    copper = next(r for r in records if r.canonical_id == "wnb:nft:torque:copper")
    copper.price_usd = 11000.0
    copper.record_checksum = copper.compute_checksum()

    event = CommercialRefreshEvent.create(
        event_type="woocommerce_variation_updated",
        provider="WOOCOMMERCE",
        provider_entity_id=878,
        provider_parent_id=875,
        reason="VARIATION_PRICE_CHANGE",
        payload={"custom_records": records},
    )
    controller.ingest_event(event, synchronous=True)

    loader.load()
    rec = loader.get_by_canonical_id("wnb:nft:torque:copper")
    assert rec is not None
    assert rec.price_usd == 11000.0
    assert "Copper" in rec.name
    assert rec.woo_variation_id == 878
    assert rec.woo_parent_product_id == 875
    assert rec.entity_type == "NFT_MEMBERSHIP_TIER"

    # Verify parent product unchanged and correctly associated
    parent = loader.get_by_canonical_id("wnb:nft:torque")
    assert parent is not None
    assert parent.entity_type == "NFT_MEMBERSHIP_PARENT"
    assert parent.woo_parent_product_id == 875

    # Verify Gold tier does NOT exist in canonical Torque tiers
    assert loader.get_by_canonical_id("wnb:nft:torque:gold") is None
    assert loader.get_by_canonical_id("wnb:nft:torque:silver") is None

    # Verify valid canonical tier set: Bronze (877), Copper (878), Titanium (879), Platinum (880)
    bronze = loader.get_by_canonical_id("wnb:nft:torque:bronze")
    titanium = loader.get_by_canonical_id("wnb:nft:torque:titanium")
    platinum = loader.get_by_canonical_id("wnb:nft:torque:platinum")
    assert bronze is not None and bronze.price_usd == 5000.0
    assert titanium is not None and titanium.price_usd == 20000.0
    assert platinum is not None and platinum.price_usd == 40000.0


def test_g_duplicate_event_delivered_twice(refresh_env):
    """TEST G: Duplicate event delivered twice → idempotent behavior (1 effective rebuild)."""
    catalog_dir, controller = refresh_env
    loader = CommercialSnapshotLoader(catalog_dir)

    event = CommercialRefreshEvent.create(
        event_type="product.updated",
        provider="WOOCOMMERCE",
        provider_entity_id=150,
        idempotency_key="idemp-key-unique-001",
    )

    # First delivery: accepted
    r1 = controller.ingest_event(event, synchronous=True)
    assert r1.accepted is True
    assert r1.status == "REBUILT_SYNCHRONOUSLY"

    # Second delivery with same idempotency key: suppressed
    r2 = controller.ingest_event(event, synchronous=True)
    assert r2.accepted is True
    assert r2.status == "DUPLICATE_SUPPRESSED"
    assert r2.rebuild_result is None


def test_h_rapid_series_of_updates_debounce_coalescing(tmp_path: Path):
    """TEST H: Rapid series of updates → debounce/coalescing produces single final rebuild."""
    catalog_dir = tmp_path / "config" / "commercial_catalog"
    catalog_dir.mkdir(parents=True)
    rebuild_catalog(
        event_reason="INIT",
        triggering_entity="TEST",
        root_dir=catalog_dir,
        canonical_source_path=ROOT / "config" / "canonical_catalog.json",
        catalog_version="1.0.0-init",
    )

    rebuild_count = 0

    def mock_rebuild(events):
        nonlocal rebuild_count
        rebuild_count += 1
        return rebuild_catalog(
            event_reason="COALESCED",
            triggering_entity=f"BATCH:{len(events)}",
            root_dir=catalog_dir,
            canonical_source_path=ROOT / "config" / "canonical_catalog.json",
        )

    queue = EventRefreshController(
        root_dir=catalog_dir,
        debounce_seconds=0.2,  # Short debounce window
        canonical_source_path=ROOT / "config" / "canonical_catalog.json",
    )
    queue.debounce_queue.rebuild_callback = mock_rebuild

    # Rapid burst of 5 events
    for i in range(5):
        ev = CommercialRefreshEvent.create(
            event_type="product.updated",
            provider_entity_id=100 + i,
            idempotency_key=f"burst-event-{i}",
        )
        queue.ingest_event(ev, synchronous=False)

    assert queue.debounce_queue.pending_count == 5

    # Wait for debounce window to fire
    time.sleep(0.35)

    assert rebuild_count == 1
    assert queue.debounce_queue.pending_count == 0


def test_i_malformed_event_rejected(refresh_env):
    """TEST I: Malformed event → rejected, no rebuild."""
    catalog_dir, controller = refresh_env
    loader = CommercialSnapshotLoader(catalog_dir)
    initial_version = loader.loaded_catalog_version

    # Missing event_type / non-qualifying
    res = controller.ingest_event({"invalid_payload": True, "event_type": "unknown_event_type"})
    assert res.accepted is False
    assert res.status == "REJECTED_NON_QUALIFYING"

    loader.load()
    assert loader.loaded_catalog_version == initial_version


def test_j_failed_validation_after_event_retains_lkg(refresh_env):
    """TEST J: Failed validation after event → Quarantine, Current unchanged, LKG remains active."""
    catalog_dir, controller = refresh_env
    loader = CommercialSnapshotLoader(catalog_dir)
    initial_version = loader.loaded_catalog_version
    initial_count = loader.record_count

    # Inject invalid record with missing canonical_id and negative price
    records = [CommercialCatalogRecord.from_dict(r.to_dict()) for r in loader.records]
    records[0].price_usd = -500.0  # Invalid price violates validation

    event = CommercialRefreshEvent.create(
        event_type="product.updated",
        provider="WOOCOMMERCE",
        provider_entity_id=150,
        payload={"custom_records": records},
    )
    res = controller.ingest_event(event, synchronous=True)
    assert res.accepted is True
    assert res.rebuild_result is not None
    assert res.rebuild_result.success is False
    assert res.rebuild_result.quarantined_to is not None
    assert Path(res.rebuild_result.quarantined_to).exists()

    # Current remains untouched
    loader.load()
    assert loader.loaded_catalog_version == initial_version
    assert loader.record_count == initial_count


def test_k_successful_rebuild_promotes_and_archives(refresh_env):
    """TEST K: Successful rebuild → Current promoted, prior Current archived, loader sees new version."""
    catalog_dir, controller = refresh_env
    loader = CommercialSnapshotLoader(catalog_dir)
    v1 = loader.loaded_catalog_version

    res = controller.manual_rebuild("operator_admin", reason="TEST_MANUAL_PROMOTION")
    assert res.success is True
    assert res.catalog_version != v1

    # Check Archive contains prior version folder
    archive_dir = catalog_dir / "Archive"
    archived_folders = list(archive_dir.glob("catalog-v*"))
    assert len(archived_folders) >= 1

    # Check Current updated
    loader.load()
    assert loader.loaded_catalog_version == res.catalog_version


def test_l_lounge_member_draft_update_remains_absent(refresh_env):
    """TEST L: Lounge Member draft update → remains absent from public snapshot."""
    catalog_dir, controller = refresh_env
    loader = CommercialSnapshotLoader(catalog_dir)

    event = CommercialRefreshEvent.create(
        event_type="product.updated",
        provider="WOOCOMMERCE",
        provider_entity_id=1048,  # Lounge Member (draft)
        reason="DRAFT_LOUNGE_MEMBER_EDIT",
    )
    res = controller.ingest_event(event, synchronous=True)
    assert res.accepted is True

    loader.load()
    assert loader.get_by_canonical_id("wnb:community:lounge-member") is None
    assert "wnb:community:lounge-member" not in [r.canonical_id for r in loader.records]


def test_m_lounge_elite_draft_update_remains_absent(refresh_env):
    """TEST M: Lounge Elite draft update → remains absent from public snapshot."""
    catalog_dir, controller = refresh_env
    loader = CommercialSnapshotLoader(catalog_dir)

    event = CommercialRefreshEvent.create(
        event_type="product.updated",
        provider="WOOCOMMERCE",
        provider_entity_id=1049,  # Lounge Elite (draft)
        reason="DRAFT_LOUNGE_ELITE_EDIT",
    )
    res = controller.ingest_event(event, synchronous=True)
    assert res.accepted is True

    loader.load()
    assert loader.get_by_canonical_id("wnb:community:lounge-elite") is None
    assert "wnb:community:lounge-elite" not in [r.canonical_id for r in loader.records]


def test_n_planned_coupon_metadata_changes_no_coupon_leakage(refresh_env):
    """TEST N: Planned coupon metadata changes → no public coupon leakage."""
    catalog_dir, controller = refresh_env
    loader = CommercialSnapshotLoader(catalog_dir)

    event = CommercialRefreshEvent.create(
        event_type="product.updated",
        provider="WOOCOMMERCE",
        provider_entity_id=150,
        reason="INTERNAL_COUPON_POLICY_CHANGE",
        payload={"coupon_codes": ["SECRET100", "DISCOUNT50"]},
    )
    res = controller.ingest_event(event, synchronous=True)
    assert res.accepted is True

    loader.load()
    manifest_data = json.loads((catalog_dir / "Current" / "catalog-manifest.json").read_text(encoding="utf-8"))
    manifest_str = json.dumps(manifest_data)
    assert "SECRET100" not in manifest_str
    assert "DISCOUNT50" not in manifest_str


# ==============================================================================
# Phase 15: Staged End-to-End Refresh Simulation
# ==============================================================================

def test_staged_end_to_end_refresh_simulation(tmp_path: Path):
    """
    Simulate full end-to-end lifecycle:
    1. Staged runtime initialized with current catalog ($1,000 Culinary Cannabis)
    2. Budly queried: answers $1,000
    3. Commercial price change event received ($1,250 Culinary Cannabis)
    4. Event refresh controller rebuilds, validates, publishes snapshot
    5. Runtime adapter reload listener reloads cache
    6. Budly queried: answers $1,250
    """
    catalog_dir = tmp_path / "config" / "commercial_catalog"
    catalog_dir.mkdir(parents=True)

    rebuild_catalog(
        event_reason="E2E_INIT",
        triggering_entity="E2E_SETUP",
        root_dir=catalog_dir,
        canonical_source_path=ROOT / "config" / "canonical_catalog.json",
        catalog_version="1.0.0-e2e-1",
    )

    settings = ProductionSettings(
        environment="staging",
        bind_host="127.0.0.1",
        port=8791,
        shared_secret="s" * 32,
        model_provider="openai",
        model_name="mock-model",
        model_api_key="mock-key",
        knowledge_path=Path("config"),
        request_timeout_seconds=10.0,
        provider_retry_count=1,
        commercial_snapshot_enabled=True,
    )
    knowledge = ApprovedRepositoryKnowledgeAdapter(
        ROOT / "config/policies.json",
        ROOT / "config/products.json",
        ROOT / "config/budly_runtime/education-corpus-v0.1.json",
        ROOT / "config/budly_runtime/commercial-knowledge-v1.0.json",
        commercial_snapshot_path=catalog_dir,
        commercial_snapshot_enabled=True,
    )
    mock_model = StagedCommercialMockModel()
    runtime = ProductionConversationRuntime(
        settings,
        ROOT,
        model_adapter=mock_model,
        knowledge_adapter=knowledge,
        events=EventLogger(),
    )

    controller = EventRefreshController(
        root_dir=catalog_dir,
        webhook_secret="test-webhook-secret",
        debounce_seconds=0.0,
        canonical_source_path=ROOT / "config" / "canonical_catalog.json",
    )
    # Register reload listener so knowledge adapter updates dynamically on rebuild
    controller.register_reload_listener(lambda _: knowledge.reload())

    # Step 1: Initial query to Budly
    req1 = {
        "conversation_id": "conv_e2e_refresh_001",
        "message": "What is the cost of the Culinary Cannabis class?",
        "channel": "website_chat",
        "correlation_id": str(uuid4()),
        "use_durable_memory": False,
    }
    resp1 = runtime.turn(req1)
    assert resp1["success"] is True
    assert "$1,000" in resp1["response"]["text"]

    # Step 2: Commercial change event ($1,250)
    loader = CommercialSnapshotLoader(catalog_dir)
    records = [CommercialCatalogRecord.from_dict(r.to_dict()) for r in loader.records]
    culinary = next(r for r in records if r.canonical_id == "ccc:course:culinary-cannabis")
    culinary.price_usd = 1250.0
    culinary.record_checksum = culinary.compute_checksum()

    event = CommercialRefreshEvent.create(
        event_type="product.updated",
        provider="WOOCOMMERCE",
        provider_entity_id=150,
        reason="PRICE_CHANGE_TO_1250",
        payload={"custom_records": records},
    )
    intake_res = controller.ingest_event(event, synchronous=True)
    assert intake_res.accepted is True
    assert intake_res.rebuild_result is not None
    assert intake_res.rebuild_result.success is True

    # Step 3: Query Budly after event refresh
    req2 = {
        "conversation_id": "conv_e2e_refresh_002",
        "message": "What is the cost of the Culinary Cannabis class now?",
        "channel": "website_chat",
        "correlation_id": str(uuid4()),
        "use_durable_memory": False,
    }
    resp2 = runtime.turn(req2)
    assert resp2["success"] is True
    assert "$1,250" in resp2["response"]["text"]
