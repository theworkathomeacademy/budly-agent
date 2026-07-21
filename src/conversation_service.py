"""Customer-facing orchestration for the five Budly Sales journeys."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from .sales_agent import Discovery, SalesAgent


class ConversationService:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.agent = SalesAgent(db_path)

    def start(self, *, name: str, email: str) -> dict[str, Any]:
        customer = self.agent.intake(name=name, email=email, source="customer_chat")
        return {
            "customer_id": customer["id"],
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
        return {
            "outcome": "recommendation",
            "journey": journey,
            "message": "Based on what you shared, this is the closest current catalog match.",
            "recommendation": card,
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
