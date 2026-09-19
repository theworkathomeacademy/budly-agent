"""
Commercial Catalog Snapshot Event-Driven Refresh Layer (CCS-001 / CCS-003).

Provides deterministic event intake, HMAC verification, deduplication, debounce/coalescing,
full public catalog rebuild dispatching, runtime cache invalidation, and scheduled reconciliation.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence
from uuid import UUID, uuid4

from .contract import CatalogManifest, CommercialCatalogRecord
from .rebuild import RebuildResult, rebuild_catalog

logger = logging.getLogger("commercial_catalog.events")

QUALIFYING_EVENT_TYPES = frozenset({
    "product.created",
    "product.updated",
    "product.deleted",
    "product.restored",
    "product.trashed",
    "woocommerce_variation_created",
    "woocommerce_variation_updated",
    "woocommerce_variation_deleted",
    "action.woocommerce_variation_created",
    "action.woocommerce_variation_updated",
    "action.woocommerce_variation_deleted",
    "manual_rebuild",
    "scheduled_reconciliation",
    "enrichment_updated",
    "REBUILD_EVENT",
})


@dataclass(frozen=True)
class CommercialRefreshEvent:
    event_id: str
    event_type: str
    provider: str
    provider_entity_id: str | int | None
    provider_parent_id: str | int | None
    occurred_at: str
    received_at: str
    source_updated_at: str | None
    reason: str
    correlation_id: str
    idempotency_key: str
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        event_type: str,
        provider: str = "WOOCOMMERCE",
        provider_entity_id: str | int | None = None,
        provider_parent_id: str | int | None = None,
        reason: str = "COMMERCIAL_TRUTH_CHANGE",
        correlation_id: str | None = None,
        occurred_at: str | None = None,
        source_updated_at: str | None = None,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> "CommercialRefreshEvent":
        now_iso = datetime.now(timezone.utc).isoformat()
        eid = str(uuid4())
        corr_id = correlation_id or str(uuid4())
        occ_at = occurred_at or now_iso
        
        # Scrub payload to ensure zero PII and zero secrets
        scrubbed_payload = dict(payload or {})
        for sensitive_key in ["customer", "user", "billing", "shipping", "email", "password", "secret", "token", "key", "api_key"]:
            scrubbed_payload.pop(sensitive_key, None)

        if not idempotency_key:
            raw_key = f"{event_type}:{provider}:{provider_entity_id}:{provider_parent_id}:{occ_at}"
            idempotency_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

        return cls(
            event_id=eid,
            event_type=event_type,
            provider=provider,
            provider_entity_id=provider_entity_id,
            provider_parent_id=provider_parent_id,
            occurred_at=occ_at,
            received_at=now_iso,
            source_updated_at=source_updated_at,
            reason=reason,
            correlation_id=corr_id,
            idempotency_key=idempotency_key,
            payload=scrubbed_payload,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EventIntakeResult:
    accepted: bool
    status: str  # QUEUED, DUPLICATE_SUPPRESSED, REJECTED_INVALID, REJECTED_UNAUTHORIZED, REJECTED_NON_QUALIFYING
    event_id: str | None
    idempotency_key: str | None
    reason: str
    rebuild_result: RebuildResult | None = None


class EventIdempotencyCache:
    """Thread-safe TTL-bounded deduplication cache."""

    def __init__(self, ttl_seconds: float = 3600.0, max_entries: int = 10000) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._seen: dict[str, tuple[str, float]] = {}  # key -> (event_id, timestamp)
        self._lock = threading.RLock()

    def is_duplicate(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            return key in self._seen

    def record(self, key: str, event_id: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            if len(self._seen) >= self.max_entries:
                oldest_key = min(self._seen, key=lambda k: self._seen[k][1])
                del self._seen[oldest_key]
            self._seen[key] = (event_id, now)

    def _prune(self, now: float) -> None:
        expired = [k for k, (_, ts) in self._seen.items() if now - ts > self.ttl_seconds]
        for k in expired:
            del self._seen[k]


class EventDebounceQueue:
    """Thread-safe sliding debounce & coalescing queue for commercial catalog rebuilds."""

    def __init__(
        self,
        rebuild_callback: Callable[[list[CommercialRefreshEvent]], RebuildResult],
        debounce_seconds: float = 30.0,
        reload_listeners: Sequence[Callable[[RebuildResult], None]] | None = None,
    ) -> None:
        self.rebuild_callback = rebuild_callback
        self.debounce_seconds = debounce_seconds
        self.reload_listeners = list(reload_listeners or [])
        
        self._queue: list[CommercialRefreshEvent] = []
        self._timer: threading.Timer | None = None
        self._lock = threading.RLock()
        self._last_rebuild_result: RebuildResult | None = None

    def enqueue(self, event: CommercialRefreshEvent, synchronous: bool = False) -> RebuildResult | None:
        with self._lock:
            self._queue.append(event)
            if synchronous or self.debounce_seconds <= 0.0:
                return self._flush_locked()
            
            if self._timer is not None:
                self._timer.cancel()
            
            self._timer = threading.Timer(self.debounce_seconds, self.flush)
            self._timer.daemon = True
            self._timer.start()
            return None

    def flush(self) -> RebuildResult | None:
        with self._lock:
            return self._flush_locked()

    def _flush_locked(self) -> RebuildResult | None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

        if not self._queue:
            return None

        events_batch = list(self._queue)
        self._queue.clear()

        logger.info(f"Flushing {len(events_batch)} coalesced commercial refresh events")
        try:
            result = self.rebuild_callback(events_batch)
            self._last_rebuild_result = result
            if result.success:
                for listener in self.reload_listeners:
                    try:
                        listener(result)
                    except Exception as e:
                        logger.error(f"Error invoking reload listener: {e}")
            return result
        except Exception as exc:
            logger.error(f"Failed to execute coalesced rebuild: {exc}")
            return None

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._queue)


class EventRefreshController:
    """Primary entry point for commercial catalog event refresh integration."""

    def __init__(
        self,
        root_dir: Path | str,
        webhook_secret: str | None = None,
        debounce_seconds: float = 0.0,  # 0.0 for immediate in tests/staged, >0 for background
        canonical_source_path: Path | str | None = None,
    ) -> None:
        self.root_dir = Path(root_dir)
        self.webhook_secret = webhook_secret
        self.canonical_source_path = Path(canonical_source_path) if canonical_source_path else None
        
        self.idempotency_cache = EventIdempotencyCache()
        self.reload_listeners: list[Callable[[RebuildResult], None]] = []
        
        self.debounce_queue = EventDebounceQueue(
            rebuild_callback=self._execute_rebuild_from_events,
            debounce_seconds=debounce_seconds,
            reload_listeners=self.reload_listeners,
        )

    def register_reload_listener(self, listener: Callable[[RebuildResult], None]) -> None:
        self.reload_listeners.append(listener)
        self.debounce_queue.reload_listeners.append(listener)

    def verify_webhook_signature(self, raw_body: bytes, signature_header: str | None) -> bool:
        if not self.webhook_secret:
            return True  # Signature not enforced if no secret configured
        if not signature_header:
            return False
        expected = hmac.new(
            self.webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header)

    def ingest_event(
        self,
        raw_data: dict[str, Any] | CommercialRefreshEvent,
        headers: dict[str, str] | None = None,
        raw_body: bytes | None = None,
        synchronous: bool = True,
    ) -> EventIntakeResult:
        headers = headers or {}
        
        # 1. Signature Verification
        sig_header = headers.get("X-WC-Webhook-Signature") or headers.get("x-wc-webhook-signature")
        if self.webhook_secret and raw_body is not None:
            if not self.verify_webhook_signature(raw_body, sig_header):
                return EventIntakeResult(
                    accepted=False,
                    status="REJECTED_UNAUTHORIZED",
                    event_id=None,
                    idempotency_key=None,
                    reason="Invalid or missing webhook signature",
                )

        # 2. Event Model Parsing
        if isinstance(raw_data, CommercialRefreshEvent):
            event = raw_data
        else:
            event_type = raw_data.get("event_type") or headers.get("X-WC-Webhook-Topic") or "product.updated"
            if not isinstance(event_type, str) or not event_type.strip():
                return EventIntakeResult(
                    accepted=False,
                    status="REJECTED_INVALID",
                    event_id=None,
                    idempotency_key=None,
                    reason="Missing or invalid event_type",
                )
            
            delivery_id = headers.get("X-WC-Webhook-Delivery-ID") or raw_data.get("delivery_id")
            idempotency_key = raw_data.get("idempotency_key") or delivery_id
            
            event = CommercialRefreshEvent.create(
                event_type=event_type,
                provider=raw_data.get("provider", "WOOCOMMERCE"),
                provider_entity_id=raw_data.get("id") or raw_data.get("provider_entity_id"),
                provider_parent_id=raw_data.get("parent_id") or raw_data.get("provider_parent_id"),
                reason=raw_data.get("reason", "WEBHOOK_EVENT"),
                correlation_id=raw_data.get("correlation_id"),
                occurred_at=raw_data.get("occurred_at") or raw_data.get("date_modified_gmt"),
                source_updated_at=raw_data.get("date_modified_gmt") or raw_data.get("source_updated_at"),
                payload=raw_data,
                idempotency_key=idempotency_key,
            )

        # 3. Check Qualifying Event Type
        if event.event_type not in QUALIFYING_EVENT_TYPES:
            return EventIntakeResult(
                accepted=False,
                status="REJECTED_NON_QUALIFYING",
                event_id=event.event_id,
                idempotency_key=event.idempotency_key,
                reason=f"Event type '{event.event_type}' does not trigger public commercial catalog rebuild",
            )

        # 4. Idempotency Check
        if self.idempotency_cache.is_duplicate(event.idempotency_key):
            logger.info(f"Duplicate event suppressed: {event.idempotency_key}")
            return EventIntakeResult(
                accepted=True,
                status="DUPLICATE_SUPPRESSED",
                event_id=event.event_id,
                idempotency_key=event.idempotency_key,
                reason="Duplicate delivery suppressed via idempotency key",
            )

        self.idempotency_cache.record(event.idempotency_key, event.event_id)

        # 5. Enqueue into Debounce & Coalescing Engine
        rebuild_res = self.debounce_queue.enqueue(event, synchronous=synchronous)

        return EventIntakeResult(
            accepted=True,
            status="QUEUED" if rebuild_res is None else "REBUILT_SYNCHRONOUSLY",
            event_id=event.event_id,
            idempotency_key=event.idempotency_key,
            reason="Event accepted for catalog refresh",
            rebuild_result=rebuild_res,
        )

    def manual_rebuild(self, operator_id: str, reason: str = "MANUAL_OPERATOR_REBUILD") -> RebuildResult:
        """Trigger an immediate governed manual catalog rebuild."""
        event = CommercialRefreshEvent.create(
            event_type="manual_rebuild",
            provider="MANUAL",
            provider_entity_id=operator_id,
            reason=reason,
        )
        res = self.ingest_event(event, synchronous=True)
        assert res.rebuild_result is not None
        return res.rebuild_result

    def reconcile_daily(self) -> RebuildResult:
        """Trigger scheduled daily commercial catalog reconciliation."""
        event = CommercialRefreshEvent.create(
            event_type="scheduled_reconciliation",
            provider="CRON",
            reason="DAILY_SCHEDULED_RECONCILIATION",
        )
        res = self.ingest_event(event, synchronous=True)
        assert res.rebuild_result is not None
        return res.rebuild_result

    def _execute_rebuild_from_events(self, events: list[CommercialRefreshEvent]) -> RebuildResult:
        entity_ids = sorted(list({str(e.provider_entity_id) for e in events if e.provider_entity_id is not None}))
        triggering_entity = f"EVENT_REFRESH:{','.join(entity_ids)}" if entity_ids else "EVENT_REFRESH_BATCH"
        event_reason = f"COALESCED_EVENTS({len(events)}):" + ",".join(sorted(list({e.event_type for e in events})))

        # If custom records/woo payload present in events, apply them
        custom_records = None
        for ev in reversed(events):
            if "custom_records" in ev.payload:
                custom_records = ev.payload["custom_records"]
                break

        return rebuild_catalog(
            event_reason=event_reason,
            triggering_entity=triggering_entity,
            root_dir=self.root_dir,
            canonical_source_path=self.canonical_source_path,
            custom_records=custom_records,
            filter_public=True,
        )
