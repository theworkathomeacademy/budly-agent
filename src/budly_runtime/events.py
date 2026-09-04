from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

COMMERCIAL_EVENTS = ("conversation_started", "meaningful_engagement", "intent_identified", "recommendation_presented", "product_link_presented", "product_clicked", "lead_opportunity", "purchase_guidance_started", "purchase_attributed", "safe_no_match", "conversation_abandoned")


class EventLogger:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def emit_turn(self, **fields: Any) -> dict[str, Any]:
        event = {"event_type": "budly.conversation_turn", "timestamp": datetime.now(timezone.utc).isoformat(), **fields}
        self.events.append(event)
        return event

    def emit_commercial(self, name: str, **fields: Any) -> dict[str, Any]:
        if name not in COMMERCIAL_EVENTS:
            raise ValueError("unsupported commercial event")
        event = {"event_type": f"budly.{name}", "timestamp": datetime.now(timezone.utc).isoformat(), **fields}
        self.events.append(event)
        return event
