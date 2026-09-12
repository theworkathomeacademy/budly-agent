"""Comprehensive 60-case test matrix for BAE Pilot 001 Step B2 Continuous Authorization and Policy Evaluation."""

import unittest
from uuid import uuid4

from src.budly_runtime.bae.capability_registry import BAECapabilityRegistry
from src.budly_runtime.bae.policy_evaluator import (
    AuthorizationDecisionStatus,
    AuthorizationDenialReason,
    AuthorizationRequest,
    BAEKillSwitchRegistry,
    DeterministicPolicyEvaluator,
    compute_material_fingerprint,
)
from src.budly_runtime.bae.schemas import CapabilityRecord
from src.budly_runtime.bae.types import (
    ApprovalLevel,
    AuthorityClass,
    AutonomyMaturity,
    CapabilityLifecycleState,
    KillSwitchScope,
    PilotWave,
    ToolAuthorityClass,
)


class TestBAEStepB2PolicyEvaluator60Cases(unittest.TestCase):
    """Complete 60-case acceptance test suite covering all continuous authorization boundaries."""

    def setUp(self):
        self.registry = BAECapabilityRegistry.load_seed()
        self.kill_switches = BAEKillSwitchRegistry()
        self.evaluator = DeterministicPolicyEvaluator(self.registry, self.kill_switches)

    def _sample_request(
        self,
        capability_id="BAE-OPS-OBSERVE-001",
        tool_class=ToolAuthorityClass.T0,
        step_number=1,
        prior_token=None,
        approval_token=None,
        requested_maturity=AutonomyMaturity.M1,
        objective_id=None,
        channel="system_internal",
        purpose="system_telemetry",
        material_state_hash=None,
        actor_id="bae-steward-001",
        actor_type="bae_steward",
        environment="development",
        resource_cost_units=1,
        max_resource_limit=100,
        data_scope=None,
        is_actor_revoked=False,
        requires_consent=False,
        consent_token=None,
        is_consent_revoked=False,
        policy_version="1.0",
        expected_policy_version="1.0",
        idempotency_key=None,
        is_rate_limited=False,
        is_human_override_active=False,
        is_verification_available=True,
        required_permission=None,
        granted_permissions=frozenset({"bae:execute", "bae:telemetry", "bae:bounded_write"}),
        release_state="PILOT_AUTHORIZED",
        expected_release_state="PILOT_AUTHORIZED",
    ):
        return AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            objective_id=objective_id or str(uuid4()),
            step_number=step_number,
            actor_id=actor_id,
            actor_type=actor_type,
            capability_id=capability_id,
            capability_version="1.0",
            environment=environment,
            channel=channel,
            purpose=purpose,
            requested_tool_authority=tool_class,
            requested_maturity=requested_maturity,
            prior_step_token=prior_token,
            approval_token=approval_token,
            material_state_hash=material_state_hash,
            resource_cost_units=resource_cost_units,
            max_resource_limit=max_resource_limit,
            data_scope=data_scope,
            is_actor_revoked=is_actor_revoked,
            requires_consent=requires_consent,
            consent_token=consent_token,
            is_consent_revoked=is_consent_revoked,
            policy_version=policy_version,
            expected_policy_version=expected_policy_version,
            idempotency_key=idempotency_key,
            is_rate_limited=is_rate_limited,
            is_human_override_active=is_human_override_active,
            is_verification_available=is_verification_available,
            required_permission=required_permission,
            granted_permissions=granted_permissions,
            release_state=release_state,
            expected_release_state=expected_release_state,
        )

    def _make_certified_record(
        self,
        capability_id="BAE-OPS-OBSERVE-001",
        authority=AuthorityClass.L1,
        maturity=AutonomyMaturity.M3,
        max_maturity=AutonomyMaturity.M5,
        approval=ApprovalLevel.A0,
        tool=ToolAuthorityClass.T0,
        bounded_write=False,
        lifecycle=CapabilityLifecycleState.AUTHORIZED_FOR_ENVIRONMENT,
        environments=frozenset({"development"}),
        purposes=frozenset({"system_telemetry"}),
        channels=frozenset({"system_internal"}),
        signature="SIG-VALID-TEST",
    ):
        return CapabilityRecord(
            capability_id=capability_id,
            capability_version="1.0",
            capability_name="Test Capability",
            wave=PilotWave.WAVE_1,
            authority_class=authority,
            current_certified_maturity=maturity,
            target_pilot_entry_maturity=maturity,
            maximum_governable_maturity=max_maturity,
            approval_level=approval,
            tool_authority=tool,
            specifically_authorized_bounded_write=bounded_write,
            lifecycle_state=lifecycle,
            certification_signature=signature,
            allowed_environments=environments,
            allowed_purposes=purposes,
            allowed_channels=channels,
        )

    # 1. Seed capabilities non-executable in DEFINED state
    def test_case_01_seed_all_denied_defined_lifecycle(self):
        for cap in self.registry.list_all():
            req = self._sample_request(capability_id=cap.capability_id, tool_class=cap.tool_authority or ToolAuthorityClass.T0)
            dec = self.evaluator.evaluate(req)
            self.assertFalse(dec.permitted)

    def test_case_02_unregistered_capability_denied(self):
        req = self._sample_request(capability_id="BAE-UNKNOWN-SERVICE-999")
        dec = self.evaluator.evaluate(req)
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.CAPABILITY_NOT_REGISTERED)

    def test_case_03_unresolved_conditional_classification_denied(self):
        req = self._sample_request(capability_id="BAE-CRM-ACTIVITY-001", tool_class=ToolAuthorityClass.T2)
        dec = self.evaluator.evaluate(req)
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.CLASSIFICATION_UNRESOLVED)

    def test_case_04_prohibited_tx_tool_denied(self):
        rec = self._make_certified_record(tool=ToolAuthorityClass.TX)
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(tool_class=ToolAuthorityClass.TX))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.AUTHORITY_CLASS_PROHIBITED)

    def test_case_05_prohibited_l3x_authority_denied(self):
        rec = self._make_certified_record(authority=AuthorityClass.L3_X)
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request())
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.AUTHORITY_CLASS_PROHIBITED)

    def test_case_06_human_only_l3h_requires_human_approval(self):
        rec = self._make_certified_record(authority=AuthorityClass.L3_H, approval=ApprovalLevel.A3)
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request())
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.AUTHORITY_CLASS_HUMAN_ONLY)

    def test_case_07_uncertified_missing_signature_denied(self):
        rec = CapabilityRecord(
            capability_id="BAE-OPS-OBSERVE-001",
            capability_version="1.0",
            capability_name="Test",
            wave=PilotWave.WAVE_1,
            authority_class=AuthorityClass.L1,
            current_certified_maturity=None,
            target_pilot_entry_maturity=AutonomyMaturity.M3,
            maximum_governable_maturity=None,
            approval_level=ApprovalLevel.A0,
            tool_authority=ToolAuthorityClass.T0,
            lifecycle_state=CapabilityLifecycleState.AUTHORIZED_FOR_ENVIRONMENT,
            certification_signature=None,
        )
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request())
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.CAPABILITY_NOT_CERTIFIED)

    def test_case_08_requested_maturity_exceeds_certified_denied(self):
        rec = self._make_certified_record(maturity=AutonomyMaturity.M1)
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(requested_maturity=AutonomyMaturity.M3))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.MATURITY_INSUFFICIENT)

    def test_case_09_ineligible_lifecycle_state_denied(self):
        rec = self._make_certified_record(lifecycle=CapabilityLifecycleState.SUSPENDED)
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request())
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.LIFECYCLE_STATE_INELIGIBLE)

    def test_case_10_unauthorized_environment_denied(self):
        rec = self._make_certified_record(environments=frozenset({"automated_test"}))
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(environment="production"))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.ENVIRONMENT_DENIED)

    def test_case_11_unauthorized_channel_denied(self):
        rec = self._make_certified_record(channels=frozenset({"system_internal"}))
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(channel="public_chat"))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.CHANNEL_DENIED)

    def test_case_12_unauthorized_purpose_denied(self):
        rec = self._make_certified_record(purposes=frozenset({"system_telemetry"}))
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(purpose="unauthorized_marketing"))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.PURPOSE_DENIED)

    def test_case_13_tool_authority_mismatch_denied(self):
        rec = self._make_certified_record(tool=ToolAuthorityClass.T0)
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(tool_class=ToolAuthorityClass.T2))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.TOOL_AUTHORITY_PROHIBITED)

    def test_case_14_t2_bounded_write_missing_denied(self):
        rec = self._make_certified_record(tool=ToolAuthorityClass.T2, bounded_write=False)
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(tool_class=ToolAuthorityClass.T2))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.BOUNDED_WRITE_NOT_AUTHORIZED)

    def test_case_15_global_kill_switch_active_denied(self):
        rec = self._make_certified_record()
        self.kill_switches.trigger(KillSwitchScope.GLOBAL, "GLOBAL", "Global emergency halt")
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request())
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.KILL_SWITCH_ACTIVE)
        self.kill_switches.reset(KillSwitchScope.GLOBAL, "GLOBAL")

    def test_case_16_capability_kill_switch_active_denied(self):
        rec = self._make_certified_record()
        self.kill_switches.trigger(KillSwitchScope.CAPABILITY, "BAE-OPS-OBSERVE-001", "Capability pause")
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request())
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.KILL_SWITCH_ACTIVE)
        self.kill_switches.reset(KillSwitchScope.CAPABILITY, "BAE-OPS-OBSERVE-001")

    def test_case_17_step_continuity_missing_token_denied(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(step_number=2, prior_token=None))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.STEP_TOKEN_INVALID)

    def test_case_18_step_continuity_valid_token_permitted(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        obj_id = str(uuid4())
        dec1 = evaluator.evaluate(self._sample_request(step_number=1, objective_id=obj_id))
        self.assertTrue(dec1.permitted)
        dec2 = evaluator.evaluate(self._sample_request(step_number=2, objective_id=obj_id, prior_token=dec1.step_token.checksum))
        self.assertTrue(dec2.permitted)

    def test_case_19_material_state_altered_invalidates_token(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        obj_id = str(uuid4())
        dec1 = evaluator.evaluate(self._sample_request(step_number=1, objective_id=obj_id, material_state_hash="HASH-1"))
        self.assertTrue(dec1.permitted)
        dec2 = evaluator.evaluate(
            self._sample_request(step_number=2, objective_id=obj_id, prior_token=dec1.step_token.checksum, material_state_hash="INVALIDATED_STATE")
        )
        self.assertEqual(dec2.denial_reason, AuthorizationDenialReason.MATERIAL_STATE_ALTERED)

    def test_case_20_l2_unapproved_requires_approval(self):
        rec = self._make_certified_record(authority=AuthorityClass.L2, approval=ApprovalLevel.A1)
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request())
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.HUMAN_APPROVAL_REQUIRED)

    def test_case_21_l2_with_approval_token_permitted(self):
        rec = self._make_certified_record(authority=AuthorityClass.L2, approval=ApprovalLevel.A1)
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(approval_token="APPROVAL-A1-SIGNED"))
        self.assertEqual(dec.status, AuthorizationDecisionStatus.PERMITTED)

    def test_case_22_unauthorized_actor_type_denied(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(actor_type="unauthorized_third_party_bot"))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.ACTOR_DENIED)

    def test_case_23_resource_limit_exceeded_denied(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(resource_cost_units=150, max_resource_limit=100))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.RESOURCE_LIMIT_EXCEEDED)

    def test_case_24_unauthorized_data_scope_denied(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(data_scope="UNAUTHORIZED_SENSITIVE_DATA"))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.DATA_SCOPE_UNAUTHORIZED)

    def test_case_25_revoked_actor_credentials_denied(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(is_actor_revoked=True))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.ACTOR_REVOKED)

    def test_case_26_missing_required_consent_denied(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(requires_consent=True, consent_token=None))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.CONSENT_REQUIRED_MISSING)

    def test_case_27_valid_consent_token_permitted(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(requires_consent=True, consent_token="CONSENT-USER-OPTIN-001"))
        self.assertTrue(dec.permitted)

    def test_case_28_invalid_certification_signature_denied(self):
        rec = self._make_certified_record(signature="INVALID_SIGNATURE_PAYLOAD")
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request())
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.SIGNATURE_VERIFICATION_FAILED)

    def test_case_29_policy_version_mismatch_denied(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(policy_version="0.9", expected_policy_version="1.0"))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.POLICY_VERSION_MISMATCH)

    def test_case_30_expired_continuous_step_token_denied(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        obj_id = str(uuid4())
        dec = evaluator.evaluate(self._sample_request(step_number=2, objective_id=obj_id, prior_token=f"TOKEN-{obj_id}-1-EXPIRED"))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.STEP_TOKEN_EXPIRED)

    def test_case_31_environment_scoped_kill_switch_denied(self):
        rec = self._make_certified_record()
        self.kill_switches.trigger(KillSwitchScope.ENVIRONMENT, "development", "Dev env maintenance")
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request())
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.KILL_SWITCH_ACTIVE)
        self.kill_switches.reset(KillSwitchScope.ENVIRONMENT, "development")

    def test_case_32_objective_scoped_kill_switch_denied(self):
        rec = self._make_certified_record()
        obj_id = str(uuid4())
        self.kill_switches.trigger(KillSwitchScope.OBJECTIVE, obj_id, "Specific objective aborted")
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(objective_id=obj_id))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.KILL_SWITCH_ACTIVE)
        self.kill_switches.reset(KillSwitchScope.OBJECTIVE, obj_id)

    def test_case_33_tool_scoped_kill_switch_denied(self):
        rec = self._make_certified_record(tool=ToolAuthorityClass.T0)
        self.kill_switches.trigger(KillSwitchScope.TOOL, ToolAuthorityClass.T0.value, "T0 tool class disabled")
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(tool_class=ToolAuthorityClass.T0))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.KILL_SWITCH_ACTIVE)
        self.kill_switches.reset(KillSwitchScope.TOOL, ToolAuthorityClass.T0.value)

    def test_case_34_material_state_fingerprint_deterministic_uniqueness(self):
        fp1 = compute_material_fingerprint(str(uuid4()), 1, "BAE-OPS-OBSERVE-001", "dev", "sys", "tel", "actor1", "H1")
        fp2 = compute_material_fingerprint(str(uuid4()), 1, "BAE-OPS-OBSERVE-001", "dev", "sys", "tel", "actor1", "H1")
        self.assertNotEqual(fp1, fp2)

    def test_case_35_three_step_sequential_continuous_authorization(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        obj_id = str(uuid4())
        dec1 = evaluator.evaluate(self._sample_request(step_number=1, objective_id=obj_id))
        self.assertTrue(dec1.permitted)
        dec2 = evaluator.evaluate(self._sample_request(step_number=2, objective_id=obj_id, prior_token=dec1.step_token.checksum))
        self.assertTrue(dec2.permitted)
        dec3 = evaluator.evaluate(self._sample_request(step_number=3, objective_id=obj_id, prior_token=dec2.step_token.checksum))
        self.assertTrue(dec3.permitted)

    def test_case_36_out_of_order_step_token_denied(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        obj_id = str(uuid4())
        dec1 = evaluator.evaluate(self._sample_request(step_number=1, objective_id=obj_id))
        self.assertTrue(dec1.permitted)
        dec3 = evaluator.evaluate(self._sample_request(step_number=3, objective_id=obj_id, prior_token=dec1.step_token.checksum))
        self.assertEqual(dec3.denial_reason, AuthorizationDenialReason.STEP_TOKEN_INVALID)

    def test_case_37_cross_objective_token_reuse_denied(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        obj1, obj2 = str(uuid4()), str(uuid4())
        dec1 = evaluator.evaluate(self._sample_request(step_number=1, objective_id=obj1))
        self.assertTrue(dec1.permitted)
        dec2 = evaluator.evaluate(self._sample_request(step_number=2, objective_id=obj2, prior_token=dec1.step_token.checksum))
        self.assertEqual(dec2.denial_reason, AuthorizationDenialReason.STEP_TOKEN_INVALID)

    def test_case_38_l1_autonomous_positive_path_with_bounded_write(self):
        rec = self._make_certified_record(tool=ToolAuthorityClass.T2, bounded_write=True)
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(tool_class=ToolAuthorityClass.T2))
        self.assertTrue(dec.permitted)
        self.assertEqual(dec.status, AuthorizationDecisionStatus.PERMITTED)

    def test_case_39_idempotency_key_replay_denied(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        idem_key = "IDEMPOTENT-ACTION-001"
        dec1 = evaluator.evaluate(self._sample_request(idempotency_key=idem_key))
        self.assertTrue(dec1.permitted)
        dec2 = evaluator.evaluate(self._sample_request(idempotency_key=idem_key))
        self.assertEqual(dec2.denial_reason, AuthorizationDenialReason.IDEMPOTENCY_KEY_REUSED)

    def test_case_40_rate_limit_exceeded_denied(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(is_rate_limited=True))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.RATE_LIMIT_EXCEEDED)

    def test_case_41_revoked_consent_denied(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(requires_consent=True, consent_token="CONSENT-123", is_consent_revoked=True))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.CONSENT_REVOKED)

    def test_case_42_m0_manual_capability_execution_denied(self):
        rec = self._make_certified_record(maturity=AutonomyMaturity.M0)
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(requested_maturity=AutonomyMaturity.M1))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.MATURITY_INSUFFICIENT)

    def test_case_43_m4_orchestration_request_within_m4_certification_permitted(self):
        rec = self._make_certified_record(maturity=AutonomyMaturity.M4)
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(requested_maturity=AutonomyMaturity.M4))
        self.assertTrue(dec.permitted)

    def test_case_44_m5_goal_directed_request_within_m5_certification_permitted(self):
        rec = self._make_certified_record(maturity=AutonomyMaturity.M5)
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(requested_maturity=AutonomyMaturity.M5))
        self.assertTrue(dec.permitted)

    def test_case_45_t1_safe_compute_positive_path_permitted(self):
        rec = self._make_certified_record(tool=ToolAuthorityClass.T1)
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(tool_class=ToolAuthorityClass.T1))
        self.assertTrue(dec.permitted)

    def test_case_46_t3_high_impact_write_requires_explicit_configured_approval(self):
        rec = self._make_certified_record(tool=ToolAuthorityClass.T3, approval=ApprovalLevel.A2)
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(tool_class=ToolAuthorityClass.T3))
        self.assertFalse(dec.permitted)
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.HUMAN_APPROVAL_REQUIRED)
        self.assertEqual(dec.approval_level, ApprovalLevel.A2)

    def test_case_47_t3_high_impact_write_with_approval_token_permitted(self):
        rec = self._make_certified_record(tool=ToolAuthorityClass.T3, approval=ApprovalLevel.A2)
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(tool_class=ToolAuthorityClass.T3, approval_token="APPROVAL-A2-PROJECT-OWNER"))
        self.assertTrue(dec.permitted)

    def test_case_48_a3_project_owner_approval_token_permitted(self):
        rec = self._make_certified_record(authority=AuthorityClass.L2, approval=ApprovalLevel.A3)
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(approval_token="APPROVAL-A3-OWNER-SIGNATURE"))
        self.assertTrue(dec.permitted)

    def test_case_49_a4_external_multiparty_approval_token_permitted(self):
        rec = self._make_certified_record(authority=AuthorityClass.L2, approval=ApprovalLevel.A4)
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(approval_token="APPROVAL-A4-EXTERNAL-BOARD"))
        self.assertTrue(dec.permitted)

    def test_case_50_actor_type_admin_operator_permitted(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(actor_type="admin_operator"))
        self.assertTrue(dec.permitted)

    def test_case_51_actor_type_system_internal_permitted(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(actor_type="system_internal"))
        self.assertTrue(dec.permitted)

    def test_case_52_four_step_continuous_chain_permitted(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        obj_id = str(uuid4())
        d1 = evaluator.evaluate(self._sample_request(step_number=1, objective_id=obj_id))
        d2 = evaluator.evaluate(self._sample_request(step_number=2, objective_id=obj_id, prior_token=d1.step_token.checksum))
        d3 = evaluator.evaluate(self._sample_request(step_number=3, objective_id=obj_id, prior_token=d2.step_token.checksum))
        d4 = evaluator.evaluate(self._sample_request(step_number=4, objective_id=obj_id, prior_token=d3.step_token.checksum))
        self.assertTrue(d4.permitted)

    def test_case_53_tampered_step_token_checksum_denied(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        obj_id = str(uuid4())
        d1 = evaluator.evaluate(self._sample_request(step_number=1, objective_id=obj_id))
        d2 = evaluator.evaluate(self._sample_request(step_number=2, objective_id=obj_id, prior_token="TOKEN-TAMPERED-CHECKSUM"))
        self.assertEqual(d2.denial_reason, AuthorizationDenialReason.STEP_TOKEN_INVALID)

    # Cases 54-60 (Section 16 Final Control Suite)
    def test_case_54_maximum_governable_maturity_exceeded_denied(self):
        rec = self._make_certified_record(maturity=AutonomyMaturity.M3, max_maturity=AutonomyMaturity.M3)
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(requested_maturity=AutonomyMaturity.M4))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.MAXIMUM_MATURITY_EXCEEDED)

    def test_case_55_missing_required_permission_denied(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(required_permission="bae:admin_override"))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.PERMISSION_DENIED)

    def test_case_56_active_human_override_denied(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(is_human_override_active=True))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.HUMAN_OVERRIDE_ACTIVE)

    def test_case_57_verification_unavailable_denied(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(is_verification_available=False))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.VERIFICATION_UNAVAILABLE)

    def test_case_58_gate_d_release_state_invalid_denied(self):
        rec = self._make_certified_record()
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request(release_state="RELEASE_HOLD", expected_release_state="PILOT_AUTHORIZED"))
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.GATE_D_RELEASE_STATE_INVALID)

    def test_case_59_restricted_lifecycle_state_denied(self):
        rec = self._make_certified_record(lifecycle=CapabilityLifecycleState.RESTRICTED)
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request())
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.CAPABILITY_RESTRICTED)

    def test_case_60_retired_lifecycle_state_denied(self):
        rec = self._make_certified_record(lifecycle=CapabilityLifecycleState.RETIRED)
        evaluator = DeterministicPolicyEvaluator(BAECapabilityRegistry([rec]), self.kill_switches)
        dec = evaluator.evaluate(self._sample_request())
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.CAPABILITY_RETIRED)


if __name__ == "__main__":
    unittest.main()
