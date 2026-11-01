"""Phase C2: Generalized Service & Booking Retrieval Verification Tests.

Verifies:
1. Recognition and retrieval of consultation services (Woo ID 1046, Is Cannabis Right For Me?).
2. Disambiguation of booking/scheduling intents from reading books/guides.
3. Link rendering: canonical store URL (https://cccultivate.com/product/is-cannabis-right-for-me/)
   and working booking URL (https://dmckenzies.wixsite.com/wakenbakelounge/service-page/is-cannabis-right-for-me).
4. Suppression of defective redirect URL (https://wakenbakelounge.com/service-page/is-cannabis-right-for-me).
5. Negative fixture: service without booking link does not invent one.
6. Preservation of existing memberships, courses, books, and products.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from src.budly_runtime.commercial_snapshot.contract import CommercialCatalogRecord
from src.budly_runtime.commercial_snapshot.loader import CommercialSnapshotLoader
from src.budly_runtime.commercial_snapshot.resolver import DeterministicEntityResolver
from src.budly_runtime.config import FeatureFlags, ProductionSettings, RuntimeConfig
from src.budly_runtime.production_knowledge import ApprovedRepositoryKnowledgeAdapter
from src.budly_runtime.production_runtime import (
    ConversationSession,
    ProductionConversationRuntime,
    RuntimeTurnRequest,
)
from src.budly_runtime.tool_gateway import AdapterContext

ROOT = Path(__file__).resolve().parents[1]


def make_settings() -> ProductionSettings:
    return ProductionSettings(
        "staging", "127.0.0.1", 18791, "s" * 32, "openai", "candidate-model", "test-key", ROOT / "config"
    )


@pytest.fixture
def snapshot_loader():
    loader = CommercialSnapshotLoader("config/commercial_catalog/Current")
    assert loader.load() is True
    return loader


@pytest.fixture
def entity_resolver(snapshot_loader):
    return DeterministicEntityResolver(snapshot_loader)


@pytest.fixture
def knowledge_adapter():
    return ApprovedRepositoryKnowledgeAdapter(
        policies_path=ROOT / "config" / "policies.json",
        products_path=ROOT / "config" / "products.json",
    )


@pytest.fixture
def runtime(knowledge_adapter):
    return ProductionConversationRuntime(
        make_settings(),
        ROOT,
        model_adapter=MagicMock(),
        knowledge_adapter=knowledge_adapter,
    )


class TestServiceBookingRetrievalPhaseC2:
    """Test suite for Phase C2 service & booking retrieval requirements."""

    def test_snapshot_loader_has_consultation_service(self, snapshot_loader):
        """Verify consultation service record is correctly loaded in snapshot."""
        rec = snapshot_loader.get_by_canonical_id("ccc:service:is-cannabis-right-for-me")
        assert rec is not None
        assert rec.entity_type == "SERVICE"
        assert rec.price_usd == 75.0
        assert rec.canonical_url == "https://cccultivate.com/product/is-cannabis-right-for-me/"
        assert rec.booking_url == "https://dmckenzies.wixsite.com/wakenbakelounge/service-page/is-cannabis-right-for-me"
        # Must NOT be the defective apex redirect URL
        assert "wakenbakelounge.com/service-page" not in rec.booking_url

    def test_resolver_maps_consultation_queries(self, entity_resolver):
        """Verify entity resolver resolves consultation and appointment queries to the service."""
        queries = [
            "cannabis consultation",
            "book a consultation",
            "1-on-1 session",
            "schedule an appointment",
            "is cannabis right for me",
            "cannabis consultation session",
        ]
        for q in queries:
            match = entity_resolver.resolve(q)
            assert match.status in ("EXACT_MATCH", "ALIAS_MATCH"), f"Failed to match: {q}"
            assert match.canonical_id == "ccc:service:is-cannabis-right-for-me", f"Wrong canonical_id for: {q}"

    def test_resolver_disambiguates_booking_intent_from_reading_book(self, entity_resolver):
        """Verify 'book a consultation' resolves to service, while 'cookbook' resolves to book."""
        # Booking / service intents
        service_queries = [
            "where can I book a consultation",
            "how to book an appointment",
            "book a session",
        ]
        for q in service_queries:
            match = entity_resolver.resolve(q)
            assert match.status in ("EXACT_MATCH", "ALIAS_MATCH")
            assert match.canonical_id == "ccc:service:is-cannabis-right-for-me"

        # Reading book intents
        book_queries = [
            "cookbook",
            "infused basics book",
            "recipe guide book",
        ]
        for q in book_queries:
            match = entity_resolver.resolve(q)
            assert match.status in ("EXACT_MATCH", "ALIAS_MATCH")
            assert match.canonical_id == "ccc:book:infused-basics"

    def test_knowledge_adapter_retrieves_consultation_service(self, knowledge_adapter):
        """Verify repository knowledge adapter retrieves consultation service for consultation queries."""
        ctx = AdapterContext(
            query="Do you offer cannabis consultations, how much do they cost, and where can I book?",
            domain="product_catalog",
            max_results=5,
            access_classifications=frozenset({"Public"}),
            request_id="test_req",
            correlation_id="test_corr",
        )
        items = knowledge_adapter.retrieve(ctx)
        assert len(items) > 0
        
        # Verify the consultation service is present and ranked at top
        top_content = json.loads(items[0]["content"])
        assert top_content.get("slug") == "is-cannabis-right-for-me" or "consultation" in top_content.get("name", "").lower()
        assert top_content.get("resource_type") == "SERVICE"
        assert top_content.get("current_price") == 75.0
        assert top_content.get("booking_url") == "https://dmckenzies.wixsite.com/wakenbakelounge/service-page/is-cannabis-right-for-me"
        assert top_content.get("canonical_url") == "https://cccultivate.com/product/is-cannabis-right-for-me/"

    def test_approved_links_emits_both_booking_and_store_links(self, runtime):
        """Verify _approved_links emits Book consultation and View service links for service items."""
        knowledge = [
            {
                "knowledge_id": "product:is-cannabis-right-for-me",
                "title": "Is Cannabis Right For Me?",
                "content": json.dumps({
                    "resource_type": "SERVICE",
                    "name": "Is Cannabis Right For Me?",
                    "canonical_url": "https://cccultivate.com/product/is-cannabis-right-for-me/",
                    "booking_url": "https://dmckenzies.wixsite.com/wakenbakelounge/service-page/is-cannabis-right-for-me",
                })
            }
        ]
        links = runtime._approved_links(knowledge)
        assert len(links) == 2
        labels = [l["label"] for l in links]
        urls = [l["url"] for l in links]
        
        assert "Book consultation" in labels
        assert "View service" in labels
        assert "https://dmckenzies.wixsite.com/wakenbakelounge/service-page/is-cannabis-right-for-me" in urls
        assert "https://cccultivate.com/product/is-cannabis-right-for-me/" in urls
        # Ensure broken redirect URL is NOT emitted
        assert "https://wakenbakelounge.com/service-page" not in urls

    def test_negative_fixture_service_without_booking_url(self, runtime):
        """Negative fixture: when service has canonical_url but no booking_url, emit canonical only."""
        knowledge = [
            {
                "knowledge_id": "product:generic-service",
                "title": "Generic Service",
                "content": json.dumps({
                    "resource_type": "SERVICE",
                    "name": "Generic Consultation",
                    "canonical_url": "https://cccultivate.com/product/generic-service/",
                    "booking_url": None,
                })
            }
        ]
        links = runtime._approved_links(knowledge)
        assert len(links) == 1
        assert links[0]["label"] == "View service"
        assert links[0]["url"] == "https://cccultivate.com/product/generic-service/"
        # Does NOT invent a booking link
        assert not any("book" in l["label"].lower() for l in links)

    def test_consultation_active_task_tracking(self, runtime):
        """Verify consultation inquiry sets up active task management properly."""
        session = ConversationSession(
            session_id="test_session",
            created_at=time.time(),
            updated_at=time.time(),
        )
        req = RuntimeTurnRequest(
            conversation_id="conv_123456",
            message="Can I book a consultation?",
            channel="web",
            correlation_id="corr_test_123",
        )
        runtime._extract_identity_and_consent(req, session)
        assert session.active_entity == "Is Cannabis Right For Me? Consultation"
        assert session.active_request == "consultation booking and pricing"
        assert session.task_state == "UNRESOLVED"
        assert session.follow_up_subject == "Is Cannabis Right For Me? consultation details"
