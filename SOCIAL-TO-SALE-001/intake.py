"""Ask Budly Attribution Intake Logic for Budly Conversion Spine (STS-1)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

try:
    from .attribution import AttributionContext, AttributionStandard
    from .cta_registry import CTARegistry
    from .journey_repository import ConversionJourney, JourneyRepository
except (ImportError, ValueError):
    from attribution import AttributionContext, AttributionStandard
    from cta_registry import CTARegistry
    from journey_repository import ConversionJourney, JourneyRepository


@dataclass(frozen=True)
class EntrySessionContext:
    session_id: str
    journey_id: str
    attribution: AttributionContext
    landing_route: str
    entry_timestamp: str
    is_new_session: bool
    cta_downgraded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "journey_id": self.journey_id,
            "attribution": self.attribution.to_dict(),
            "landing_route": self.landing_route,
            "entry_timestamp": self.entry_timestamp,
            "is_new_session": self.is_new_session,
            "cta_downgraded": self.cta_downgraded,
        }


class AskBudlyIntake:
    """Handles landing page attribution intake and initializes anonymous conversion journeys."""

    def __init__(
        self,
        repository: JourneyRepository | None = None,
        cta_registry: CTARegistry | None = None,
    ) -> None:
        self.repository = repository or JourneyRepository()
        self.cta_registry = cta_registry or CTARegistry()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def handle_entry(
        self,
        request_input: str | dict[str, Any],
        session_id: str | None = None,
        landing_route: str = "https://www.wakenbakelounge.com/ask-budly",
    ) -> EntrySessionContext:
        """Processes an incoming web/social landing into an attributable Budly session."""
        now = self._now()

        # 1. Parse attribution context
        if isinstance(request_input, str):
            route_from_url, attribution = AttributionStandard.parse_url(request_input)
            if route_from_url:
                landing_route = route_from_url
        elif isinstance(request_input, dict):
            attribution = AttributionStandard.parse_query_params(request_input)
            if "landing_route" in request_input:
                landing_route = str(request_input["landing_route"])
        else:
            attribution = AttributionContext.direct()

        # 2. Validate / Downgrade CTA if invalid or unapproved
        cta_downgraded = False
        cta_record = self.cta_registry.get_active_cta(attribution.cta_id)
        valid_cta_id = attribution.cta_id

        if not cta_record:
            # Downgrade safely to default Ask Budly CTA
            valid_cta_id = "CTA-ASK-BUDLY-001"
            cta_downgraded = True
            attribution = AttributionContext(
                source=attribution.source,
                platform=attribution.platform,
                content_id=attribution.content_id,
                campaign_id=attribution.campaign_id,
                cta_id=valid_cta_id,
                product_or_topic=attribution.product_or_topic,
                published_post_id=attribution.published_post_id,
            )

        # 3. Check for existing session (Idempotency)
        if session_id:
            existing_journey = self.repository.get_by_session(session_id)
            if existing_journey:
                return EntrySessionContext(
                    session_id=existing_journey.session_id,
                    journey_id=existing_journey.journey_id,
                    attribution=attribution,
                    landing_route=landing_route,
                    entry_timestamp=existing_journey.entry_timestamp,
                    is_new_session=False,
                    cta_downgraded=cta_downgraded,
                )

        # 4. Generate deterministic identifiers for new session
        resolved_session_id = session_id or f"sess_{uuid.uuid4().hex[:16]}"
        journey_id = f"jrn_{uuid.uuid4().hex[:16]}"

        # 5. Create initial anonymous Conversion Journey record
        journey = ConversionJourney(
            journey_id=journey_id,
            session_id=resolved_session_id,
            source=attribution.source,
            platform=attribution.platform,
            content_id=attribution.content_id,
            campaign_id=attribution.campaign_id,
            cta_id=attribution.cta_id,
            entry_timestamp=now,
            intent="UNKNOWN",
            product_or_topic=attribution.product_or_topic or "UNKNOWN",
            qualification_state="UNQUALIFIED",
            lead_id=None,
            recommended_destination=None,
            conversion_state="initiated",
            last_activity_at=now,
        )
        self.repository.save_journey(journey)
        self.repository.audit_event(journey_id, "social_entry_captured", {
            "session_id": resolved_session_id,
            "landing_route": landing_route,
            "attribution": attribution.to_dict(),
            "cta_downgraded": cta_downgraded,
        })

        return EntrySessionContext(
            session_id=resolved_session_id,
            journey_id=journey_id,
            attribution=attribution,
            landing_route=landing_route,
            entry_timestamp=now,
            is_new_session=True,
            cta_downgraded=cta_downgraded,
        )
