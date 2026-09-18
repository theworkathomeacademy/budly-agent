"""Budly Commercial Catalog Snapshot System (CCS-001 / CCS-002 / CCS-003)."""

from .contract import CatalogManifest, CommercialCatalogRecord
from .enrichment import APPROVED_ENRICHMENT_REGISTRY, get_approved_enrichment
from .fetcher import WooCommerceCatalogFetcher
from .generator import CommercialSnapshotGenerator
from .loader import CommercialSnapshotLoader
from .rebuild import RebuildResult, rebuild_catalog
from .resolver import DeterministicEntityResolver, EntityResolutionResult
from .returning_customer import (
    CustomerVerificationState,
    EntitlementRecord,
    ReturningCustomerContext,
    ReturningCustomerRetrievalService,
)
from .validator import CommercialSnapshotValidator, SnapshotValidationError

__all__ = [
    "CatalogManifest",
    "CommercialCatalogRecord",
    "CommercialSnapshotGenerator",
    "CommercialSnapshotLoader",
    "CommercialSnapshotValidator",
    "CustomerVerificationState",
    "DeterministicEntityResolver",
    "EntityResolutionResult",
    "EntitlementRecord",
    "RebuildResult",
    "ReturningCustomerContext",
    "ReturningCustomerRetrievalService",
    "SnapshotValidationError",
    "WooCommerceCatalogFetcher",
    "get_approved_enrichment",
    "rebuild_catalog",
]
