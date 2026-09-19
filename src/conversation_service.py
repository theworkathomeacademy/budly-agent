"""Customer-facing orchestration for the five Budly Sales journeys."""

from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .sales_agent import Discovery, SalesAgent

ROOT = Path(__file__).resolve().parents[1]
STS_DIR = ROOT / "SOCIAL-TO-SALE-001"
if str(STS_DIR) not in sys.path:
    sys.path.insert(0, str(STS_DIR))

try:
    from conversion_spine import ConversionSpine, SpineTurnResponse
    from intake import AskBudlyIntake, EntrySessionContext
    from journey_repository import JourneyRepository
except ImportError:
    ConversionSpine = None  # type: ignore
    AskBudlyIntake = None  # type: ignore
    JourneyRepository = None  # type: ignore


class ConversationService:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.agent = SalesAgent(db_path)
        if JourneyRepository is not None and ConversionSpine is not None:
            self.journey_repo = JourneyRepository(self.agent.db_path)
            self.spine = ConversionSpine(repository=self.journey_repo)
        else:
            self.journey_repo = None
            self.spine = None

    def intake(
        self,
        landing_input: str | dict[str, Any],
        session_id: str | None = None,
        landing_route: str = "https://www.wakenbakelounge.com/ask-budly",
    ) -> dict[str, Any]:
        """Processes social landing attribution into an attributable anonymous conversion journey."""
        if self.spine is None:
            raise RuntimeError("STS-1 Conversion Spine is not available")
        entry_ctx = self.spine.handle_social_landing(landing_input, session_id=session_id, landing_route=landing_route)
        return entry_ctx.to_dict()

    def turn(
        self,
        *,
        session_id: str,
        message: str,
        contact_data: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Processes an attributable conversational turn through the STS-1 conversion spine."""
        if self.spine is None:
            raise RuntimeError("STS-1 Conversion Spine is not available")
        res: SpineTurnResponse = self.spine.process_turn(session_id=session_id, user_message=message, contact_data=contact_data)
        return res.to_dict()

    def start(
        self,
        *,
        name: str,
        email: str,
        session_id: str | None = None,
        attribution: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        source = "customer_chat"
        if attribution and attribution.get("source"):
            source = str(attribution["source"])
        customer = self.agent.intake(name=name, email=email, source=source)

        # If a session exists, link customer to journey
        if session_id and self.journey_repo:
            journey = self.journey_repo.get_by_session(session_id)
            if journey:
                # If lead promotion criteria triggered with voluntary contact info, promote to lead
                if not journey.lead_id:
                    self.journey_repo.promote_to_lead(
                        journey_id=journey.journey_id,
                        reason="CONTACT_INFO_SUPPLIED",
                        customer_id=customer["id"],
                        contact_data={"name": name, "email": email, "customer_id": customer["id"]},
                    )

        return {
            "customer_id": customer["id"],
            "session_id": session_id,
            "message": (
                f"Nice to meet you, {customer['name']}. What are you shopping for today? "
                "I’ll ask a few short questions before suggesting anything."
            ),
        }

    def route(self, *, customer_id: str, shopping_goal: str) -> dict[str, Any]:
        discovery = Discovery(shopping_goal, "unknown", "", "", "")
        self.agent.record_discovery(customer_id, discovery)
        journey = self.agent.select_journey(customer_id)
        return {
            "journey": journey,
            "message": f"I’ll use the {journey['label']} path so the next questions stay relevant.",
        }

    def complete(
        self,
        *,
        customer_id: str,
        shopping_goal: str,
        journey_answers: list[str],
        experience_level: str,
        preferred_format: str,
        budget_range: str,
        purchase_timeline: str,
    ) -> dict[str, Any]:
        combined_goal = " ".join([shopping_goal, *journey_answers]).strip()
        discovery = Discovery(
            shopping_goal=combined_goal,
            experience_level=experience_level,
            preferred_format=preferred_format,
            budget_range=budget_range,
            purchase_timeline=purchase_timeline,
        )
        discovery.validate()
        self.agent.record_discovery(customer_id, discovery)
        journey = self.agent.select_journey(customer_id)

        risk = self.agent.risk_category(combined_goal)
        if journey["id"] == "wholesale":
            risk = "commercial_negotiation"
        if risk:
            escalation_id = self.agent.escalate(customer_id, risk, combined_goal)
            return {
                "outcome": "human_handoff",
                "journey": journey,
                "escalation_id": escalation_id,
                "message": self._handoff_message(journey["id"], risk),
                "human_sales_email": self.agent.settings.get("human_sales_email"),
                "captured": asdict(discovery),
            }

        card = self.agent.recommendation_card(customer_id)
        if card is None:
            return {
                "outcome": "no_match",
                "journey": journey,
                "message": (
                    "I don’t have a confident catalog match yet, so I won’t guess. "
                    "You can browse the full shop or ask the team for help."
                ),
                "catalog_url": self.agent.settings["catalog_url"],
            }
        rationale = self.agent.explain_recommendation(card, discovery)
        return {
            "outcome": "recommendation",
            "journey": journey,
            "message": "Based on what you shared, this is the closest current catalog match.",
            "recommendation": card,
            "rationale": rationale,
            "canonical_lifecycle": self.agent.canonical_lifecycle_stage(self.agent.get_customer(customer_id)),
        }

    @staticmethod
    def _handoff_message(journey_id: str, risk: str) -> str:
        if journey_id == "wholesale":
            return (
                "Wholesale details need a person to confirm specifications, pricing, labeling, "
                "fulfillment, and terms. I saved your needs for a human-sales follow-up."
            )
        if risk == "medical":
            return (
                "I can explain product facts, but I can’t provide medical or dosage advice. "
                "I saved the context for qualified human review."
            )
        return "That question needs human review, so I saved the context instead of guessing."
