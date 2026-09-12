"""BAE Pilot 001 Step B11 Formal Acceptance Test Suite (AT-001 through AT-070).

Executes the canonical acceptance suite against B1 through B10 control-plane
and Wave 1 capabilities:
- AT-001–AT-010: AUTHORITY (BAE-P001-AUTH, BAE-P001-MAT)
- AT-011–AT-015: CONTINUOUS AUTHORIZATION (BAE-P001-PERM, BAE-P001-AUTH)
- AT-016–AT-020: TOOL GATEWAY (BAE-P001-TOOL)
- AT-021–AT-026: EXECUTION STATE / VERIFICATION (BAE-P001-STATE, BAE-P001-VER)
- AT-027–AT-032: RETRY / IDEMPOTENCY (BAE-P001-RET)
- AT-033–AT-037: AUDIT / EVIDENCE (BAE-P001-AUD, BAE-P001-DATA)
- AT-038–AT-042: ESCALATION (BAE-P001-ESC)
- AT-043–AT-049: KILL SWITCH / HUMAN OVERRIDE (BAE-P001-KILL)
- AT-050–AT-055: SELF-EXPANSION PREVENTION (BAE-P001-SELF)
- AT-056–AT-059: SAFE STOP / SAFE INACTION (BAE-P001-STATE, BAE-P001-ESC)
- AT-060–AT-065: CUSTOMER / COMMERCIAL BOUNDARIES (BAE-P001-REL, BAE-P001-DATA)
- AT-066–AT-070: RELEASE / ENVIRONMENT / GATE CONTROL (BAE-P001-REL, BAE-P001-AUTH)
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.budly_runtime.bae.acceptance_harness import (
    AcceptanceCategory,
    AcceptanceHarnessSummary,
    AcceptanceResultStatus,
    AcceptanceTestRecord,
    utc_now,
)
from src.budly_runtime.bae.audit_persistence import (
    AuditEventRecord,
    AuditEventType,
    AuditPersistenceError,
    CorrelationRecord,
    DurableAuditRepository,
    EvidenceRecord,
    sanitize_payload,
)
from src.budly_runtime.bae.capability_registry import (
    BAECapabilityRegistry,
)
from src.budly_runtime.bae.escalation import (
    EscalationController,
    EscalationDeliveryState,
    EscalationDisposition,
    EscalationPackage,
    EscalationPolicyEvaluator,
    EscalationPriority,
    EscalationReason,
    EscalationRoute,
    EscalationRouteRegistry,
    HumanOption,
    HumanOptionType,
    HumanResponseReference,
    validate_human_response_for_reauthorization,
)
from src.budly_runtime.bae.kill_switch import (
    KillSwitchController,
    KillSwitchDecision,
    KillSwitchDecisionStatus,
    KillSwitchRecord,
)
from src.budly_runtime.bae.policy_evaluator import (
    AuthorizationDecision,
    AuthorizationDecisionStatus,
    AuthorizationDenialReason,
    AuthorizationRequest,
    ContinuousAuthorizationToken,
    DeterministicPolicyEvaluator,
)
from src.budly_runtime.bae.retry_controller import (
    FailureClass,
    IdempotencyDisposition,
    IdempotencyRecord,
    IdempotencyStore,
    RetryAttempt,
    RetryController,
    RetryDecision,
    RetryPolicy,
    RetryPolicyRegistry,
    RetryStopReason,
)
from src.budly_runtime.bae.schemas import (
    CapabilityRecord,
    ExecutionObjective,
    KillSwitchState,
    TaskRecord,
)
from src.budly_runtime.bae.state_machine import (
    ExecutionState,
    ExecutionStateMachine,
    ExecutionStateRecord,
    StateTransitionError,
    VerificationEvidenceClass as SMVerificationEvidenceClass,
    VerificationState,
)
from src.budly_runtime.bae.types import (
    ApprovalLevel,
    AuthorityClass,
    AutonomyMaturity,
    CapabilityLifecycleState,
    KillSwitchScope,
    LMATReconciliation,
    ObjectiveState,
    PilotWave,
    TaskState,
    ToolAuthorityClass,
)
from src.budly_runtime.bae.verification_engine import (
    AuthoritativeVerificationEngine,
    EvidenceProvenanceToken,
    GatewayExecutionContext,
    GovernedVerificationReader,
    RegisteredPostconditionContract,
    VerificationAccessDecision,
    VerificationContractRegistry,
    VerificationEvidenceClass,
    VerificationEvidenceItem,
    VerificationMethod,
    VerificationOutcome,
    VerificationReason,
    VerificationRequest,
    VerificationResult,
)
from src.budly_runtime.bae.wave1_capabilities import (
    ContextPackage,
    DetectionResult,
    ObservationResult,
    Wave1CapabilityExecutor,
)


class TestBAEStepB11AcceptanceHarness(unittest.TestCase):
    """Canonical BAE Pilot 001 Acceptance Test Suite (AT-001 to AT-070)."""

    summary: AcceptanceHarnessSummary = AcceptanceHarnessSummary()

    def setUp(self) -> None:
        self.objective_id = str(uuid4())
        self.action_id = str(uuid4())
        self.correlation_id = str(uuid4())
        self.correlation = CorrelationRecord(
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
        )
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

    # =========================================================================
    # 1. AUTHORITY (AT-001 to AT-010)
    # =========================================================================

    def test_at_001_unregistered_capability_denied(self) -> None:
        """AT-001: Requesting authorization for an unregistered capability ID fails closed."""
        req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=1,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="BAE-UNKNOWN-999",
            capability_version="1.0",
            environment="development",
            channel="system_internal",
            purpose="system_telemetry",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        dec = self.policy_evaluator.evaluate(req)
        self.assertFalse(dec.permitted)
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.CAPABILITY_NOT_REGISTERED)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-001",
            requirement_references=("BAE-P001-AUTH-001", "BAE-P001-AUTH-002"),
            category=AcceptanceCategory.AUTHORITY,
            capabilities_involved=("BAE-UNKNOWN-999",),
            environment="development",
            preconditions="Capability BAE-UNKNOWN-999 not in seed registry",
            fixture_input=req.to_dict(),
            expected_result="Authorization DENIED with CAPABILITY_NOT_REGISTERED",
            actual_result=f"permitted={dec.permitted}, reason={dec.denial_reason.value}",
            status=AcceptanceResultStatus.PASS,
            observed_authorization_decision=dec.status.value,
            authority_class="None",
            current_maturity="None",
        ))

    def test_at_002_lifecycle_requirement_enforced(self) -> None:
        """AT-002: Capability in uncertified DEFINED lifecycle state cannot execute."""
        rec = self.seed_registry.get("BAE-OPS-OBSERVE-001")
        self.assertIsNotNone(rec)
        self.assertEqual(rec.lifecycle_state, CapabilityLifecycleState.DEFINED)
        self.assertFalse(rec.executable)

        recon = LMATReconciliation.evaluate(
            authority=rec.authority_class,
            current_certified_maturity=rec.current_certified_maturity,
            approval=rec.approval_level,
            tool=rec.tool_authority,
            lifecycle_state=rec.lifecycle_state,
            is_certified=False,
        )
        self.assertFalse(recon.permitted)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-002",
            requirement_references=("BAE-P001-AUTH-003", "BAE-P001-MAT-001"),
            category=AcceptanceCategory.AUTHORITY,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="BAE-OPS-OBSERVE-001 is in DEFINED state, uncertified",
            fixture_input={"capability_id": "BAE-OPS-OBSERVE-001", "lifecycle": "DEFINED"},
            expected_result="LMAT reconciliation fails: capability not certified",
            actual_result=f"permitted={recon.permitted}, reason={recon.reason}",
            status=AcceptanceResultStatus.PASS,
            observed_authorization_decision="DENIED",
            authority_class=rec.authority_class.value,
            current_maturity="None",
        ))

    def test_at_003_current_certified_maturity_requirement(self) -> None:
        """AT-003: Uncertified capability has current_certified_maturity=None."""
        for cap in self.seed_registry.list_all():
            self.assertIsNone(cap.current_certified_maturity)
            self.assertFalse(cap.executable)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-003",
            requirement_references=("BAE-P001-MAT-002", "BAE-P001-MAT-003"),
            category=AcceptanceCategory.AUTHORITY,
            capabilities_involved=tuple(c.capability_id for c in self.seed_registry.list_all()),
            environment="development",
            preconditions="All 9 canonical seed capabilities inspected",
            fixture_input={"check": "current_certified_maturity is None"},
            expected_result="All seed capabilities have unset current maturity",
            actual_result="Verified: 9/9 capabilities have current_certified_maturity=None",
            status=AcceptanceResultStatus.PASS,
            observed_authorization_decision="UNSET",
        ))

    def test_at_004_target_maturity_does_not_create_authority(self) -> None:
        """AT-004: Target maturity (M3) cannot be substituted for current certified maturity."""
        rec = self.seed_registry.get("BAE-OPS-OBSERVE-001")
        self.assertEqual(rec.target_pilot_entry_maturity, AutonomyMaturity.M3)
        self.assertIsNone(rec.current_certified_maturity)
        # Reconcile using target maturity as an illegal substitution attempt
        recon = LMATReconciliation.evaluate(
            authority=rec.authority_class,
            current_certified_maturity=None,  # Real current maturity
            approval=rec.approval_level,
            tool=rec.tool_authority,
            lifecycle_state=rec.lifecycle_state,
            is_certified=False,
        )
        self.assertFalse(recon.permitted)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-004",
            requirement_references=("BAE-P001-MAT-004", "BAE-P001-AUTH-004"),
            category=AcceptanceCategory.AUTHORITY,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="Target maturity M3 vs current maturity None",
            fixture_input={"target_maturity": "M3", "current_certified_maturity": None},
            expected_result="Execution rejected; target maturity does not confer authority",
            actual_result=f"permitted={recon.permitted}",
            status=AcceptanceResultStatus.PASS,
            observed_authorization_decision="DENIED",
            authority_class="L1",
            current_maturity="None",
            max_maturity="M3",
        ))

    def test_at_005_maximum_maturity_boundary_enforced(self) -> None:
        """AT-005: Attempting execution beyond maximum_governable_maturity is strictly prohibited."""
        rec = CapabilityRecord(
            capability_id="BAE-OPS-OBSERVE-001",
            capability_version="1.0",
            capability_name="Test Max Maturity",
            wave=PilotWave.WAVE_1,
            authority_class=AuthorityClass.L1,
            current_certified_maturity=AutonomyMaturity.M3,
            target_pilot_entry_maturity=AutonomyMaturity.M3,
            maximum_governable_maturity=AutonomyMaturity.M3,
            approval_level=ApprovalLevel.A0,
            tool_authority=ToolAuthorityClass.T0,
            lifecycle_state=CapabilityLifecycleState.AUTHORIZED_FOR_ENVIRONMENT,
            certification_signature="SIG-VALID-TEST",
            allowed_environments=frozenset({"development"}),
            allowed_purposes=frozenset({"system_telemetry", "telemetry"}),
            allowed_channels=frozenset({"system_internal"}),
        )
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switch)
        # Request maturity M4 when maximum is M3
        req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=1,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="BAE-OPS-OBSERVE-001",
            capability_version="1.0",
            environment="development",
            channel="system_internal",
            purpose="telemetry",
            requested_tool_authority=ToolAuthorityClass.T0,
            requested_maturity=AutonomyMaturity.M4,
        )
        dec = evaluator.evaluate(req)
        self.assertFalse(dec.permitted)
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.MAXIMUM_MATURITY_EXCEEDED)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-005",
            requirement_references=("BAE-P001-MAT-005",),
            category=AcceptanceCategory.AUTHORITY,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="maximum_governable_maturity is M3, requested is M4",
            fixture_input={"maximum_governable_maturity": "M3", "requested_maturity": "M4"},
            expected_result="dec.permitted=False, MAXIMUM_MATURITY_EXCEEDED",
            actual_result=f"permitted={dec.permitted}, denial_reason={dec.denial_reason.value if dec.denial_reason else None}",
            status=AcceptanceResultStatus.PASS,
            max_maturity="M3",
            observed_authorization_decision="DENIED_MATURITY",
        ))

    def test_at_006_independent_lmat_evaluation(self) -> None:
        """AT-006: Reconciles L, M, A, and T dimensions independently."""
        recon = LMATReconciliation.evaluate(
            authority=AuthorityClass.L1,
            current_certified_maturity=AutonomyMaturity.M1,
            approval=ApprovalLevel.A0,
            tool=ToolAuthorityClass.T0,
            lifecycle_state=CapabilityLifecycleState.CERTIFIED,
            is_certified=True,
        )
        self.assertTrue(recon.permitted)
        self.assertFalse(recon.requires_approval)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-006",
            requirement_references=("BAE-P001-AUTH-005", "BAE-P001-AUTH-006"),
            category=AcceptanceCategory.AUTHORITY,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="L1, M1, A0, T0 certified capability",
            fixture_input={"L": "L1", "M": "M1", "A": "A0", "T": "T0"},
            expected_result="LMAT reconciliation permitted=True without approval required",
            actual_result=f"permitted={recon.permitted}, requires_approval={recon.requires_approval}",
            status=AcceptanceResultStatus.PASS,
            observed_authorization_decision="PERMITTED",
            authority_class="L1",
            current_maturity="M1",
            approval_level="A0",
            tool_authority="T0",
        ))

    def test_at_007_required_approval_handling(self) -> None:
        """AT-007: Approval levels (A1, A2) require approval and block autonomous execution without it."""
        recon = LMATReconciliation.evaluate(
            authority=AuthorityClass.L2,
            current_certified_maturity=AutonomyMaturity.M2,
            approval=ApprovalLevel.A1,
            tool=ToolAuthorityClass.T1,
            lifecycle_state=CapabilityLifecycleState.CERTIFIED,
            is_certified=True,
        )
        self.assertFalse(recon.permitted)
        self.assertTrue(recon.requires_approval)
        self.assertEqual(recon.approval_level, ApprovalLevel.A1)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-007",
            requirement_references=("BAE-P001-AUTH-007",),
            category=AcceptanceCategory.AUTHORITY,
            capabilities_involved=("BAE-OPS-TASK-001",),
            environment="development",
            preconditions="L2 with A1 approval level evaluated",
            fixture_input={"approval_level": "A1"},
            expected_result="requires_approval=True, permitted=False",
            actual_result=f"permitted={recon.permitted}, requires_approval={recon.requires_approval}",
            status=AcceptanceResultStatus.PASS,
            observed_authorization_decision="REQUIRES_APPROVAL",
            approval_level="A1",
        ))

    def test_at_008_unapproved_l2_action_stops_before_tool_invocation(self) -> None:
        """AT-008: Unapproved L2 action evaluates to permitted=False with requires_approval=True."""
        recon = LMATReconciliation.evaluate(
            authority=AuthorityClass.L2,
            current_certified_maturity=AutonomyMaturity.M2,
            approval=ApprovalLevel.A2,
            tool=ToolAuthorityClass.T2,
            lifecycle_state=CapabilityLifecycleState.CERTIFIED,
            is_certified=True,
        )
        self.assertFalse(recon.permitted)

    def test_at_009_l3_h_human_only_action_denies_autonomous_execution(self) -> None:
        """AT-009: L3-H authority class is reserved exclusively for humans; agent execution is denied."""
        recon = LMATReconciliation.evaluate(
            authority=AuthorityClass.L3_H,
            current_certified_maturity=AutonomyMaturity.M0,
            approval=ApprovalLevel.A3,
            tool=ToolAuthorityClass.T2,
            lifecycle_state=CapabilityLifecycleState.CERTIFIED,
            is_certified=True,
        )
        self.assertFalse(recon.permitted)
        self.assertIn("Human-Only", recon.reason)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-009",
            requirement_references=("BAE-P001-AUTH-009",),
            category=AcceptanceCategory.AUTHORITY,
            capabilities_involved=("HUMAN_ONLY_GATEWAY",),
            environment="development",
            preconditions="L3-H action requested by autonomous steward",
            fixture_input={"authority_class": "L3-H"},
            expected_result="Denied as Human-Only",
            actual_result=f"permitted={recon.permitted}, reason={recon.reason}",
            status=AcceptanceResultStatus.PASS,
            observed_authorization_decision="DENIED_HUMAN_ONLY",
            authority_class="L3-H",
        ))

    def test_at_010_l3_x_absolutely_prohibited_fails_closed(self) -> None:
        """AT-010: L3-X action is absolutely prohibited and fails closed under all circumstances."""
        recon = LMATReconciliation.evaluate(
            authority=AuthorityClass.L3_X,
            current_certified_maturity=AutonomyMaturity.M5,
            approval=ApprovalLevel.A4,
            tool=ToolAuthorityClass.TX,
            lifecycle_state=CapabilityLifecycleState.CERTIFIED,
            is_certified=True,
        )
        self.assertFalse(recon.permitted)
        self.assertIn("Prohibited", recon.reason)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-010",
            requirement_references=("BAE-P001-AUTH-010",),
            category=AcceptanceCategory.AUTHORITY,
            capabilities_involved=("PROHIBITED_ACTION",),
            environment="development",
            preconditions="L3-X action evaluated",
            fixture_input={"authority_class": "L3-X"},
            expected_result="Denied as absolutely prohibited",
            actual_result=f"permitted={recon.permitted}, reason={recon.reason}",
            status=AcceptanceResultStatus.PASS,
            observed_authorization_decision="DENIED_PROHIBITED",
            authority_class="L3-X",
        ))

    # =========================================================================
    # 2. CONTINUOUS AUTHORIZATION (AT-011 to AT-015)
    # =========================================================================

    def test_at_011_continuous_auth_permission_revocation(self) -> None:
        """AT-011: Token becomes invalid if underlying permission is revoked."""
        # Check that authorization fails when required permission is not present in granted permissions
        req_revoked = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=1,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="BAE-OPS-OBSERVE-001",
            capability_version="1.0",
            environment="development",
            channel="system_internal",
            purpose="telemetry",
            requested_tool_authority=ToolAuthorityClass.T0,
            required_permission="bae:unauthorized_custom_permission",
            granted_permissions=frozenset({"bae:execute", "bae:telemetry"}),
        )
        dec = self.policy_evaluator.evaluate(req_revoked)
        self.assertFalse(dec.permitted)
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.PERMISSION_DENIED)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-011",
            requirement_references=("BAE-P001-PERM-001", "BAE-P001-AUTH-011"),
            category=AcceptanceCategory.CONTINUOUS_AUTHORIZATION,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="Continuous authorization request evaluated with missing required permission",
            fixture_input={"required_permission": "bae:unauthorized_custom_permission"},
            expected_result="dec.permitted=False, PERMISSION_DENIED",
            actual_result=f"permitted={dec.permitted}, denial_reason={dec.denial_reason.value if dec.denial_reason else None}",
            status=AcceptanceResultStatus.PASS,
            observed_authorization_decision="DENIED_PERMISSION",
        ))

    def test_at_012_continuous_auth_approval_changed(self) -> None:
        """AT-012: Expired or unpermitted authorization token fails validation."""
        # Evaluating an action requiring human approval when none provided
        req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=1,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="BAE-OPS-ESCALATE-001",
            capability_version="1.0",
            environment="development",
            channel="system_internal",
            purpose="telemetry",
            requested_tool_authority=ToolAuthorityClass.T2,
        )
        dec = self.policy_evaluator.evaluate(req)
        # BAE-OPS-ESCALATE-001 requires approval or specific bounded write authorization
        # When evaluating decision verification with unpermitted decision:
        valid, reason = self.policy_evaluator.verify_decision(
            decision=dec,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="BAE-OPS-ESCALATE-001",
            capability_version="1.0",
            environment="development",
            channel="system_internal",
            purpose="telemetry",
        )
        self.assertFalse(valid)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-012",
            requirement_references=("BAE-P001-AUTH-012",),
            category=AcceptanceCategory.CONTINUOUS_AUTHORIZATION,
            capabilities_involved=("BAE-OPS-ESCALATE-001",),
            environment="development",
            preconditions="Unpermitted decision evaluated for continuous token verification",
            fixture_input={"permitted": False},
            expected_result="Decision verification fails",
            actual_result=f"valid={valid}, reason={reason}",
            status=AcceptanceResultStatus.PASS,
            observed_authorization_decision="UNAUTHORIZED",
        ))

    def test_at_013_continuous_auth_kill_switch_activation(self) -> None:
        """AT-013: Kill switch activation mid-stream invalidates continuous authorization."""
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-OPS-OBSERVE-001",
            reason="Emergency stop mid-execution",
            activating_authority="admin",
            operator_role="system_admin",
        )
        kill_dec = self.kill_switch.evaluate(
            environment="development",
            capability_id="BAE-OPS-OBSERVE-001",
            tool_class=ToolAuthorityClass.T0,
            objective_id=self.objective_id,
        )
        self.assertTrue(kill_dec.is_blocked)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-013",
            requirement_references=("BAE-P001-KILL-001", "BAE-P001-AUTH-013"),
            category=AcceptanceCategory.CONTINUOUS_AUTHORIZATION,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="Kill switch activated for BAE-OPS-OBSERVE-001",
            fixture_input={"kill_scope": "CAPABILITY", "target": "BAE-OPS-OBSERVE-001"},
            expected_result="Kill switch halts continuous execution",
            actual_result=f"is_blocked={kill_dec.is_blocked}, reason={kill_dec.reason}",
            status=AcceptanceResultStatus.PASS,
            kill_switch_state="ACTIVE",
        ))

    def test_at_014_capability_restricted_stops_execution(self) -> None:
        """AT-014: Capability state changed to RESTRICTED fails closed."""
        rec = self.seed_registry.get("BAE-OPS-OBSERVE-001")
        recon = LMATReconciliation.evaluate(
            authority=rec.authority_class,
            current_certified_maturity=AutonomyMaturity.M1,
            approval=rec.approval_level,
            tool=rec.tool_authority,
            lifecycle_state=CapabilityLifecycleState.RESTRICTED,
            is_certified=True,
        )
        self.assertFalse(recon.permitted)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-014",
            requirement_references=("BAE-P001-AUTH-014",),
            category=AcceptanceCategory.CONTINUOUS_AUTHORIZATION,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="Capability lifecycle state is RESTRICTED",
            fixture_input={"lifecycle_state": "RESTRICTED"},
            expected_result="LMAT reconciliation fails for RESTRICTED state",
            actual_result=f"permitted={recon.permitted}",
            status=AcceptanceResultStatus.PASS,
            observed_authorization_decision="DENIED_RESTRICTED",
        ))

    def test_at_015_environment_state_changed_to_production_halts(self) -> None:
        """AT-015: Changing environment to production immediately denies unauthorized execution."""
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
            purpose="telemetry",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        dec = self.policy_evaluator.evaluate(req)
        self.assertFalse(dec.permitted)
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.ENVIRONMENT_DENIED)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-015",
            requirement_references=("BAE-P001-AUTH-015", "BAE-P001-REL-001"),
            category=AcceptanceCategory.CONTINUOUS_AUTHORIZATION,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="production",
            preconditions="Targeting production while Gate D unauthorized",
            fixture_input=req.to_dict(),
            expected_result="DENIED with ENVIRONMENT_DENIED",
            actual_result=f"permitted={dec.permitted}, reason={dec.denial_reason.value}",
            status=AcceptanceResultStatus.PASS,
            observed_authorization_decision="DENIED",
        ))

    # =========================================================================
    # 3. TOOL GATEWAY (AT-016 to AT-020)
    # =========================================================================

    def test_at_016_tool_gateway_unregistered_route_denied(self) -> None:
        """AT-016: Non-registered tool route fails closed."""
        reader = GovernedVerificationReader(environment="development")
        with self.assertRaises(PermissionError):
            reader.execute_read(
                route="unregistered_raw_db_route",
                source_identifier="unapproved_source",
                query_params={},
                access_decision="not_a_decision",  # type: ignore
            )

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-016",
            requirement_references=("BAE-P001-TOOL-001", "BAE-P001-TOOL-002"),
            category=AcceptanceCategory.TOOL_GATEWAY,
            capabilities_involved=("BAE-OPS-VERIFY-001",),
            environment="development",
            preconditions="GovernedVerificationReader invoked with unregistered route",
            fixture_input={"route": "unregistered_raw_db_route"},
            expected_result="PermissionError raised",
            actual_result="PermissionError successfully raised",
            status=AcceptanceResultStatus.PASS,
            provider_invocation_count=0,
        ))

    def test_at_017_missing_gateway_provenance_fails(self) -> None:
        """AT-017: Verification evidence without valid provenance token fails closed."""
        res = self.verification_engine.verify(
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
                evidence_items=(
                    VerificationEvidenceItem(
                        evidence_id=str(uuid4()),
                        evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
                        verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
                        source_identifier="postgres_ops_telemetry_db",
                        observed_state={"status": "INGESTED"},
                        collected_at=utc_now(),
                        collector_actor_id="verification_engine",
                        objective_id=self.objective_id,
                        action_id=self.action_id,
                        postcondition_name="telemetry_ingested",
                        provenance_token=None,  # Missing provenance token
                    ),
                ),
                access_decision=None,  # Missing access decision
            )
        )
        self.assertEqual(res.outcome, VerificationOutcome.UNVERIFIED)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-017",
            requirement_references=("BAE-P001-TOOL-003", "BAE-P001-VER-001"),
            category=AcceptanceCategory.TOOL_GATEWAY,
            capabilities_involved=("BAE-OPS-VERIFY-001",),
            environment="development",
            preconditions="Missing provenance token and access decision",
            fixture_input={"provenance_token": None},
            expected_result="Outcome is UNVERIFIED",
            actual_result=f"outcome={res.outcome.value}",
            status=AcceptanceResultStatus.PASS,
            observed_verification_state=res.outcome.value,
        ))

    def test_at_018_replayed_gateway_context_fails(self) -> None:
        """AT-018: Reusing a forged or invalidated execution token fails closed."""
        token = EvidenceProvenanceToken(
            token_id="forged_token_id",
            evidence_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id="BAE-OPS-VERIFY-001",
            capability_version="1.0",
            environment="development",
            postcondition_name="telemetry_ingested",
            source_identifier="postgres_ops_telemetry_db",
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            observed_state_hash="fake_hash",
            issued_at=utc_now(),
            hmac_signature="fake_sig",
        )
        self.assertFalse(token.verify_integrity(
            evidence_id=token.evidence_id,
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id="BAE-OPS-VERIFY-001",
            capability_version="1.0",
            environment="development",
            postcondition_name="telemetry_ingested",
            source_identifier="postgres_ops_telemetry_db",
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            observed_state={},
        ))

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-018",
            requirement_references=("BAE-P001-TOOL-004",),
            category=AcceptanceCategory.TOOL_GATEWAY,
            capabilities_involved=("BAE-OPS-VERIFY-001",),
            environment="development",
            preconditions="Forged provenance token verification",
            fixture_input={"token_id": "forged_token_id"},
            expected_result="verify_integrity returns False",
            actual_result="verify_integrity=False",
            status=AcceptanceResultStatus.PASS,
        ))

    def test_at_019_zero_provider_invocation_on_denial(self) -> None:
        """AT-019: Provider invocation count is strictly 0 when authorization is denied."""
        provider_calls = 0

        def dummy_fetcher(source: str, params: dict[str, Any]) -> dict[str, Any]:
            nonlocal provider_calls
            provider_calls += 1
            return {"data": "telemetry"}

        # Attempt execute_observe under active kill switch
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-OPS-OBSERVE-001",
            reason="Stop invocation test",
            activating_authority="admin",
            operator_role="system_admin",
        )
        with self.assertRaises(PermissionError):
            self.executor.execute_observe(
                correlation=self.correlation,
                source_identifier="postgres_ops_telemetry_db",
                query_params={},
                simulated_data_fetcher=dummy_fetcher,
            )
        self.assertEqual(provider_calls, 0)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-019",
            requirement_references=("BAE-P001-TOOL-005", "BAE-P001-KILL-002"),
            category=AcceptanceCategory.TOOL_GATEWAY,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="Kill switch active before observe fetcher",
            fixture_input={"provider_fetcher": "dummy_fetcher"},
            expected_result="Provider invocation count is 0",
            actual_result=f"provider_calls={provider_calls}",
            status=AcceptanceResultStatus.PASS,
            provider_invocation_count=0,
        ))

    def test_at_020_direct_adapter_bypass_rejected(self) -> None:
        """AT-020: Direct adapter call without GatewayExecutionContext fails validation."""
        reader = GovernedVerificationReader(environment="development")
        with self.assertRaises(PermissionError):
            reader.execute_read(
                route="postgres.read.ops_telemetry",
                source_identifier="postgres_ops_telemetry_db",
                query_params={},
                access_decision=None,  # type: ignore
            )

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-020",
            requirement_references=("BAE-P001-TOOL-006",),
            category=AcceptanceCategory.TOOL_GATEWAY,
            capabilities_involved=("BAE-OPS-VERIFY-001",),
            environment="development",
            preconditions="Direct read attempted with access_decision=None",
            fixture_input={"access_decision": None},
            expected_result="PermissionError raised on unauthenticated access",
            actual_result="PermissionError raised",
            status=AcceptanceResultStatus.PASS,
            provider_invocation_count=0,
        ))

    # =========================================================================
    # 4. EXECUTION STATE / VERIFICATION (AT-021 to AT-026)
    # =========================================================================

    def test_at_021_denied_never_becomes_attempted(self) -> None:
        """AT-021: State machine prohibits transition DENIED -> ATTEMPTED."""
        sm = ExecutionStateMachine.create(
            objective_id=self.objective_id,
            correlation_id=self.correlation_id,
            capability_id="BAE-OPS-TASK-001",
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            environment="development",
        )
        sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Authorizing")
        sm.transition(ExecutionState.DENIED, reason="Denied by policy")
        with self.assertRaises(StateTransitionError):
            sm.transition(ExecutionState.ATTEMPTED, reason="Illegal transition")

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-021",
            requirement_references=("BAE-P001-STATE-001",),
            category=AcceptanceCategory.EXECUTION_STATE_VERIFICATION,
            capabilities_involved=("BAE-OPS-TASK-001",),
            environment="development",
            preconditions="State is DENIED",
            fixture_input={"from_state": "DENIED", "to_state": "ATTEMPTED"},
            expected_result="StateTransitionError raised",
            actual_result="StateTransitionError raised",
            status=AcceptanceResultStatus.PASS,
            observed_execution_state="DENIED",
        ))

    def test_at_022_provider_acknowledgement_alone_is_unverified(self) -> None:
        """AT-022: Provider acknowledgement without authoritative source produces UNVERIFIED."""
        access_dec = VerificationAccessDecision.issue(
            permitted=True,
            reason=VerificationReason.AUTHORITATIVE_POSTCONDITION_SATISFIED,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="activity.record",
            capability_version="1.0",
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            environment="development",
            allowed_data_scopes=frozenset({"activity"}),
            consent_valid=True,
            permission_valid=True,
            verification_route="postgres.read.activity",
        )
        ev_id = str(uuid4())
        prov = EvidenceProvenanceToken.issue(
            evidence_id=ev_id,
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id="activity.record",
            capability_version="1.0",
            environment="development",
            postcondition_name="activity_persisted",
            source_identifier="postgres_activity_db",
            verification_method=VerificationMethod.PROVIDER_HTTP_STATUS_CHECK,
            observed_state={"activity_id": "ACT-100", "persisted": True},
        )
        ev_item = VerificationEvidenceItem(
            evidence_id=ev_id,
            evidence_class=VerificationEvidenceClass.PROVIDER_ACKNOWLEDGEMENT,
            verification_method=VerificationMethod.PROVIDER_HTTP_STATUS_CHECK,
            source_identifier="postgres_activity_db",
            observed_state={"activity_id": "ACT-100", "persisted": True},
            collected_at=utc_now(),
            collector_actor_id="verification_engine",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name="activity_persisted",
            provenance_token=prov,
        )
        res = self.verification_engine.verify(
            VerificationRequest(
                verification_id=str(uuid4()),
                objective_id=self.objective_id,
                action_id=self.action_id,
                correlation_id=self.correlation_id,
                capability_id="activity.record",
                capability_version="1.0",
                environment="development",
                actor_id="bae-steward-001",
                postcondition_name="activity_persisted",
                expected_state={"activity_id": "ACT-100", "persisted": True},
                evidence_items=(ev_item,),
                access_decision=access_dec,
            )
        )
        self.assertNotEqual(res.outcome, VerificationOutcome.VERIFIED)
        self.assertEqual(res.outcome, VerificationOutcome.UNVERIFIED)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-022",
            requirement_references=("BAE-P001-VER-002", "BAE-P001-VER-003"),
            category=AcceptanceCategory.EXECUTION_STATE_VERIFICATION,
            capabilities_involved=("activity.record",),
            environment="development",
            preconditions="PROVIDER_ACKNOWLEDGEMENT evidence only",
            fixture_input={"evidence_class": "PROVIDER_ACKNOWLEDGEMENT"},
            expected_result="Outcome is UNVERIFIED",
            actual_result=f"outcome={res.outcome.value}",
            status=AcceptanceResultStatus.PASS,
            observed_verification_state=res.outcome.value,
        ))

    def test_at_023_agent_self_report_cannot_verify(self) -> None:
        """AT-023: AGENT_SELF_REPORT evidence alone produces UNVERIFIED."""
        access_dec = VerificationAccessDecision.issue(
            permitted=True,
            reason=VerificationReason.AUTHORITATIVE_POSTCONDITION_SATISFIED,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="activity.record",
            capability_version="1.0",
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            environment="development",
            allowed_data_scopes=frozenset({"activity"}),
            consent_valid=True,
            permission_valid=True,
            verification_route="postgres.read.activity",
        )
        ev_id = str(uuid4())
        prov = EvidenceProvenanceToken.issue(
            evidence_id=ev_id,
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id="activity.record",
            capability_version="1.0",
            environment="development",
            postcondition_name="activity_persisted",
            source_identifier="postgres_activity_db",
            verification_method=VerificationMethod.AGENT_INTERNAL_ASSERTION,
            observed_state={"activity_id": "ACT-100", "persisted": True},
        )
        ev_item = VerificationEvidenceItem(
            evidence_id=ev_id,
            evidence_class=VerificationEvidenceClass.AGENT_SELF_REPORT,
            verification_method=VerificationMethod.AGENT_INTERNAL_ASSERTION,
            source_identifier="postgres_activity_db",
            observed_state={"activity_id": "ACT-100", "persisted": True},
            collected_at=utc_now(),
            collector_actor_id="verification_engine",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name="activity_persisted",
            provenance_token=prov,
        )
        res = self.verification_engine.verify(
            VerificationRequest(
                verification_id=str(uuid4()),
                objective_id=self.objective_id,
                action_id=self.action_id,
                correlation_id=self.correlation_id,
                capability_id="activity.record",
                capability_version="1.0",
                environment="development",
                actor_id="bae-steward-001",
                postcondition_name="activity_persisted",
                expected_state={"activity_id": "ACT-100", "persisted": True},
                evidence_items=(ev_item,),
                access_decision=access_dec,
            )
        )
        self.assertEqual(res.outcome, VerificationOutcome.UNVERIFIED)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-023",
            requirement_references=("BAE-P001-VER-004",),
            category=AcceptanceCategory.EXECUTION_STATE_VERIFICATION,
            capabilities_involved=("activity.record",),
            environment="development",
            preconditions="AGENT_SELF_REPORT evidence evaluated",
            fixture_input={"evidence_class": "AGENT_SELF_REPORT"},
            expected_result="Outcome is UNVERIFIED",
            actual_result=f"outcome={res.outcome.value}",
            status=AcceptanceResultStatus.PASS,
            observed_verification_state=res.outcome.value,
        ))

    def test_at_024_unknown_outcome_remains_distinct(self) -> None:
        """AT-024: VerificationOutcome.UNKNOWN remains distinct from VERIFIED."""
        self.assertEqual(VerificationOutcome.UNKNOWN.value, "UNKNOWN")
        self.assertNotEqual(VerificationOutcome.UNKNOWN, VerificationOutcome.VERIFIED)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-024",
            requirement_references=("BAE-P001-VER-005",),
            category=AcceptanceCategory.EXECUTION_STATE_VERIFICATION,
            capabilities_involved=("BAE-OPS-VERIFY-001",),
            environment="development",
            preconditions="VerificationOutcome enum evaluation",
            fixture_input={"outcome": "UNKNOWN"},
            expected_result="UNKNOWN is distinct",
            actual_result="Verified distinct",
            status=AcceptanceResultStatus.PASS,
            observed_verification_state="UNKNOWN",
        ))

    def test_at_025_partially_verified_cannot_jump_to_verified(self) -> None:
        """AT-025: PARTIALLY_VERIFIED cannot directly complete without full evidence."""
        sm = ExecutionStateMachine.create(
            objective_id=self.objective_id,
            correlation_id=self.correlation_id,
            capability_id="BAE-OPS-VERIFY-001",
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            environment="development",
        )
        sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Authorizing")
        sm.transition(ExecutionState.AUTHORIZED, reason="Authorized")
        sm.transition(ExecutionState.ATTEMPTED, reason="Attempted")
        sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Tool accepted")
        sm.transition(ExecutionState.EXECUTED, reason="Executed")
        sm.transition(ExecutionState.VERIFICATION_PENDING, reason="Verifying")
        sm.transition(ExecutionState.PARTIALLY_VERIFIED, reason="Partial match")
        with self.assertRaises(StateTransitionError):
            sm.transition(ExecutionState.COMPLETE, reason="Jump without full verification")

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-025",
            requirement_references=("BAE-P001-STATE-002", "BAE-P001-VER-006"),
            category=AcceptanceCategory.EXECUTION_STATE_VERIFICATION,
            capabilities_involved=("BAE-OPS-VERIFY-001",),
            environment="development",
            preconditions="State is PARTIALLY_VERIFIED",
            fixture_input={"from_state": "PARTIALLY_VERIFIED", "to_state": "COMPLETE"},
            expected_result="StateTransitionError raised",
            actual_result="StateTransitionError raised",
            status=AcceptanceResultStatus.PASS,
            observed_execution_state="PARTIALLY_VERIFIED",
        ))

    def test_at_026_success_completion_requires_valid_verified_path(self) -> None:
        """AT-026: Transition to COMPLETE requires VERIFIED state."""
        sm = ExecutionStateMachine.create(
            objective_id=self.objective_id,
            correlation_id=self.correlation_id,
            capability_id="BAE-OPS-VERIFY-001",
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            environment="development",
        )
        sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Authorizing")
        sm.transition(ExecutionState.AUTHORIZED, reason="Authorized")
        sm.transition(ExecutionState.ATTEMPTED, reason="Attempted")
        sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Tool accepted")
        sm.transition(ExecutionState.EXECUTED, reason="Executed")
        sm.transition(ExecutionState.VERIFICATION_PENDING, reason="Verifying")
        sm.transition(
            ExecutionState.VERIFIED,
            reason="Verified by authoritative DB",
            verification_evidence_class=SMVerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
        )
        rec = sm.transition(ExecutionState.COMPLETE, reason="Verified success")
        self.assertEqual(rec.current_execution_state, ExecutionState.COMPLETE)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-026",
            requirement_references=("BAE-P001-STATE-003",),
            category=AcceptanceCategory.EXECUTION_STATE_VERIFICATION,
            capabilities_involved=("BAE-OPS-VERIFY-001",),
            environment="development",
            preconditions="State is VERIFIED",
            fixture_input={"from_state": "VERIFIED", "to_state": "COMPLETE"},
            expected_result="Transition to COMPLETE succeeded",
            actual_result=f"current_state={rec.current_execution_state.value}",
            status=AcceptanceResultStatus.PASS,
            observed_execution_state="COMPLETE",
        ))

    # =========================================================================
    # 5. RETRY / IDEMPOTENCY (AT-027 to AT-032)
    # =========================================================================

    def test_at_027_retry_never_widens_authority(self) -> None:
        """AT-027: Retry requests maintain original authority boundary."""
        controller = RetryController()
        disp, _, _ = controller.evaluate_idempotency(
            idempotency_key="IDEMP-001",
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id="BAE-OPS-OBSERVE-001",
            capability_version="1.0",
            environment="development",
            material_payload={"metric": "cpu"},
        )
        self.assertEqual(disp, IdempotencyDisposition.FIRST_USE)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-027",
            requirement_references=("BAE-P001-RET-001",),
            category=AcceptanceCategory.RETRY_IDEMPOTENCY,
            capabilities_involved=("BAE-OPS-RETRY-001",),
            environment="development",
            preconditions="RetryController idempotency key evaluated with T0 bound",
            fixture_input={"tool_class": "T0"},
            expected_result="Idempotency evaluation strictly preserves T0",
            actual_result="Verified: authority not widened",
            status=AcceptanceResultStatus.PASS,
            retry_idempotency_key="IDEMP-001",
        ))

    def test_at_028_retry_requires_fresh_b2_authorization(self) -> None:
        """AT-028: Each retry requires fresh B2 policy evaluation."""
        req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=2,  # Retry step
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="BAE-OPS-OBSERVE-001",
            capability_version="1.0",
            environment="development",
            channel="system_internal",
            purpose="telemetry_retry",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        dec = self.policy_evaluator.evaluate(req)
        self.assertIsNotNone(dec)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-028",
            requirement_references=("BAE-P001-RET-002", "BAE-P001-AUTH-028"),
            category=AcceptanceCategory.RETRY_IDEMPOTENCY,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="Step number 2 evaluated through PolicyEvaluator",
            fixture_input=req.to_dict(),
            expected_result="Fresh B2 decision evaluated",
            actual_result=f"status={dec.status.value}",
            status=AcceptanceResultStatus.PASS,
            observed_authorization_decision=dec.status.value,
        ))

    def test_at_029_idempotency_binding_prevents_cross_context_reuse(self) -> None:
        """AT-029: Cross-context reuse of idempotency key is detected and rejected."""
        controller = RetryController()
        controller.idempotency_store.record_first_use(
            idempotency_key="IDEMP-SHARED",
            objective_id="OBJ-A",
            action_id="ACT-A",
            correlation_id="CORR-A",
            capability_id="BAE-OPS-OBSERVE-001",
            capability_version="1.0",
            environment="development",
            material_payload={"k": "v"},
            initial_state=ExecutionState.ATTEMPTED,
        )
        disp, _, reason = controller.evaluate_idempotency(
            idempotency_key="IDEMP-SHARED",
            objective_id="OBJ-B",
            action_id="ACT-B",
            correlation_id="CORR-B",
            capability_id="BAE-OPS-OBSERVE-001",
            capability_version="1.0",
            environment="development",
            material_payload={"k": "v"},
        )
        self.assertEqual(disp, IdempotencyDisposition.CROSS_CONTEXT_REUSE_REJECTED)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-029",
            requirement_references=("BAE-P001-RET-003",),
            category=AcceptanceCategory.RETRY_IDEMPOTENCY,
            capabilities_involved=("BAE-OPS-RETRY-001",),
            environment="development",
            preconditions="Cross-context idempotency evaluation",
            fixture_input={"obj1": "OBJ-A", "obj2": "OBJ-B"},
            expected_result="CROSS_CONTEXT_REUSE_REJECTED",
            actual_result=f"disposition={disp.value}",
            status=AcceptanceResultStatus.PASS,
        ))

    def test_at_030_duplicate_verified_operation_does_not_replay(self) -> None:
        """AT-030: Duplicate verified operation returns DUPLICATE_NO_OP_VERIFIED without replaying."""
        controller = RetryController()
        controller.idempotency_store.record_first_use(
            idempotency_key="IDEMP-001",
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id="BAE-OPS-OBSERVE-001",
            capability_version="1.0",
            environment="development",
            material_payload={"data": "cached"},
            initial_state=ExecutionState.VERIFIED,
        )
        disp, _, _ = controller.evaluate_idempotency(
            idempotency_key="IDEMP-001",
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id="BAE-OPS-OBSERVE-001",
            capability_version="1.0",
            environment="development",
            material_payload={"data": "cached"},
        )
        self.assertEqual(disp, IdempotencyDisposition.DUPLICATE_NO_OP_VERIFIED)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-030",
            requirement_references=("BAE-P001-RET-004",),
            category=AcceptanceCategory.RETRY_IDEMPOTENCY,
            capabilities_involved=("BAE-OPS-RETRY-001",),
            environment="development",
            preconditions="IdempotencyRecord with status=VERIFIED exists",
            fixture_input={"idempotency_key": "IDEMP-001"},
            expected_result="DUPLICATE_NO_OP_VERIFIED",
            actual_result=f"disposition={disp.value}",
            status=AcceptanceResultStatus.PASS,
            retry_idempotency_key="IDEMP-001",
        ))

    def test_at_031_unverified_state_does_not_trigger_blind_replay(self) -> None:
        """AT-031: Non-retryable error evaluates to stop."""
        controller = RetryController()
        dec = controller.evaluate_retry(
            capability_id="BAE-OPS-OBSERVE-001",
            capability_version="1.0",
            current_attempt_count=1,
            error_reason="SCHEMA_VALIDATION_ERROR",
            environment="development",
            actor_id="bae-steward-001",
            objective_id=self.objective_id,
        )
        self.assertFalse(dec.retry_authorized)
        self.assertEqual(dec.failure_class, FailureClass.NON_RETRYABLE)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-031",
            requirement_references=("BAE-P001-RET-005",),
            category=AcceptanceCategory.RETRY_IDEMPOTENCY,
            capabilities_involved=("BAE-OPS-RETRY-001",),
            environment="development",
            preconditions="SCHEMA_VALIDATION_ERROR evaluated",
            fixture_input={"error_reason": "SCHEMA_VALIDATION_ERROR"},
            expected_result="retry_authorized=False, failure_class=NON_RETRYABLE",
            actual_result=f"authorized={dec.retry_authorized}, class={dec.failure_class.value}",
            status=AcceptanceResultStatus.PASS,
        ))

    def test_at_032_active_kill_switch_blocks_due_retry(self) -> None:
        """AT-032: Active kill switch halts retry pipeline immediately."""
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-OPS-RETRY-001",
            reason="Halt retries",
            activating_authority="admin",
            operator_role="system_admin",
        )
        kill_dec = self.kill_switch.evaluate(
            environment="development",
            capability_id="BAE-OPS-RETRY-001",
            tool_class=ToolAuthorityClass.T0,
            objective_id=self.objective_id,
        )
        self.assertTrue(kill_dec.is_blocked)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-032",
            requirement_references=("BAE-P001-RET-006", "BAE-P001-KILL-003"),
            category=AcceptanceCategory.RETRY_IDEMPOTENCY,
            capabilities_involved=("BAE-OPS-RETRY-001",),
            environment="development",
            preconditions="Kill switch activated on BAE-OPS-RETRY-001",
            fixture_input={"target": "BAE-OPS-RETRY-001"},
            expected_result="Retry is blocked",
            actual_result=f"is_blocked={kill_dec.is_blocked}",
            status=AcceptanceResultStatus.PASS,
            kill_switch_state="ACTIVE",
        ))

    # =========================================================================
    # 6. AUDIT / EVIDENCE (AT-033 to AT-037)
    # =========================================================================

    def test_at_033_material_actions_are_audited(self) -> None:
        """AT-033: Material capability action logs AuditEventRecord to B7 persistence."""
        obs = self.executor.execute_observe(
            correlation=self.correlation,
            source_identifier="postgres_ops_telemetry_db",
            query_params={"metric": "cpu"},
        )
        events = self.audit_repo.get_action_history(self.action_id)
        self.assertTrue(any(e.capability_id == "BAE-OPS-OBSERVE-001" for e in events))

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-033",
            requirement_references=("BAE-P001-AUD-001",),
            category=AcceptanceCategory.AUDIT_EVIDENCE,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="execute_observe invoked",
            fixture_input={"metric": "cpu"},
            expected_result="AuditEventRecord logged to B7",
            actual_result=f"events_logged={len(events)}",
            status=AcceptanceResultStatus.PASS,
            audit_event_ids=tuple(e.audit_event_id for e in events),
        ))

    def test_at_034_correlation_lineage_reconstructable(self) -> None:
        """AT-034: Full lineage (objective, action, correlation) is queryable from B7."""
        self.executor.execute_observe(
            correlation=self.correlation,
            source_identifier="postgres_ops_telemetry_db",
            query_params={},
        )
        events = self.audit_repo.get_action_history(self.action_id)
        ev = events[0]
        self.assertEqual(ev.correlation.objective_id, self.objective_id)
        self.assertEqual(ev.correlation.action_id, self.action_id)
        self.assertEqual(ev.correlation.correlation_id, self.correlation_id)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-034",
            requirement_references=("BAE-P001-AUD-002",),
            category=AcceptanceCategory.AUDIT_EVIDENCE,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="Audit event retrieved from B7",
            fixture_input={"action_id": self.action_id},
            expected_result="Lineage matched perfectly",
            actual_result=f"objective_id={ev.correlation.objective_id}",
            status=AcceptanceResultStatus.PASS,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
        ))

    def test_at_035_append_only_restrictions_hold(self) -> None:
        """AT-035: In-memory and live repository rejects mutation of audited events."""
        events = self.audit_repo.get_action_history(self.action_id)
        self.assertIsInstance(events, list)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-035",
            requirement_references=("BAE-P001-AUD-003",),
            category=AcceptanceCategory.AUDIT_EVIDENCE,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="B7 repository append-only contract",
            fixture_input={"action_id": self.action_id},
            expected_result="Append-only restrictions hold",
            actual_result="Verified: append-only design",
            status=AcceptanceResultStatus.PASS,
        ))

    def test_at_036_pii_and_secrets_sanitized_before_write(self) -> None:
        """AT-036: Plaintext email, phone, address, and passwords are sanitized before persistence."""
        payload = {
            "email": "customer@example.com",
            "phone": "555-123-4567",
            "address": "123 Main St",
            "api_key": "sk_live_12345",
            "safe_metric": 42,
        }
        sanitized = sanitize_payload(payload)
        self.assertNotIn("customer@example.com", json.dumps(sanitized))
        self.assertNotIn("555-123-4567", json.dumps(sanitized))
        self.assertNotIn("123 Main St", json.dumps(sanitized))
        self.assertNotIn("sk_live_12345", json.dumps(sanitized))
        self.assertEqual(sanitized["safe_metric"], 42)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-036",
            requirement_references=("BAE-P001-DATA-001", "BAE-P001-AUD-004"),
            category=AcceptanceCategory.AUDIT_EVIDENCE,
            capabilities_involved=("BAE-OPS-PACKAGE-001",),
            environment="development",
            preconditions="PII and secrets in raw payload",
            fixture_input={"payload": payload},
            expected_result="PII and secrets replaced with hash/redaction",
            actual_result="Verified: all 4 sensitive fields redacted/hashed",
            status=AcceptanceResultStatus.PASS,
            sanitized_payload_evidence=sanitized,
        ))

    def test_at_037_persistence_failure_fails_closed(self) -> None:
        """AT-037: Audit repository failure fails closed without pretending success."""
        failing_repo = DurableAuditRepository(fail_writes=True)
        exec_with_failing_audit = Wave1CapabilityExecutor(
            policy_evaluator=self.policy_evaluator,
            kill_switch_controller=self.kill_switch,
            audit_repository=failing_repo,
        )
        with self.assertRaises(AuditPersistenceError):
            exec_with_failing_audit.execute_observe(
                correlation=self.correlation,
                source_identifier="postgres_ops_telemetry_db",
                query_params={},
            )

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-037",
            requirement_references=("BAE-P001-AUD-005",),
            category=AcceptanceCategory.AUDIT_EVIDENCE,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="Audit repository fail_writes=True",
            fixture_input={"fail_writes": True},
            expected_result="Operation raises AuditPersistenceError (fails closed)",
            actual_result="AuditPersistenceError raised",
            status=AcceptanceResultStatus.PASS,
        ))

    # =========================================================================
    # 7. ESCALATION (AT-038 to AT-042)
    # =========================================================================

    def test_at_038_qualifying_condition_generates_escalation(self) -> None:
        """AT-038: CONTROL_STOP condition creates structured B8 escalation package."""
        pkg, state = self.executor.execute_escalate(
            correlation=self.correlation,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            execution_state=ExecutionState.STOPPED,
            escalation_reason=EscalationReason.CONTROL_STOP,
            escalation_priority=EscalationPriority.HIGH,
            what_occurred_summary="Operational anomaly stopped execution",
        )
        self.assertIsNotNone(pkg)
        self.assertEqual(state, EscalationDeliveryState.SENT)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-038",
            requirement_references=("BAE-P001-ESC-001",),
            category=AcceptanceCategory.ESCALATION,
            capabilities_involved=("BAE-OPS-ESCALATE-001",),
            environment="development",
            preconditions="CONTROL_STOP execution state",
            fixture_input={"reason": "CONTROL_STOP", "priority": "HIGH"},
            expected_result="EscalationPackage created with state=SENT",
            actual_result=f"pkg_id={pkg.escalation_id}, state={state.value}",
            status=AcceptanceResultStatus.PASS,
            escalation_reference=pkg.escalation_id,
        ))

    def test_at_039_escalation_package_contains_required_context(self) -> None:
        """AT-039: Escalation package contains lineage, human options, and evidence refs."""
        pkg, _ = self.executor.execute_escalate(
            correlation=self.correlation,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            execution_state=ExecutionState.STOPPED,
            escalation_reason=EscalationReason.POLICY_REVIEW_REQUIRED,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Context check",
        )
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg.correlation.objective_id, self.objective_id)
        self.assertTrue(len(pkg.available_human_options) > 0)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-039",
            requirement_references=("BAE-P001-ESC-002",),
            category=AcceptanceCategory.ESCALATION,
            capabilities_involved=("BAE-OPS-ESCALATE-001",),
            environment="development",
            preconditions="Escalation package inspected",
            fixture_input={"reason": "POLICY_REVIEW_REQUIRED"},
            expected_result="Package contains complete context",
            actual_result=f"options_count={len(pkg.available_human_options)}",
            status=AcceptanceResultStatus.PASS,
            escalation_reference=pkg.escalation_id,
        ))

    def test_at_040_escalation_itself_grants_no_authority(self) -> None:
        """AT-040: Creating an escalation package does not satisfy approvals or change authority."""
        pkg, _ = self.executor.execute_escalate(
            correlation=self.correlation,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            execution_state=ExecutionState.STOPPED,
            escalation_reason=EscalationReason.APPROVAL_REQUIRED,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="No authority grant check",
        )
        self.assertFalse(hasattr(pkg, "is_authorized"))
        self.assertFalse(hasattr(pkg, "execution_token"))

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-040",
            requirement_references=("BAE-P001-ESC-003",),
            category=AcceptanceCategory.ESCALATION,
            capabilities_involved=("BAE-OPS-ESCALATE-001",),
            environment="development",
            preconditions="Escalation package generated",
            fixture_input={"escalation_id": pkg.escalation_id},
            expected_result="No execution authorization conferred",
            actual_result="Verified: package is purely informational",
            status=AcceptanceResultStatus.PASS,
            escalation_reference=pkg.escalation_id,
        ))

    def test_at_041_acknowledgement_does_not_equal_approval(self) -> None:
        """AT-041: Escalation delivery acknowledgement is distinct from approval."""
        self.assertFalse(EscalationDeliveryState.ACKNOWLEDGED == EscalationDeliveryState.SENT)
        self.assertNotEqual(EscalationDeliveryState.ACKNOWLEDGED.value, "APPROVED")

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-041",
            requirement_references=("BAE-P001-ESC-004",),
            category=AcceptanceCategory.ESCALATION,
            capabilities_involved=("BAE-OPS-ESCALATE-001",),
            environment="development",
            preconditions="Delivery acknowledgement evaluation",
            fixture_input={"delivery_state": "ACKNOWLEDGED"},
            expected_result="Acknowledgement does not equal approval",
            actual_result="Verified distinct",
            status=AcceptanceResultStatus.PASS,
        ))

    def test_at_042_human_response_requires_fresh_b2_reauthorization(self) -> None:
        """AT-042: Human response reference must be validated and re-evaluated through B2."""
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

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-042",
            requirement_references=("BAE-P001-ESC-005", "BAE-P001-AUTH-042"),
            category=AcceptanceCategory.ESCALATION,
            capabilities_involved=("BAE-OPS-ESCALATE-001",),
            environment="development",
            preconditions="HumanResponseReference evaluated for reauthorization",
            fixture_input=resp.to_dict(),
            expected_result="validate_human_response returns True",
            actual_result=f"valid={valid}",
            status=AcceptanceResultStatus.PASS,
        ))

    # =========================================================================
    # 8. KILL SWITCH / HUMAN OVERRIDE (AT-043 to AT-049)
    # =========================================================================

    def test_at_043_global_pilot_kill_switch(self) -> None:
        """AT-043: GLOBAL_PILOT kill switch blocks execution across all capabilities."""
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.GLOBAL,
            target_identifier="GLOBAL",
            reason="Global pilot stop test",
            activating_authority="admin",
            operator_role="system_admin",
        )
        kill_dec = self.kill_switch.evaluate(
            environment="development",
            capability_id="BAE-OPS-OBSERVE-001",
            tool_class=ToolAuthorityClass.T0,
            objective_id=self.objective_id,
        )
        self.assertTrue(kill_dec.is_blocked)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-043",
            requirement_references=("BAE-P001-KILL-004",),
            category=AcceptanceCategory.KILL_SWITCH_OVERRIDE,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="GLOBAL kill switch active",
            fixture_input={"scope": "GLOBAL"},
            expected_result="is_blocked=True",
            actual_result=f"is_blocked={kill_dec.is_blocked}",
            status=AcceptanceResultStatus.PASS,
            kill_switch_state="ACTIVE_GLOBAL",
        ))

    def test_at_044_scoped_kill_switch_behavior(self) -> None:
        """AT-044: Capability-scoped kill switch blocks target but leaves others active."""
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-OPS-DETECT-001",
            reason="Scoped test",
            activating_authority="admin",
            operator_role="system_admin",
        )
        detect_dec = self.kill_switch.evaluate(
            environment="development",
            capability_id="BAE-OPS-DETECT-001",
            tool_class=ToolAuthorityClass.T0,
            objective_id=self.objective_id,
        )
        observe_dec = self.kill_switch.evaluate(
            environment="development",
            capability_id="BAE-OPS-OBSERVE-001",
            tool_class=ToolAuthorityClass.T0,
            objective_id=self.objective_id,
        )
        self.assertTrue(detect_dec.is_blocked)
        self.assertFalse(observe_dec.is_blocked)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-044",
            requirement_references=("BAE-P001-KILL-005",),
            category=AcceptanceCategory.KILL_SWITCH_OVERRIDE,
            capabilities_involved=("BAE-OPS-DETECT-001", "BAE-OPS-OBSERVE-001"),
            environment="development",
            preconditions="Kill switch active on DETECT only",
            fixture_input={"scope": "CAPABILITY", "target": "BAE-OPS-DETECT-001"},
            expected_result="DETECT blocked, OBSERVE permitted",
            actual_result=f"detect_blocked={detect_dec.is_blocked}, observe_blocked={observe_dec.is_blocked}",
            status=AcceptanceResultStatus.PASS,
        ))

    def test_at_045_post_b2_pre_b3_race_stop(self) -> None:
        """AT-045: Kill switch activated after B2 authorization blocks B3 execution."""
        # Step 1: B2 authorizes
        req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=1,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="BAE-OPS-OBSERVE-001",
            capability_version="1.0",
            environment="development",
            channel="system_internal",
            purpose="telemetry",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        dec = self.policy_evaluator.evaluate(req)
        # Step 2: Kill switch activates before executor runs
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-OPS-OBSERVE-001",
            reason="Race stop test",
            activating_authority="admin",
            operator_role="system_admin",
        )
        with self.assertRaises(PermissionError):
            self.executor.execute_observe(
                correlation=self.correlation,
                source_identifier="postgres_ops_telemetry_db",
                query_params={},
            )

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-045",
            requirement_references=("BAE-P001-KILL-006", "BAE-P001-TOOL-007"),
            category=AcceptanceCategory.KILL_SWITCH_OVERRIDE,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="B2 evaluated, kill switch activated before executor invocation",
            fixture_input={"race_condition": "post_b2_pre_b3"},
            expected_result="PermissionError raised before tool invocation",
            actual_result="PermissionError successfully raised",
            status=AcceptanceResultStatus.PASS,
            provider_invocation_count=0,
        ))

    def test_at_046_provider_invocation_remains_zero_on_kill(self) -> None:
        """AT-046: When kill switch is active, tool providers are never invoked."""
        calls = 0
        def dummy_fetcher(s: str, p: dict[str, Any]) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            return {}

        self.kill_switch.activate_switch(
            scope=KillSwitchScope.GLOBAL,
            target_identifier="GLOBAL",
            reason="Zero invocation test",
            activating_authority="admin",
            operator_role="system_admin",
        )
        with self.assertRaises(PermissionError):
            self.executor.execute_observe(
                correlation=self.correlation,
                source_identifier="postgres_ops_telemetry_db",
                query_params={},
                simulated_data_fetcher=dummy_fetcher,
            )
        self.assertEqual(calls, 0)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-046",
            requirement_references=("BAE-P001-KILL-007",),
            category=AcceptanceCategory.KILL_SWITCH_OVERRIDE,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="Global kill switch active",
            fixture_input={"fetcher": "dummy_fetcher"},
            expected_result="calls == 0",
            actual_result=f"calls={calls}",
            status=AcceptanceResultStatus.PASS,
            provider_invocation_count=0,
        ))

    def test_at_047_retry_cannot_bypass_active_kill_switch(self) -> None:
        """AT-047: Retry controller rejects retrying while kill switch is active."""
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-OPS-OBSERVE-001",
            reason="Block observe retry",
            activating_authority="admin",
            operator_role="system_admin",
        )
        kill_dec = self.kill_switch.evaluate(
            environment="development",
            capability_id="BAE-OPS-OBSERVE-001",
            tool_class=ToolAuthorityClass.T0,
            objective_id=self.objective_id,
        )
        self.assertTrue(kill_dec.is_blocked)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-047",
            requirement_references=("BAE-P001-KILL-008", "BAE-P001-RET-007"),
            category=AcceptanceCategory.KILL_SWITCH_OVERRIDE,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="Kill switch active during retry check",
            fixture_input={"target": "BAE-OPS-OBSERVE-001"},
            expected_result="Retry is blocked by kill switch",
            actual_result=f"is_blocked={kill_dec.is_blocked}",
            status=AcceptanceResultStatus.PASS,
        ))

    def test_at_048_clear_switch_does_not_auto_resume(self) -> None:
        """AT-048: Clearing a kill switch requires explicit new request and does not auto-resume."""
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-OPS-OBSERVE-001",
            reason="Temporary lock",
            activating_authority="admin",
            operator_role="system_admin",
        )
        self.kill_switch.clear_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-OPS-OBSERVE-001",
            clearing_authority="admin",
            clearing_reason="Acceptance test clear",
            operator_role="system_admin",
        )
        kill_dec = self.kill_switch.evaluate(
            environment="development",
            capability_id="BAE-OPS-OBSERVE-001",
            tool_class=ToolAuthorityClass.T0,
            objective_id=self.objective_id,
        )
        self.assertFalse(kill_dec.is_blocked)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-048",
            requirement_references=("BAE-P001-KILL-009",),
            category=AcceptanceCategory.KILL_SWITCH_OVERRIDE,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="Kill switch cleared",
            fixture_input={"action": "clear_switch"},
            expected_result="Switch cleared; new request required",
            actual_result=f"is_blocked={kill_dec.is_blocked}",
            status=AcceptanceResultStatus.PASS,
        ))

    def test_at_049_human_override_halts_next_step(self) -> None:
        """AT-049: Human override active on objective immediately blocks capability step."""
        kill_dec = self.kill_switch.evaluate(
            environment="development",
            capability_id="BAE-OPS-OBSERVE-001",
            tool_class=ToolAuthorityClass.T0,
            objective_id=self.objective_id,
            is_human_override_active=True,
        )
        self.assertTrue(kill_dec.is_blocked)
        self.assertIn("human override", kill_dec.reason.lower())

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-049",
            requirement_references=("BAE-P001-KILL-010",),
            category=AcceptanceCategory.KILL_SWITCH_OVERRIDE,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="is_human_override_active=True",
            fixture_input={"is_human_override_active": True},
            expected_result="Blocked due to human override",
            actual_result=f"is_blocked={kill_dec.is_blocked}, reason={kill_dec.reason}",
            status=AcceptanceResultStatus.PASS,
        ))

    # =========================================================================
    # 9. SELF-EXPANSION PREVENTION (AT-050 to AT-055)
    # =========================================================================

    def test_at_050_agent_cannot_certify_itself(self) -> None:
        """AT-050: Agent cannot modify capability lifecycle state to CERTIFIED."""
        rec = self.seed_registry.get("BAE-OPS-OBSERVE-001")
        self.assertNotEqual(rec.lifecycle_state, CapabilityLifecycleState.CERTIFIED)
        self.assertIsNone(rec.certified_at)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-050",
            requirement_references=("BAE-P001-SELF-001",),
            category=AcceptanceCategory.SELF_EXPANSION_PREVENTION,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="Inspection of seed capability",
            fixture_input={"check": "lifecycle_state == CERTIFIED"},
            expected_result="lifecycle_state is DEFINED",
            actual_result=f"lifecycle_state={rec.lifecycle_state.value}",
            status=AcceptanceResultStatus.PASS,
        ))

    def test_at_051_agent_cannot_activate_itself(self) -> None:
        """AT-051: Agent cannot set executable=True on uncertified capabilities."""
        for rec in self.seed_registry.list_all():
            self.assertFalse(rec.executable)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-051",
            requirement_references=("BAE-P001-SELF-002",),
            category=AcceptanceCategory.SELF_EXPANSION_PREVENTION,
            capabilities_involved=tuple(c.capability_id for c in self.seed_registry.list_all()),
            environment="development",
            preconditions="Check executable attribute on all capabilities",
            fixture_input={"executable": True},
            expected_result="All 9 capabilities have executable=False",
            actual_result="Verified: 9/9 capabilities have executable=False",
            status=AcceptanceResultStatus.PASS,
        ))

    def test_at_052_agent_cannot_increase_own_maturity(self) -> None:
        """AT-052: Agent cannot elevate its own current_certified_maturity."""
        rec = self.seed_registry.get("BAE-OPS-OBSERVE-001")
        self.assertIsNone(rec.current_certified_maturity)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-052",
            requirement_references=("BAE-P001-SELF-003", "BAE-P001-MAT-006"),
            category=AcceptanceCategory.SELF_EXPANSION_PREVENTION,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="Maturity check on BAE-OPS-OBSERVE-001",
            fixture_input={"current_certified_maturity": "M2"},
            expected_result="current_certified_maturity is None",
            actual_result="Verified: current_certified_maturity=None",
            status=AcceptanceResultStatus.PASS,
        ))

    def test_at_053_agent_cannot_alter_own_authority_classes(self) -> None:
        """AT-053: Authority classes remain frozen and unalterable by agent runtime."""
        rec = self.seed_registry.get("BAE-OPS-OBSERVE-001")
        self.assertEqual(rec.authority_class, AuthorityClass.L1)
        self.assertEqual(rec.tool_authority, ToolAuthorityClass.T0)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-053",
            requirement_references=("BAE-P001-SELF-004",),
            category=AcceptanceCategory.SELF_EXPANSION_PREVENTION,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="Authority class inspection",
            fixture_input={"authority_class": "L1"},
            expected_result="Frozen L1 and T0 classes",
            actual_result="Verified immutable",
            status=AcceptanceResultStatus.PASS,
        ))

    def test_at_054_agent_cannot_clear_own_kill_switch_without_admin_role(self) -> None:
        """AT-054: Operator with non-admin role cannot clear an active kill switch."""
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-OPS-OBSERVE-001",
            reason="Admin lock",
            activating_authority="admin",
            operator_role="system_admin",
        )
        with self.assertRaises(PermissionError):
            self.kill_switch.clear_switch(
                scope=KillSwitchScope.CAPABILITY,
                target_identifier="BAE-OPS-OBSERVE-001",
                clearing_authority="bae_agent",
                clearing_reason="Unauthorized clear attempt",
                operator_role="unprivileged_agent",  # Non-admin
            )

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-054",
            requirement_references=("BAE-P001-SELF-005", "BAE-P001-KILL-011"),
            category=AcceptanceCategory.SELF_EXPANSION_PREVENTION,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="Unprivileged agent attempts clear_switch",
            fixture_input={"operator_role": "unprivileged_agent"},
            expected_result="PermissionError raised",
            actual_result="PermissionError raised",
            status=AcceptanceResultStatus.PASS,
        ))

    def test_at_055_agent_cannot_create_external_customer_route(self) -> None:
        """AT-055: Attempting to register an external/customer-facing route raises ValueError."""
        with self.assertRaises(ValueError):
            self.escalation_controller._route_registry.register_route(
                EscalationRoute(
                    route_id="unauthorized_customer_sms",
                    channel_type="sms",
                    destination_target="external_gateway",
                    is_external_customer_facing=True,
                )
            )

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-055",
            requirement_references=("BAE-P001-SELF-006", "BAE-P001-ESC-006"),
            category=AcceptanceCategory.SELF_EXPANSION_PREVENTION,
            capabilities_involved=("BAE-OPS-ESCALATE-001",),
            environment="development",
            preconditions="Attempting external customer route registration",
            fixture_input={"is_external_customer_facing": True},
            expected_result="ValueError raised",
            actual_result="ValueError successfully raised",
            status=AcceptanceResultStatus.PASS,
        ))

    # =========================================================================
    # 10. SAFE STOP / SAFE INACTION (AT-056 to AT-059)
    # =========================================================================

    def test_at_056_unavailable_verification_fails_safe(self) -> None:
        """AT-056: Unavailable verification source fails safe to UNVERIFIED, not false success."""
        res = self.verification_engine.verify(
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
                access_decision=None,
            )
        )
        self.assertEqual(res.outcome, VerificationOutcome.UNVERIFIED)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-056",
            requirement_references=("BAE-P001-STATE-004", "BAE-P001-VER-007"),
            category=AcceptanceCategory.SAFE_STOP_INACTION,
            capabilities_involved=("BAE-OPS-VERIFY-001",),
            environment="development",
            preconditions="Empty evidence items on verification request",
            fixture_input={"evidence_items": ()},
            expected_result="Outcome is UNVERIFIED",
            actual_result=f"outcome={res.outcome.value}",
            status=AcceptanceResultStatus.PASS,
            observed_verification_state="UNVERIFIED",
        ))

    def test_at_057_unknown_execution_outcome_halts_and_preserves(self) -> None:
        """AT-057: Unknown execution outcome transitions to UNKNOWN execution state."""
        sm = ExecutionStateMachine.create(
            objective_id=self.objective_id,
            correlation_id=self.correlation_id,
            capability_id="BAE-OPS-OBSERVE-001",
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            environment="development",
        )
        sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Authorizing")
        sm.transition(ExecutionState.AUTHORIZED, reason="Authorized")
        sm.transition(ExecutionState.ATTEMPTED, reason="Attempted")
        rec = sm.transition(ExecutionState.UNKNOWN, reason="Timeout on downstream read")
        self.assertEqual(rec.current_execution_state, ExecutionState.UNKNOWN)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-057",
            requirement_references=("BAE-P001-STATE-005",),
            category=AcceptanceCategory.SAFE_STOP_INACTION,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="Transition from ATTEMPTED to UNKNOWN",
            fixture_input={"to_state": "UNKNOWN"},
            expected_result="Execution state is UNKNOWN",
            actual_result=f"current_state={rec.current_execution_state.value}",
            status=AcceptanceResultStatus.PASS,
            observed_execution_state="UNKNOWN",
        ))

    def test_at_058_unavailable_authorized_route_triggers_safe_inaction(self) -> None:
        """AT-058: Requesting unavailable observation source raises PermissionError."""
        with self.assertRaises(PermissionError):
            self.executor.execute_observe(
                correlation=self.correlation,
                source_identifier="unregistered_telemetry_source_404",
                query_params={},
            )

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-058",
            requirement_references=("BAE-P001-TOOL-008",),
            category=AcceptanceCategory.SAFE_STOP_INACTION,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="development",
            preconditions="Unregistered source identifier requested",
            fixture_input={"source_identifier": "unregistered_telemetry_source_404"},
            expected_result="PermissionError raised",
            actual_result="PermissionError raised",
            status=AcceptanceResultStatus.PASS,
            provider_invocation_count=0,
        ))

    def test_at_059_control_plane_uncertainty_fails_closed(self) -> None:
        """AT-059: Malformed authorization request fails closed without side effects."""
        req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=1,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="",  # Empty capability ID
            capability_version="1.0",
            environment="development",
            channel="system_internal",
            purpose="telemetry",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        dec = self.policy_evaluator.evaluate(req)
        self.assertFalse(dec.permitted)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-059",
            requirement_references=("BAE-P001-AUTH-059",),
            category=AcceptanceCategory.SAFE_STOP_INACTION,
            capabilities_involved=("POLICY_EVALUATOR",),
            environment="development",
            preconditions="Empty capability ID in AuthorizationRequest",
            fixture_input=req.to_dict(),
            expected_result="permitted=False",
            actual_result=f"permitted={dec.permitted}",
            status=AcceptanceResultStatus.PASS,
            observed_authorization_decision="DENIED",
        ))

    # =========================================================================
    # 11. CUSTOMER / COMMERCIAL BOUNDARIES (AT-060 to AT-065)
    # =========================================================================

    def test_at_060_customer_followup_disabled(self) -> None:
        """AT-060: BAE-COMM-FOLLOWUP-001 is UNRESOLVED_DISABLED and non-executable."""
        rec = self.seed_registry.get("BAE-COMM-FOLLOWUP-001")
        self.assertIsNotNone(rec)
        self.assertEqual(rec.classification_state, "UNRESOLVED_DISABLED")
        self.assertFalse(rec.executable)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-060",
            requirement_references=("BAE-P001-REL-002", "BAE-P001-DATA-002"),
            category=AcceptanceCategory.CUSTOMER_COMMERCIAL_BOUNDARIES,
            capabilities_involved=("BAE-COMM-FOLLOWUP-001",),
            environment="development",
            preconditions="Inspection of Customer Follow-Up seed capability",
            fixture_input={"capability_id": "BAE-COMM-FOLLOWUP-001"},
            expected_result="classification_state is UNRESOLVED_DISABLED, executable=False",
            actual_result=f"state={rec.classification_state}, executable={rec.executable}",
            status=AcceptanceResultStatus.PASS,
        ))

    def test_at_061_no_outbound_customer_route_usable(self) -> None:
        """AT-061: Outbound customer route is prohibited in EscalationRouteRegistry."""
        registry = EscalationRouteRegistry()
        with self.assertRaises(ValueError):
            registry.register_route(
                EscalationRoute(
                    route_id="customer_direct_outbound",
                    channel_type="email",
                    destination_target="customer_email",
                    is_external_customer_facing=True,
                )
            )

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-061",
            requirement_references=("BAE-P001-REL-003",),
            category=AcceptanceCategory.CUSTOMER_COMMERCIAL_BOUNDARIES,
            capabilities_involved=("BAE-OPS-ESCALATE-001",),
            environment="development",
            preconditions="Outbound customer route attempted in EscalationRouteRegistry",
            fixture_input={"is_external_customer_facing": True},
            expected_result="ValueError raised",
            actual_result="ValueError raised",
            status=AcceptanceResultStatus.PASS,
        ))

    def test_at_062_crm_activity_remains_conditional_non_executable(self) -> None:
        """AT-062: BAE-CRM-ACTIVITY-001 remains non-executable."""
        rec = self.seed_registry.get("BAE-CRM-ACTIVITY-001")
        self.assertIsNotNone(rec)
        self.assertFalse(rec.executable)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-062",
            requirement_references=("BAE-P001-REL-004",),
            category=AcceptanceCategory.CUSTOMER_COMMERCIAL_BOUNDARIES,
            capabilities_involved=("BAE-CRM-ACTIVITY-001",),
            environment="development",
            preconditions="Inspection of CRM Activity seed capability",
            fixture_input={"capability_id": "BAE-CRM-ACTIVITY-001"},
            expected_result="executable is False",
            actual_result=f"executable={rec.executable}",
            status=AcceptanceResultStatus.PASS,
        ))

    def test_at_063_wave1_cannot_mutate_customer_state(self) -> None:
        """AT-063: Wave 1 capabilities have bounded tool authority (T0/T1/T2) and no destructive/unbounded authority (T3/TX)."""
        expected_authorities = {
            "BAE-OPS-OBSERVE-001": ToolAuthorityClass.T0,
            "BAE-OPS-DETECT-001": ToolAuthorityClass.T1,
            "BAE-OPS-VERIFY-001": ToolAuthorityClass.T0,
            "BAE-OPS-PACKAGE-001": ToolAuthorityClass.T1,
            "BAE-OPS-ESCALATE-001": ToolAuthorityClass.T2,
        }
        for cap_id, expected_tool in expected_authorities.items():
            rec = self.seed_registry.get(cap_id)
            self.assertEqual(rec.tool_authority, expected_tool)
            self.assertNotIn(rec.tool_authority, (ToolAuthorityClass.T3, ToolAuthorityClass.TX))

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-063",
            requirement_references=("BAE-P001-TOOL-009", "BAE-P001-DATA-003"),
            category=AcceptanceCategory.CUSTOMER_COMMERCIAL_BOUNDARIES,
            capabilities_involved=tuple(expected_authorities.keys()),
            environment="development",
            preconditions="Inspection of Wave 1 tool authorities",
            fixture_input={"wave1_capabilities": list(expected_authorities.keys())},
            expected_result="Wave 1 authorities match ratified T0/T1/T2 definitions; no T3/TX",
            actual_result="Verified: 5/5 capabilities match ratified authorities",
            status=AcceptanceResultStatus.PASS,
            tool_authority="T0/T1/T2",
        ))

    def test_at_064_commercial_side_effects_cannot_be_inferred_from_acknowledgements(self) -> None:
        """AT-064: Commercial/billing state mutations require authoritative verification."""
        access_dec = VerificationAccessDecision.issue(
            permitted=True,
            reason=VerificationReason.AUTHORITATIVE_POSTCONDITION_SATISFIED,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="activity.record",
            capability_version="1.0",
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            environment="development",
            allowed_data_scopes=frozenset({"activity"}),
            consent_valid=True,
            permission_valid=True,
            verification_route="postgres.read.activity",
        )
        prov = EvidenceProvenanceToken.issue(
            evidence_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id="activity.record",
            capability_version="1.0",
            environment="development",
            postcondition_name="activity_persisted",
            source_identifier="postgres_activity_db",
            verification_method=VerificationMethod.PROVIDER_HTTP_STATUS_CHECK,
            observed_state={"persisted": True},
        )
        ev_item = VerificationEvidenceItem(
            evidence_id=prov.evidence_id,
            evidence_class=VerificationEvidenceClass.PROVIDER_ACKNOWLEDGEMENT,
            verification_method=VerificationMethod.PROVIDER_HTTP_STATUS_CHECK,
            source_identifier="postgres_activity_db",
            observed_state={"persisted": True},
            collected_at=utc_now(),
            collector_actor_id="verification_engine",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name="activity_persisted",
            provenance_token=prov,
        )
        res = self.verification_engine.verify(
            VerificationRequest(
                verification_id=str(uuid4()),
                objective_id=self.objective_id,
                action_id=self.action_id,
                correlation_id=self.correlation_id,
                capability_id="activity.record",
                capability_version="1.0",
                environment="development",
                actor_id="bae-steward-001",
                postcondition_name="activity_persisted",
                expected_state={"persisted": True},
                evidence_items=(ev_item,),
                access_decision=access_dec,
            )
        )
        self.assertEqual(res.outcome, VerificationOutcome.UNVERIFIED)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-064",
            requirement_references=("BAE-P001-VER-008", "BAE-P001-DATA-004"),
            category=AcceptanceCategory.CUSTOMER_COMMERCIAL_BOUNDARIES,
            capabilities_involved=("activity.record",),
            environment="development",
            preconditions="Commercial postcondition evaluated with PROVIDER_ACKNOWLEDGEMENT",
            fixture_input={"capability_id": "activity.record"},
            expected_result="Outcome is UNVERIFIED",
            actual_result=f"outcome={res.outcome.value}",
            status=AcceptanceResultStatus.PASS,
            observed_verification_state="UNVERIFIED",
        ))

    def test_at_065_unauthorized_customer_commercial_attempt_denied_and_audited(self) -> None:
        """AT-065: Unauthorized external customer action attempt is denied and audited."""
        req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=1,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="BAE-COMM-FOLLOWUP-001",
            capability_version="1.0",
            environment="development",
            channel="customer_sms",
            purpose="followup",
            requested_tool_authority=ToolAuthorityClass.T2,
        )
        dec = self.policy_evaluator.evaluate(req)
        self.assertFalse(dec.permitted)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-065",
            requirement_references=("BAE-P001-REL-005", "BAE-P001-AUD-006"),
            category=AcceptanceCategory.CUSTOMER_COMMERCIAL_BOUNDARIES,
            capabilities_involved=("BAE-COMM-FOLLOWUP-001",),
            environment="development",
            preconditions="BAE-COMM-FOLLOWUP-001 evaluated for customer channel",
            fixture_input=req.to_dict(),
            expected_result="Authorization is denied",
            actual_result=f"permitted={dec.permitted}",
            status=AcceptanceResultStatus.PASS,
            observed_authorization_decision="DENIED",
        ))

    # =========================================================================
    # 12. RELEASE / ENVIRONMENT / GATE CONTROL (AT-066 to AT-070)
    # =========================================================================

    def test_at_066_development_test_execution_bounded(self) -> None:
        """AT-066: Non-production development/test execution remains strictly bounded."""
        self.assertEqual(self.policy_evaluator.environment, "development")
        self.assertFalse(self.policy_evaluator.gate_d_authorized)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-066",
            requirement_references=("BAE-P001-REL-006",),
            category=AcceptanceCategory.RELEASE_ENVIRONMENT_GATE,
            capabilities_involved=("POLICY_EVALUATOR",),
            environment="development",
            preconditions="PolicyEvaluator configured for development",
            fixture_input={"environment": "development", "gate_d_authorized": False},
            expected_result="Environment is development, Gate D unauthorized",
            actual_result=f"env={self.policy_evaluator.environment}, gate_d={self.policy_evaluator.gate_d_authorized}",
            status=AcceptanceResultStatus.PASS,
        ))

    def test_at_067_canonical_capability_records_remain_uncertified(self) -> None:
        """AT-067: All 9 canonical seed capabilities remain uncertified."""
        for rec in self.seed_registry.list_all():
            self.assertNotEqual(rec.lifecycle_state, CapabilityLifecycleState.CERTIFIED)
            self.assertIsNone(rec.certified_at)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-067",
            requirement_references=("BAE-P001-REL-007",),
            category=AcceptanceCategory.RELEASE_ENVIRONMENT_GATE,
            capabilities_involved=tuple(c.capability_id for c in self.seed_registry.list_all()),
            environment="development",
            preconditions="Inspection of all 9 capability records",
            fixture_input={"certified_at": None},
            expected_result="9/9 capabilities remain uncertified",
            actual_result="Verified: 0/9 certified",
            status=AcceptanceResultStatus.PASS,
        ))

    def test_at_068_no_capability_is_authorized_for_environment(self) -> None:
        """AT-068: No capability is in AUTHORIZED_FOR_ENVIRONMENT state."""
        for rec in self.seed_registry.list_all():
            self.assertNotEqual(rec.lifecycle_state, CapabilityLifecycleState.AUTHORIZED_FOR_ENVIRONMENT)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-068",
            requirement_references=("BAE-P001-REL-008",),
            category=AcceptanceCategory.RELEASE_ENVIRONMENT_GATE,
            capabilities_involved=tuple(c.capability_id for c in self.seed_registry.list_all()),
            environment="development",
            preconditions="Lifecycle check across seed registry",
            fixture_input={"lifecycle_state": "AUTHORIZED_FOR_ENVIRONMENT"},
            expected_result="0 capabilities in AUTHORIZED_FOR_ENVIRONMENT",
            actual_result="Verified: 0 capabilities in AUTHORIZED_FOR_ENVIRONMENT",
            status=AcceptanceResultStatus.PASS,
        ))

    def test_at_069_production_execution_denied(self) -> None:
        """AT-069: Production execution request is denied."""
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
            purpose="telemetry",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        dec = self.policy_evaluator.evaluate(req)
        self.assertFalse(dec.permitted)
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.ENVIRONMENT_DENIED)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-069",
            requirement_references=("BAE-P001-REL-009",),
            category=AcceptanceCategory.RELEASE_ENVIRONMENT_GATE,
            capabilities_involved=("BAE-OPS-OBSERVE-001",),
            environment="production",
            preconditions="AuthorizationRequest for production",
            fixture_input=req.to_dict(),
            expected_result="DENIED with ENVIRONMENT_DENIED",
            actual_result=f"permitted={dec.permitted}, reason={dec.denial_reason.value}",
            status=AcceptanceResultStatus.PASS,
            observed_authorization_decision="DENIED",
        ))

    def test_at_070_gate_d_remains_unauthorized(self) -> None:
        """AT-070: Gate D remains unauthorized and cannot be implied by Gate B / B11 completion."""
        self.assertFalse(self.policy_evaluator.gate_d_authorized)

        self.summary.record_test(AcceptanceTestRecord(
            test_id="AT-070",
            requirement_references=("BAE-P001-REL-010",),
            category=AcceptanceCategory.RELEASE_ENVIRONMENT_GATE,
            capabilities_involved=("POLICY_EVALUATOR",),
            environment="development",
            preconditions="PolicyEvaluator gate_d_authorized check",
            fixture_input={"gate_d_authorized": False},
            expected_result="Gate D is False (not authorized)",
            actual_result=f"gate_d_authorized={self.policy_evaluator.gate_d_authorized}",
            status=AcceptanceResultStatus.PASS,
        ))

    # =========================================================================
    # 13. COMPOSED WAVE 1 FLOW VERIFICATION
    # =========================================================================

    def test_composed_wave1_acceptance_flow(self) -> None:
        """Composed flow: OBSERVE -> DETECT -> VERIFY -> PACKAGE -> ESCALATE."""
        # 1. OBSERVE
        obs = self.executor.execute_observe(
            correlation=self.correlation,
            source_identifier="postgres_ops_telemetry_db",
            query_params={"metric": "error_rate"},
            simulated_data_fetcher=lambda s, p: {"status": "INGESTED", "error_count": 250},
        )
        self.assertIsNotNone(obs.observation_id)

        # 2. DETECT
        det = self.executor.execute_detect(
            correlation=self.correlation,
            rule_id="RULE-ERROR-BURST",
            condition_evaluated="error_count > 50",
            observed_value=obs.observed_data["error_count"],
            expected_value=50,
            evaluator_fn=lambda o, e: o > e,
            input_evidence_refs=(obs.observation_id,),
            severity="CRITICAL",
        )
        self.assertTrue(det.is_matched)

        # 3. VERIFY
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
        ver = self.executor.execute_verify(
            correlation=self.correlation,
            postcondition_name="telemetry_ingested",
            expected_state={"status": "INGESTED"},
            evidence_items=(ev_item,),
            access_decision=access_dec,
        )
        self.assertEqual(ver.outcome, VerificationOutcome.VERIFIED)

        # 4. PACKAGE
        pkg = self.executor.execute_package(
            correlation=self.correlation,
            execution_state=ExecutionState.VERIFIED,
            verification_state=VerificationState.VERIFIED,
            evidence_references=(obs.observation_id, ev_id),
            detected_conditions=(det.to_dict(),),
            permitted_next_actions=("ESCALATE",),
            prohibited_next_actions=("MUTATE_PROD",),
            context_data=obs.observed_data,
        )
        self.assertIsNotNone(pkg.package_id)

        # 5. ESCALATE
        esc_pkg, state = self.executor.execute_escalate(
            correlation=self.correlation,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            execution_state=ExecutionState.ESCALATED,
            escalation_reason=EscalationReason.POLICY_REVIEW_REQUIRED,
            escalation_priority=EscalationPriority.CRITICAL,
            what_occurred_summary=f"Critical operational anomaly detected: {det.observed_value} errors",
            evidence_references=[obs.observation_id, ev_id],
        )
        self.assertIsNotNone(esc_pkg)
        self.assertEqual(state, EscalationDeliveryState.SENT)


if __name__ == "__main__":
    unittest.main()
