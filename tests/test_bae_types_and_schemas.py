"""Unit tests for BAE Pilot 001 Control Types, Schemas, and Capability Registry."""

import unittest
from uuid import uuid4

from src.budly_runtime.bae.capability_registry import BAECapabilityRegistry, CapabilityRegistryError
from src.budly_runtime.bae.schemas import (
    CapabilityRecord,
    EscalationPackage,
    ExecutionObjective,
    KillSwitchState,
    SchemaValidationError,
    TaskRecord,
    VerificationRecord,
    utc_now,
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
    VerificationState,
)


class TestBAETypesAndSchemas(unittest.TestCase):
    """Verifies BAE Pilot 001 control types and schema validation."""

    def test_canonical_lifecycle_state_values(self):
        """Lifecycle must contain exact 10 states and must NOT contain DRAFT, ACTIVE, or DEPRECATED."""
        expected_states = {
            "DEFINED",
            "REGISTERED",
            "IMPLEMENTED",
            "TESTED",
            "CERTIFICATION_PENDING",
            "CERTIFIED",
            "AUTHORIZED_FOR_ENVIRONMENT",
            "SUSPENDED",
            "RESTRICTED",
            "RETIRED",
        }
        actual_states = {state.value for state in CapabilityLifecycleState}
        self.assertEqual(actual_states, expected_states)

        # Explicit prohibited state checks
        for prohibited in ("DRAFT", "ACTIVE", "DEPRECATED"):
            self.assertNotIn(prohibited, actual_states)

    def test_three_independent_maturity_fields(self):
        """CapabilityRecord enforces three distinct, non-interchangeable maturity fields."""
        record = CapabilityRecord(
            capability_id="BAE-OPS-OBSERVE-001",
            capability_version="1.0",
            capability_name="Operational Observation",
            wave=PilotWave.WAVE_1,
            authority_class=AuthorityClass.L1,
            current_certified_maturity=None,  # Not certified
            target_pilot_entry_maturity=AutonomyMaturity.M3,
            maximum_governable_maturity=None,
            approval_level=ApprovalLevel.A0,
            tool_authority=ToolAuthorityClass.T0,
            lifecycle_state=CapabilityLifecycleState.DEFINED,
            executable=False,
        )
        self.assertIsNone(record.current_certified_maturity)
        self.assertEqual(record.target_pilot_entry_maturity, AutonomyMaturity.M3)
        self.assertIsNone(record.maximum_governable_maturity)
        self.assertNotEqual(record.current_certified_maturity, record.target_pilot_entry_maturity)

    def test_all_nine_seed_records_in_defined_state_and_non_executable(self):
        """Seed registry must load 9 capabilities, all with lifecycle DEFINED, uncertified, executable=False."""
        registry = BAECapabilityRegistry.load_seed()
        all_records = registry.list_all()
        self.assertEqual(len(all_records), 9)

        for r in all_records:
            self.assertEqual(r.lifecycle_state, CapabilityLifecycleState.DEFINED)
            self.assertFalse(r.executable)
            self.assertIsNone(r.current_certified_maturity)
            self.assertIsNone(r.certification_signature)

    def test_wave3_and_wave4_unresolved_conditional_classifications(self):
        """Wave 3 and Wave 4 records must have unresolved/null final L/A/T classifications in seed."""
        registry = BAECapabilityRegistry.load_seed()
        
        # Wave 3 CRM Activity
        crm = registry.get("BAE-CRM-ACTIVITY-001")
        self.assertIsNotNone(crm)
        self.assertEqual(crm.classification_state, "CONDITIONAL")
        self.assertIsNone(crm.authority_class)
        self.assertIsNone(crm.approval_level)
        self.assertIsNone(crm.tool_authority)
        self.assertEqual(crm.target_pilot_entry_maturity, AutonomyMaturity.M3)

        # Wave 4 Customer Followup
        followup = registry.get("BAE-COMM-FOLLOWUP-001")
        self.assertIsNotNone(followup)
        self.assertEqual(followup.classification_state, "UNRESOLVED_DISABLED")
        self.assertIsNone(followup.authority_class)
        self.assertIsNone(followup.approval_level)
        self.assertIsNone(followup.tool_authority)
        self.assertIsNone(followup.target_pilot_entry_maturity)
        self.assertFalse(followup.executable)

    def test_lmat_reconciliation_prohibited_tx_and_l3x(self):
        """TX tool class or L3-X authority class is always denied."""
        rec = LMATReconciliation.evaluate(
            authority=AuthorityClass.L1,
            current_certified_maturity=AutonomyMaturity.M3,
            approval=ApprovalLevel.A0,
            tool=ToolAuthorityClass.TX,
            is_certified=True,
            lifecycle_state=CapabilityLifecycleState.CERTIFIED,
        )
        self.assertFalse(rec.permitted)
        self.assertIn("Prohibited", rec.reason)

        rec_l3x = LMATReconciliation.evaluate(
            authority=AuthorityClass.L3_X,
            current_certified_maturity=AutonomyMaturity.M3,
            approval=ApprovalLevel.A0,
            tool=ToolAuthorityClass.T1,
            is_certified=True,
            lifecycle_state=CapabilityLifecycleState.CERTIFIED,
        )
        self.assertFalse(rec_l3x.permitted)

    def test_lmat_reconciliation_uncertified_or_non_authorized_state(self):
        """Uncertified or non-authorized lifecycle state cannot execute autonomously."""
        rec_uncert = LMATReconciliation.evaluate(
            authority=AuthorityClass.L1,
            current_certified_maturity=None,
            approval=ApprovalLevel.A0,
            tool=ToolAuthorityClass.T0,
            is_certified=False,
            lifecycle_state=CapabilityLifecycleState.DEFINED,
        )
        self.assertFalse(rec_uncert.permitted)
        self.assertIn("lacks active certification", rec_uncert.reason)

        rec_defined = LMATReconciliation.evaluate(
            authority=AuthorityClass.L1,
            current_certified_maturity=AutonomyMaturity.M3,
            approval=ApprovalLevel.A0,
            tool=ToolAuthorityClass.T0,
            is_certified=True,
            lifecycle_state=CapabilityLifecycleState.DEFINED,
        )
        self.assertFalse(rec_defined.permitted)
        self.assertIn("not eligible", rec_defined.reason)

    def test_lmat_reconciliation_maturity_never_overrides_authority(self):
        """High autonomy maturity (M5) cannot override L2 or L3-H authority class."""
        rec_l2 = LMATReconciliation.evaluate(
            authority=AuthorityClass.L2,
            current_certified_maturity=AutonomyMaturity.M5,
            approval=ApprovalLevel.A1,
            tool=ToolAuthorityClass.T1,
            is_certified=True,
            lifecycle_state=CapabilityLifecycleState.AUTHORIZED_FOR_ENVIRONMENT,
        )
        self.assertFalse(rec_l2.permitted)
        self.assertTrue(rec_l2.requires_approval)
        self.assertEqual(rec_l2.approval_level, ApprovalLevel.A1)

        rec_l3h = LMATReconciliation.evaluate(
            authority=AuthorityClass.L3_H,
            current_certified_maturity=AutonomyMaturity.M5,
            approval=ApprovalLevel.A3,
            tool=ToolAuthorityClass.T1,
            is_certified=True,
            lifecycle_state=CapabilityLifecycleState.AUTHORIZED_FOR_ENVIRONMENT,
        )
        self.assertFalse(rec_l3h.permitted)
        self.assertTrue(rec_l3h.requires_approval)
        self.assertEqual(rec_l3h.approval_level, ApprovalLevel.A3)

    def test_lmat_reconciliation_conditional_unresolved(self):
        """Unresolved / conditional L/A/T fields cannot execute."""
        rec_cond = LMATReconciliation.evaluate(
            authority=None,
            current_certified_maturity=None,
            approval=None,
            tool=None,
            is_certified=False,
            lifecycle_state=CapabilityLifecycleState.DEFINED,
        )
        self.assertFalse(rec_cond.permitted)
        self.assertIn("conditional or unresolved", rec_cond.reason)

    def test_capability_record_schema_validation(self):
        """CapabilityRecord enforces naming conventions and certification constraints."""
        record = CapabilityRecord(
            capability_id="BAE-OPS-OBSERVE-001",
            capability_version="1.0",
            capability_name="Operational Observation",
            wave=PilotWave.WAVE_1,
            authority_class=AuthorityClass.L1,
            current_certified_maturity=None,
            target_pilot_entry_maturity=AutonomyMaturity.M3,
            maximum_governable_maturity=None,
            approval_level=ApprovalLevel.A0,
            tool_authority=ToolAuthorityClass.T0,
            lifecycle_state=CapabilityLifecycleState.DEFINED,
            executable=False,
        )
        self.assertEqual(record.capability_id, "BAE-OPS-OBSERVE-001")

        # Invalid ID format
        with self.assertRaises(SchemaValidationError):
            CapabilityRecord(
                capability_id="invalid_id",
                capability_version="1.0",
                capability_name="Invalid",
                wave=PilotWave.WAVE_1,
                authority_class=AuthorityClass.L1,
                current_certified_maturity=None,
                target_pilot_entry_maturity=AutonomyMaturity.M3,
                maximum_governable_maturity=None,
                approval_level=ApprovalLevel.A0,
                tool_authority=ToolAuthorityClass.T0,
                lifecycle_state=CapabilityLifecycleState.DEFINED,
            )

        # Cannot be executable if in DEFINED state
        with self.assertRaises(SchemaValidationError):
            CapabilityRecord(
                capability_id="BAE-OPS-OBSERVE-001",
                capability_version="1.0",
                capability_name="Operational Observation",
                wave=PilotWave.WAVE_1,
                authority_class=AuthorityClass.L1,
                current_certified_maturity=None,
                target_pilot_entry_maturity=AutonomyMaturity.M3,
                maximum_governable_maturity=None,
                approval_level=ApprovalLevel.A0,
                tool_authority=ToolAuthorityClass.T0,
                lifecycle_state=CapabilityLifecycleState.DEFINED,
                executable=True,
            )

    def test_wave4_customer_followup_must_remain_disabled(self):
        """Wave 4 capability cannot be marked executable."""
        with self.assertRaises(SchemaValidationError):
            CapabilityRecord(
                capability_id="BAE-COMM-FOLLOWUP-001",
                capability_version="1.0",
                capability_name="Customer Followup",
                wave=PilotWave.WAVE_4,
                authority_class=AuthorityClass.L3_H,
                current_certified_maturity=None,
                target_pilot_entry_maturity=None,
                maximum_governable_maturity=None,
                approval_level=ApprovalLevel.A3,
                tool_authority=ToolAuthorityClass.TX,
                lifecycle_state=CapabilityLifecycleState.CERTIFIED,
                certification_signature="SIG-123",
                executable=True,
            )

    def test_execution_objective_and_task_schemas(self):
        """Verify ExecutionObjective, TaskRecord, and VerificationRecord schema constraints."""
        obj_id, corr_id = str(uuid4()), str(uuid4())
        obj = ExecutionObjective(
            objective_id=obj_id,
            correlation_id=corr_id,
            objective_type="metric_variance_reconciliation",
            target_system="woocommerce",
            created_at=utc_now(),
        )
        self.assertEqual(obj.state, ObjectiveState.CREATED)

        task_id = str(uuid4())
        task = TaskRecord(
            task_id=task_id,
            objective_id=obj_id,
            correlation_id=corr_id,
            step_number=1,
            capability_id="BAE-OPS-OBSERVE-001",
            capability_version="1.0",
            state=TaskState.PENDING,
            input_payload={"metric": "order_volume"},
            idempotency_key="task-step-1",
            created_at=utc_now(),
        )
        self.assertEqual(task.step_number, 1)

        # Verification Record match requires observed_state and evidence_reference
        verif_id = str(uuid4())
        verif = VerificationRecord(
            verification_id=verif_id,
            task_id=task_id,
            objective_id=obj_id,
            correlation_id=corr_id,
            target_sor="postgresql_primary",
            query_reference="SELECT status FROM orders WHERE id=123",
            expected_state={"status": "completed"},
            observed_state={"status": "completed"},
            state=VerificationState.VERIFIED_MATCH,
            verified_at=utc_now(),
            evidence_reference="AUDIT-VERIF-001",
        )
        self.assertEqual(verif.state, VerificationState.VERIFIED_MATCH)

    def test_escalation_package_schema(self):
        """Verify EscalationPackage formatting and approval level requirements."""
        esc_id, obj_id, corr_id = str(uuid4()), str(uuid4()), str(uuid4())
        esc = EscalationPackage(
            escalation_id=esc_id,
            objective_id=obj_id,
            task_id=None,
            correlation_id=corr_id,
            required_approval_level=ApprovalLevel.A1,
            authority_class=AuthorityClass.L2,
            reason_code="VARIANCE_EXCEEDS_THRESHOLD",
            summary="Order total variance of 15% detected between gateway and SoR.",
            context_data={"variance_pct": 15.0},
            evidence_references=("AUDIT-1", "AUDIT-2"),
            created_at=utc_now(),
        )
        self.assertEqual(esc.required_approval_level, ApprovalLevel.A1)

        # Cannot escalate with A0
        with self.assertRaises(SchemaValidationError):
            EscalationPackage(
                escalation_id=esc_id,
                objective_id=obj_id,
                task_id=None,
                correlation_id=corr_id,
                required_approval_level=ApprovalLevel.A0,
                authority_class=AuthorityClass.L2,
                reason_code="VARIANCE_EXCEEDS_THRESHOLD",
                summary="Order total variance detected.",
                context_data={},
                evidence_references=(),
                created_at=utc_now(),
            )

    def test_kill_switch_state_schema(self):
        """Verify KillSwitchState validation."""
        ks = KillSwitchState(
            switch_id="KS-GLOBAL-001",
            scope=KillSwitchScope.GLOBAL,
            target_identifier="GLOBAL",
            is_active=True,
            triggered_at=utc_now(),
            triggered_by="operator_admin",
            reason="Emergency stop triggered due to upstream SoR latency.",
        )
        self.assertTrue(ks.is_active)
        self.assertEqual(ks.scope, KillSwitchScope.GLOBAL)


if __name__ == "__main__":
    unittest.main()
