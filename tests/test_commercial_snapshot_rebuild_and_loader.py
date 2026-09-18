"""Comprehensive Unit & Lifecycle Tests for Commercial Snapshot System.

Verifies:
- Rebuild pipeline
- CSV/JSON generation parity
- Manifest hashing and verification
- Quarantine isolation upon corrupted/invalid records
- Last-known-good retention upon reload failure
- Lookups by SKU, WooCommerce ID, Wix Plan ID, and Entity Type
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
import pytest

from src.budly_runtime.commercial_snapshot.contract import CommercialCatalogRecord
from src.budly_runtime.commercial_snapshot.fetcher import WooCommerceCatalogFetcher
from src.budly_runtime.commercial_snapshot.loader import CommercialSnapshotLoader
from src.budly_runtime.commercial_snapshot.rebuild import normalize_catalog_entry, rebuild_catalog
from src.budly_runtime.commercial_snapshot.validator import CommercialSnapshotValidator

ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT / "config" / "commercial_catalog"


def test_rebuild_success_and_artifacts():
    result = rebuild_catalog(
        event_reason="TEST_REBUILD",
        triggering_entity="TEST_RUNNER",
        root_dir=CATALOG_DIR,
        canonical_source_path=ROOT / "config" / "canonical_catalog.json",
        catalog_version="1.9.0-test-rebuild",
    )
    assert result.success is True
    assert result.validation_status == "PASSED"
    assert result.record_count > 0
    assert Path(result.json_path).exists()
    assert Path(result.csv_path).exists()
    assert Path(result.manifest_path).exists()
    assert len(result.json_sha256) == 64
    assert len(result.csv_sha256) == 64


def test_loader_indexing_and_lookups():
    loader = CommercialSnapshotLoader(CATALOG_DIR)
    assert loader.record_count > 0
    assert loader.loaded_catalog_version is not None

    # Lookup by canonical_id
    rec = loader.get_by_canonical_id("ccc:book:infused-basics")
    assert rec is not None
    assert rec.name == "Infused Basics: The Beginner's Guide to Infuse Everything Edible"

    # Lookup by Woo ID (150 is Culinary Cannabis)
    rec_woo = loader.get_by_woo_id(150)
    assert rec_woo is not None
    assert rec_woo.canonical_id == "ccc:course:culinary-cannabis"

    # Lookup by Wix Plan ID on public loader fails closed (excluded community membership)
    rec_wix = loader.get_by_wix_plan_id("1658a089-db78-418c-85ed-ac01d5bcabb0")
    assert rec_wix is None

    # Lookup by SKU
    rec_sku = loader.get_by_sku(rec.sku)
    assert rec_sku is not None
    assert rec_sku.canonical_id == rec.canonical_id

    # Lookup by entity_type
    nfts = loader.get_by_entity_type("NFT_MEMBERSHIP_PARENT")
    assert len(nfts) == 10

    # Verify Wix Plan ID is preserved in internal inventory
    internal_inv_path = CATALOG_DIR / "Internal" / "budly-canonical-inventory.json"
    assert internal_inv_path.exists()
    with open(internal_inv_path, "r", encoding="utf-8") as f:
        internal_records = json.load(f)
    wix_matches = [r for r in internal_records if r.get("wix_plan_id") == "1658a089-db78-418c-85ed-ac01d5bcabb0"]
    assert len(wix_matches) == 1
    assert wix_matches[0]["canonical_id"] == "wnb:community:lounge-member"


def test_quarantine_on_fatal_validation_failure(tmp_path: Path):
    # Create invalid record (e.g. APPROVED_NOT_RELEASED with customer_purchasable=True)
    invalid_record = CommercialCatalogRecord(
        canonical_id="wnb:community:bad-record",
        sku="SKU-BAD",
        slug="bad-record",
        name="Bad Record",
        entity_type="COMMUNITY_MEMBERSHIP",
        category=["Test"],
        brand="Test Brand",
        status="DRAFT",
        approval_status="OWNER_APPROVED",
        release_state="APPROVED_NOT_RELEASED",
        customer_purchasable=True,  # VIOLATION!
        catalog_visibility="hidden",
        stock_status="not_applicable",
        price_usd=0.0,
        currency="USD",
        billing_model="FREE",
        short_summary="Test",
        description="Test",
        benefits=["Test"],
        audience=["Test"],
        customer_goals=["Test"],
        eligibility_rules=[],
        exclusions=[],
        fulfillment_type="MEMBERSHIP_ACCESS",
        fulfillment_platform="WIX_PLANS",
        canonical_url="https://wakenbakelounge.com/bad",
        checkout_url=None,
        booking_url=None,
        payment_plan_available=False,
        payment_plan_amount=None,
        payment_plan_url=None,
        payment_processor="NONE",
        coupon_relationship=None,
        wix_plan_id=None,
        wordpress_page_id=None,
        source_authority="owner_approved_specification",
        source_ids={},
        source_updated_at=None,
        snapshot_generated_at="2026-09-14T00:00:00Z",
        catalog_version="1.0.0",
    )

    result = rebuild_catalog(
        event_reason="TEST_FAILURE",
        triggering_entity="TEST_RUNNER",
        root_dir=tmp_path,
        custom_records=[invalid_record],
        catalog_version="1.0.0-bad",
    )

    assert result.success is False
    assert result.validation_status == "FAILED_IN_MEMORY"
    assert len(result.errors) > 0
    assert result.quarantined_to is not None
    assert Path(result.quarantined_to).exists()


def test_last_known_good_retention_on_corrupt_reload(tmp_path: Path):
    # Setup valid initial catalog in tmp_path
    init_result = rebuild_catalog(
        event_reason="INIT",
        triggering_entity="TEST_RUNNER",
        root_dir=tmp_path,
        canonical_source_path=ROOT / "config" / "canonical_catalog.json",
        catalog_version="1.0.0-good",
    )
    assert init_result.success is True

    loader = CommercialSnapshotLoader(tmp_path)
    assert loader.loaded_catalog_version == "1.0.0-good"
    good_record_count = loader.record_count

    # Corrupt the JSON file by tampering with bytes (manifest hash mismatch)
    json_file = tmp_path / "Current" / "budly-commercial-catalog.json"
    json_file.write_text("[]", encoding="utf-8")

    # Reload should fail and preserve last known good state
    reload_success = loader.load()
    assert reload_success is False
    assert loader.loaded_catalog_version == "1.0.0-good"
    assert loader.record_count == good_record_count


def test_authenticated_fetch_includes_draft_products():
    """Prove that authenticated fetch retrieves products with status='draft'."""
    raw_payload = [
        {"id": 1047, "name": "Wake'n'Bake Lounge Pass", "status": "draft", "type": "simple", "price": "0.00"},
        {"id": 875, "name": "Torque", "status": "publish", "type": "variable", "price": "5000.00"},
    ]

    def mock_opener(req, timeout=15.0):
        class MockResp:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self):
                return json.dumps(raw_payload).encode("utf-8")
        return MockResp()

    fetcher = WooCommerceCatalogFetcher(
        base_url="https://cccultivate.com/wp-json/wc/v3",
        consumer_key="ck_test",
        consumer_secret="cs_test",
        opener=mock_opener,
    )
    products = fetcher.fetch_all_products(status="any")
    assert len(products) == 2
    draft_products = [p for p in products if p["status"] == "draft"]
    assert len(draft_products) == 1
    assert draft_products[0]["id"] == 1047


def test_authenticated_fetch_includes_hidden_products():
    """Prove that authenticated fetch retrieves products with catalog_visibility='hidden'."""
    raw_payload = [
        {"id": 1048, "name": "Wake'n'Bake Lounge Member", "status": "draft", "catalog_visibility": "hidden", "price": "9.99"},
        {"id": 1049, "name": "Wake'n'Bake Lounge Elite", "status": "draft", "catalog_visibility": "hidden", "price": "24.99"},
    ]

    def mock_opener(req, timeout=15.0):
        class MockResp:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self):
                return json.dumps(raw_payload).encode("utf-8")
        return MockResp()

    fetcher = WooCommerceCatalogFetcher(
        base_url="https://cccultivate.com/wp-json/wc/v3",
        consumer_key="ck_test",
        consumer_secret="cs_test",
        opener=mock_opener,
    )
    products = fetcher.fetch_all_products(status="any")
    hidden_products = [p for p in products if p.get("catalog_visibility") == "hidden"]
    assert len(hidden_products) == 2
    assert {p["id"] for p in hidden_products} == {1048, 1049}


def test_1047_1048_1049_survive_normalization():
    """Prove that raw WooCommerce representations of 1047, 1048, and 1049 survive normalization."""
    mock_1047 = {
        "id": 1047,
        "canonical_id": "wnb:community:lounge-pass",
        "name": "Wake'n'Bake Lounge Pass",
        "slug": "lounge-pass",
        "sku": "WNB-MBR-PASS",
        "status": "draft",
        "catalog_visibility": "hidden",
        "price": "0.00",
        "regular_price": "0.00",
        "stock_status": "instock",
        "date_modified_gmt": "2026-09-14T06:50:20",
    }
    mock_1048 = {
        "id": 1048,
        "canonical_id": "wnb:community:lounge-member",
        "name": "Wake'n'Bake Lounge Member",
        "slug": "lounge-member",
        "sku": "WNB-MBR-MEMBER",
        "status": "draft",
        "catalog_visibility": "hidden",
        "price": "9.99",
        "regular_price": "9.99",
        "stock_status": "instock",
        "date_modified_gmt": "2026-09-14T06:50:20",
    }
    mock_1049 = {
        "id": 1049,
        "canonical_id": "wnb:community:lounge-elite",
        "name": "Wake'n'Bake Lounge Elite",
        "slug": "lounge-elite",
        "sku": "WNB-MBR-ELITE",
        "status": "draft",
        "catalog_visibility": "hidden",
        "price": "24.99",
        "regular_price": "24.99",
        "stock_status": "instock",
        "date_modified_gmt": "2026-09-14T06:50:20",
    }

    for raw in [mock_1047, mock_1048, mock_1049]:
        rec = normalize_catalog_entry(raw, "1.0.0-test", "2026-09-14T12:00:00Z")
        assert rec.status == "DRAFT"
        assert rec.release_state == "APPROVED_NOT_RELEASED"
        assert rec.customer_purchasable is False
        assert rec.catalog_visibility == "hidden"
        assert rec.woo_product_id == raw["id"]
        assert rec.price_usd == float(raw["price"])
        assert rec.source_updated_at == "2026-09-14T06:50:20"


def test_woo_source_fields_override_stale_local_commercial_values():
    """Prove that live WooCommerce fields override stale local commercial values."""
    live_woo_entry = {
        "id": 87,
        "canonical_id": "ccc:book:infused-basics",
        "name": "Infused Basics - Special Live Edition",
        "sku": "CCC-BK-INF-LIVE",
        "slug": "infused-basics-live",
        "status": "publish",
        "price": "49.99",
        "regular_price": "49.99",
        "stock_status": "instock",
        "date_modified_gmt": "2026-09-14T10:00:00Z",
    }

    rec = normalize_catalog_entry(live_woo_entry, "1.0.0-test", "2026-09-14T12:00:00Z")
    assert rec.name == "Infused Basics - Special Live Edition"
    assert rec.sku == "CCC-BK-INF-LIVE"
    assert rec.slug == "infused-basics-live"
    assert rec.price_usd == 49.99
    assert rec.status == "ACTIVE"
    assert rec.source_updated_at == "2026-09-14T10:00:00Z"


def test_enrichment_cannot_override_authoritative_woo_price_status():
    """Prove that enrichment cannot override authoritative WooCommerce price and status."""
    # Even if enrichment has price_usd=75.0, raw WooCommerce price 99.00 takes precedence
    live_service = {
        "id": 1046,
        "canonical_id": "ccc:service:is-cannabis-right-for-me",
        "status": "publish",
        "price": "99.00",
        "regular_price": "99.00",
    }

    rec = normalize_catalog_entry(live_service, "1.0.0-test", "2026-09-14T12:00:00Z")
    assert rec.price_usd == 99.00
    assert rec.status == "ACTIVE"


def test_manifest_provenance_accurately_describes_rebuild_source(tmp_path: Path):
    """Prove that manifest provenance accurately reflects the rebuild source."""
    result = rebuild_catalog(
        event_reason="AUTHENTICATED_WOOCOMMERCE_REBUILD",
        triggering_entity="WOOCOMMERCE_REST_V3",
        root_dir=tmp_path,
        canonical_source_path=ROOT / "config" / "canonical_catalog.json",
        catalog_version="1.0.0-provenance",
        source_max_updated_at="2026-09-14T06:50:20Z",
    )
    assert result.success is True
    assert result.validation_status == "PASSED"

    manifest_file = tmp_path / "Current" / "catalog-manifest.json"
    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)

    assert manifest_data["event_reason"] == "AUTHENTICATED_WOOCOMMERCE_REBUILD"
    assert manifest_data["triggering_entity"] == "WOOCOMMERCE_REST_V3"
    assert manifest_data["source_max_updated_at"] == "2026-09-14T06:50:20Z"
    assert manifest_data["catalog_version"] == "1.0.0-provenance"

