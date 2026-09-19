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
                    last_activity_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_journey_content
                    ON conversion_journeys(content_id);
                CREATE INDEX IF NOT EXISTS idx_journey_campaign
                    ON conversion_journeys(campaign_id);
                CREATE INDEX IF NOT EXISTS idx_journey_qualification
                    ON conversion_journeys(qualification_state);

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

    def save_journey(self, journey: ConversionJourney) -> None:
        now = self._now()
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO conversion_journeys (
                    journey_id, session_id, source, platform, content_id,
                    campaign_id, cta_id, entry_timestamp, intent, product_or_topic,
                    qualification_state, lead_id, recommended_destination,
                    conversion_state, last_activity_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    intent = excluded.intent,
                    product_or_topic = excluded.product_or_topic,
                    qualification_state = excluded.qualification_state,
                    lead_id = COALESCE(excluded.lead_id, conversion_journeys.lead_id),
                    recommended_destination = COALESCE(excluded.recommended_destination, conversion_journeys.recommended_destination),
                    conversion_state = excluded.conversion_state,
                    last_activity_at = excluded.last_activity_at
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
