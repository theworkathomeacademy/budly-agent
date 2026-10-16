"""Conversion Journey and Lead Repository for Budly Conversion Spine (STS-1)."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "sales.db"


@dataclass
class ConversionJourney:
    journey_id: str
    session_id: str
    source: str
    platform: str
    content_id: str
    campaign_id: str
    cta_id: str
    entry_timestamp: str
    intent: str
    product_or_topic: str
    qualification_state: str
    lead_id: str | None
    recommended_destination: str | None
    conversion_state: str  # "initiated", "engaged", "qualified", "recommended", "converted", "closed"
    last_activity_at: str
    order_id: str | None = None
    gross_revenue: float | None = None
    net_revenue: float | None = None
    currency: str = "USD"
    converted_at: str | None = None
    canonical_id: str | None = None
    catalog_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConversionLead:
    lead_id: str
    journey_id: str
    session_id: str
    promotion_reason: str
    qualification_state: str
    intent: str
    product_or_topic: str
    contact_data_json: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class JourneyRepository:
    """Manages persistent conversion journeys and qualified leads in the BROS CRM database."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or os.getenv("SALES_DB_PATH") or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_tables()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _initialize_tables(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversion_journeys (
                    journey_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL UNIQUE,
                    source TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    content_id TEXT NOT NULL,
                    campaign_id TEXT NOT NULL,
                    cta_id TEXT NOT NULL,
                    entry_timestamp TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    product_or_topic TEXT NOT NULL,
                    qualification_state TEXT NOT NULL,
                    lead_id TEXT,
                    recommended_destination TEXT,
                    conversion_state TEXT NOT NULL,
                    last_activity_at TEXT NOT NULL,
                    order_id TEXT,
                    gross_revenue REAL,
                    net_revenue REAL,
                    currency TEXT DEFAULT 'USD',
                    converted_at TEXT,
                    canonical_id TEXT,
                    catalog_version TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_journey_content
                    ON conversion_journeys(content_id);
                CREATE INDEX IF NOT EXISTS idx_journey_campaign
                    ON conversion_journeys(campaign_id);
                CREATE INDEX IF NOT EXISTS idx_journey_qualification
                    ON conversion_journeys(qualification_state);
                CREATE INDEX IF NOT EXISTS idx_journey_order
                    ON conversion_journeys(order_id);

                CREATE TABLE IF NOT EXISTS conversion_leads (
                    lead_id TEXT PRIMARY KEY,
                    journey_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    promotion_reason TEXT NOT NULL,
                    qualification_state TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    product_or_topic TEXT NOT NULL,
                    contact_data_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(journey_id) REFERENCES conversion_journeys(journey_id)
                );

                CREATE TABLE IF NOT EXISTS sts_audit_log (
                    id TEXT PRIMARY KEY,
                    journey_id TEXT,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            # Automatic schema migration for existing SQLite databases
            cursor = db.execute("PRAGMA table_info(conversion_journeys)")
            existing_cols = {row["name"] for row in cursor.fetchall()}
            for col_name, col_type in [
                ("order_id", "TEXT"),
                ("gross_revenue", "REAL"),
                ("net_revenue", "REAL"),
                ("currency", "TEXT DEFAULT 'USD'"),
                ("converted_at", "TEXT"),
                ("canonical_id", "TEXT"),
                ("catalog_version", "TEXT"),
            ]:
                if col_name not in existing_cols:
                    db.execute(f"ALTER TABLE conversion_journeys ADD COLUMN {col_name} {col_type}")

    def save_journey(self, journey: ConversionJourney) -> None:
        now = self._now()
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO conversion_journeys (
                    journey_id, session_id, source, platform, content_id,
                    campaign_id, cta_id, entry_timestamp, intent, product_or_topic,
                    qualification_state, lead_id, recommended_destination,
                    conversion_state, last_activity_at,
                    order_id, gross_revenue, net_revenue, currency,
                    converted_at, canonical_id, catalog_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    intent = excluded.intent,
                    product_or_topic = excluded.product_or_topic,
                    qualification_state = excluded.qualification_state,
                    lead_id = COALESCE(excluded.lead_id, conversion_journeys.lead_id),
                    recommended_destination = COALESCE(excluded.recommended_destination, conversion_journeys.recommended_destination),
                    conversion_state = excluded.conversion_state,
                    last_activity_at = excluded.last_activity_at,
                    order_id = COALESCE(excluded.order_id, conversion_journeys.order_id),
                    gross_revenue = COALESCE(excluded.gross_revenue, conversion_journeys.gross_revenue),
                    net_revenue = COALESCE(excluded.net_revenue, conversion_journeys.net_revenue),
                    currency = COALESCE(excluded.currency, conversion_journeys.currency),
                    converted_at = COALESCE(excluded.converted_at, conversion_journeys.converted_at),
                    canonical_id = COALESCE(excluded.canonical_id, conversion_journeys.canonical_id),
                    catalog_version = COALESCE(excluded.catalog_version, conversion_journeys.catalog_version)
                """,
                (
                    journey.journey_id,
                    journey.session_id,
                    journey.source,
                    journey.platform,
                    journey.content_id,
                    journey.campaign_id,
                    journey.cta_id,
                    journey.entry_timestamp,
                    journey.intent,
                    journey.product_or_topic,
                    journey.qualification_state,
                    journey.lead_id,
                    journey.recommended_destination,
                    journey.conversion_state,
                    journey.last_activity_at or now,
                    journey.order_id,
                    journey.gross_revenue,
                    journey.net_revenue,
                    journey.currency,
                    journey.converted_at,
                    journey.canonical_id,
                    journey.catalog_version,
                ),
            )
        self.audit_event(journey.journey_id, "journey_updated", journey.to_dict())

    def get_journey(self, journey_id: str) -> ConversionJourney | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM conversion_journeys WHERE journey_id=?", (journey_id,)).fetchone()
        if not row:
            return None
        return ConversionJourney(**dict(row))

    def get_by_session(self, session_id: str) -> ConversionJourney | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM conversion_journeys WHERE session_id=?", (session_id,)).fetchone()
        if not row:
            return None
        return ConversionJourney(**dict(row))

    def get_by_order_id(self, order_id: str) -> ConversionJourney | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM conversion_journeys WHERE order_id=?", (order_id,)).fetchone()
        if not row:
            return None
        return ConversionJourney(**dict(row))

    def record_conversion(
        self,
        order_id: str,
        gross_revenue: float,
        net_revenue: float | None = None,
        session_id: str | None = None,
        journey_id: str | None = None,
        currency: str = "USD",
        canonical_id: str | None = None,
        catalog_version: str | None = None,
    ) -> ConversionJourney:
        """Deterministically records an attributed conversion event for a journey.
        
        Strict Identity & Privacy Rules:
        - Replay safe: Identical order_id conversion events return existing state idempotently.
        - Anonymous visitor protection: Never automatically generates a ConversionLead.
        """
        journey: ConversionJourney | None = None
        if session_id:
            journey = self.get_by_session(session_id)
        if not journey and journey_id:
            journey = self.get_journey(journey_id)
        if not journey and order_id:
            journey = self.get_by_order_id(order_id)

        if not journey:
            raise KeyError(f"No journey found for session_id='{session_id}' or journey_id='{journey_id}'")

        # Idempotency / replay check: If this order has already been recorded for this journey, do not mutate/duplicate
        if journey.order_id == str(order_id) and journey.conversion_state == "converted":
            self.audit_event(journey.journey_id, "conversion_replay_suppressed", {
                "order_id": order_id,
                "gross_revenue": gross_revenue,
            })
            return journey

        now = self._now()
        calculated_net = float(net_revenue if net_revenue is not None else gross_revenue)

        journey.order_id = str(order_id)
        journey.gross_revenue = float(gross_revenue)
        journey.net_revenue = calculated_net
        journey.currency = str(currency).upper()
        journey.converted_at = now
        journey.conversion_state = "converted"
        journey.last_activity_at = now
        if canonical_id:
            journey.canonical_id = str(canonical_id)
        if catalog_version:
            journey.catalog_version = str(catalog_version)

        self.save_journey(journey)
        self.audit_event(journey.journey_id, "journey_converted", {
            "order_id": str(order_id),
            "gross_revenue": float(gross_revenue),
            "net_revenue": calculated_net,
            "currency": journey.currency,
            "canonical_id": journey.canonical_id,
            "catalog_version": journey.catalog_version,
            "converted_at": now,
        })
        return journey

    def record_refund(
        self,
        order_id: str,
        refund_amount: float,
        reason: str = "order_refunded",
    ) -> ConversionJourney | None:
        """Adjusts net revenue on refund while preserving historical conversion audit trail."""
        journey = self.get_by_order_id(str(order_id))
        if not journey:
            return None

        now = self._now()
        current_net = float(journey.net_revenue if journey.net_revenue is not None else journey.gross_revenue or 0.0)
        new_net = max(0.0, current_net - float(refund_amount))
        journey.net_revenue = new_net
        journey.last_activity_at = now

        self.save_journey(journey)
        self.audit_event(journey.journey_id, "journey_refunded", {
            "order_id": str(order_id),
            "refund_amount": float(refund_amount),
            "adjusted_net_revenue": new_net,
            "reason": reason,
            "refunded_at": now,
        })
        return journey

    def promote_to_lead(
        self,
        journey_id: str,
        reason: str,
        customer_id: str | None = None,
        contact_data: dict[str, Any] | None = None,
    ) -> ConversionLead:
        journey = self.get_journey(journey_id)
        if not journey:
            raise KeyError(f"Journey {journey_id} not found")

        now = self._now()
        # If already promoted to a lead, return existing lead record (Idempotent)
        if journey.lead_id:
            lead = self.get_lead(journey.lead_id)
            if lead:
                return lead

        # Canonical customer/person ID from existing Sales Agent path, or generated lead identifier
        lead_id = customer_id or f"lead_{uuid.uuid4().hex[:12]}"
        contact_json = json.dumps(contact_data or {}, sort_keys=True)

        with self._connect() as db:
            db.execute(
                """
                INSERT INTO conversion_leads (
                    lead_id, journey_id, session_id, promotion_reason,
                    qualification_state, intent, product_or_topic,
                    contact_data_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(lead_id) DO UPDATE SET
                    updated_at = excluded.updated_at
                """,
                (
                    lead_id,
                    journey.journey_id,
                    journey.session_id,
                    reason,
                    journey.qualification_state,
                    journey.intent,
                    journey.product_or_topic,
                    contact_json,
                    now,
                    now,
                ),
            )
            db.execute(
                "UPDATE conversion_journeys SET lead_id=?, last_activity_at=? WHERE journey_id=?",
                (lead_id, now, journey.journey_id),
            )

        self.audit_event(journey_id, "lead_promoted", {
            "lead_id": lead_id,
            "reason": reason,
            "qualification_state": journey.qualification_state,
        })
        return self.get_lead(lead_id)  # type: ignore[return-value]

    def get_lead(self, lead_id: str) -> ConversionLead | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM conversion_leads WHERE lead_id=?", (lead_id,)).fetchone()
        if not row:
            return None
        return ConversionLead(**dict(row))

    def audit_event(self, journey_id: str | None, event_type: str, payload: dict[str, Any]) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO sts_audit_log VALUES (?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    journey_id,
                    event_type,
                    json.dumps(payload, sort_keys=True),
                    self._now(),
                ),
            )
