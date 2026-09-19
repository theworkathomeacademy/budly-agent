"""Complete acceptance and unit test matrix for BAE Pilot 001 Step B5 Authoritative Verification Engine.

Combines the full baseline of 24 original verification tests with the Section 24/25 cryptographic trust-boundary,
access token revocation, and material adapter read verification tests.
"""

import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.budly_runtime.bae.capability_registry import BAECapabilityRegistry
from src.budly_runtime.bae.policy_evaluator import (
    AuthorizationDecision,
    AuthorizationDecisionStatus,
    AuthorizationDenialReason,
    AuthorizationRequest,
    BAEKillSwitchRegistry,
    ContinuousAuthorizationToken,
    DeterministicPolicyEvaluator,
    compute_material_fingerprint,
    utc_now,
)
from src.budly_runtime.bae.state_machine import (
    ExecutionState,
    ExecutionStateMachine,
    ExecutionStateRecord,
    StateTransitionError,
    VerificationEvidenceClass,
    VerificationState,
)
from src.budly_runtime.bae.types import (
    ApprovalLevel,
    AuthorityClass,
    AutonomyMaturity,
    CapabilityLifecycleState,
    ToolAuthorityClass,
)
from src.budly_runtime.bae.verification_engine import (
    AuthoritativeVerificationEngine,
    EvidenceProvenanceToken,
    GovernedVerificationReader,
    RegisteredPostconditionContract,
    VerificationAccessDecision,
    VerificationContractRegistry,
    VerificationEvidenceItem,
    VerificationMethod,
    VerificationOutcome,
    VerificationReason,
    VerificationRequest,
    VerificationResult,
)
from src.budly_runtime.tool_gateway import (
    Actor,
    CapabilityRef,
    CustomerMemoryRetrieveInput,
    MemoryCurrentContext,
    MemoryLimits,
    MemoryRecallAdapterContext,
    SessionMemoryUse,
    ToolRequest,
    VerifiedMemorySubject,
)
from src.budly_runtime.postgres_memory_recall import PostgresMemoryRecallAdapter


class TestBAEStepB5VerificationEngine(unittest.TestCase):
    def setUp(self):
        self.objective_id = str(uuid4())
        self.action_id = str(uuid4())
        self.correlation_id = str(uuid4())
        self.capability_id = "activity.record"
        self.capability_version = "1.0"
        self.actor_id = "bae-steward-001"
        self.actor_type = "bae_steward"
        self.environment = "development"
        self.postcondition_name = "activity_persisted"
        self.source_identifier = "postgres_activity_db"
        self.expected_state = {"activity_id": "ACT-100", "persisted": True}

        self.engine = AuthoritativeVerificationEngine()
        self.kill_switches = BAEKillSwitchRegistry()

        # Issue trusted, cryptographically signed VerificationAccessDecision
        self.valid_access = VerificationAccessDecision.issue(
            permitted=True,
            reason=VerificationReason.AUTHORITATIVE_POSTCONDITION_SATISFIED,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            environment=self.environment,
            allowed_data_scopes=frozenset({"operational_telemetry", "customer_profile"}),
            consent_valid=True,
            permission_valid=True,
            verification_route="postgres.read.activity",
        )

        self.sm = ExecutionStateMachine.create(
            objective_id=self.objective_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            environment=self.environment,
            kill_switches=self.kill_switches,
        )
        # Advance state machine to EXECUTED
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Auth check")
        decision = AuthorizationDecision(
            status=AuthorizationDecisionStatus.PERMITTED,
            permitted=True,
            requires_approval=False,
            approval_level=ApprovalLevel.A0,
            denial_reason=None,
            reason_detail="Permitted under L1/T0",
            step_token=ContinuousAuthorizationToken(
                token_id=str(uuid4()), objective_id=self.objective_id, step_number=1,
                capability_id=self.capability_id, issued_at=utc_now(), expires_at=utc_now(),
                actor_id=self.actor_id, environment=self.environment,
                checksum="TOKEN-1", material_state_fingerprint="fp1",
            ),
        )
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Permitted", authorization_decision=decision)
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Attempted")
        self.sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Accepted")
        self.sm.transition(ExecutionState.EXECUTED, reason="Executed")

    # =========================================================================
    # ORIGINAL 24 BASELINE VERIFICATION TESTS (RESTORED & PRESERVED)
    # =========================================================================

    def test_b5_01_authoritative_sot_match_yields_verified(self):
        """Authoritative Source-of-Truth match yields VERIFIED."""
        obs_state = {"activity_id": "ACT-100", "persisted": True}
        prov = EvidenceProvenanceToken.issue(
            evidence_id="EV-SOT-1",
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            postcondition_name=self.postcondition_name,
            source_identifier=self.source_identifier,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            observed_state=obs_state,
        )
        evidence = VerificationEvidenceItem(
            evidence_id="EV-SOT-1",
            evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            source_identifier=self.source_identifier,
            observed_state=obs_state,
            collected_at=utc_now(),
            collector_actor_id="verification_service",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name=self.postcondition_name,
            provenance_token=prov,
        )
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name=self.postcondition_name,
            expected_state=self.expected_state,
            evidence_items=(evidence,),
            access_decision=self.valid_access,
        )
        res = self.engine.verify(req)
        self.assertEqual(res.outcome, VerificationOutcome.VERIFIED)
        self.assertEqual(res.primary_reason, VerificationReason.AUTHORITATIVE_POSTCONDITION_SATISFIED)
        self.assertEqual(res.primary_evidence_class, VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH)

    def test_b5_02_authoritative_sot_mismatch_yields_failed(self):
        """Authoritative Source-of-Truth state mismatch yields FAILED."""
        obs_state = {"activity_id": "ACT-100", "persisted": False}
        prov = EvidenceProvenanceToken.issue(
            evidence_id="EV-SOT-2",
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            postcondition_name=self.postcondition_name,
            source_identifier=self.source_identifier,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            observed_state=obs_state,
        )
        evidence = VerificationEvidenceItem(
            evidence_id="EV-SOT-2",
            evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            source_identifier=self.source_identifier,
            observed_state=obs_state,
            collected_at=utc_now(),
            collector_actor_id="verification_service",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name=self.postcondition_name,
            provenance_token=prov,
        )
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name=self.postcondition_name,
            expected_state=self.expected_state,
            evidence_items=(evidence,),
            access_decision=self.valid_access,
        )
        res = self.engine.verify(req)
        self.assertEqual(res.outcome, VerificationOutcome.FAILED)
        self.assertEqual(res.primary_reason, VerificationReason.POSTCONDITION_STATE_MISMATCH)

    def test_b5_03_authoritative_sot_unavailable_yields_unknown_never_verified(self):
        """Authoritative Source-of-Truth unavailable yields UNKNOWN/UNVERIFIED, never VERIFIED."""
        evidence = VerificationEvidenceItem(
            evidence_id="EV-SOT-3",
            evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            source_identifier=self.source_identifier,
            observed_state=None,
            collected_at=utc_now(),
            collector_actor_id="verification_service",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name=self.postcondition_name,
            is_available=False,
        )
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name=self.postcondition_name,
            expected_state=self.expected_state,
            evidence_items=(evidence,),
            access_decision=self.valid_access,
        )
        res = self.engine.verify(req)
        self.assertIn(res.outcome, {VerificationOutcome.UNKNOWN, VerificationOutcome.UNVERIFIED})
        self.assertNotEqual(res.outcome, VerificationOutcome.VERIFIED)

    def test_b5_04_sufficient_registered_deterministic_technical_yields_verified(self):
        """Sufficient registered deterministic technical verification yields VERIFIED."""
        cap_id = "customer.memory.retrieve"
        obs_state = {"payload_hash": "abc123hash"}
        access = VerificationAccessDecision.issue(
            permitted=True,
            reason=VerificationReason.AUTHORITATIVE_POSTCONDITION_SATISFIED,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=cap_id,
            capability_version="1.0",
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            environment=self.environment,
            allowed_data_scopes=frozenset({"operational_telemetry"}),
            consent_valid=True,
            permission_valid=True,
            verification_route="gateway.read.memory",
        )
        prov = EvidenceProvenanceToken.issue(
            evidence_id="EV-TECH-1",
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id=cap_id,
            capability_version="1.0",
            environment=self.environment,
            postcondition_name="memory_retrieved",
            source_identifier="memory_checksum_verifier",
            verification_method=VerificationMethod.DETERMINISTIC_PAYLOAD_COMPARISON,
            observed_state=obs_state,
        )
        evidence = VerificationEvidenceItem(
            evidence_id="EV-TECH-1",
            evidence_class=VerificationEvidenceClass.DETERMINISTIC_DIRECT_TECHNICAL,
            verification_method=VerificationMethod.DETERMINISTIC_PAYLOAD_COMPARISON,
            source_identifier="memory_checksum_verifier",
            observed_state=obs_state,
            collected_at=utc_now(),
            collector_actor_id="verification_service",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name="memory_retrieved",
            provenance_token=prov,
        )
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=cap_id,
            capability_version="1.0",
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name="memory_retrieved",
            expected_state={"payload_hash": "abc123hash"},
            evidence_items=(evidence,),
            access_decision=access,
        )
        res = self.engine.verify(req)
        self.assertEqual(res.outcome, VerificationOutcome.VERIFIED)
        self.assertEqual(res.primary_reason, VerificationReason.DETERMINISTIC_TECHNICAL_MATCH)

    def test_b5_05_insufficient_deterministic_technical_evidence_yields_not_verified(self):
        """Deterministic technical evidence where contract requires authoritative SoT yields PARTIALLY_VERIFIED."""
        obs_state = {"activity_id": "ACT-100", "persisted": True}
        prov = EvidenceProvenanceToken.issue(
            evidence_id="EV-TECH-2",
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            postcondition_name=self.postcondition_name,
            source_identifier=self.source_identifier,
            verification_method=VerificationMethod.DETERMINISTIC_PAYLOAD_COMPARISON,
            observed_state=obs_state,
        )
        evidence = VerificationEvidenceItem(
            evidence_id="EV-TECH-2",
            evidence_class=VerificationEvidenceClass.DETERMINISTIC_DIRECT_TECHNICAL,
            verification_method=VerificationMethod.DETERMINISTIC_PAYLOAD_COMPARISON,
            source_identifier=self.source_identifier,
            observed_state=obs_state,
            collected_at=utc_now(),
            collector_actor_id="verification_service",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name=self.postcondition_name,
            provenance_token=prov,
        )
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name=self.postcondition_name,
            expected_state=self.expected_state,
            evidence_items=(evidence,),
            access_decision=self.valid_access,
        )
        res = self.engine.verify(req)
        self.assertNotEqual(res.outcome, VerificationOutcome.VERIFIED)
        self.assertEqual(res.outcome, VerificationOutcome.PARTIALLY_VERIFIED)

    def test_b5_06_corroborated_secondary_evidence_alone_yields_partially_verified(self):
        """Corroborated secondary operational evidence alone yields PARTIALLY_VERIFIED."""
        evidence = VerificationEvidenceItem(
            evidence_id="EV-SEC-1",
            evidence_class=VerificationEvidenceClass.CORROBORATED_SECONDARY_OPERATIONAL,
            verification_method=VerificationMethod.SECONDARY_AUDIT_LOG_CORROBORATION,
            source_identifier=self.source_identifier,
            observed_state={"activity_id": "ACT-100", "persisted": True},
            collected_at=utc_now(),
            collector_actor_id="verification_service",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name=self.postcondition_name,
        )
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name=self.postcondition_name,
            expected_state=self.expected_state,
            evidence_items=(evidence,),
            access_decision=self.valid_access,
        )
        res = self.engine.verify(req)
        self.assertEqual(res.outcome, VerificationOutcome.PARTIALLY_VERIFIED)

    def test_b5_07_provider_acknowledgement_alone_yields_unverified(self):
        """Provider acknowledgement alone yields UNVERIFIED, never VERIFIED."""
        evidence = VerificationEvidenceItem(
            evidence_id="EV-ACK-1",
            evidence_class=VerificationEvidenceClass.PROVIDER_ACKNOWLEDGEMENT,
            verification_method=VerificationMethod.PROVIDER_HTTP_STATUS_CHECK,
            source_identifier=self.source_identifier,
            observed_state={"activity_id": "ACT-100", "persisted": True},
            collected_at=utc_now(),
            collector_actor_id="verification_service",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name=self.postcondition_name,
        )
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name=self.postcondition_name,
            expected_state=self.expected_state,
            evidence_items=(evidence,),
            access_decision=self.valid_access,
        )
        res = self.engine.verify(req)
        self.assertEqual(res.outcome, VerificationOutcome.UNVERIFIED)

    def test_b5_08_agent_self_report_alone_yields_unverified(self):
        """Agent self-report alone yields UNVERIFIED, never VERIFIED."""
        evidence = VerificationEvidenceItem(
            evidence_id="EV-SELF-1",
            evidence_class=VerificationEvidenceClass.AGENT_SELF_REPORT,
            verification_method=VerificationMethod.AGENT_INTERNAL_ASSERTION,
            source_identifier=self.source_identifier,
            observed_state={"activity_id": "ACT-100", "persisted": True},
            collected_at=utc_now(),
            collector_actor_id=self.actor_id,
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name=self.postcondition_name,
        )
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name=self.postcondition_name,
            expected_state=self.expected_state,
            evidence_items=(evidence,),
            access_decision=self.valid_access,
        )
        res = self.engine.verify(req)
        self.assertEqual(res.outcome, VerificationOutcome.UNVERIFIED)

    def test_b5_09_provider_ack_plus_agent_self_report_alone_yields_unverified(self):
        """Provider acknowledgement + agent self-report combined cannot produce VERIFIED."""
        ack = VerificationEvidenceItem(
            evidence_id="EV-ACK-2",
            evidence_class=VerificationEvidenceClass.PROVIDER_ACKNOWLEDGEMENT,
            verification_method=VerificationMethod.PROVIDER_HTTP_STATUS_CHECK,
            source_identifier=self.source_identifier,
            observed_state={"activity_id": "ACT-100", "persisted": True},
            collected_at=utc_now(),
            collector_actor_id="verification_service",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name=self.postcondition_name,
        )
        self_rep = VerificationEvidenceItem(
            evidence_id="EV-SELF-2",
            evidence_class=VerificationEvidenceClass.AGENT_SELF_REPORT,
            verification_method=VerificationMethod.AGENT_INTERNAL_ASSERTION,
            source_identifier=self.source_identifier,
            observed_state={"activity_id": "ACT-100", "persisted": True},
            collected_at=utc_now(),
            collector_actor_id=self.actor_id,
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name=self.postcondition_name,
        )
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name=self.postcondition_name,
            expected_state=self.expected_state,
            evidence_items=(ack, self_rep),
            access_decision=self.valid_access,
        )
        res = self.engine.verify(req)
        self.assertNotEqual(res.outcome, VerificationOutcome.VERIFIED)
        self.assertEqual(res.outcome, VerificationOutcome.UNVERIFIED)

    def test_b5_10_authoritative_evidence_overrides_conflicting_lower_precedence_ack(self):
        """Authoritative SoT evidence overrides conflicting lower-precedence provider ack and records contradiction."""
        obs_state = {"activity_id": "ACT-100", "persisted": False}
        sot_prov = EvidenceProvenanceToken.issue(
            evidence_id="EV-SOT-4",
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            postcondition_name=self.postcondition_name,
            source_identifier=self.source_identifier,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            observed_state=obs_state,
        )
        sot = VerificationEvidenceItem(
            evidence_id="EV-SOT-4",
            evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            source_identifier=self.source_identifier,
            observed_state=obs_state,
            collected_at=utc_now(),
            collector_actor_id="verification_service",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name=self.postcondition_name,
            provenance_token=sot_prov,
        )
        ack = VerificationEvidenceItem(
            evidence_id="EV-ACK-3",
            evidence_class=VerificationEvidenceClass.PROVIDER_ACKNOWLEDGEMENT,
            verification_method=VerificationMethod.PROVIDER_HTTP_STATUS_CHECK,
            source_identifier=self.source_identifier,
            observed_state={"activity_id": "ACT-100", "persisted": True},
            collected_at=utc_now(),
            collector_actor_id="verification_service",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name=self.postcondition_name,
        )
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name=self.postcondition_name,
            expected_state=self.expected_state,
            evidence_items=(ack, sot),
            access_decision=self.valid_access,
        )
        res = self.engine.verify(req)
        self.assertEqual(res.outcome, VerificationOutcome.FAILED)
        self.assertTrue(res.contradictions_detected)

    def test_b5_11_contradictory_evidence_is_preserved_and_auditable(self):
        """Contradictory evidence items are preserved in all_evaluated_evidence."""
        obs_state = {"activity_id": "ACT-100", "persisted": True}
        sot_prov = EvidenceProvenanceToken.issue(
            evidence_id="EV-SOT-5",
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            postcondition_name=self.postcondition_name,
            source_identifier=self.source_identifier,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            observed_state=obs_state,
        )
        sot = VerificationEvidenceItem(
            evidence_id="EV-SOT-5",
            evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            source_identifier=self.source_identifier,
            observed_state=obs_state,
            collected_at=utc_now(),
            collector_actor_id="verification_service",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name=self.postcondition_name,
            provenance_token=sot_prov,
        )
        sec = VerificationEvidenceItem(
            evidence_id="EV-SEC-2",
            evidence_class=VerificationEvidenceClass.CORROBORATED_SECONDARY_OPERATIONAL,
            verification_method=VerificationMethod.SECONDARY_AUDIT_LOG_CORROBORATION,
            source_identifier=self.source_identifier,
            observed_state={"activity_id": "ACT-100", "persisted": False},
            collected_at=utc_now(),
            collector_actor_id="verification_service",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name=self.postcondition_name,
        )
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name=self.postcondition_name,
            expected_state=self.expected_state,
            evidence_items=(sot, sec),
            access_decision=self.valid_access,
        )
        res = self.engine.verify(req)
        self.assertEqual(res.outcome, VerificationOutcome.VERIFIED)
        self.assertTrue(res.contradictions_detected)
        self.assertEqual(len(res.all_evaluated_evidence), 2)

    def test_b5_12_stale_evidence_is_rejected(self):
        """Evidence older than contract max_evidence_age_seconds is rejected as stale."""
        stale_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
        obs_state = {"activity_id": "ACT-100", "persisted": True}
        prov = EvidenceProvenanceToken.issue(
            evidence_id="EV-STALE-1",
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            postcondition_name=self.postcondition_name,
            source_identifier=self.source_identifier,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            observed_state=obs_state,
        )
        evidence = VerificationEvidenceItem(
            evidence_id="EV-STALE-1",
            evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            source_identifier=self.source_identifier,
            observed_state=obs_state,
            collected_at=stale_time,
            collector_actor_id="verification_service",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name=self.postcondition_name,
            provenance_token=prov,
        )
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name=self.postcondition_name,
            expected_state=self.expected_state,
            evidence_items=(evidence,),
            access_decision=self.valid_access,
        )
        res = self.engine.verify(req)
        self.assertEqual(res.outcome, VerificationOutcome.UNKNOWN)

    def test_b5_13_cross_objective_or_action_evidence_cannot_be_reused(self):
        """Evidence referencing a different objective or action ID is rejected."""
        obs_state = {"activity_id": "ACT-100", "persisted": True}
        prov = EvidenceProvenanceToken.issue(
            evidence_id="EV-CROSS-1",
            objective_id=str(uuid4()),
            action_id=self.action_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            postcondition_name=self.postcondition_name,
            source_identifier=self.source_identifier,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            observed_state=obs_state,
        )
        evidence = VerificationEvidenceItem(
            evidence_id="EV-CROSS-1",
            evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            source_identifier=self.source_identifier,
            observed_state=obs_state,
            collected_at=utc_now(),
            collector_actor_id="verification_service",
            objective_id=str(uuid4()),
            action_id=self.action_id,
            postcondition_name=self.postcondition_name,
            provenance_token=prov,
        )
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name=self.postcondition_name,
            expected_state=self.expected_state,
            evidence_items=(evidence,),
            access_decision=self.valid_access,
        )
        res = self.engine.verify(req)
        self.assertEqual(res.outcome, VerificationOutcome.UNKNOWN)

    def test_b5_14_missing_registered_verification_contract_yields_safe_unverified(self):
        """Unregistered capability contract yields safe UNVERIFIED."""
        obs_state = {"persisted": True}
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id="UNKNOWN-CAPABILITY-001",
            capability_version="1.0",
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name="custom_postcondition",
            expected_state={"persisted": True},
            evidence_items=(),
            access_decision=self.valid_access,
        )
        res = self.engine.verify(req)
        self.assertEqual(res.outcome, VerificationOutcome.UNVERIFIED)
        self.assertEqual(res.primary_reason, VerificationReason.VERIFICATION_CONTRACT_NOT_FOUND)

    def test_b5_15_ambiguous_verification_source_yields_safe_non_success(self):
        """Ambiguous evidence source is discarded and yields safe UNKNOWN."""
        obs_state = {"activity_id": "ACT-100", "persisted": True}
        prov = EvidenceProvenanceToken.issue(
            evidence_id="EV-AMBIG-1",
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            postcondition_name=self.postcondition_name,
            source_identifier=self.source_identifier,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            observed_state=obs_state,
        )
        evidence = VerificationEvidenceItem(
            evidence_id="EV-AMBIG-1",
            evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            source_identifier=self.source_identifier,
            observed_state=obs_state,
            collected_at=utc_now(),
            collector_actor_id="verification_service",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name=self.postcondition_name,
            is_ambiguous=True,
            provenance_token=prov,
        )
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name=self.postcondition_name,
            expected_state=self.expected_state,
            evidence_items=(evidence,),
            access_decision=self.valid_access,
        )
        res = self.engine.verify(req)
        self.assertEqual(res.outcome, VerificationOutcome.UNKNOWN)

    def test_b5_16_executed_enters_verification_pending_before_verification(self):
        """Applying verification from EXECUTED state enters VERIFICATION_PENDING before setting outcome."""
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.EXECUTED)
        obs_state = {"activity_id": "ACT-100", "persisted": True}
        prov = EvidenceProvenanceToken.issue(
            evidence_id="EV-SOT-6",
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            postcondition_name=self.postcondition_name,
            source_identifier=self.source_identifier,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            observed_state=obs_state,
        )
        evidence = VerificationEvidenceItem(
            evidence_id="EV-SOT-6",
            evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            source_identifier=self.source_identifier,
            observed_state=obs_state,
            collected_at=utc_now(),
            collector_actor_id="verification_service",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name=self.postcondition_name,
            provenance_token=prov,
        )
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name=self.postcondition_name,
            expected_state=self.expected_state,
            evidence_items=(evidence,),
            access_decision=self.valid_access,
        )
        res = self.engine.verify(req)
        self.engine.apply_to_state_machine(self.sm, res)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.VERIFIED)
        self.assertEqual(self.sm.record.verification_state, VerificationState.VERIFIED)
        states_in_history = [entry["to_state"] for entry in self.sm.record.state_history]
        self.assertIn("VERIFICATION_PENDING", states_in_history)

    def test_b5_17_verified_synchronizes_b4_correctly(self):
        """VERIFIED outcome synchronizes B4 ExecutionState.VERIFIED and VerificationState.VERIFIED."""
        obs_state = {"activity_id": "ACT-100", "persisted": True}
        prov = EvidenceProvenanceToken.issue(
            evidence_id="EV-SOT-7",
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            postcondition_name=self.postcondition_name,
            source_identifier=self.source_identifier,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            observed_state=obs_state,
        )
        evidence = VerificationEvidenceItem(
            evidence_id="EV-SOT-7",
            evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            source_identifier=self.source_identifier,
            observed_state=obs_state,
            collected_at=utc_now(),
            collector_actor_id="verification_service",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name=self.postcondition_name,
            provenance_token=prov,
        )
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name=self.postcondition_name,
            expected_state=self.expected_state,
            evidence_items=(evidence,),
            access_decision=self.valid_access,
        )
        res = self.engine.verify(req)
        self.engine.apply_to_state_machine(self.sm, res)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.VERIFIED)
        self.assertEqual(self.sm.record.verification_state, VerificationState.VERIFIED)

    def test_b5_18_partially_verified_synchronizes_b4_correctly(self):
        """PARTIALLY_VERIFIED outcome synchronizes B4 ExecutionState and VerificationState."""
        evidence = VerificationEvidenceItem(
            evidence_id="EV-SEC-3",
            evidence_class=VerificationEvidenceClass.CORROBORATED_SECONDARY_OPERATIONAL,
            verification_method=VerificationMethod.SECONDARY_AUDIT_LOG_CORROBORATION,
            source_identifier=self.source_identifier,
            observed_state={"activity_id": "ACT-100", "persisted": True},
            collected_at=utc_now(),
            collector_actor_id="verification_service",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name=self.postcondition_name,
        )
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name=self.postcondition_name,
            expected_state=self.expected_state,
            evidence_items=(evidence,),
            access_decision=self.valid_access,
        )
        res = self.engine.verify(req)
        self.engine.apply_to_state_machine(self.sm, res)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.PARTIALLY_VERIFIED)
        self.assertEqual(self.sm.record.verification_state, VerificationState.PARTIALLY_VERIFIED)

    def test_b5_19_unverified_synchronizes_b4_correctly(self):
        """UNVERIFIED outcome synchronizes B4 ExecutionState and VerificationState."""
        evidence = VerificationEvidenceItem(
            evidence_id="EV-ACK-4",
            evidence_class=VerificationEvidenceClass.PROVIDER_ACKNOWLEDGEMENT,
            verification_method=VerificationMethod.PROVIDER_HTTP_STATUS_CHECK,
            source_identifier=self.source_identifier,
            observed_state={"activity_id": "ACT-100", "persisted": True},
            collected_at=utc_now(),
            collector_actor_id="verification_service",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name=self.postcondition_name,
        )
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name=self.postcondition_name,
            expected_state=self.expected_state,
            evidence_items=(evidence,),
            access_decision=self.valid_access,
        )
        res = self.engine.verify(req)
        self.engine.apply_to_state_machine(self.sm, res)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.UNVERIFIED)
        self.assertEqual(self.sm.record.verification_state, VerificationState.UNVERIFIED)

    def test_b5_20_failed_synchronizes_b4_correctly(self):
        """FAILED outcome synchronizes B4 ExecutionState.FAILED and VerificationState.FAILED."""
        obs_state = {"activity_id": "ACT-100", "persisted": False}
        prov = EvidenceProvenanceToken.issue(
            evidence_id="EV-SOT-8",
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            postcondition_name=self.postcondition_name,
            source_identifier=self.source_identifier,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            observed_state=obs_state,
        )
        evidence = VerificationEvidenceItem(
            evidence_id="EV-SOT-8",
            evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            source_identifier=self.source_identifier,
            observed_state=obs_state,
            collected_at=utc_now(),
            collector_actor_id="verification_service",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name=self.postcondition_name,
            provenance_token=prov,
        )
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name=self.postcondition_name,
            expected_state=self.expected_state,
            evidence_items=(evidence,),
            access_decision=self.valid_access,
        )
        res = self.engine.verify(req)
        self.engine.apply_to_state_machine(self.sm, res)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.FAILED)
        self.assertEqual(self.sm.record.verification_state, VerificationState.FAILED)

    def test_b5_21_unknown_synchronizes_b4_correctly(self):
        """UNKNOWN outcome synchronizes B4 ExecutionState.UNKNOWN and VerificationState.UNKNOWN."""
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name=self.postcondition_name,
            expected_state=self.expected_state,
            evidence_items=(),
            access_decision=self.valid_access,
        )
        res = self.engine.verify(req)
        self.engine.apply_to_state_machine(self.sm, res)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.UNKNOWN)
        self.assertEqual(self.sm.record.verification_state, VerificationState.UNKNOWN)

    def test_b5_22_no_verification_outcome_can_directly_mark_complete(self):
        """No verification outcome can transition directly to COMPLETE; must follow B4 state machine."""
        obs_state = {"activity_id": "ACT-100", "persisted": True}
        prov = EvidenceProvenanceToken.issue(
            evidence_id="EV-SOT-9",
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            postcondition_name=self.postcondition_name,
            source_identifier=self.source_identifier,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            observed_state=obs_state,
        )
        evidence = VerificationEvidenceItem(
            evidence_id="EV-SOT-9",
            evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            source_identifier=self.source_identifier,
            observed_state=obs_state,
            collected_at=utc_now(),
            collector_actor_id="verification_service",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name=self.postcondition_name,
            provenance_token=prov,
        )
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name=self.postcondition_name,
            expected_state=self.expected_state,
            evidence_items=(evidence,),
            access_decision=self.valid_access,
        )
        res = self.engine.verify(req)
        self.engine.apply_to_state_machine(self.sm, res)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.VERIFIED)
        self.assertNotEqual(self.sm.record.current_execution_state, ExecutionState.COMPLETE)

        self.sm.transition(ExecutionState.COMPLETE, reason="Objective fully verified and complete")
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.COMPLETE)
        self.assertEqual(self.sm.record.final_disposition, "SUCCESS")

    def test_b5_23_all_nine_pilot_capabilities_remain_non_executable(self):
        """All 9 seed capabilities are non-executable in B2 evaluator and deny in B4/B5 lifecycle."""
        seed_registry = BAECapabilityRegistry.load_seed()
        seed_evaluator = DeterministicPolicyEvaluator(seed_registry, self.kill_switches)

        for seed_cap in seed_registry.list_all():
            sm = ExecutionStateMachine.create(
                objective_id=str(uuid4()),
                correlation_id=str(uuid4()),
                capability_id=seed_cap.capability_id,
                actor_id=self.actor_id,
                actor_type=self.actor_type,
                environment=self.environment,
                kill_switches=self.kill_switches,
                policy_evaluator=seed_evaluator,
            )
            sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Evaluating seed capability")
            auth_req = AuthorizationRequest(
                request_id=str(uuid4()),
                correlation_id=str(uuid4()),
                objective_id=sm.record.objective_id,
                step_number=1,
                actor_id=self.actor_id,
                actor_type=self.actor_type,
                capability_id=seed_cap.capability_id,
                capability_version="1.0",
                environment=self.environment,
                channel="system_internal",
                purpose="internal_test",
                requested_tool_authority=seed_cap.tool_authority or ToolAuthorityClass.T0,
            )
            decision = seed_evaluator.evaluate(auth_req)
            self.assertFalse(decision.permitted)
            sm.transition(ExecutionState.DENIED, reason="Seed capability denied", authorization_decision=decision)
            self.assertEqual(sm.record.current_execution_state, ExecutionState.DENIED)

    # =========================================================================
    # SECTION 24/25 TRUST-BOUNDARY & REPLAY/REVOCATION TESTS
    # =========================================================================

    def test_b5_24_forged_access_decision_rejected(self):
        """Forged VerificationAccessDecision dataclass with unverified signature is rejected."""
        forged_access = VerificationAccessDecision(
            decision_id="FORGED-DECISION-001",
            permitted=True,
            reason=VerificationReason.AUTHORITATIVE_POSTCONDITION_SATISFIED,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            environment=self.environment,
            allowed_data_scopes=frozenset({"operational_telemetry"}),
            consent_valid=True,
            permission_valid=True,
            verification_route="postgres.read.activity",
            issued_at=utc_now(),
            hmac_signature="FORGED_HMAC_SIGNATURE",
        )
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name=self.postcondition_name,
            expected_state=self.expected_state,
            evidence_items=(),
            access_decision=forged_access,
        )
        res = self.engine.verify(req)
        self.assertEqual(res.outcome, VerificationOutcome.UNVERIFIED)
        self.assertEqual(res.primary_reason, VerificationReason.VERIFICATION_ACCESS_FORGED_OR_INVALID)

    def test_b5_25_revocation_after_issuance_invalidates_access_decision(self):
        """Revoking an active VerificationAccessDecision invalidates it on next verification evaluation."""
        self.valid_access.revoke()
        req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name=self.postcondition_name,
            expected_state=self.expected_state,
            evidence_items=(),
            access_decision=self.valid_access,
        )
        res = self.engine.verify(req)
        self.assertEqual(res.outcome, VerificationOutcome.UNVERIFIED)
        self.assertEqual(res.primary_reason, VerificationReason.VERIFICATION_ACCESS_REVOKED)

    def test_b5_26_actual_material_adapter_direct_bypass_fails_without_governed_provenance(self):
        """Direct material call to PostgresMemoryRecallAdapter fails closed without authentic GatewayExecutionContext."""
        from src.budly_runtime.postgres_memory_recall import PostgresMemoryRecallAdapter

        adapter = PostgresMemoryRecallAdapter.__new__(PostgresMemoryRecallAdapter)
        adapter.environment = "development"

        untrusted_ctx = MemoryRecallAdapterContext(
            subject=VerifiedMemorySubject("synthetic_person", "P-TEST-001", "VERIFIED"),
            session_memory_use=SessionMemoryUse("ACTIVE", "ACTIVE", True),
            purpose="customer_education",
            current_context=MemoryCurrentContext("faq", "help", (), {}, "NORMAL", "CHAT"),
            limits=MemoryLimits(),
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            channel="website_chat",
            gateway_execution_context=None,  # Missing execution provenance
        )
        req = ToolRequest(
            request_id=untrusted_ctx.request_id, correlation_id=untrusted_ctx.correlation_id,
            actor=Actor("bae-steward-001", "bae_steward"),
            capability=CapabilityRef("customer.memory.retrieve", "1.0"),
            purpose="customer_education", channel="website_chat", environment="development",
            input=untrusted_ctx,
        )
        with self.assertRaises(PermissionError) as cm:
            adapter.retrieve_memory(
                context=untrusted_ctx, request=req, definition=None,
                permission_version="1.0", started_at=utc_now(), audit_event_id=str(uuid4()),
            )
        self.assertIn("Direct adapter execution prohibited", str(cm.exception))

    def test_b5_27_actual_material_read_succeeds_through_governed_verification_reader(self):
        """Actual material read via GovernedVerificationReader succeeds with valid access decision."""
        reader = GovernedVerificationReader(environment="development")
        adapter = PostgresMemoryRecallAdapter.__new__(PostgresMemoryRecallAdapter)
        adapter.environment = "development"

        valid_ctx = MemoryRecallAdapterContext(
            subject=VerifiedMemorySubject("synthetic_person", "P-TEST-001", "VERIFIED"),
            session_memory_use=SessionMemoryUse("ACTIVE", "ACTIVE", True),
            purpose="customer_education",
            current_context=MemoryCurrentContext("faq", "help", (), {}, "NORMAL", "CHAT"),
            limits=MemoryLimits(),
            request_id=self.action_id,
            correlation_id=self.correlation_id,
            channel="website_chat",
            gateway_execution_context=None,
        )

        res = reader.execute_read(
            route="postgres.read.activity",
            source_identifier="postgres_activity_db",
            query_params={"customer_id": "P-TEST-001"},
            access_decision=self.valid_access,
            adapter_instance=adapter,
            context=valid_ctx,
        )
        self.assertEqual(res["source"], "postgres_activity_db")
        self.assertEqual(res["adapter_status"], "AUTHENTICATED_EXECUTION")
        self.assertIsNotNone(res["authenticated_context"].gateway_execution_context)


if __name__ == "__main__":
    unittest.main()
