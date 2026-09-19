"""Conversion Spine Orchestrator for Budly Social-to-Sale (STS-1)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

try:
    from .attribution import AttributionContext, AttributionStandard
    from .cta_registry import CTARegistry
    from .intake import AskBudlyIntake, EntrySessionContext
    from .intent_taxonomy import IntentClassifier, IntentRecognitionResult
    from .journey_repository import ConversionJourney, ConversionLead, JourneyRepository
    from .lead_threshold import LeadPromotionDecision, LeadThresholdEvaluator
    from .qualification import QualificationDecision, QualificationEngine, QualificationState
    from .recommendation_router import RecommendationOutcome, RecommendationRouter
except (ImportError, ValueError):
    from attribution import AttributionContext, AttributionStandard
    from cta_registry import CTARegistry
    from intake import AskBudlyIntake, EntrySessionContext
    from intent_taxonomy import IntentClassifier, IntentRecognitionResult
    from journey_repository import ConversionJourney, ConversionLead, JourneyRepository
    from lead_threshold import LeadPromotionDecision, LeadThresholdEvaluator
    from qualification import QualificationDecision, QualificationEngine, QualificationState
    from recommendation_router import RecommendationOutcome, RecommendationRouter


@dataclass(frozen=True)
class SpineTurnResponse:
    session_id: str
    journey_id: str
    intent: str
    product_or_topic: str
    qualification_state: str
    is_lead: bool
    lead_id: str | None
    lead_promotion_reason: str | None
    recommended_destination: str
    recommended_cta_id: str
    display_label: str
    bot_message: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConversionSpine:
    """End-to-end conversion spine executing the Social -> Ask Budly -> Recommendation pipeline."""

    def __init__(
        self,
        repository: JourneyRepository | None = None,
        cta_registry: CTARegistry | None = None,
    ) -> None:
        self.repository = repository or JourneyRepository()
        self.cta_registry = cta_registry or CTARegistry()
        self.intake = AskBudlyIntake(self.repository, self.cta_registry)
        self.router = RecommendationRouter(self.cta_registry)
        self._turn_counts: dict[str, int] = {}

    def handle_social_landing(
        self,
        landing_url_or_params: str | dict[str, Any],
        session_id: str | None = None,
        landing_route: str = "https://www.wakenbakelounge.com/ask-budly",
    ) -> EntrySessionContext:
        """Entry point 1: Attributed landing capture and anonymous journey initialization."""
        entry_ctx = self.intake.handle_entry(landing_url_or_params, session_id, landing_route)
        if entry_ctx.session_id not in self._turn_counts:
            self._turn_counts[entry_ctx.session_id] = 0
        return entry_ctx

    def process_turn(
        self,
        session_id: str,
        user_message: str,
        contact_data: dict[str, str] | None = None,
    ) -> SpineTurnResponse:
        """Entry point 2: Processes a user message turn within an attributed session."""
        journey = self.repository.get_by_session(session_id)
        if not journey:
            # Safe fallback: create direct journey if intake wasn't invoked prior
            direct_ctx = self.handle_social_landing(AttributionContext.direct().to_dict(), session_id)
            journey = self.repository.get_journey(direct_ctx.journey_id)
            assert journey is not None

        turn_count = self._turn_counts.get(session_id, 0) + 1
        self._turn_counts[session_id] = turn_count

        # 1. Intent & Topic Recognition
        intent_res: IntentRecognitionResult = IntentClassifier.classify(
            user_message,
            initial_topic=journey.product_or_topic,
        )

        # 2. Qualification Evaluation
        qual_decision: QualificationDecision = QualificationEngine.evaluate(
            intent=intent_res.intent,
            product_or_topic=intent_res.product_or_topic,
            turn_count=turn_count,
            has_contact_info=bool(contact_data),
            prior_state=journey.qualification_state,
        )

        # 3. Lead Promotion Threshold Check
        lead_decision: LeadPromotionDecision = LeadThresholdEvaluator.evaluate(
            intent=intent_res.intent,
            product_or_topic=intent_res.product_or_topic,
            qualification_state=qual_decision.state,
            turn_count=turn_count,
            user_message=user_message,
            contact_info_provided=contact_data,
        )

        lead_id = journey.lead_id
        if lead_decision.is_promoted and not lead_id:
            lead = self.repository.promote_to_lead(
                journey_id=journey.journey_id,
                reason=lead_decision.reason or "QUALIFIED_INTEREST",
                contact_data=contact_data or {},
            )
            lead_id = lead.lead_id

        # 4. Recommendation Routing (Deterministic from CTA Registry)
        rec_outcome: RecommendationOutcome = self.router.route(
            intent=intent_res.intent,
            product_or_topic=intent_res.product_or_topic,
            qualification_state=qual_decision.state,
            platform=journey.platform,
        )

        # 5. Persist updated journey record
        updated_journey = ConversionJourney(
            journey_id=journey.journey_id,
            session_id=journey.session_id,
            source=journey.source,
            platform=journey.platform,
            content_id=journey.content_id,
            campaign_id=journey.campaign_id,
            cta_id=journey.cta_id,
            entry_timestamp=journey.entry_timestamp,
            intent=intent_res.intent,
            product_or_topic=intent_res.product_or_topic,
            qualification_state=qual_decision.state,
            lead_id=lead_id,
            recommended_destination=rec_outcome.destination_url,
            conversion_state="recommended" if rec_outcome.is_approved else "engaged",
            last_activity_at=JourneyRepository._now(),
        )
        self.repository.save_journey(updated_journey)

        evidence = {
            "source": journey.source,
            "platform": journey.platform,
            "content_id": journey.content_id,
            "campaign_id": journey.campaign_id,
            "entry_cta_id": journey.cta_id,
            "matched_signals": intent_res.matched_signals,
            "qualification_rationale": qual_decision.rationale,
            "lead_promotion_rationale": lead_decision.rationale,
            "recommendation_rationale": rec_outcome.rationale,
        }

        return SpineTurnResponse(
            session_id=session_id,
            journey_id=journey.journey_id,
            intent=intent_res.intent,
            product_or_topic=intent_res.product_or_topic,
            qualification_state=qual_decision.state,
            is_lead=bool(lead_id),
            lead_id=lead_id,
            lead_promotion_reason=lead_decision.reason if lead_decision.is_promoted else None,
            recommended_destination=rec_outcome.destination_url,
            recommended_cta_id=rec_outcome.cta_id,
            display_label=rec_outcome.display_label,
            bot_message=rec_outcome.suggested_dialogue,
            evidence=evidence,
        )
