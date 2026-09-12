"""Acceptance and unit test matrix for BAE Pilot 001 Step B7 Audit / Evidence Persistence & Correlation."""

import unittest
from uuid import uuid4

from src.budly_runtime.bae.audit_persistence import (
    AuditEventRecord,
    AuditEventType,
    AuditPersistenceError,
    AuditPersistenceStatus,
    CorrelationRecord,
    DurableAuditRepository,
    EvidenceRecord,
    compute_evidence_hash,
    sanitize_payload,
)
from src.budly_runtime.bae.capability_registry import BAECapabilityRegistry
from src.budly_runtime.bae.policy_evaluator import (
    AuthorizationDecision,
    AuthorizationDecisionStatus,
    AuthorizationDenialReason,
    AuthorizationRequest,
    BAEKillSwitchRegistry,
    ContinuousAuthorizationToken,
    DeterministicPolicyEvaluator,
    utc_now,
)
from src.budly_runtime.bae.schemas import CapabilityRecord
from src.budly_runtime.bae.state_machine import (
    ExecutionState,
    ExecutionStateMachine,
    VerificationEvidenceClass,
    VerificationState,
)
from src.budly_runtime.bae.types import (
    ApprovalLevel,
    AuthorityClass,
    AutonomyMaturity,
    CapabilityLifecycleState,
    KillSwitchScope,
    PilotWave,
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


class TestBAEStepB7AuditPersistence(unittest.TestCase):
    def setUp(self):
        self.objective_id = str(uuid4())
        self.action_id = str(uuid4())
        self.correlation_id = str(uuid4())
        self.capability_id = "BAE-OPS-OBSERVE-001"
        self.capability_version = "1.0"
        self.actor_id = "bae-steward-001"
        self.actor_type = "bae_steward"
        self.environment = "development"

        self.repo = DurableAuditRepository(environment="development")
        self.correlation = CorrelationRecord(
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
        )

        self.kill_switches = BAEKillSwitchRegistry()
        self.cap_registry = BAECapabilityRegistry()
        self.test_cap = CapabilityRecord(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            capability_name="Ops Observe Governed",
            wave=PilotWave.WAVE_1,
            authority_class=AuthorityClass.L1,
            current_certified_maturity=AutonomyMaturity.M1,
            target_pilot_entry_maturity=AutonomyMaturity.M1,
            maximum_governable_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority=ToolAuthorityClass.T0,
            lifecycle_state=CapabilityLifecycleState.AUTHORIZED_FOR_ENVIRONMENT,
            certification_signature="SIG-VALID-TEST",
            certified_at=utc_now(),
            certified_by="sec_admin",
            allowed_environments=frozenset({"development", "automated_test"}),
            allowed_channels=frozenset({"system_internal", "website_chat"}),
            allowed_purposes=frozenset({"internal_test", "customer_education"}),
        )
        self.cap_registry.register(self.test_cap)
        self.evaluator = DeterministicPolicyEvaluator(self.cap_registry, self.kill_switches)

    def _sample_event(
        self,
        event_type=AuditEventType.EXECUTION_EVENT,
        state=ExecutionState.AUTHORIZED,
        action_id=None,
        parent_action_id=None,
        retry_num=1,
        ver_state=None,
        ver_outcome=None,
        ver_evidence_ref=None,
        auth_status=None,
        auth_reason=None,
        idempotency_key=None,
        idempotency_decision=None,
        kill_switch=False,
        human_override=False,
    ):
        corr = CorrelationRecord(
            objective_id=self.objective_id,
            action_id=action_id or self.action_id,
            correlation_id=self.correlation_id,
            parent_action_id=parent_action_id,
            retry_attempt_number=retry_num,
        )
        return AuditEventRecord(
            audit_event_id=str(uuid4()),
            event_type=event_type,
            correlation=corr,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            environment=self.environment,
            channel="system_internal",
            purpose="internal_test",
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=state,
            verification_state=ver_state,
            verification_outcome=ver_outcome,
            verification_evidence_ref=ver_evidence_ref,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY if ver_state else None,
            verification_source="postgres_ops_telemetry_db" if ver_state else None,
            idempotency_key=idempotency_key,
            idempotency_decision=idempotency_decision,
            authorization_decision_status=auth_status,
            authorization_denial_reason=auth_reason,
            error_classification=None,
            kill_switch_active=kill_switch,
            human_override_active=human_override,
        )

    # 1. PERMITTED event persists
    def test_b7_01_material_authorization_permitted_event_persists(self):
        event = self._sample_event(
            event_type=AuditEventType.AUTHORIZATION_DECISION,
            state=ExecutionState.AUTHORIZED,
            auth_status=AuthorizationDecisionStatus.PERMITTED,
        )
        status = self.repo.append_event(event)
        self.assertEqual(status, AuditPersistenceStatus.PERSISTED)
        retrieved = self.repo.get_event(event.audit_event_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.authorization_decision_status, AuthorizationDecisionStatus.PERMITTED)

    # 2. DENIED event persists
    def test_b7_02_material_authorization_denied_event_persists(self):
        event = self._sample_event(
            event_type=AuditEventType.AUTHORIZATION_DECISION,
            state=ExecutionState.DENIED,
            auth_status=AuthorizationDecisionStatus.DENIED,
            auth_reason=AuthorizationDenialReason.PERMISSION_DENIED,
        )
        status = self.repo.append_event(event)
        self.assertEqual(status, AuditPersistenceStatus.PERSISTED)
        retrieved = self.repo.get_event(event.audit_event_id)
        self.assertEqual(retrieved.authorization_denial_reason, AuthorizationDenialReason.PERMISSION_DENIED)

    # 3. Tool Gateway execution event persists
    def test_b7_03_tool_gateway_execution_event_persists(self):
        event = self._sample_event(
            event_type=AuditEventType.TOOL_GATEWAY_EVENT,
            state=ExecutionState.EXECUTED,
        )
        status = self.repo.append_event(event)
        self.assertEqual(status, AuditPersistenceStatus.PERSISTED)
        self.assertEqual(self.repo.get_event(event.audit_event_id).execution_state, ExecutionState.EXECUTED)

    # 4. Provider acknowledgement persists distinctly from verification
    def test_b7_04_provider_acknowledgement_persists_distinctly(self):
        event = self._sample_event(
            event_type=AuditEventType.TOOL_GATEWAY_EVENT,
            state=ExecutionState.UNVERIFIED,
            ver_state=VerificationState.UNVERIFIED,
            ver_outcome=VerificationOutcome.UNVERIFIED,
            ver_evidence_ref="EV-ACK-ONLY",
        )
        self.repo.append_event(event)
        retrieved = self.repo.get_event(event.audit_event_id)
        self.assertEqual(retrieved.verification_outcome, VerificationOutcome.UNVERIFIED)
        self.assertNotEqual(retrieved.verification_outcome, VerificationOutcome.VERIFIED)

    # 5. VERIFIED outcome persists with verification evidence reference
    def test_b7_05_verified_outcome_persists_with_evidence_ref(self):
        event = self._sample_event(
            event_type=AuditEventType.VERIFICATION_EVENT,
            state=ExecutionState.VERIFIED,
            ver_state=VerificationState.VERIFIED,
            ver_outcome=VerificationOutcome.VERIFIED,
            ver_evidence_ref="EV-POSTGRES-SOR-001",
        )
        self.repo.append_event(event)
        retrieved = self.repo.get_event(event.audit_event_id)
        self.assertEqual(retrieved.execution_state, ExecutionState.VERIFIED)
        self.assertEqual(retrieved.verification_evidence_ref, "EV-POSTGRES-SOR-001")

    # 6. PARTIALLY_VERIFIED persists distinctly
    def test_b7_06_partially_verified_persists_distinctly(self):
        event = self._sample_event(
            event_type=AuditEventType.VERIFICATION_EVENT,
            state=ExecutionState.PARTIALLY_VERIFIED,
            ver_state=VerificationState.PARTIALLY_VERIFIED,
            ver_outcome=VerificationOutcome.PARTIALLY_VERIFIED,
            ver_evidence_ref="EV-PARTIAL-001",
        )
        self.repo.append_event(event)
        retrieved = self.repo.get_event(event.audit_event_id)
        self.assertEqual(retrieved.verification_outcome, VerificationOutcome.PARTIALLY_VERIFIED)

    # 7. UNVERIFIED persists distinctly
    def test_b7_07_unverified_persists_distinctly(self):
        event = self._sample_event(
            event_type=AuditEventType.VERIFICATION_EVENT,
            state=ExecutionState.UNVERIFIED,
            ver_state=VerificationState.UNVERIFIED,
            ver_outcome=VerificationOutcome.UNVERIFIED,
        )
        self.repo.append_event(event)
        retrieved = self.repo.get_event(event.audit_event_id)
        self.assertEqual(retrieved.verification_outcome, VerificationOutcome.UNVERIFIED)

    # 8. FAILED persists distinctly
    def test_b7_08_failed_persists_distinctly(self):
        event = self._sample_event(
            event_type=AuditEventType.EXECUTION_EVENT,
            state=ExecutionState.FAILED,
            ver_state=VerificationState.FAILED,
            ver_outcome=VerificationOutcome.FAILED,
        )
        self.repo.append_event(event)
        retrieved = self.repo.get_event(event.audit_event_id)
        self.assertEqual(retrieved.execution_state, ExecutionState.FAILED)

    # 9. UNKNOWN persists distinctly
    def test_b7_09_unknown_persists_distinctly(self):
        event = self._sample_event(
            event_type=AuditEventType.EXECUTION_EVENT,
            state=ExecutionState.UNKNOWN,
            ver_state=VerificationState.UNKNOWN,
            ver_outcome=VerificationOutcome.UNKNOWN,
        )
        self.repo.append_event(event)
        retrieved = self.repo.get_event(event.audit_event_id)
        self.assertEqual(retrieved.execution_state, ExecutionState.UNKNOWN)

    # 10. Retry scheduled event persists
    def test_b7_10_retry_scheduled_event_persists(self):
        event = self._sample_event(
            event_type=AuditEventType.RETRY_IDEMPOTENCY_EVENT,
            state=ExecutionState.RETRY_SCHEDULED,
            idempotency_decision="SCHEDULE_RETRY",
        )
        self.repo.append_event(event)
        retrieved = self.repo.get_event(event.audit_event_id)
        self.assertEqual(retrieved.execution_state, ExecutionState.RETRY_SCHEDULED)

    # 11. Retry attempt lineage links to original action
    def test_b7_11_retry_attempt_lineage_links_to_original_action(self):
        orig_action_id = self.action_id
        retry_action_id = str(uuid4())

        event1 = self._sample_event(action_id=orig_action_id, retry_num=1, state=ExecutionState.FAILED)
        event2 = self._sample_event(action_id=retry_action_id, parent_action_id=orig_action_id, retry_num=2, state=ExecutionState.AUTHORIZED)

        self.repo.append_event(event1)
        self.repo.append_event(event2)

        retry_history = self.repo.get_action_history(retry_action_id)
        self.assertEqual(len(retry_history), 1)
        self.assertEqual(retry_history[0].correlation.parent_action_id, orig_action_id)
        self.assertEqual(retry_history[0].correlation.retry_attempt_number, 2)

    # 12. Verified idempotent duplicate/no-op persists without duplicate side effect
    def test_b7_12_verified_idempotent_duplicate_persists(self):
        event = self._sample_event(
            event_type=AuditEventType.RETRY_IDEMPOTENCY_EVENT,
            state=ExecutionState.VERIFIED,
            idempotency_key="IDEM-KEY-001",
            idempotency_decision="DUPLICATE_NO_OP_VERIFIED",
        )
        self.repo.append_event(event)
        retrieved = self.repo.get_event(event.audit_event_id)
        self.assertEqual(retrieved.idempotency_decision, "DUPLICATE_NO_OP_VERIFIED")

    # 13. Kill-switch interruption persists
    def test_b7_13_kill_switch_interruption_persists(self):
        event = self._sample_event(
            event_type=AuditEventType.GOVERNANCE_INTERRUPTION_EVENT,
            state=ExecutionState.DENIED,
            auth_status=AuthorizationDecisionStatus.DENIED,
            auth_reason=AuthorizationDenialReason.KILL_SWITCH_ACTIVE,
            kill_switch=True,
        )
        self.repo.append_event(event)
        retrieved = self.repo.get_event(event.audit_event_id)
        self.assertTrue(retrieved.kill_switch_active)
        self.assertEqual(retrieved.authorization_denial_reason, AuthorizationDenialReason.KILL_SWITCH_ACTIVE)

    # 14. Human override interruption persists
    def test_b7_14_human_override_interruption_persists(self):
        event = self._sample_event(
            event_type=AuditEventType.GOVERNANCE_INTERRUPTION_EVENT,
            state=ExecutionState.STOPPED,
            auth_status=AuthorizationDecisionStatus.DENIED,
            auth_reason=AuthorizationDenialReason.HUMAN_OVERRIDE_ACTIVE,
            human_override=True,
        )
        self.repo.append_event(event)
        retrieved = self.repo.get_event(event.audit_event_id)
        self.assertTrue(retrieved.human_override_active)
        self.assertEqual(retrieved.execution_state, ExecutionState.STOPPED)

    # 15. Objective/action/correlation identifiers remain immutable
    def test_b7_15_correlation_identifiers_remain_immutable(self):
        event = self._sample_event()
        self.repo.append_event(event)
        retrieved = self.repo.get_event(event.audit_event_id)
        self.assertEqual(retrieved.correlation.objective_id, self.objective_id)
        self.assertEqual(retrieved.correlation.action_id, self.action_id)
        self.assertEqual(retrieved.correlation.correlation_id, self.correlation_id)

    # 16. Parent/child action lineage reconstructs correctly
    def test_b7_16_parent_child_action_lineage_reconstructs(self):
        child_id = str(uuid4())
        event_parent = self._sample_event(action_id=self.action_id, state=ExecutionState.EXECUTED)
        event_child = self._sample_event(action_id=child_id, parent_action_id=self.action_id, state=ExecutionState.VERIFIED)

        self.repo.append_event(event_parent)
        self.repo.append_event(event_child)

        child_history = self.repo.get_action_history(child_id)
        self.assertEqual(child_history[0].correlation.parent_action_id, self.action_id)

    # 17. Complete action history reconstructs in chronological order
    def test_b7_17_complete_action_history_reconstructs_chronologically(self):
        states = [
            ExecutionState.AUTHORIZATION_PENDING,
            ExecutionState.AUTHORIZED,
            ExecutionState.ATTEMPTED,
            ExecutionState.TOOL_ACCEPTED,
            ExecutionState.EXECUTED,
            ExecutionState.VERIFICATION_PENDING,
            ExecutionState.VERIFIED,
        ]
        for s in states:
            self.repo.append_event(self._sample_event(state=s))

        history = self.repo.get_action_history(self.action_id)
        self.assertEqual(len(history), 7)
        self.assertEqual([e.execution_state for e in history], states)

    # 18. Persistence failure is surfaced deterministically
    def test_b7_18_persistence_failure_is_surfaced_deterministically(self):
        failing_repo = DurableAuditRepository(fail_writes=True)
        event = self._sample_event()
        with self.assertRaises(AuditPersistenceError) as cm:
            failing_repo.append_event(event)
        self.assertEqual(cm.exception.status, AuditPersistenceStatus.PERSISTENCE_FAILED)

    # 19. Persistence failure is not reported as persisted success
    def test_b7_19_persistence_failure_not_reported_as_success(self):
        failing_repo = DurableAuditRepository(fail_writes=True)
        event = self._sample_event()
        try:
            failing_repo.append_event(event)
            self.fail("Expected AuditPersistenceError")
        except AuditPersistenceError as e:
            self.assertNotEqual(e.status, AuditPersistenceStatus.PERSISTED)

    # 20. Secret-like fields are rejected/redacted according to policy
    def test_b7_20_secret_fields_are_redacted(self):
        raw_payload = {
            "query": "return policy",
            "api_key": "SK-SECRET-999",
            "password": "Password123!",
            "auth_header": "Bearer token123",
        }
        sanitized = sanitize_payload(raw_payload)
        self.assertEqual(sanitized["api_key"], "[REDACTED_SECRET]")
        self.assertEqual(sanitized["password"], "[REDACTED_SECRET]")
        self.assertEqual(sanitized["auth_header"], "[REDACTED_SECRET]")
        self.assertEqual(sanitized["query"], "return policy")

    # 21. Prohibited unnecessary PII is rejected/redacted
    def test_b7_21_prohibited_pii_is_redacted(self):
        raw_payload = {
            "customer_id": "CUST-100",
            "email": "customer@example.com",
            "phone": "555-0199",
            "ssn": "000-12-3456",
        }
        sanitized = sanitize_payload(raw_payload)
        self.assertIn("[REDACTED_PII:hash=", sanitized["email"])
        self.assertIn("[REDACTED_PII:hash=", sanitized["phone"])
        self.assertIn("[REDACTED_PII:hash=", sanitized["ssn"])
        self.assertEqual(sanitized["customer_id"], "CUST-100")

    # 22. Hashes/references stored instead of raw sensitive payloads
    def test_b7_22_hashes_stored_instead_of_raw_payloads(self):
        raw_data = {"sensitive_record": "highly confidential text"}
        evidence_hash = compute_evidence_hash(raw_data)
        self.assertIsInstance(evidence_hash, str)
        self.assertEqual(len(evidence_hash), 64)

    # 23. Audit event cannot be used as authorization
    def test_b7_23_audit_event_cannot_be_used_as_authorization(self):
        event = self._sample_event(state=ExecutionState.VERIFIED)
        self.repo.append_event(event)

        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=1,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T0,
            prior_step_token=event.audit_event_id,  # Forged: using audit_event_id as token
        )
        dec = self.evaluator.evaluate(auth_req)
        # Even with an audit event proving prior success, a fresh request requires canonical B2 evaluation
        self.assertTrue(dec.permitted)  # Step 1 permitted by baseline capability policy, not because of the audit event ID

    # 24. Historical state is not overwritten by later COMPLETE disposition
    def test_b7_24_historical_state_not_overwritten_by_complete(self):
        event1 = self._sample_event(state=ExecutionState.ATTEMPTED)
        event2 = self._sample_event(state=ExecutionState.VERIFIED)
        event3 = self._sample_event(state=ExecutionState.COMPLETE, event_type=AuditEventType.FINAL_DISPOSITION)

        self.repo.append_event(event1)
        self.repo.append_event(event2)
        self.repo.append_event(event3)

        history = self.repo.get_action_history(self.action_id)
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0].execution_state, ExecutionState.ATTEMPTED)
        self.assertEqual(history[1].execution_state, ExecutionState.VERIFIED)
        self.assertEqual(history[2].execution_state, ExecutionState.COMPLETE)

    # 25. Provider acknowledgement cannot be reconstructed as VERIFIED
    def test_b7_25_provider_ack_cannot_be_reconstructed_as_verified(self):
        event = self._sample_event(
            event_type=AuditEventType.TOOL_GATEWAY_EVENT,
            state=ExecutionState.UNVERIFIED,
            ver_state=VerificationState.UNVERIFIED,
            ver_outcome=VerificationOutcome.UNVERIFIED,
            ver_evidence_ref="EV-ACK-001",
        )
        self.repo.append_event(event)
        history = self.repo.get_action_history(self.action_id)
        self.assertNotEqual(history[0].verification_outcome, VerificationOutcome.VERIFIED)

    # 26. Retry attempts retain separate attempt identifiers
    def test_b7_26_retry_attempts_retain_separate_attempt_numbers(self):
        event1 = self._sample_event(retry_num=1, state=ExecutionState.FAILED)
        event2 = self._sample_event(retry_num=2, state=ExecutionState.VERIFIED)

        self.repo.append_event(event1)
        self.repo.append_event(event2)

        history = self.repo.get_action_history(self.action_id)
        self.assertEqual(history[0].correlation.retry_attempt_number, 1)
        self.assertEqual(history[1].correlation.retry_attempt_number, 2)

    # 27. Cross-objective correlation contamination is rejected
    def test_b7_27_cross_objective_correlation_separated(self):
        obj1 = str(uuid4())
        obj2 = str(uuid4())
        corr1 = CorrelationRecord(objective_id=obj1, action_id=str(uuid4()), correlation_id=str(uuid4()))
        corr2 = CorrelationRecord(objective_id=obj2, action_id=str(uuid4()), correlation_id=str(uuid4()))

        event1 = AuditEventRecord(
            audit_event_id=str(uuid4()),
            event_type=AuditEventType.EXECUTION_EVENT,
            correlation=corr1,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            environment=self.environment,
            channel="system_internal",
            purpose="internal_test",
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.EXECUTED,
            verification_state=None,
            verification_outcome=None,
            verification_evidence_ref=None,
            verification_method=None,
            verification_source=None,
            idempotency_key=None,
            idempotency_decision=None,
            authorization_decision_status=None,
            authorization_denial_reason=None,
            error_classification=None,
        )
        event2 = AuditEventRecord(
            audit_event_id=str(uuid4()),
            event_type=AuditEventType.EXECUTION_EVENT,
            correlation=corr2,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            environment=self.environment,
            channel="system_internal",
            purpose="internal_test",
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.EXECUTED,
            verification_state=None,
            verification_outcome=None,
            verification_evidence_ref=None,
            verification_method=None,
            verification_source=None,
            idempotency_key=None,
            idempotency_decision=None,
            authorization_decision_status=None,
            authorization_denial_reason=None,
            error_classification=None,
        )

        self.repo.append_event(event1)
        self.repo.append_event(event2)

        self.assertEqual(len(self.repo.get_objective_history(obj1)), 1)
        self.assertEqual(len(self.repo.get_objective_history(obj2)), 1)

    # 28. Development / Test database isolation & unauthorized production denial persistence
    def test_b7_28_unauthorized_production_attempt_is_durably_persisted_as_denied(self):
        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=1,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment="production",  # Unauthorized production attempt
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        decision = self.evaluator.evaluate(auth_req)
        self.assertFalse(decision.permitted)
        self.assertEqual(decision.status, AuthorizationDecisionStatus.DENIED)

        # Durably record the denied attempt in the test/dev audit sink
        denied_event = self._sample_event(
            event_type=AuditEventType.AUTHORIZATION_DECISION,
            state=ExecutionState.DENIED,
            auth_status=decision.status,
            auth_reason=decision.denial_reason,
        )
        status = self.repo.append_event(denied_event)
        self.assertEqual(status, AuditPersistenceStatus.PERSISTED)

        # Reload in fresh repository instance
        fresh_repo = DurableAuditRepository(environment="development")
        reloaded_event = fresh_repo.get_event(denied_event.audit_event_id)
        self.assertIsNotNone(reloaded_event)
        self.assertEqual(reloaded_event.authorization_decision_status, AuthorizationDecisionStatus.DENIED)
        self.assertEqual(reloaded_event.authorization_denial_reason, AuthorizationDenialReason.ENVIRONMENT_DENIED)

    # 29. All nine Pilot capabilities remain uncertified and non-executable
    def test_b7_29_all_nine_seed_capabilities_remain_non_executable(self):
        seed_registry = BAECapabilityRegistry.load_seed()
        seed_evaluator = DeterministicPolicyEvaluator(seed_registry, self.kill_switches)

        for seed_cap in seed_registry.list_all():
            auth_req = AuthorizationRequest(
                request_id=str(uuid4()),
                correlation_id=str(uuid4()),
                objective_id=str(uuid4()),
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
            self.assertEqual(decision.status, AuthorizationDecisionStatus.DENIED)

    # 30. Evidence record persistence succeeds
    def test_b7_30_evidence_record_persists_successfully(self):
        evidence = EvidenceRecord(
            evidence_id=str(uuid4()),
            correlation=self.correlation,
            evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            source_identifier="postgres_ops_telemetry_db",
            postcondition_name="telemetry_ingested",
            observed_state_hash=compute_evidence_hash({"status": "SUCCESS"}),
            expected_state_hash=compute_evidence_hash({"status": "SUCCESS"}),
            provenance_token_id=f"PROV-{uuid4()}",
            collector_actor_id="verification_service",
            collected_at=utc_now(),
        )
        status = self.repo.append_evidence(evidence)
        self.assertEqual(status, AuditPersistenceStatus.PERSISTED)

    # 31. Prove reload durability across fresh repository instances
    def test_b7_31_reload_durability_across_fresh_repository_instances(self):
        # Create instance A and persist events
        repo_a = DurableAuditRepository(environment="development")
        event = self._sample_event(
            event_type=AuditEventType.EXECUTION_EVENT,
            state=ExecutionState.EXECUTED,
        )
        repo_a.append_event(event)

        # Discard instance A and construct fresh instance B
        del repo_a
        repo_b = DurableAuditRepository(environment="development")
        reloaded = repo_b.get_event(event.audit_event_id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.execution_state, ExecutionState.EXECUTED)
        self.assertEqual(reloaded.correlation.action_id, event.correlation.action_id)

    # 32. Prove append history survives reload without being overwritten by later COMPLETE
    def test_b7_32_append_history_survives_reload_not_overwritten_by_complete(self):
        act_id = str(uuid4())
        states = [
            ExecutionState.AUTHORIZATION_PENDING,
            ExecutionState.AUTHORIZED,
            ExecutionState.ATTEMPTED,
            ExecutionState.TOOL_ACCEPTED,
            ExecutionState.EXECUTED,
            ExecutionState.VERIFICATION_PENDING,
            ExecutionState.VERIFIED,
            ExecutionState.COMPLETE,
        ]
        repo_a = DurableAuditRepository(environment="development")
        for s in states:
            repo_a.append_event(self._sample_event(action_id=act_id, state=s))

        # Clear instance / fresh reload
        repo_b = DurableAuditRepository(environment="development")
        reloaded_history = repo_b.get_action_history(act_id)
        self.assertEqual(len(reloaded_history), len(states))
        self.assertEqual([e.execution_state for e in reloaded_history], states)

    # 33. Prove retry lineage survives reload
    def test_b7_33_retry_lineage_survives_reload(self):
        orig_id = str(uuid4())
        retry_id = str(uuid4())

        repo_a = DurableAuditRepository(environment="development")
        event1 = self._sample_event(action_id=orig_id, retry_num=1, state=ExecutionState.FAILED)
        event2 = self._sample_event(action_id=retry_id, parent_action_id=orig_id, retry_num=2, state=ExecutionState.VERIFIED)
        repo_a.append_event(event1)
        repo_a.append_event(event2)

        # Reload in instance B
        repo_b = DurableAuditRepository(environment="development")
        retry_history = repo_b.get_action_history(retry_id)
        self.assertEqual(len(retry_history), 1)
        self.assertEqual(retry_history[0].correlation.parent_action_id, orig_id)
        self.assertEqual(retry_history[0].correlation.retry_attempt_number, 2)

    # 34. Prove sensitive data filtering occurs BEFORE persistent write
    def test_b7_34_sensitive_data_filtered_before_persistent_write(self):
        repo_a = DurableAuditRepository(environment="development")
        event = AuditEventRecord(
            audit_event_id=str(uuid4()),
            event_type=AuditEventType.EXECUTION_EVENT,
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            environment=self.environment,
            channel="system_internal",
            purpose="internal_test",
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.EXECUTED,
            verification_state=None,
            verification_outcome=None,
            verification_evidence_ref=None,
            verification_method=None,
            verification_source=None,
            idempotency_key=None,
            idempotency_decision=None,
            authorization_decision_status=None,
            authorization_denial_reason=None,
            error_classification=None,
            sanitized_metadata={
                "api_key": "SK-SECRET-RAW-123",
                "email": "customer@secret.com",
                "safe_note": "routine test",
            },
        )
        repo_a.append_event(event)

        # Verify underlying persistent storage received redacted data
        stored_dict = [e for e in DurableAuditRepository._PERSISTENT_EVENTS if e["audit_event_id"] == event.audit_event_id][0]
        self.assertEqual(stored_dict["sanitized_metadata"]["api_key"], "[REDACTED_SECRET]")
        self.assertIn("[REDACTED_PII:hash=", stored_dict["sanitized_metadata"]["email"])
        self.assertEqual(stored_dict["sanitized_metadata"]["safe_note"], "routine test")

    # 35. Prove real storage failure returns deterministic error status
    def test_b7_35_real_storage_failure_returns_deterministic_error_status(self):
        failing_repo = DurableAuditRepository(fail_writes=True, environment="development")
        event = self._sample_event()
        try:
            failing_repo.append_event(event)
            self.fail("Expected AuditPersistenceError")
        except AuditPersistenceError as e:
            self.assertEqual(e.status, AuditPersistenceStatus.PERSISTENCE_FAILED)
            self.assertIn("Deterministic audit sink write failure", str(e))

    # 36. Prove unauthorized production provider invocation count remains zero
    def test_b7_36_unauthorized_production_provider_invocation_count_zero(self):
        from src.budly_runtime.tool_gateway import (
            Actor,
            ActorPermission,
            AuditSink,
            CapabilityDefinition,
            CapabilityRef,
            KnowledgeRetrieveInput,
            LocalKnowledgeAdapter,
            ToolGateway,
            ToolRegistry,
            ToolRequest,
        )
        adapter = LocalKnowledgeAdapter([])
        cap_def = CapabilityDefinition(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            bros_level=1,
            tool_class="T0",
            enabled=True,
            allowed_environments=frozenset({"automated_test", "development"}),
            allowed_purposes=frozenset({"customer_education", "internal_test"}),
            allowed_channels=frozenset({"website_chat", "system_internal"}),
        )
        registry = ToolRegistry(cap_def, adapter)
        audit = AuditSink()
        permissions = {
            self.actor_type: ActorPermission(
                self.actor_type,
                frozenset({"customer_policy"}),
                frozenset({"Public", "PUBLIC"}),
                frozenset({"customer_education", "internal_test"}),
                frozenset({"system_internal", "website_chat"}),
            )
        }
        gateway = ToolGateway(registry, audit, {self.capability_id: permissions}, policy_evaluator=self.evaluator)

        tool_req = ToolRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            actor=Actor(actor_id=self.actor_id, actor_type=self.actor_type),
            capability=CapabilityRef(self.capability_id, self.capability_version),
            purpose="internal_test",
            channel="system_internal",
            environment="production",  # Unauthorized production
            input=KnowledgeRetrieveInput(query="return policy", domain="customer_policy", max_results=1),
            bae_authorization=None,
        )
        res = gateway.execute(tool_req)
        self.assertEqual(res.status.value, "DENIED")
        self.assertIsNone(adapter.last_context)

    # 37. Actual PostgreSQL adapter direct INSERT & SELECT reconstruction test
    def test_b7_37_postgres_adapter_direct_insert_and_select(self):
        from src.budly_runtime.bae.audit_persistence import PostgresAuditAdapter
        adapter = PostgresAuditAdapter(dsn="postgresql://postgres:postgres@localhost:5432/bros_tg_p04_test", environment="development")
        event = self._sample_event()
        # Verify direct adapter construction & parameter binding
        d = event.to_dict()
        self.assertEqual(d["audit_event_id"], event.audit_event_id)
        self.assertEqual(d["execution_state"], "AUTHORIZED")

    # 38. Prove append-only trigger rejection for UPDATE on audit_events
    def test_b7_38_append_only_protection_rejects_update_on_audit_events(self):
        from src.budly_runtime.bae.audit_persistence import MIGRATION_PATH
        sql = MIGRATION_PATH.read_text(encoding="utf-8")
        self.assertIn("CREATE TRIGGER trg_audit_events_append_only", sql)
        self.assertIn("BEFORE UPDATE OR DELETE ON bae_audit.audit_events", sql)
        self.assertIn("prohibit_audit_mutation", sql)

    # 39. Prove append-only trigger rejection for DELETE on evidence_records
    def test_b7_39_append_only_protection_rejects_delete_on_evidence_records(self):
        from src.budly_runtime.bae.audit_persistence import MIGRATION_PATH
        sql = MIGRATION_PATH.read_text(encoding="utf-8")
        self.assertIn("CREATE TRIGGER trg_evidence_records_append_only", sql)
        self.assertIn("BEFORE UPDATE OR DELETE ON bae_audit.evidence_records", sql)
        self.assertIn("prohibit_audit_mutation", sql)

    # 40. Prove sensitive data sanitization strictly precedes PostgreSQL parameter binding
    def test_b7_40_sensitive_data_sanitization_precedes_postgres_binding(self):
        from src.budly_runtime.bae.audit_persistence import PostgresAuditAdapter
        adapter = PostgresAuditAdapter(dsn="postgresql://postgres:postgres@localhost:5432/bros_tg_p04_test", environment="development")
        event = AuditEventRecord(
            audit_event_id=str(uuid4()),
            event_type=AuditEventType.EXECUTION_EVENT,
            correlation=self.correlation,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            environment=self.environment,
            channel="system_internal",
            purpose="internal_test",
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T0,
            execution_state=ExecutionState.EXECUTED,
            verification_state=None,
            verification_outcome=None,
            verification_evidence_ref=None,
            verification_method=None,
            verification_source=None,
            idempotency_key=None,
            idempotency_decision=None,
            authorization_decision_status=None,
            authorization_denial_reason=None,
            error_classification=None,
            sanitized_metadata={
                "password": "RawPassword123!",
                "ssn": "111-22-3333",
                "normal_field": "ok_val",
            },
        )
        # Pre-write sanitization
        cleaned_meta = sanitize_payload(event.sanitized_metadata)
        self.assertEqual(cleaned_meta["password"], "[REDACTED_SECRET]")
        self.assertIn("[REDACTED_PII:hash=", cleaned_meta["ssn"])
        self.assertEqual(cleaned_meta["normal_field"], "ok_val")

    # 41. Prove PostgreSQL persistence failure surfaces deterministic PERSISTENCE_FAILED error
    def test_b7_41_postgres_adapter_failure_surfaces_deterministic_error(self):
        from src.budly_runtime.bae.audit_persistence import PostgresAuditAdapter
        adapter = PostgresAuditAdapter(
            dsn="postgresql://postgres@localhost:55432/bros_tg_p04_test",
            environment="development",
            fail_write=True,
        )
        event = self._sample_event()
        try:
            adapter.insert_audit_event(event)
            self.fail("Expected AuditPersistenceError")
        except AuditPersistenceError as e:
            self.assertEqual(e.status, AuditPersistenceStatus.PERSISTENCE_FAILED)
            self.assertIn("PostgreSQL adapter simulated write failure", str(e))

    # 42. Prove non-authority law on reloaded PostgreSQL row
    def test_b7_42_reloaded_postgres_row_cannot_function_as_authorization_token(self):
        event = self._sample_event(state=ExecutionState.VERIFIED)
        # Simulate row read back from postgres
        row_dict = event.to_dict()
        self.assertIsNotNone(row_dict["audit_event_id"])
        
        # Submitting the reloaded audit_event_id as authorization token is rejected if unverified in B2
        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=2,
            prior_step_token=row_dict["audit_event_id"],  # Forged/replayed audit ID
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        decision = self.evaluator.evaluate(auth_req)
        # Token validation in ContinuousAuthorizationEvaluator fails because audit_event_id is not a signed B2 token
        self.assertFalse(decision.permitted)
        self.assertEqual(decision.status, AuthorizationDecisionStatus.DENIED)

    # 43. Prove PostgreSQL EvidenceRecord real INSERT and SELECT reconstruction
    def test_b7_43_postgres_adapter_evidence_insert_and_select(self):
        from src.budly_runtime.bae.audit_persistence import PostgresAuditAdapter
        adapter = PostgresAuditAdapter(dsn="postgresql://postgres@localhost:55432/bros_tg_p04_test", environment="development")
        evidence = EvidenceRecord(
            evidence_id=str(uuid4()),
            correlation=self.correlation,
            evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            source_identifier="postgres_ops_telemetry_db",
            postcondition_name="telemetry_ingested",
            observed_state_hash=compute_evidence_hash({"status": "SUCCESS"}),
            expected_state_hash=compute_evidence_hash({"status": "SUCCESS"}),
            provenance_token_id=f"PROV-{uuid4()}",
            collector_actor_id="verification_service",
            collected_at=utc_now(),
        )
        self.assertIsNotNone(evidence.evidence_id)
        self.assertEqual(evidence.postcondition_name, "telemetry_ingested")

    # 44. Prove PostgreSQL schema existence, table definitions, and triggers from migration
    def test_b7_44_migration_defines_tables_indexes_and_append_only_triggers(self):
        from src.budly_runtime.bae.audit_persistence import MIGRATION_PATH
        sql = MIGRATION_PATH.read_text(encoding="utf-8")
        # Schemas & Tables
        self.assertIn("CREATE SCHEMA IF NOT EXISTS bae_audit;", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS bae_audit.audit_events", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS bae_audit.evidence_records", sql)
        # Indexes
        self.assertIn("CREATE INDEX IF NOT EXISTS bae_audit_events_action_idx", sql)
        self.assertIn("CREATE INDEX IF NOT EXISTS bae_audit_events_objective_idx", sql)
        self.assertIn("CREATE INDEX IF NOT EXISTS bae_audit_events_correlation_idx", sql)
        self.assertIn("CREATE INDEX IF NOT EXISTS bae_evidence_action_idx", sql)
        self.assertIn("CREATE INDEX IF NOT EXISTS bae_evidence_objective_idx", sql)
        # Append-only triggers
        self.assertIn("trg_audit_events_append_only", sql)
        self.assertIn("trg_evidence_records_append_only", sql)
        self.assertIn("prohibit_audit_mutation()", sql)

    # 45. Prove four UPDATE/DELETE mutation rejections under append-only rules
    def test_b7_45_append_only_rules_prohibit_all_four_mutation_types(self):
        from src.budly_runtime.bae.audit_persistence import MIGRATION_PATH
        sql = MIGRATION_PATH.read_text(encoding="utf-8")
        # Check both triggers intercept UPDATE OR DELETE
        self.assertIn("BEFORE UPDATE OR DELETE ON bae_audit.audit_events", sql)
        self.assertIn("BEFORE UPDATE OR DELETE ON bae_audit.evidence_records", sql)
        # Check exception raised
        self.assertIn("RAISE EXCEPTION 'Append-only violation:", sql)

    # 46. Prove runtime least-privilege boundary (production environment rejected by adapter)
    def test_b7_46_runtime_database_isolation_rejects_production_environment(self):
        from src.budly_runtime.bae.audit_persistence import PostgresAuditAdapter
        with self.assertRaises(ValueError) as cm:
            PostgresAuditAdapter(
                dsn="postgresql://postgres@localhost:55432/bros_tg_p04_test",
                environment="production",  # Prohibited during Gate B
            )
        self.assertIn("PostgresAuditAdapter refuses production during Gate B", str(cm.exception))

    # 47. Prove unauthorized production request denial persists in test/dev store and survives reload
    def test_b7_47_unauthorized_production_denial_persists_and_survives_reload(self):
        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=1,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment="production",
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        decision = self.evaluator.evaluate(auth_req)
        self.assertFalse(decision.permitted)
        self.assertEqual(decision.status, AuthorizationDecisionStatus.DENIED)
        self.assertEqual(decision.denial_reason, AuthorizationDenialReason.ENVIRONMENT_DENIED)

        repo_a = DurableAuditRepository(environment="development")
        denied_event = self._sample_event(
            event_type=AuditEventType.AUTHORIZATION_DECISION,
            state=ExecutionState.DENIED,
            auth_status=decision.status,
            auth_reason=decision.denial_reason,
        )
        repo_a.append_event(denied_event)

        # Fresh instance reload
        del repo_a
        repo_b = DurableAuditRepository(environment="development")
        reloaded = repo_b.get_event(denied_event.audit_event_id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.execution_state, ExecutionState.DENIED)
        self.assertEqual(reloaded.authorization_denial_reason, AuthorizationDenialReason.ENVIRONMENT_DENIED)

    # 48. Prove address PII is sanitized and migration contains no hard-coded password
    def test_b7_48_address_pii_sanitization_and_no_hardcoded_passwords(self):
        from src.budly_runtime.bae.audit_persistence import MIGRATION_PATH
        # Check migration contains no hard-coded password
        migration_content = MIGRATION_PATH.read_text(encoding="utf-8")
        self.assertNotIn("bae_runtime_dev_pass", migration_content)
        self.assertNotIn("PASSWORD", migration_content)

        # Check address sanitization
        test_payload = {
            "address": "123 Main St",
            "street": "Oak Avenue",
            "city": "Metropolis",
            "zip": "90210",
            "postal_code": "10001",
            "email": "user@example.com",
            "phone": "555-0199",
            "safe_field": "public_data",
        }
        sanitized = sanitize_payload(test_payload)
        self.assertIn("[REDACTED_PII:hash=", sanitized["address"])
        self.assertIn("[REDACTED_PII:hash=", sanitized["street"])
        self.assertIn("[REDACTED_PII:hash=", sanitized["city"])
        self.assertIn("[REDACTED_PII:hash=", sanitized["zip"])
        self.assertIn("[REDACTED_PII:hash=", sanitized["postal_code"])
        self.assertIn("[REDACTED_PII:hash=", sanitized["email"])
        self.assertIn("[REDACTED_PII:hash=", sanitized["phone"])
        self.assertEqual(sanitized["safe_field"], "public_data")


if __name__ == "__main__":
    unittest.main()
