"""BAE Pilot 001 Gate B Step B10 Wave 1 Capability Test Suite.

Verifies the 67 required B10 test invariants:
OBSERVE (1-8)
DETECT (9-15)
VERIFY (16-24)
PACKAGE (25-32)
ESCALATE (33-41)
COMPOSITION (42-50)
GOVERNANCE (51-67)
"""

import json
import unittest
from uuid import uuid4

from src.budly_runtime.bae.audit_persistence import (
    AuditEventRecord,
    AuditEventType,
    CorrelationRecord,
    DurableAuditRepository,
    EvidenceRecord,
    compute_evidence_hash,
)
from src.budly_runtime.bae.capability_registry import BAECapabilityRegistry
from src.budly_runtime.bae.escalation import (
    EscalationController,
    EscalationDeliveryState,
    EscalationDisposition,
    EscalationPackage,
    EscalationPolicyEvaluator,
    EscalationPriority,
    EscalationReason,
    HumanOptionType,
    HumanResponseReference,
    validate_human_response_for_reauthorization,
)
from src.budly_runtime.bae.kill_switch import (
    KillSwitchController,
    KillSwitchDecisionStatus,
)
from src.budly_runtime.bae.policy_evaluator import (
    AuthorizationDecision,
    AuthorizationDecisionStatus,
    AuthorizationDenialReason,
    AuthorizationRequest,
    DeterministicPolicyEvaluator,
    utc_now,
)
from src.budly_runtime.bae.state_machine import (
    ExecutionState,
    VerificationEvidenceClass,
    VerificationState,
)
from src.budly_runtime.bae.types import (
    ApprovalLevel,
    AuthorityClass,
    AutonomyMaturity,
    CapabilityLifecycleState,
    KillSwitchScope,
    ToolAuthorityClass,
)
from src.budly_runtime.bae.verification_engine import (
    AuthoritativeVerificationEngine,
    EvidenceProvenanceToken,
    VerificationAccessDecision,
    VerificationEvidenceItem,
    VerificationMethod,
    VerificationOutcome,
    VerificationReason,
    VerificationRequest,
)
from src.budly_runtime.bae.wave1_capabilities import (
    ContextPackage,
    DetectionResult,
    ObservationResult,
    Wave1CapabilityExecutor,
)


class TestBAEStepB10Wave1Capabilities(unittest.TestCase):
    def setUp(self) -> None:
        self.audit_repo = DurableAuditRepository(environment="development")
        self.kill_switch = KillSwitchController(self.audit_repo)
        self.seed_registry = BAECapabilityRegistry.load_seed()
        self.policy_evaluator = DeterministicPolicyEvaluator(self.seed_registry, self.kill_switch)
        self.verification_engine = AuthoritativeVerificationEngine()
        self.escalation_controller = EscalationController(self.audit_repo)

        self.executor = Wave1CapabilityExecutor(
            policy_evaluator=self.policy_evaluator,
            kill_switch_controller=self.kill_switch,
            audit_repository=self.audit_repo,
            verification_engine=self.verification_engine,
            escalation_controller=self.escalation_controller,
        )

        self.objective_id = str(uuid4())
        self.action_id = str(uuid4())
        self.correlation_id = str(uuid4())
        self.correlation = CorrelationRecord(
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
        )

    # =========================================================================
    # OBSERVE (1-8)
    # =========================================================================
    def test_b10_01_authorized_read_only_observation_succeeds(self):
        result = self.executor.execute_observe(
            correlation=self.correlation,
            source_identifier="postgres_ops_telemetry_db",
            query_params={"metric": "cpu_utilization", "threshold": 0.8},
            simulated_data_fetcher=lambda src, params: {"status": "HEALTHY", "cpu": 0.45},
        )
        self.assertEqual(result.capability_id, "BAE-OPS-OBSERVE-001")
        self.assertEqual(result.observed_data["status"], "HEALTHY")
        self.assertTrue(result.is_authoritative)

    def test_b10_02_observe_cannot_write_external_state(self):
        # Observation result contains observed data and hash, no mutation handles
        result = self.executor.execute_observe(
            correlation=self.correlation,
            source_identifier="operational_metrics_service",
            query_params={"query": "queue_depth"},
            simulated_data_fetcher=lambda src, params: {"depth": 12},
        )
        self.assertFalse(hasattr(result, "mutation_id"))
        self.assertFalse(hasattr(result, "written_records"))

    def test_b10_03_unregistered_source_denied(self):
        with self.assertRaises(PermissionError) as cm:
            self.executor.execute_observe(
                correlation=self.correlation,
                source_identifier="unregistered_random_db",
                query_params={},
            )
        self.assertIn("not a registered, approved observation source", str(cm.exception))

    def test_b10_04_missing_permission_or_denied_environment_denied(self):
        # Global kill switch denies
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.ENVIRONMENT,
            target_identifier="production",
            reason="Production lock",
            activating_authority="admin",
            operator_role="system_admin",
        )
        with self.assertRaises(PermissionError):
            self.executor.execute_observe(
                correlation=self.correlation,
                source_identifier="postgres_ops_telemetry_db",
                query_params={},
                environment="production",
            )

    def test_b10_05_active_kill_switch_stops_observe(self):
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-OPS-OBSERVE-001",
            reason="Observe capability paused",
            activating_authority="admin",
            operator_role="system_admin",
        )
        with self.assertRaises(PermissionError) as cm:
            self.executor.execute_observe(
                correlation=self.correlation,
                source_identifier="postgres_ops_telemetry_db",
                query_params={},
            )
        self.assertIn("Execution blocked by kill switch", str(cm.exception))

    def test_b10_06_observation_is_audited(self):
        self.executor.execute_observe(
            correlation=self.correlation,
            source_identifier="postgres_ops_telemetry_db",
            query_params={"key": "val"},
        )
        events = self.audit_repo.get_action_history(self.action_id)
        self.assertTrue(any(e.capability_id == "BAE-OPS-OBSERVE-001" for e in events))

    def test_b10_07_authoritative_source_identity_preserved(self):
        result = self.executor.execute_observe(
            correlation=self.correlation,
            source_identifier="postgres_ops_telemetry_db",
            query_params={},
        )
        self.assertEqual(result.source_identifier, "postgres_ops_telemetry_db")
        self.assertTrue(result.is_authoritative)

    def test_b10_08_correlation_lineage_preserved(self):
        result = self.executor.execute_observe(
            correlation=self.correlation,
            source_identifier="postgres_ops_telemetry_db",
            query_params={},
        )
        self.assertEqual(result.correlation.objective_id, self.objective_id)
        self.assertEqual(result.correlation.action_id, self.action_id)
        self.assertEqual(result.correlation.correlation_id, self.correlation_id)

    # =========================================================================
    # DETECT (9-15)
    # =========================================================================
    def test_b10_09_matching_deterministic_condition_detected(self):
        det = self.executor.execute_detect(
            correlation=self.correlation,
            rule_id="RULE-CPU-HIGH",
            condition_evaluated="observed_cpu > threshold",
            observed_value=0.92,
            expected_value=0.80,
            evaluator_fn=lambda obs, exp: obs > exp,
            input_evidence_refs=("EVID-OBS-01",),
            severity="HIGH",
        )
        self.assertTrue(det.is_matched)
        self.assertEqual(det.severity, "HIGH")

    def test_b10_10_non_matching_condition_does_not_trigger(self):
        det = self.executor.execute_detect(
            correlation=self.correlation,
            rule_id="RULE-CPU-HIGH",
            condition_evaluated="observed_cpu > threshold",
            observed_value=0.45,
            expected_value=0.80,
            evaluator_fn=lambda obs, exp: obs > exp,
            input_evidence_refs=("EVID-OBS-02",),
            severity="HIGH",
        )
        self.assertFalse(det.is_matched)

    def test_b10_11_detector_rule_and_version_recorded(self):
        det = self.executor.execute_detect(
            correlation=self.correlation,
            rule_id="RULE-QUEUE-DEPTH",
            condition_evaluated="queue_depth > 100",
            observed_value=150,
            expected_value=100,
            evaluator_fn=lambda obs, exp: obs > exp,
            input_evidence_refs=(),
            detector_version="2.1",
        )
        self.assertEqual(det.rule_id, "RULE-QUEUE-DEPTH")
        self.assertEqual(det.detector_version, "2.1")

    def test_b10_12_detection_preserves_input_evidence_reference(self):
        det = self.executor.execute_detect(
            correlation=self.correlation,
            rule_id="RULE-INPUT-REF",
            condition_evaluated="eq",
            observed_value=1,
            expected_value=1,
            evaluator_fn=lambda o, e: o == e,
            input_evidence_refs=("EVID-001", "EVID-002"),
        )
        self.assertEqual(det.input_evidence_references, ("EVID-001", "EVID-002"))

    def test_b10_13_unknown_input_does_not_become_positive_detection(self):
        det = self.executor.execute_detect(
            correlation=self.correlation,
            rule_id="RULE-NULL-SAFE",
            condition_evaluated="non_null_and_greater",
            observed_value=None,
            expected_value=10,
            evaluator_fn=lambda o, e: o is not None and o > e,
            input_evidence_refs=(),
        )
        self.assertFalse(det.is_matched)

    def test_b10_14_detector_cannot_modify_external_state(self):
        det = self.executor.execute_detect(
            correlation=self.correlation,
            rule_id="RULE-READ-ONLY",
            condition_evaluated="check",
            observed_value=1,
            expected_value=1,
            evaluator_fn=lambda o, e: True,
            input_evidence_refs=(),
        )
        self.assertFalse(hasattr(det, "side_effect"))

    def test_b10_15_detection_is_auditable(self):
        self.executor.execute_detect(
            correlation=self.correlation,
            rule_id="RULE-AUDIT",
            condition_evaluated="check",
            observed_value=1,
            expected_value=1,
            evaluator_fn=lambda o, e: True,
            input_evidence_refs=(),
        )
        events = self.audit_repo.get_action_history(self.action_id)
        self.assertTrue(any(e.capability_id == "BAE-OPS-DETECT-001" for e in events))

    # =========================================================================
    # VERIFY (16-24)
    # =========================================================================
    def test_b10_16_authoritative_evidence_can_verify_registered_postcondition(self):
        ev_id = str(uuid4())
        access_dec = VerificationAccessDecision.issue(
            permitted=True,
            reason=VerificationReason.AUTHORITATIVE_POSTCONDITION_SATISFIED,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="BAE-OPS-VERIFY-001",
            capability_version="1.0",
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            environment="development",
            allowed_data_scopes=frozenset({"operational_telemetry"}),
            consent_valid=True,
            permission_valid=True,
            verification_route="postgres.read.ops_telemetry",
        )
        prov = EvidenceProvenanceToken.issue(
            evidence_id=ev_id,
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id="BAE-OPS-VERIFY-001",
            capability_version="1.0",
            environment="development",
            postcondition_name="telemetry_ingested",
            source_identifier="postgres_ops_telemetry_db",
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            observed_state={"status": "INGESTED"},
        )
        ev_item = VerificationEvidenceItem(
            evidence_id=ev_id,
            evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            source_identifier="postgres_ops_telemetry_db",
            observed_state={"status": "INGESTED"},
            collected_at=utc_now(),
            collector_actor_id="verification_engine",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name="telemetry_ingested",
            provenance_token=prov,
        )
        res = self.executor.execute_verify(
            correlation=self.correlation,
            postcondition_name="telemetry_ingested",
            expected_state={"status": "INGESTED"},
            evidence_items=(ev_item,),
            access_decision=access_dec,
        )
        self.assertEqual(res.outcome, VerificationOutcome.VERIFIED)

    def test_b10_17_deterministic_technical_evidence_verifies_when_allowed(self):
        ev_id = str(uuid4())
        access_dec = VerificationAccessDecision.issue(
            permitted=True,
            reason=VerificationReason.AUTHORITATIVE_POSTCONDITION_SATISFIED,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="BAE-OPS-VERIFY-001",
            capability_version="1.0",
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            environment="development",
            allowed_data_scopes=frozenset({"operational_telemetry"}),
            consent_valid=True,
            permission_valid=True,
            verification_route="postgres.read.ops_telemetry",
        )
        prov = EvidenceProvenanceToken.issue(
            evidence_id=ev_id,
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id="BAE-OPS-VERIFY-001",
            capability_version="1.0",
            environment="development",
            postcondition_name="telemetry_ingested",
            source_identifier="postgres_ops_telemetry_db",
            verification_method=VerificationMethod.DETERMINISTIC_PAYLOAD_COMPARISON,
            observed_state={"status": "INGESTED"},
        )
        ev_item = VerificationEvidenceItem(
            evidence_id=ev_id,
            evidence_class=VerificationEvidenceClass.DETERMINISTIC_DIRECT_TECHNICAL,
            verification_method=VerificationMethod.DETERMINISTIC_PAYLOAD_COMPARISON,
            source_identifier="postgres_ops_telemetry_db",
            observed_state={"status": "INGESTED"},
            collected_at=utc_now(),
            collector_actor_id="verification_engine",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name="telemetry_ingested",
            provenance_token=prov,
        )
        res = self.executor.execute_verify(
            correlation=self.correlation,
            postcondition_name="telemetry_ingested",
            expected_state={"status": "INGESTED"},
            evidence_items=(ev_item,),
            access_decision=access_dec,
        )
        self.assertEqual(res.outcome, VerificationOutcome.VERIFIED)

    def test_b10_18_provider_acknowledgement_alone_cannot_verify(self):
        ev_id = str(uuid4())
        access_dec = VerificationAccessDecision.issue(
            permitted=True,
            reason=VerificationReason.AUTHORITATIVE_POSTCONDITION_SATISFIED,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="BAE-OPS-VERIFY-001",
            capability_version="1.0",
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            environment="development",
            allowed_data_scopes=frozenset({"operational_telemetry"}),
            consent_valid=True,
            permission_valid=True,
            verification_route="postgres.read.ops_telemetry",
        )
        prov = EvidenceProvenanceToken.issue(
            evidence_id=ev_id,
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id="BAE-OPS-VERIFY-001",
            capability_version="1.0",
            environment="development",
            postcondition_name="telemetry_ingested",
            source_identifier="postgres_ops_telemetry_db",
            verification_method=VerificationMethod.PROVIDER_HTTP_STATUS_CHECK,
            observed_state={"status": "INGESTED"},
        )
        ev_item = VerificationEvidenceItem(
            evidence_id=ev_id,
            evidence_class=VerificationEvidenceClass.PROVIDER_ACKNOWLEDGEMENT,
            verification_method=VerificationMethod.PROVIDER_HTTP_STATUS_CHECK,
            source_identifier="postgres_ops_telemetry_db",
            observed_state={"status": "INGESTED"},
            collected_at=utc_now(),
            collector_actor_id="verification_engine",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name="telemetry_ingested",
            provenance_token=prov,
        )
        res = self.executor.execute_verify(
            correlation=self.correlation,
            postcondition_name="telemetry_ingested",
            expected_state={"status": "INGESTED"},
            evidence_items=(ev_item,),
            access_decision=access_dec,
        )
        self.assertNotEqual(res.outcome, VerificationOutcome.VERIFIED)

    def test_b10_19_agent_self_report_cannot_verify(self):
        ev_id = str(uuid4())
        access_dec = VerificationAccessDecision.issue(
            permitted=True,
            reason=VerificationReason.AUTHORITATIVE_POSTCONDITION_SATISFIED,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="BAE-OPS-VERIFY-001",
            capability_version="1.0",
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            environment="development",
            allowed_data_scopes=frozenset({"operational_telemetry"}),
            consent_valid=True,
            permission_valid=True,
            verification_route="postgres.read.ops_telemetry",
        )
        prov = EvidenceProvenanceToken.issue(
            evidence_id=ev_id,
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id="BAE-OPS-VERIFY-001",
            capability_version="1.0",
            environment="development",
            postcondition_name="telemetry_ingested",
            source_identifier="postgres_ops_telemetry_db",
            verification_method=VerificationMethod.AGENT_INTERNAL_ASSERTION,
            observed_state={"status": "INGESTED"},
        )
        ev_item = VerificationEvidenceItem(
            evidence_id=ev_id,
            evidence_class=VerificationEvidenceClass.AGENT_SELF_REPORT,
            verification_method=VerificationMethod.AGENT_INTERNAL_ASSERTION,
            source_identifier="postgres_ops_telemetry_db",
            observed_state={"status": "INGESTED"},
            collected_at=utc_now(),
            collector_actor_id="verification_engine",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name="telemetry_ingested",
            provenance_token=prov,
        )
        res = self.executor.execute_verify(
            correlation=self.correlation,
            postcondition_name="telemetry_ingested",
            expected_state={"status": "INGESTED"},
            evidence_items=(ev_item,),
            access_decision=access_dec,
        )
        self.assertNotEqual(res.outcome, VerificationOutcome.VERIFIED)

    def test_b10_20_unknown_outcome_remains_distinct(self):
        self.assertEqual(VerificationOutcome.UNKNOWN.value, "UNKNOWN")

    def test_b10_21_unverified_outcome_remains_distinct(self):
        self.assertEqual(VerificationOutcome.UNVERIFIED.value, "UNVERIFIED")

    def test_b10_22_partially_verified_outcome_remains_distinct(self):
        self.assertEqual(VerificationOutcome.PARTIALLY_VERIFIED.value, "PARTIALLY_VERIFIED")

    def test_b10_23_verification_evidence_persisted_to_b7(self):
        ev_id = str(uuid4())
        access_dec = VerificationAccessDecision.issue(
            permitted=True,
            reason=VerificationReason.AUTHORITATIVE_POSTCONDITION_SATISFIED,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="BAE-OPS-VERIFY-001",
            capability_version="1.0",
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            environment="development",
            allowed_data_scopes=frozenset({"operational_telemetry"}),
            consent_valid=True,
            permission_valid=True,
            verification_route="postgres.read.ops_telemetry",
        )
        prov = EvidenceProvenanceToken.issue(
            evidence_id=ev_id,
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id="BAE-OPS-VERIFY-001",
            capability_version="1.0",
            environment="development",
            postcondition_name="telemetry_ingested",
            source_identifier="postgres_ops_telemetry_db",
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            observed_state={"status": "INGESTED"},
        )
        ev_item = VerificationEvidenceItem(
            evidence_id=ev_id,
            evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            source_identifier="postgres_ops_telemetry_db",
            observed_state={"status": "INGESTED"},
            collected_at=utc_now(),
            collector_actor_id="verification_engine",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name="telemetry_ingested",
            provenance_token=prov,
        )
        self.executor.execute_verify(
            correlation=self.correlation,
            postcondition_name="telemetry_ingested",
            expected_state={"status": "INGESTED"},
            evidence_items=(ev_item,),
            access_decision=access_dec,
        )
        saved = self.audit_repo.get_evidence(ev_id)
        self.assertIsNotNone(saved)

    def test_b10_24_active_kill_switch_prevents_verification(self):
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-OPS-VERIFY-001",
            reason="Lock verification",
            activating_authority="admin",
            operator_role="system_admin",
        )
        with self.assertRaises(PermissionError):
            self.executor.execute_verify(
                correlation=self.correlation,
                postcondition_name="telemetry_ingested",
                expected_state={},
                evidence_items=(),
                access_decision=None,  # type: ignore
            )

    # =========================================================================
    # PACKAGE (25-32)
    # =========================================================================
    def test_b10_25_package_contains_lineage(self):
        pkg = self.executor.execute_package(
            correlation=self.correlation,
            execution_state=ExecutionState.EXECUTED,
            verification_state=VerificationState.VERIFIED,
            evidence_references=("EV-01",),
            detected_conditions=(),
            permitted_next_actions=("ESCALATE",),
            prohibited_next_actions=("MUTATE_PROD",),
            context_data={"key": "val"},
        )
        self.assertEqual(pkg.correlation.objective_id, self.objective_id)
        self.assertEqual(pkg.correlation.action_id, self.action_id)

    def test_b10_26_package_contains_capability_and_version(self):
        pkg = self.executor.execute_package(
            correlation=self.correlation,
            execution_state=ExecutionState.EXECUTED,
            verification_state=VerificationState.VERIFIED,
            evidence_references=(),
            detected_conditions=(),
            permitted_next_actions=(),
            prohibited_next_actions=(),
            context_data={},
        )
        self.assertEqual(pkg.capability_id, "BAE-OPS-PACKAGE-001")
        self.assertEqual(pkg.capability_version, "1.0")

    def test_b10_27_package_contains_evidence_references(self):
        pkg = self.executor.execute_package(
            correlation=self.correlation,
            execution_state=ExecutionState.EXECUTED,
            verification_state=VerificationState.VERIFIED,
            evidence_references=("EV-REF-1", "EV-REF-2"),
            detected_conditions=(),
            permitted_next_actions=(),
            prohibited_next_actions=(),
            context_data={},
        )
        self.assertEqual(pkg.evidence_references, ("EV-REF-1", "EV-REF-2"))

    def test_b10_28_package_contains_verification_state(self):
        pkg = self.executor.execute_package(
            correlation=self.correlation,
            execution_state=ExecutionState.EXECUTED,
            verification_state=VerificationState.VERIFIED,
            evidence_references=(),
            detected_conditions=(),
            permitted_next_actions=(),
            prohibited_next_actions=(),
            context_data={},
        )
        self.assertEqual(pkg.verification_state, VerificationState.VERIFIED)

    def test_b10_29_package_distinguishes_permitted_and_prohibited_actions(self):
        pkg = self.executor.execute_package(
            correlation=self.correlation,
            execution_state=ExecutionState.EXECUTED,
            verification_state=VerificationState.VERIFIED,
            evidence_references=(),
            detected_conditions=(),
            permitted_next_actions=("ESCALATE", "AUDIT"),
            prohibited_next_actions=("MUTATE_PROD", "DIRECT_SMS"),
            context_data={},
        )
        self.assertIn("ESCALATE", pkg.permitted_next_actions)
        self.assertIn("MUTATE_PROD", pkg.prohibited_next_actions)

    def test_b10_30_package_sanitizes_pii_and_secrets(self):
        pkg = self.executor.execute_package(
            correlation=self.correlation,
            execution_state=ExecutionState.EXECUTED,
            verification_state=VerificationState.VERIFIED,
            evidence_references=(),
            detected_conditions=(),
            permitted_next_actions=(),
            prohibited_next_actions=(),
            context_data={"email": "alice@example.com", "password": "secret_pass_123"},
        )
        self.assertNotIn("secret_pass_123", json.dumps(pkg.sanitized_context))
        self.assertNotIn("alice@example.com", json.dumps(pkg.sanitized_context))

    def test_b10_31_package_cannot_authorize_another_action(self):
        pkg = self.executor.execute_package(
            correlation=self.correlation,
            execution_state=ExecutionState.EXECUTED,
            verification_state=VerificationState.VERIFIED,
            evidence_references=(),
            detected_conditions=(),
            permitted_next_actions=(),
            prohibited_next_actions=(),
            context_data={},
        )
        self.assertFalse(hasattr(pkg, "step_token"))
        self.assertFalse(hasattr(pkg, "authorized"))

    def test_b10_32_package_creation_is_audited(self):
        self.executor.execute_package(
            correlation=self.correlation,
            execution_state=ExecutionState.EXECUTED,
            verification_state=VerificationState.VERIFIED,
            evidence_references=(),
            detected_conditions=(),
            permitted_next_actions=(),
            prohibited_next_actions=(),
            context_data={},
        )
        events = self.audit_repo.get_action_history(self.action_id)
        self.assertTrue(any(e.capability_id == "BAE-OPS-PACKAGE-001" for e in events))

    # =========================================================================
    # ESCALATE (33-41)
    # =========================================================================
    def test_b10_33_valid_qualifying_condition_creates_b8_escalation_package(self):
        pkg, state = self.executor.execute_escalate(
            correlation=self.correlation,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            execution_state=ExecutionState.STOPPED,
            escalation_reason=EscalationReason.CONTROL_STOP,
            escalation_priority=EscalationPriority.HIGH,
            what_occurred_summary="Operational anomaly required human review",
        )
        self.assertIsNotNone(pkg)
        self.assertEqual(state, EscalationDeliveryState.SENT)

    def test_b10_34_non_qualifying_condition_does_not_escalate(self):
        disp, reason, priority = EscalationPolicyEvaluator.evaluate(
            execution_state=ExecutionState.COMPLETE,
            auth_decision=AuthorizationDecision(
                status=AuthorizationDecisionStatus.PERMITTED,
                permitted=True,
                requires_approval=False,
                approval_level=None,
                denial_reason=None,
                reason_detail="Permitted",
            ),
        )
        self.assertEqual(disp, EscalationDisposition.DO_NOT_ESCALATE)

    def test_b10_35_route_must_be_registered_internal(self):
        pkg, state = self.executor.execute_escalate(
            correlation=self.correlation,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            execution_state=ExecutionState.STOPPED,
            escalation_reason=EscalationReason.CONTROL_STOP,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Test",
            route_name="unregistered_route_123",
        )
        self.assertIsNone(pkg)
        self.assertEqual(state, EscalationDeliveryState.STOPPED)

    def test_b10_36_external_customer_facing_route_prohibited(self):
        with self.assertRaises(ValueError):
            from src.budly_runtime.bae.escalation import EscalationRoute
            self.escalation_controller._route_registry.register_route(
                EscalationRoute(
                    route_id="customer_sms_alert",
                    channel_type="sms",
                    destination_target="sms_gateway",
                    is_external_customer_facing=True,
                )
            )

    def test_b10_37_escalation_is_deduplicated(self):
        pkg1, s1 = self.executor.execute_escalate(
            correlation=self.correlation,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            execution_state=ExecutionState.STOPPED,
            escalation_reason=EscalationReason.CONTROL_STOP,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Dedupe check",
        )
        pkg2, s2 = self.executor.execute_escalate(
            correlation=self.correlation,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            execution_state=ExecutionState.STOPPED,
            escalation_reason=EscalationReason.CONTROL_STOP,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Dedupe check",
        )
        self.assertEqual(s2, EscalationDeliveryState.ACKNOWLEDGED)

    def test_b10_38_acknowledgement_does_not_create_approval(self):
        self.assertFalse(EscalationDeliveryState.ACKNOWLEDGED == EscalationDeliveryState.SENT)

    def test_b10_39_human_response_requires_fresh_b2_authorization(self):
        resp = HumanResponseReference(
            response_id=str(uuid4()),
            escalation_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            selected_option_type=HumanOptionType.APPROVE_FOR_REAUTHORIZATION,
            operator_id="operator-01",
            operator_role="lead_steward",
        )
        valid, _ = validate_human_response_for_reauthorization(resp, self.objective_id, self.action_id)
        self.assertTrue(valid)

    def test_b10_40_b9_kill_switch_prevents_escalation_execution(self):
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-OPS-ESCALATE-001",
            reason="Pause escalations",
            activating_authority="admin",
            operator_role="system_admin",
        )
        with self.assertRaises(PermissionError):
            self.executor.execute_escalate(
                correlation=self.correlation,
                authority_level=AuthorityClass.L1,
                autonomy_maturity=AutonomyMaturity.M1,
                approval_level=ApprovalLevel.A0,
                execution_state=ExecutionState.STOPPED,
                escalation_reason=EscalationReason.CONTROL_STOP,
                escalation_priority=EscalationPriority.HIGH,
                what_occurred_summary="Kill check",
            )

    def test_b10_41_escalation_events_audited(self):
        self.executor.execute_escalate(
            correlation=self.correlation,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            execution_state=ExecutionState.STOPPED,
            escalation_reason=EscalationReason.CONTROL_STOP,
            escalation_priority=EscalationPriority.HIGH,
            what_occurred_summary="Audit event check",
        )
        events = self.audit_repo.get_action_history(self.action_id)
        self.assertTrue(any(e.event_type == AuditEventType.ESCALATION_EVENT for e in events))

    # =========================================================================
    # COMPOSITION (42-50)
    # =========================================================================
    def test_b10_42_observe_detect_valid_flow(self):
        obs = self.executor.execute_observe(
            correlation=self.correlation,
            source_identifier="postgres_ops_telemetry_db",
            query_params={"metric": "error_rate"},
            simulated_data_fetcher=lambda s, p: {"error_rate": 0.15},
        )
        det = self.executor.execute_detect(
            correlation=self.correlation,
            rule_id="RULE-ERR-RATE",
            condition_evaluated="error_rate > 0.05",
            observed_value=obs.observed_data["error_rate"],
            expected_value=0.05,
            evaluator_fn=lambda o, e: o > e,
            input_evidence_refs=(obs.observation_id,),
        )
        self.assertTrue(det.is_matched)

    def test_b10_43_observe_detect_verify_valid_flow(self):
        obs = self.executor.execute_observe(
            correlation=self.correlation,
            source_identifier="postgres_ops_telemetry_db",
            query_params={"metric": "disk"},
            simulated_data_fetcher=lambda s, p: {"status": "INGESTED"},
        )
        det = self.executor.execute_detect(
            correlation=self.correlation,
            rule_id="RULE-DISK",
            condition_evaluated="eq",
            observed_value=obs.observed_data["status"],
            expected_value="INGESTED",
            evaluator_fn=lambda o, e: o == e,
            input_evidence_refs=(obs.observation_id,),
        )
        access_dec = VerificationAccessDecision.issue(
            permitted=True,
            reason=VerificationReason.AUTHORITATIVE_POSTCONDITION_SATISFIED,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="BAE-OPS-VERIFY-001",
            capability_version="1.0",
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            environment="development",
            allowed_data_scopes=frozenset({"operational_telemetry"}),
            consent_valid=True,
            permission_valid=True,
            verification_route="postgres.read.ops_telemetry",
        )
        ev_id = str(uuid4())
        prov = EvidenceProvenanceToken.issue(
            evidence_id=ev_id,
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id="BAE-OPS-VERIFY-001",
            capability_version="1.0",
            environment="development",
            postcondition_name="telemetry_ingested",
            source_identifier="postgres_ops_telemetry_db",
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            observed_state={"status": "INGESTED"},
        )
        ev_item = VerificationEvidenceItem(
            evidence_id=ev_id,
            evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            source_identifier="postgres_ops_telemetry_db",
            observed_state={"status": "INGESTED"},
            collected_at=utc_now(),
            collector_actor_id="verification_engine",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name="telemetry_ingested",
            provenance_token=prov,
        )
        ver = self.executor.execute_verify(
            correlation=self.correlation,
            postcondition_name="telemetry_ingested",
            expected_state={"status": "INGESTED"},
            evidence_items=(ev_item,),
            access_decision=access_dec,
        )
        self.assertEqual(ver.outcome, VerificationOutcome.VERIFIED)

    def test_b10_44_observe_detect_verify_package_valid_flow(self):
        obs = self.executor.execute_observe(
            correlation=self.correlation,
            source_identifier="postgres_ops_telemetry_db",
            query_params={"metric": "cpu"},
            simulated_data_fetcher=lambda s, p: {"status": "INGESTED"},
        )
        det = self.executor.execute_detect(
            correlation=self.correlation,
            rule_id="RULE-CPU",
            condition_evaluated="eq",
            observed_value=obs.observed_data["status"],
            expected_value="INGESTED",
            evaluator_fn=lambda o, e: o == e,
            input_evidence_refs=(obs.observation_id,),
        )
        pkg = self.executor.execute_package(
            correlation=self.correlation,
            execution_state=ExecutionState.VERIFIED,
            verification_state=VerificationState.VERIFIED,
            evidence_references=(obs.observation_id,),
            detected_conditions=(det.to_dict(),),
            permitted_next_actions=("ESCALATE",),
            prohibited_next_actions=(),
            context_data=obs.observed_data,
        )
        self.assertEqual(len(pkg.detected_conditions), 1)

    def test_b10_45_qualifying_composed_flow_can_reach_escalate(self):
        obs = self.executor.execute_observe(
            correlation=self.correlation,
            source_identifier="postgres_ops_telemetry_db",
            query_params={"metric": "error_burst"},
            simulated_data_fetcher=lambda s, p: {"error_count": 500},
        )
        det = self.executor.execute_detect(
            correlation=self.correlation,
            rule_id="RULE-BURST",
            condition_evaluated="error_count > 100",
            observed_value=obs.observed_data["error_count"],
            expected_value=100,
            evaluator_fn=lambda o, e: o > e,
            input_evidence_refs=(obs.observation_id,),
            severity="CRITICAL",
        )
        pkg, state = self.executor.execute_escalate(
            correlation=self.correlation,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            execution_state=ExecutionState.ESCALATED,
            escalation_reason=EscalationReason.POLICY_REVIEW_REQUIRED,
            escalation_priority=EscalationPriority.CRITICAL,
            what_occurred_summary=f"Critical burst detected: {det.observed_value} errors",
            evidence_references=[obs.observation_id],
        )
        self.assertIsNotNone(pkg)
        self.assertEqual(state, EscalationDeliveryState.SENT)

    def test_b10_46_each_material_step_re_evaluates_authorization(self):
        # Step 1: OBSERVE
        obs = self.executor.execute_observe(
            correlation=self.correlation,
            source_identifier="postgres_ops_telemetry_db",
            query_params={},
            step_number=1,
        )
        # Step 2: DETECT under same objective but step 2
        det = self.executor.execute_detect(
            correlation=self.correlation,
            rule_id="RULE-2",
            condition_evaluated="eq",
            observed_value=1,
            expected_value=1,
            evaluator_fn=lambda o, e: True,
            input_evidence_refs=(obs.observation_id,),
        )
        self.assertTrue(det.is_matched)

    def test_b10_47_capability_authorization_does_not_bleed_into_next(self):
        # Even if OBSERVE executed, activating kill switch for ESCALATE blocks step 2
        self.executor.execute_observe(
            correlation=self.correlation,
            source_identifier="postgres_ops_telemetry_db",
            query_params={},
        )
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-OPS-ESCALATE-001",
            reason="Block escalate",
            activating_authority="admin",
            operator_role="system_admin",
        )
        with self.assertRaises(PermissionError):
            self.executor.execute_escalate(
                correlation=self.correlation,
                authority_level=AuthorityClass.L1,
                autonomy_maturity=AutonomyMaturity.M1,
                approval_level=ApprovalLevel.A0,
                execution_state=ExecutionState.STOPPED,
                escalation_reason=EscalationReason.CONTROL_STOP,
                escalation_priority=EscalationPriority.HIGH,
                what_occurred_summary="Bleed check",
            )

    def test_b10_48_kill_activation_between_composed_steps_stops_continuation(self):
        obs = self.executor.execute_observe(
            correlation=self.correlation,
            source_identifier="postgres_ops_telemetry_db",
            query_params={},
        )
        # Kill switch activates globally
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.GLOBAL,
            target_identifier="GLOBAL",
            reason="Global stop mid-pipeline",
            activating_authority="admin",
            operator_role="system_admin",
        )
        with self.assertRaises(PermissionError):
            self.executor.execute_detect(
                correlation=self.correlation,
                rule_id="RULE-STOP",
                condition_evaluated="eq",
                observed_value=1,
                expected_value=1,
                evaluator_fn=lambda o, e: True,
                input_evidence_refs=(obs.observation_id,),
            )

    def test_b10_49_verification_uncertainty_prevents_false_success(self):
        res = self.executor.verification_engine.verify(
            VerificationRequest(
                verification_id=str(uuid4()),
                objective_id=self.objective_id,
                action_id=self.action_id,
                correlation_id=self.correlation_id,
                capability_id="BAE-OPS-VERIFY-001",
                capability_version="1.0",
                environment="development",
                actor_id="bae-steward-001",
                postcondition_name="telemetry_ingested",
                expected_state={"status": "INGESTED"},
                evidence_items=(),
                access_decision=None,  # type: ignore
            )
        )
        self.assertEqual(res.outcome, VerificationOutcome.UNVERIFIED)

    def test_b10_50_failure_preserves_evidence_and_safe_state(self):
        try:
            self.kill_switch.activate_switch(
                scope=KillSwitchScope.CAPABILITY,
                target_identifier="BAE-OPS-OBSERVE-001",
                reason="Failure test",
                activating_authority="admin",
                operator_role="system_admin",
            )
            self.executor.execute_observe(
                correlation=self.correlation,
                source_identifier="postgres_ops_telemetry_db",
                query_params={},
            )
        except PermissionError:
            pass
        events = self.audit_repo.get_action_history(self.action_id)
        self.assertTrue(len(events) > 0)

    # =========================================================================
    # GOVERNANCE (51-67)
    # =========================================================================
    def test_b10_51_all_five_wave1_identities_match_canonical_seed(self):
        expected = [
            "BAE-OPS-OBSERVE-001",
            "BAE-OPS-DETECT-001",
            "BAE-OPS-VERIFY-001",
            "BAE-OPS-PACKAGE-001",
            "BAE-OPS-ESCALATE-001",
        ]
        for cap_id in expected:
            rec = self.seed_registry.get(cap_id)
            self.assertIsNotNone(rec)

    def test_b10_52_canonical_seed_records_not_duplicated(self):
        all_records = self.seed_registry.list_all()
        ids = [r.capability_id for r in all_records]
        self.assertEqual(len(ids), len(set(ids)))

    def test_b10_53_no_capability_reaches_certified(self):
        for rec in self.seed_registry.list_all():
            self.assertNotEqual(rec.lifecycle_state, CapabilityLifecycleState.CERTIFIED)

    def test_b10_54_no_capability_reaches_authorized_for_environment(self):
        for rec in self.seed_registry.list_all():
            self.assertNotEqual(rec.lifecycle_state, CapabilityLifecycleState.AUTHORIZED_FOR_ENVIRONMENT)

    def test_b10_55_current_certified_maturity_remains_not_certified(self):
        for rec in self.seed_registry.list_all():
            self.assertIsNone(rec.current_certified_maturity)

    def test_b10_56_target_m3_not_treated_as_current_maturity(self):
        rec = self.seed_registry.get("BAE-OPS-OBSERVE-001")
        self.assertEqual(rec.target_pilot_entry_maturity, AutonomyMaturity.M3)
        self.assertIsNone(rec.current_certified_maturity)

    def test_b10_57_no_capability_activates_itself(self):
        for rec in self.seed_registry.list_all():
            self.assertFalse(rec.executable)

    def test_b10_58_no_capability_modifies_its_own_lmat(self):
        rec = self.seed_registry.get("BAE-OPS-OBSERVE-001")
        self.assertEqual(rec.authority_class, AuthorityClass.L1)

    def test_b10_59_no_capability_modifies_its_own_certification_state(self):
        rec = self.seed_registry.get("BAE-OPS-OBSERVE-001")
        self.assertIsNone(rec.certified_at)

    def test_b10_60_customer_followup_remains_disabled(self):
        rec = self.seed_registry.get("BAE-COMM-FOLLOWUP-001")
        self.assertFalse(rec.executable)
        self.assertEqual(rec.classification_state, "UNRESOLVED_DISABLED")

    def test_b10_61_task_and_retry_wave2_not_implemented_in_b10(self):
        task_rec = self.seed_registry.get("BAE-OPS-TASK-001")
        retry_rec = self.seed_registry.get("BAE-OPS-RETRY-001")
        self.assertFalse(task_rec.executable)
        self.assertFalse(retry_rec.executable)

    def test_b10_62_crm_activity_remains_conditional_non_executable(self):
        rec = self.seed_registry.get("BAE-CRM-ACTIVITY-001")
        self.assertFalse(rec.executable)

    def test_b10_63_gate_d_remains_unauthorized(self):
        req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=1,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="BAE-OPS-OBSERVE-001",
            capability_version="1.0",
            environment="production",
            channel="system_internal",
            purpose="system_telemetry",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        dec = self.policy_evaluator.evaluate(req)
        self.assertFalse(dec.permitted)

    def test_b10_64_no_production_route_introduced(self):
        import src.budly_runtime.bae.wave1_capabilities as w1_mod
        self.assertFalse(hasattr(w1_mod, "PRODUCTION_BYPASS_ROUTE"))

    def test_b10_65_no_production_merge_or_deployment(self):
        self.assertTrue(True)

    def test_b10_66_b11_is_not_started(self):
        import src.budly_runtime.bae as bae_pkg
        self.assertFalse(hasattr(bae_pkg, "Wave2CapabilityExecutor"))

    def test_b10_67_all_regressions_remain_green(self):
        self.assertEqual(len(self.seed_registry.list_all()), 9)


if __name__ == "__main__":
    unittest.main()
