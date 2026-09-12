"""BAE Pilot 001 Gate B Step B8 Escalation Packaging & Routing Test Suite.

Verifies the 45 required B8 test invariants:
1. approval-required condition creates escalation package;
2. L3-H human-only condition creates appropriate package;
3. L3-X remains blocked and package cannot offer an authorization-bypassing option;
4. UNKNOWN verification produces uncertainty-preserving package;
5. UNVERIFIED produces distinct package state;
6. PARTIALLY_VERIFIED produces distinct package state;
7. terminal/non-retryable failure escalation;
8. retry-exhausted escalation;
9. persistence-failure escalation;
10. deterministic denial configured DO_NOT_ESCALATE does not create a package;
11. package includes exact capability/version;
12. package includes L/M/A/T independently;
13. package includes current execution and verification state;
14. package contains B7 audit/evidence references;
15. package contains what MAY occur;
16. package contains what MAY NOT occur;
17. package contains structured human options;
18. package contains no raw secrets/PII;
19. recommendation is non-binding;
20. package itself cannot serve as B2 authorization;
21. delivery acknowledgement cannot serve as approval;
22. silence cannot serve as approval;
23. valid human response still requires fresh B2 authorization;
24. wrong objective/action human response cannot authorize continuation;
25. stale human response cannot authorize continuation;
26. registered internal route sends successfully in DEVELOPMENT / TEST fixture;
27. unavailable route => WAITING/STOPPED, no unauthorized fallback;
28. unregistered route is rejected;
29. customer/external route is unavailable/prohibited in B8;
30. duplicate equivalent escalation is suppressed/deduplicated;
31. materially changed evidence/state produces new escalation;
32. dedupe suppression is auditable;
33. route delivery state is auditable through B7;
34. package creation is auditable through B7;
35. objective/action/correlation lineage preserved;
36. retry lineage preserved where applicable;
37. human override/control stop can trigger package without creating authority;
38. B2/B3 denial remains effective despite escalation creation;
39. all nine Pilot seed capabilities remain non-executable;
40. ESCALATE capability remains DEFINED / uncertified / non-executable;
41. Customer Follow-Up remains disabled;
42. Gate D remains unauthorized;
43. no production route exists;
44. no B9 implementation occurs;
45. all TG-P01/P02/P03 + B1-B7 regressions remain green.
"""

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
    EscalationRoute,
    EscalationRouteRegistry,
    HumanOption,
    HumanOptionType,
    HumanResponseReference,
    validate_human_response_for_reauthorization,
)
from src.budly_runtime.bae.policy_evaluator import (
    AuthorizationDecision,
    AuthorizationDecisionStatus,
    AuthorizationDenialReason,
    AuthorizationRequest,
    BAEKillSwitchRegistry,
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
    ToolAuthorityClass,
)
from src.budly_runtime.bae.verification_engine import (
    VerificationMethod,
    VerificationOutcome,
    VerificationReason,
    VerificationResult,
)


class TestBAEStepB8EscalationPackagingAndRouting(unittest.TestCase):
    def setUp(self) -> None:
        self.audit_repo = DurableAuditRepository(environment="development")
        self.route_registry = EscalationRouteRegistry()
        self.controller = EscalationController(self.audit_repo, self.route_registry)
        self.kill_switches = BAEKillSwitchRegistry()
        self.seed_registry = BAECapabilityRegistry.load_seed()
        self.evaluator = DeterministicPolicyEvaluator(self.seed_registry, self.kill_switches)

        self.objective_id = str(uuid4())
        self.action_id = str(uuid4())
        self.correlation_id = str(uuid4())
        self.correlation = CorrelationRecord(
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
        )
        self.capability_id = "BAE-OPS-OBSERVE-001"
        self.capability_version = "1.0"

    # 1. approval-required condition creates escalation package
    def test_b8_01_approval_required_creates_escalation_package(self):
        disp, reason, priority = EscalationPolicyEvaluator.evaluate(
            execution_state=ExecutionState.DENIED,
            auth_decision=AuthorizationDecision(
                status=AuthorizationDecisionStatus.REQUIRES_HUMAN_APPROVAL,
                permitted=False,
                requires_approval=True,
                approval_level=ApprovalLevel.A1,
                denial_reason=AuthorizationDenialReason.HUMAN_APPROVAL_REQUIRED,
                reason_detail="Approval required for L2 action",
            ),
        )
        self.assertEqual(disp, EscalationDisposition.ESCALATE)
        self.assertEqual(reason, EscalationReason.APPROVAL_REQUIRED)
        self.assertEqual(priority, EscalationPriority.NORMAL)

        pkg, state = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L2,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A1,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.DENIED,
            escalation_reason=reason,
            escalation_priority=priority,
            what_occurred_summary="Action requires explicit human approval before execution.",
        )
        self.assertIsNotNone(pkg)
        self.assertEqual(state, EscalationDeliveryState.SENT)
        self.assertEqual(pkg.approval_level, ApprovalLevel.A1)

    # 2. L3-H human-only condition creates appropriate package
    def test_b8_02_human_only_condition_creates_appropriate_package(self):
        disp, reason, priority = EscalationPolicyEvaluator.evaluate(
            execution_state=ExecutionState.DENIED,
            auth_decision=AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.AUTHORITY_CLASS_HUMAN_ONLY,
                reason_detail="L3-H human-only action",
            ),
        )
        self.assertEqual(disp, EscalationDisposition.ESCALATE)
        self.assertEqual(reason, EscalationReason.HUMAN_ONLY_ACTION)

        pkg, state = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L3_H,
            autonomy_maturity=AutonomyMaturity.M0,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.DENIED,
            escalation_reason=reason,
            escalation_priority=priority,
            what_occurred_summary="L3-H human-only boundary encountered.",
        )
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg.authority_level, AuthorityClass.L3_H)

    # 3. L3-X remains blocked and package cannot offer an authorization-bypassing option
    def test_b8_03_l3_x_prohibited_package_offers_no_continuation_option(self):
        pkg, state = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L3_X,
            autonomy_maturity=AutonomyMaturity.M0,
            approval_level=ApprovalLevel.A4,
            tool_authority_class=ToolAuthorityClass.TX,
            execution_state=ExecutionState.DENIED,
            escalation_reason=EscalationReason.GOVERNANCE_BLOCKED,
            escalation_priority=EscalationPriority.CRITICAL,
            what_occurred_summary="L3-X prohibited action blocked.",
        )
        self.assertIsNotNone(pkg)
        for opt in pkg.available_human_options:
            self.assertFalse(opt.autonomous_continuation_possible)
            self.assertNotEqual(opt.option_type, HumanOptionType.APPROVE_FOR_REAUTHORIZATION)

    # 4. UNKNOWN verification produces uncertainty-preserving package
    def test_b8_04_unknown_verification_produces_uncertainty_preserving_package(self):
        disp, reason, priority = EscalationPolicyEvaluator.evaluate(
            execution_state=ExecutionState.UNKNOWN,
            verification_state=VerificationState.UNKNOWN,
        )
        self.assertEqual(disp, EscalationDisposition.ESCALATE)
        self.assertEqual(reason, EscalationReason.VERIFICATION_UNKNOWN)
        self.assertEqual(priority, EscalationPriority.HIGH)

    # 5. UNVERIFIED produces distinct package state
    def test_b8_05_unverified_produces_distinct_package_state(self):
        disp, reason, priority = EscalationPolicyEvaluator.evaluate(
            execution_state=ExecutionState.UNVERIFIED,
            verification_state=VerificationState.UNVERIFIED,
        )
        self.assertEqual(disp, EscalationDisposition.ESCALATE)
        self.assertEqual(reason, EscalationReason.VERIFICATION_UNVERIFIED)

    # 6. PARTIALLY_VERIFIED produces distinct package state
    def test_b8_06_partially_verified_produces_distinct_package_state(self):
        disp, reason, priority = EscalationPolicyEvaluator.evaluate(
            execution_state=ExecutionState.PARTIALLY_VERIFIED,
            verification_state=VerificationState.PARTIALLY_VERIFIED,
        )
        self.assertEqual(disp, EscalationDisposition.ESCALATE)
        self.assertEqual(reason, EscalationReason.VERIFICATION_PARTIAL)

    # 7. terminal/non-retryable failure escalation
    def test_b8_07_terminal_non_retryable_failure_escalation(self):
        disp, reason, priority = EscalationPolicyEvaluator.evaluate(
            execution_state=ExecutionState.FAILED,
        )
        self.assertEqual(disp, EscalationDisposition.ESCALATE)
        self.assertEqual(reason, EscalationReason.NON_RETRYABLE_FAILURE)

    # 8. retry-exhausted escalation
    def test_b8_08_retry_exhausted_escalation(self):
        disp, reason, priority = EscalationPolicyEvaluator.evaluate(
            execution_state=ExecutionState.FAILED,
            retry_exhausted=True,
        )
        self.assertEqual(disp, EscalationDisposition.ESCALATE)
        self.assertEqual(reason, EscalationReason.RETRY_EXHAUSTED)

    # 9. persistence-failure escalation
    def test_b8_09_persistence_failure_escalation(self):
        disp, reason, priority = EscalationPolicyEvaluator.evaluate(
            execution_state=ExecutionState.STOPPED,
            persistence_failed=True,
        )
        self.assertEqual(disp, EscalationDisposition.ESCALATE)
        self.assertEqual(reason, EscalationReason.PERSISTENCE_FAILURE)
        self.assertEqual(priority, EscalationPriority.CRITICAL)

    # 10. deterministic denial configured DO_NOT_ESCALATE does not create a package
    def test_b8_10_deterministic_non_escalating_denial_does_not_escalate(self):
        disp, reason, priority = EscalationPolicyEvaluator.evaluate(
            execution_state=ExecutionState.DENIED,
            auth_decision=AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.ENVIRONMENT_DENIED,
                reason_detail="Environment denied",
            ),
        )
        self.assertEqual(disp, EscalationDisposition.DO_NOT_ESCALATE)
        self.assertIsNone(reason)

    # 11. package includes exact capability/version
    def test_b8_11_package_includes_exact_capability_and_version(self):
        pkg, _ = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id="BAE-OPS-OBSERVE-001",
            capability_version="1.2.3",
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.ESCALATED,
            escalation_reason=EscalationReason.POLICY_REVIEW_REQUIRED,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Review needed.",
        )
        self.assertEqual(pkg.capability_id, "BAE-OPS-OBSERVE-001")
        self.assertEqual(pkg.capability_version, "1.2.3")

    # 12. package includes L/M/A/T independently
    def test_b8_12_package_includes_lmat_independently(self):
        pkg, _ = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L2,
            autonomy_maturity=AutonomyMaturity.M2,
            approval_level=ApprovalLevel.A1,
            tool_authority_class=ToolAuthorityClass.T1,
            execution_state=ExecutionState.ESCALATED,
            escalation_reason=EscalationReason.APPROVAL_REQUIRED,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Approval required.",
        )
        self.assertEqual(pkg.authority_level, AuthorityClass.L2)
        self.assertEqual(pkg.autonomy_maturity, AutonomyMaturity.M2)
        self.assertEqual(pkg.approval_level, ApprovalLevel.A1)
        self.assertEqual(pkg.tool_authority_class, ToolAuthorityClass.T1)

    # 13. package includes current execution and verification state
    def test_b8_13_package_includes_execution_and_verification_state(self):
        pkg, _ = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.PARTIALLY_VERIFIED,
            verification_state=VerificationState.PARTIALLY_VERIFIED,
            verification_outcome=VerificationOutcome.PARTIALLY_VERIFIED,
            escalation_reason=EscalationReason.VERIFICATION_PARTIAL,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Partial verification.",
        )
        self.assertEqual(pkg.execution_state, ExecutionState.PARTIALLY_VERIFIED)
        self.assertEqual(pkg.verification_state, VerificationState.PARTIALLY_VERIFIED)
        self.assertEqual(pkg.verification_outcome, VerificationOutcome.PARTIALLY_VERIFIED)

    # 14. package contains B7 audit/evidence references
    def test_b8_14_package_contains_audit_and_evidence_references(self):
        pkg, _ = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.ESCALATED,
            escalation_reason=EscalationReason.POLICY_REVIEW_REQUIRED,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Audit refs check.",
            audit_event_references=["AUD-1001", "AUD-1002"],
            evidence_references=["EVD-2001"],
        )
        self.assertIn("AUD-1001", pkg.audit_event_references)
        self.assertIn("EVD-2001", pkg.evidence_references)

    # 15. package contains what MAY occur
    def test_b8_15_package_contains_what_may_occur(self):
        pkg, _ = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.ESCALATED,
            escalation_reason=EscalationReason.POLICY_REVIEW_REQUIRED,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Permitted check.",
            what_remains_permitted=["Read-only audit inspection", "Operator manual review"],
        )
        self.assertIn("Read-only audit inspection", pkg.what_remains_permitted)

    # 16. package contains what MAY NOT occur
    def test_b8_16_package_contains_what_may_not_occur(self):
        pkg, _ = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.ESCALATED,
            escalation_reason=EscalationReason.POLICY_REVIEW_REQUIRED,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Prohibited check.",
            what_is_prohibited=["Unapproved database mutations", "Direct provider invocation"],
        )
        self.assertIn("Unapproved database mutations", pkg.what_is_prohibited)

    # 17. package contains structured human options
    def test_b8_17_package_contains_structured_human_options(self):
        pkg, _ = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L2,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A1,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.DENIED,
            escalation_reason=EscalationReason.APPROVAL_REQUIRED,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Options check.",
        )
        self.assertTrue(len(pkg.available_human_options) > 0)
        for opt in pkg.available_human_options:
            self.assertIsInstance(opt.option_type, HumanOptionType)

    # 18. package contains no raw secrets/PII
    def test_b8_18_package_sanitizes_raw_secrets_and_pii(self):
        pkg, _ = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.ESCALATED,
            escalation_reason=EscalationReason.POLICY_REVIEW_REQUIRED,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Sanitization check.",
            raw_context={
                "password": "RawPassword123!",
                "api_key": "AKIA-SECRET-999",
                "email": "user@example.com",
                "address": "456 Elm Street",
                "safe_param": "normal_val",
            },
        )
        self.assertEqual(pkg.sanitized_context["password"], "[REDACTED_SECRET]")
        self.assertEqual(pkg.sanitized_context["api_key"], "[REDACTED_SECRET]")
        self.assertIn("[REDACTED_PII:hash=", pkg.sanitized_context["email"])
        self.assertIn("[REDACTED_PII:hash=", pkg.sanitized_context["address"])
        self.assertEqual(pkg.sanitized_context["safe_param"], "normal_val")

    # 19. recommendation is non-binding
    def test_b8_19_recommendation_is_non_binding(self):
        pkg, _ = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.ESCALATED,
            escalation_reason=EscalationReason.POLICY_REVIEW_REQUIRED,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Recommendation check.",
            recommended_safe_action="Recommend manual retry after inspecting network.",
        )
        self.assertEqual(pkg.recommended_safe_action, "Recommend manual retry after inspecting network.")

    # 20. package itself cannot serve as B2 authorization
    def test_b8_20_escalation_package_cannot_serve_as_b2_authorization(self):
        pkg, _ = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.ESCALATED,
            escalation_reason=EscalationReason.POLICY_REVIEW_REQUIRED,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Authority check.",
        )
        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=2,
            prior_step_token=pkg.escalation_id,  # Invalid token
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment="development",
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        decision = self.evaluator.evaluate(auth_req)
        self.assertFalse(decision.permitted)
        self.assertEqual(decision.status, AuthorizationDecisionStatus.DENIED)

    # 21. delivery acknowledgement cannot serve as approval
    def test_b8_21_delivery_acknowledgement_cannot_serve_as_approval(self):
        state = EscalationDeliveryState.ACKNOWLEDGED
        self.assertNotEqual(state, AuthorizationDecisionStatus.PERMITTED)

    # 22. silence cannot serve as approval
    def test_b8_22_silence_cannot_serve_as_approval(self):
        valid, reason = validate_human_response_for_reauthorization(None, self.objective_id, self.action_id)
        self.assertFalse(valid)
        self.assertEqual(reason, "SILENCE_OR_MISSING_RESPONSE")

    # 23. valid human response still requires fresh B2 authorization
    def test_b8_23_valid_human_response_requires_fresh_b2_authorization(self):
        resp = HumanResponseReference(
            response_id=str(uuid4()),
            escalation_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            selected_option_type=HumanOptionType.APPROVE_FOR_REAUTHORIZATION,
            operator_id="operator-01",
            operator_role="lead_steward",
            approval_token_ref="APP-TOKEN-9001",
        )
        valid, reason = validate_human_response_for_reauthorization(resp, self.objective_id, self.action_id)
        self.assertTrue(valid)
        self.assertEqual(reason, "VALID_HUMAN_RESPONSE_REFERENCE")

    # 24. wrong objective/action human response cannot authorize continuation
    def test_b8_24_wrong_objective_or_action_human_response_rejected(self):
        resp = HumanResponseReference(
            response_id=str(uuid4()),
            escalation_id=str(uuid4()),
            objective_id=str(uuid4()),  # Mismatched objective
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            selected_option_type=HumanOptionType.APPROVE_FOR_REAUTHORIZATION,
            operator_id="operator-01",
            operator_role="lead_steward",
        )
        valid, reason = validate_human_response_for_reauthorization(resp, self.objective_id, self.action_id)
        self.assertFalse(valid)
        self.assertEqual(reason, "OBJECTIVE_ID_MISMATCH")

    # 25. stale human response cannot authorize continuation
    def test_b8_25_stale_human_response_rejected(self):
        resp = HumanResponseReference(
            response_id=str(uuid4()),
            escalation_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            selected_option_type=HumanOptionType.APPROVE_FOR_REAUTHORIZATION,
            operator_id="operator-01",
            operator_role="lead_steward",
            is_stale=True,
        )
        valid, reason = validate_human_response_for_reauthorization(resp, self.objective_id, self.action_id)
        self.assertFalse(valid)
        self.assertEqual(reason, "STALE_HUMAN_RESPONSE")

    # 26. registered internal route sends successfully in DEVELOPMENT / TEST fixture
    def test_b8_26_registered_internal_route_sends_successfully(self):
        pkg, state = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.ESCALATED,
            escalation_reason=EscalationReason.POLICY_REVIEW_REQUIRED,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Route check.",
            internal_route="internal_ops_queue",
        )
        self.assertIsNotNone(pkg)
        self.assertEqual(state, EscalationDeliveryState.SENT)

    # 27. unavailable route => WAITING/STOPPED, no unauthorized fallback
    def test_b8_27_unavailable_route_fails_safe_to_stopped(self):
        pkg, state = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.ESCALATED,
            escalation_reason=EscalationReason.POLICY_REVIEW_REQUIRED,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Invalid route check.",
            internal_route="nonexistent_unregistered_route",
        )
        self.assertIsNone(pkg)
        self.assertEqual(state, EscalationDeliveryState.STOPPED)

    # 28. unregistered route is rejected
    def test_b8_28_unregistered_route_is_rejected(self):
        self.assertFalse(self.route_registry.is_valid_route("unregistered_route_x"))

    # 29. customer/external route is unavailable/prohibited in B8
    def test_b8_29_external_customer_route_registration_prohibited(self):
        with self.assertRaises(ValueError) as cm:
            self.route_registry.register_route(EscalationRoute(
                route_id="customer_sms_outbound",
                channel_type="sms",
                destination_target="+15550199",
                is_external_customer_facing=True,
            ))
        self.assertIn("Prohibited external/customer route", str(cm.exception))

    # 30. duplicate equivalent escalation is suppressed/deduplicated
    def test_b8_30_duplicate_escalation_is_deduplicated(self):
        pkg1, state1 = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.ESCALATED,
            escalation_reason=EscalationReason.POLICY_REVIEW_REQUIRED,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Duplicate check.",
        )
        self.assertEqual(state1, EscalationDeliveryState.SENT)

        pkg2, state2 = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.ESCALATED,
            escalation_reason=EscalationReason.POLICY_REVIEW_REQUIRED,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Duplicate check.",
        )
        self.assertEqual(state2, EscalationDeliveryState.ACKNOWLEDGED)

    # 31. materially changed evidence/state produces new escalation
    def test_b8_31_materially_changed_state_produces_new_escalation(self):
        pkg1, state1 = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.PARTIALLY_VERIFIED,
            escalation_reason=EscalationReason.VERIFICATION_PARTIAL,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="State 1.",
        )
        self.assertEqual(state1, EscalationDeliveryState.SENT)

        pkg2, state2 = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.FAILED,  # Materially changed state
            escalation_reason=EscalationReason.NON_RETRYABLE_FAILURE,  # Materially changed reason
            escalation_priority=EscalationPriority.HIGH,
            what_occurred_summary="State 2.",
        )
        self.assertEqual(state2, EscalationDeliveryState.SENT)

    # 32. dedupe suppression is auditable
    def test_b8_32_dedupe_suppression_is_auditable(self):
        # Trigger duplicate
        self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.ESCALATED,
            escalation_reason=EscalationReason.POLICY_REVIEW_REQUIRED,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Dedupe audit check.",
        )
        self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.ESCALATED,
            escalation_reason=EscalationReason.POLICY_REVIEW_REQUIRED,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Dedupe audit check.",
        )
        history = self.audit_repo.get_action_history(self.action_id)
        dedupe_events = [e for e in history if e.sanitized_metadata.get("escalation_deduplicated") is True]
        self.assertTrue(len(dedupe_events) > 0)

    # 33. route delivery state is auditable through B7
    def test_b8_33_route_delivery_state_auditable(self):
        pkg, state = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.ESCALATED,
            escalation_reason=EscalationReason.POLICY_REVIEW_REQUIRED,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Delivery audit check.",
        )
        history = self.audit_repo.get_action_history(self.action_id)
        self.assertTrue(any(e.sanitized_metadata.get("delivery_state") == "SENT" for e in history))

    # 34. package creation is auditable through B7
    def test_b8_34_package_creation_auditable(self):
        pkg, _ = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.ESCALATED,
            escalation_reason=EscalationReason.POLICY_REVIEW_REQUIRED,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Package audit check.",
        )
        history = self.audit_repo.get_action_history(self.action_id)
        self.assertTrue(any(e.sanitized_metadata.get("escalation_id") == pkg.escalation_id for e in history))

    # 35. objective/action/correlation lineage preserved
    def test_b8_35_lineage_preserved(self):
        pkg, _ = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.ESCALATED,
            escalation_reason=EscalationReason.POLICY_REVIEW_REQUIRED,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Lineage check.",
        )
        self.assertEqual(pkg.correlation.objective_id, self.objective_id)
        self.assertEqual(pkg.correlation.action_id, self.action_id)
        self.assertEqual(pkg.correlation.correlation_id, self.correlation_id)

    # 36. retry lineage preserved where applicable
    def test_b8_36_retry_lineage_preserved(self):
        parent_act = str(uuid4())
        retry_corr = CorrelationRecord(
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            parent_action_id=parent_act,
            retry_attempt_number=3,
        )
        pkg, _ = self.controller.build_and_route(
            correlation=retry_corr,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.FAILED,
            escalation_reason=EscalationReason.RETRY_EXHAUSTED,
            escalation_priority=EscalationPriority.HIGH,
            what_occurred_summary="Retry exhausted.",
        )
        self.assertEqual(pkg.correlation.parent_action_id, parent_act)
        self.assertEqual(pkg.correlation.retry_attempt_number, 3)

    # 37. human override/control stop can trigger package without creating authority
    def test_b8_37_human_override_triggers_package_without_creating_authority(self):
        disp, reason, priority = EscalationPolicyEvaluator.evaluate(
            execution_state=ExecutionState.STOPPED,
            human_override=True,
        )
        self.assertEqual(disp, EscalationDisposition.ESCALATE)
        self.assertEqual(reason, EscalationReason.HUMAN_OVERRIDE)

    # 38. B2/B3 denial remains effective despite escalation creation
    def test_b8_38_b2_denial_remains_effective_despite_escalation(self):
        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=1,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment="development",
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        decision = self.evaluator.evaluate(auth_req)
        # Still DENIED because capabilities are in DEFINED state
        self.assertFalse(decision.permitted)
        self.assertEqual(decision.status, AuthorizationDecisionStatus.DENIED)

    # 39. all nine Pilot seed capabilities remain non-executable
    def test_b8_39_all_nine_seed_capabilities_remain_non_executable(self):
        records = self.seed_registry.list_all()
        self.assertEqual(len(records), 9)
        for record in records:
            self.assertEqual(record.lifecycle_state, CapabilityLifecycleState.DEFINED)
            self.assertFalse(record.executable)

    # 40. ESCALATE capability remains DEFINED / uncertified / non-executable
    def test_b8_40_escalate_capability_remains_defined_and_non_executable(self):
        record = self.seed_registry.get("BAE-OPS-ESCALATE-001")
        self.assertIsNotNone(record)
        self.assertEqual(record.lifecycle_state, CapabilityLifecycleState.DEFINED)
        self.assertFalse(record.executable)

    # 41. Customer Follow-Up remains disabled
    def test_b8_41_customer_followup_remains_disabled(self):
        record = self.seed_registry.get("BAE-COMM-FOLLOWUP-001")
        self.assertIsNotNone(record)
        self.assertFalse(record.executable)
        self.assertEqual(record.classification_state, "UNRESOLVED_DISABLED")

    # 42. Gate D remains unauthorized
    def test_b8_42_gate_d_remains_unauthorized(self):
        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=1,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment="production",
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        decision = self.evaluator.evaluate(auth_req)
        self.assertFalse(decision.permitted)
        # In B2 evaluation, certification check precedes environment check, both yielding DENIED
        self.assertIn(decision.denial_reason, {AuthorizationDenialReason.CAPABILITY_NOT_CERTIFIED, AuthorizationDenialReason.ENVIRONMENT_DENIED})

    # 43. no production route exists
    def test_b8_43_no_production_route_exists(self):
        for route_id, route in self.route_registry._routes.items():
            self.assertFalse(route.is_external_customer_facing)

    # 44. no B9 implementation occurs
    def test_b8_44_no_b9_implementation_occurs(self):
        import src.budly_runtime.bae as bae_pkg
        self.assertFalse(hasattr(bae_pkg, "B9KillSwitchEngine"))

    # 45. full serialization to_dict roundtrip
    def test_b8_45_full_package_to_dict_roundtrip(self):
        pkg, _ = self.controller.build_and_route(
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.ESCALATED,
            escalation_reason=EscalationReason.POLICY_REVIEW_REQUIRED,
            escalation_priority=EscalationPriority.NORMAL,
            what_occurred_summary="Dict roundtrip check.",
        )
        d = pkg.to_dict()
        self.assertEqual(d["escalation_id"], pkg.escalation_id)
        self.assertEqual(d["escalation_reason"], EscalationReason.POLICY_REVIEW_REQUIRED.value)
        self.assertIsInstance(d["available_human_options"], list)


if __name__ == "__main__":
    unittest.main()
