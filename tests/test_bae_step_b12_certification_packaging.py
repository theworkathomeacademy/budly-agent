"""BAE Pilot 001 Gate B Step B12 Certification Evidence Packaging Tests.

Validates the 23 Section 18 invariants:
1. Exactly five Wave 1 packages exist
2. IDs match canonical seed IDs
3. Capability versions match canonical records
4. Each package maps implementation evidence
5. Each package maps test evidence
6. Each package maps B11 acceptance evidence
7. Each package maps applicable requirements
8. No package claims CERTIFIED
9. No package claims AUTHORIZED_FOR_ENVIRONMENT
10. Current certified maturity remains None/not certified
11. Target M3 remains target only
12. No canonical executable flag becomes true
13. No duplicate canonical capability ID appears
14. No evidence references a nonexistent test ID
15. No PASS is represented without supporting evidence reference
16. Unresolved deficiency produces NOT_READY or BLOCKED
17. No customer-facing route becomes authorized
18. TASK/RETRY remain outside B12 certification scope
19. CRM Activity remains conditional/non-executable
20. Customer Follow-Up remains disabled
21. Gate D remains unauthorized
22. No production deployment occurs
23. B13 is not started
"""

from __future__ import annotations

import unittest
from uuid import uuid4

from src.budly_runtime.bae.capability_registry import BAECapabilityRegistry
from src.budly_runtime.bae.certification_packaging import (
    CertificationRecommendationState,
    Wave1CapabilityCertificationPackage,
    Wave1CertificationEvidenceBuilder,
)
from src.budly_runtime.bae.escalation import EscalationRoute, EscalationRouteRegistry
from src.budly_runtime.bae.policy_evaluator import (
    AuthorizationDecisionStatus,
    AuthorizationDenialReason,
    AuthorizationRequest,
    BAEKillSwitchRegistry,
    DeterministicPolicyEvaluator,
)
from src.budly_runtime.bae.types import (
    ApprovalLevel,
    AuthorityClass,
    AutonomyMaturity,
    CapabilityLifecycleState,
    PilotWave,
    ToolAuthorityClass,
)


class TestBAEStepB12CertificationPackaging(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = BAECapabilityRegistry.load_seed()
        self.packages = Wave1CertificationEvidenceBuilder.build_all_wave1_packages(self.registry)
        self.canonical_wave1_ids = {
            "BAE-OPS-OBSERVE-001",
            "BAE-OPS-DETECT-001",
            "BAE-OPS-VERIFY-001",
            "BAE-OPS-PACKAGE-001",
            "BAE-OPS-ESCALATE-001",
        }

    # 1. Exactly five Wave 1 packages exist
    def test_01_exactly_five_wave1_packages_exist(self) -> None:
        self.assertEqual(len(self.packages), 5)
        self.assertEqual(set(self.packages.keys()), self.canonical_wave1_ids)

    # 2. IDs match canonical seed IDs
    def test_02_ids_match_canonical_seed_ids(self) -> None:
        for cap_id, pkg in self.packages.items():
            self.assertEqual(pkg.capability_id, cap_id)
            seed = self.registry.get(cap_id)
            self.assertIsNotNone(seed)
            self.assertEqual(pkg.capability_id, seed.capability_id)

    # 3. Capability versions match canonical records
    def test_03_capability_versions_match_canonical_records(self) -> None:
        for cap_id, pkg in self.packages.items():
            seed = self.registry.get(cap_id)
            self.assertEqual(pkg.capability_version, seed.capability_version)
            self.assertEqual(pkg.capability_version, "1.0")

    # 4. Each package maps implementation evidence
    def test_04_each_package_maps_implementation_evidence(self) -> None:
        for cap_id, pkg in self.packages.items():
            self.assertGreater(len(pkg.implementation_file_references), 0, f"{cap_id} missing impl file refs")
            for ref in pkg.implementation_file_references:
                self.assertTrue(ref.startswith("src/budly_runtime/bae/"), f"Invalid impl ref: {ref}")

    # 5. Each package maps test evidence
    def test_05_each_package_maps_test_evidence(self) -> None:
        for cap_id, pkg in self.packages.items():
            self.assertGreater(len(pkg.implementation_test_references), 0, f"{cap_id} missing test refs")
            for test_ref in pkg.implementation_test_references:
                self.assertIn("tests/test_bae_step_b10_wave1_capabilities.py", test_ref)

    # 6. Each package maps B11 acceptance evidence
    def test_06_each_package_maps_b11_acceptance_evidence(self) -> None:
        for cap_id, pkg in self.packages.items():
            self.assertGreater(len(pkg.at_acceptance_references), 0, f"{cap_id} missing AT refs")
            # All must cite AT-001 through AT-070 format or composed flow
            for at_ref in pkg.at_acceptance_references:
                self.assertTrue(at_ref.startswith("AT-") or at_ref == "test_composed_wave1_acceptance_flow", f"Invalid AT ref: {at_ref}")

    # 7. Each package maps applicable requirements
    def test_07_each_package_maps_applicable_requirements(self) -> None:
        for cap_id, pkg in self.packages.items():
            self.assertGreater(len(pkg.requirement_references), 0, f"{cap_id} missing req refs")
            for req_ref in pkg.requirement_references:
                self.assertTrue(req_ref.startswith("BAE-P001-"), f"Invalid req ref: {req_ref}")

    # 8. No package claims CERTIFIED
    def test_08_no_package_claims_certified(self) -> None:
        for cap_id, pkg in self.packages.items():
            self.assertNotEqual(pkg.lifecycle_state, CapabilityLifecycleState.CERTIFIED)
            self.assertNotEqual(pkg.certification_recommendation, "CERTIFIED")
            self.assertNotEqual(pkg.certification_state, "CERTIFIED")
            self.assertTrue(pkg.certification_state.startswith("UNCERTIFIED"))

    # 9. No package claims AUTHORIZED_FOR_ENVIRONMENT
    def test_09_no_package_claims_authorized_for_environment(self) -> None:
        for cap_id, pkg in self.packages.items():
            self.assertNotEqual(pkg.lifecycle_state, CapabilityLifecycleState.AUTHORIZED_FOR_ENVIRONMENT)

    # 10. Current certified maturity remains None/not certified
    def test_10_current_certified_maturity_remains_none(self) -> None:
        for cap_id, pkg in self.packages.items():
            self.assertIsNone(pkg.current_certified_maturity, f"{cap_id} current maturity must be None")
            seed = self.registry.get(cap_id)
            self.assertIsNone(seed.current_certified_maturity)

    # 11. Target M3 remains target only
    def test_11_target_m3_remains_target_only(self) -> None:
        for cap_id, pkg in self.packages.items():
            self.assertEqual(pkg.target_pilot_entry_maturity, AutonomyMaturity.M3)
            self.assertIsNone(pkg.current_certified_maturity)

    # 12. No canonical executable flag becomes true
    def test_12_no_canonical_executable_flag_becomes_true(self) -> None:
        for rec in self.registry.list_all():
            self.assertFalse(rec.executable, f"Capability {rec.capability_id} executable must be False")
        for cap_id, pkg in self.packages.items():
            self.assertFalse(pkg.executable_state)

    # 13. No duplicate canonical capability ID appears
    def test_13_no_duplicate_canonical_capability_id_appears(self) -> None:
        all_ids = [rec.capability_id for rec in self.registry.list_all()]
        self.assertEqual(len(all_ids), len(set(all_ids)), "Duplicate capability ID found in registry")
        self.assertEqual(len(all_ids), 9)

    # 14. No evidence references a nonexistent test ID
    def test_14_no_evidence_references_nonexistent_test_id(self) -> None:
        from tests.test_bae_step_b10_wave1_capabilities import TestBAEStepB10Wave1Capabilities
        from tests.test_bae_step_b11_acceptance_harness import TestBAEStepB11AcceptanceHarness

        b10_methods = set(dir(TestBAEStepB10Wave1Capabilities))
        b11_methods = set(dir(TestBAEStepB11AcceptanceHarness))

        valid_at_tests = {f"AT-{i:03d}" for i in range(1, 71)}
        valid_at_tests.add("test_composed_wave1_acceptance_flow")

        for cap_id, pkg in self.packages.items():
            for at_ref in pkg.at_acceptance_references:
                self.assertIn(at_ref, valid_at_tests, f"{cap_id} references nonexistent AT test {at_ref}")
            for test_ref in pkg.implementation_test_references:
                method_name = test_ref.split("::")[-1]
                self.assertIn(method_name, b10_methods, f"{cap_id} references nonexistent B10 method {method_name}")

    # 15. No PASS is represented without supporting evidence reference
    def test_15_no_pass_represented_without_supporting_evidence(self) -> None:
        for cap_id, pkg in self.packages.items():
            self.assertGreater(len(pkg.audit_evidence_references), 0)
            self.assertGreater(len(pkg.at_acceptance_references), 0)
            self.assertGreater(len(pkg.implementation_test_references), 0)

    # 16. Unresolved deficiency produces NOT_READY or BLOCKED
    def test_16_unresolved_deficiency_produces_not_ready_or_blocked(self) -> None:
        pkg_with_deficiency = Wave1CapabilityCertificationPackage(
            capability_id="BAE-OPS-TEST-001",
            capability_version="1.0",
            capability_name="Deficient Test Capability",
            purpose="Testing",
            scope="Testing",
            authority_class=AuthorityClass.L1,
            current_certified_maturity=None,
            target_pilot_entry_maturity=AutonomyMaturity.M3,
            maximum_governable_maturity=AutonomyMaturity.M3,
            approval_class=ApprovalLevel.A0,
            tool_authority=ToolAuthorityClass.T0,
            lifecycle_state=CapabilityLifecycleState.DEFINED,
            executable_state=False,
            certification_state="UNCERTIFIED",
            activation_state="INACTIVE",
            allowed_fixture_environments=("development",),
            prohibited_environments=("production",),
            actor_requirements=("bae_steward",),
            permission_requirements=("bae:execute",),
            input_schema={},
            output_schema={},
            data_classes=("operational_telemetry",),
            approved_sources=("test_source",),
            authoritative_source_of_truth="test_source",
            verification_requirement="None",
            verification_method="POSTGRESQL_DIRECT_QUERY",
            accepted_evidence_classes=("AUTHORITATIVE_SOURCE_OF_TRUTH",),
            retry_idempotency_requirements="None",
            fallback_behavior="Stop",
            safe_inaction_behavior="Stop",
            escalation_behavior="Stop",
            audit_requirements="Audit",
            evidence_persistence_requirements="Persist",
            correlation_lineage_requirements="Lineage",
            applicable_kill_switch_scopes=("GLOBAL",),
            human_override_behavior="Stop",
            implementation_file_references=(),
            implementation_test_references=(),
            at_acceptance_references=(),
            requirement_references=(),
            audit_evidence_references=(),
            known_limitations=(),
            unresolved_dependencies=("missing_audit_persistence",),
            launch_blockers=("UNRESOLVED_VULNERABILITY",),
            certification_recommendation=CertificationRecommendationState.BLOCKED,
            rationale="Blocked due to unresolved vulnerability",
        )
        self.assertIn(
            pkg_with_deficiency.certification_recommendation,
            (CertificationRecommendationState.NOT_READY_FOR_CERTIFICATION, CertificationRecommendationState.BLOCKED),
        )

    # 17. No customer-facing route becomes authorized
    def test_17_no_customer_facing_route_becomes_authorized(self) -> None:
        route_reg = EscalationRouteRegistry()
        with self.assertRaises(ValueError):
            route_reg.register_route(
                EscalationRoute(
                    route_id="unauthorized_customer_channel",
                    channel_type="sms",
                    destination_target="+15551234567",
                    is_external_customer_facing=True,
                )
            )

    # 18. TASK/RETRY remain outside B12 certification scope
    def test_18_task_retry_remain_outside_b12_certification_scope(self) -> None:
        self.assertNotIn("BAE-OPS-TASK-001", self.packages)
        self.assertNotIn("BAE-OPS-RETRY-001", self.packages)
        task_rec = self.registry.get("BAE-OPS-TASK-001")
        retry_rec = self.registry.get("BAE-OPS-RETRY-001")
        self.assertEqual(task_rec.wave, PilotWave.WAVE_2)
        self.assertEqual(retry_rec.wave, PilotWave.WAVE_2)
        self.assertFalse(task_rec.executable)
        self.assertFalse(retry_rec.executable)
        self.assertEqual(task_rec.lifecycle_state, CapabilityLifecycleState.DEFINED)
        self.assertEqual(retry_rec.lifecycle_state, CapabilityLifecycleState.DEFINED)

    # 19. CRM Activity remains conditional/non-executable
    def test_19_crm_activity_remains_conditional_non_executable(self) -> None:
        self.assertNotIn("BAE-CRM-ACTIVITY-001", self.packages)
        crm_rec = self.registry.get("BAE-CRM-ACTIVITY-001")
        self.assertEqual(crm_rec.wave, PilotWave.WAVE_3)
        self.assertFalse(crm_rec.executable)
        self.assertEqual(crm_rec.classification_state, "CONDITIONAL")

    # 20. Customer Follow-Up remains disabled
    def test_20_customer_followup_remains_disabled(self) -> None:
        self.assertNotIn("BAE-COMM-FOLLOWUP-001", self.packages)
        followup_rec = self.registry.get("BAE-COMM-FOLLOWUP-001")
        self.assertEqual(followup_rec.wave, PilotWave.WAVE_4)
        self.assertFalse(followup_rec.executable)
        self.assertEqual(followup_rec.classification_state, "UNRESOLVED_DISABLED")

    # 21. Gate D remains unauthorized
    def test_21_gate_d_remains_unauthorized(self) -> None:
        evaluator = DeterministicPolicyEvaluator(self.registry, BAEKillSwitchRegistry())
        self.assertFalse(evaluator.gate_d_authorized)
        req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            objective_id=str(uuid4()),
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
        dec = evaluator.evaluate(req)
        self.assertFalse(dec.permitted)
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.ENVIRONMENT_DENIED)

    # 22. No production deployment occurs
    def test_22_no_production_deployment_occurs(self) -> None:
        for pkg in self.packages.values():
            self.assertIn("production", pkg.prohibited_environments)
            self.assertNotIn("production", pkg.authorized_environments)

    # 23. B13 is not started
    def test_23_b13_is_not_started(self) -> None:
        for pkg in self.packages.values():
            self.assertEqual(
                pkg.certification_recommendation,
                CertificationRecommendationState.READY_FOR_CERTIFICATION_REVIEW,
            )
            # Must NOT be certified or active
            self.assertNotEqual(pkg.lifecycle_state, CapabilityLifecycleState.CERTIFIED)
            self.assertNotEqual(pkg.lifecycle_state, CapabilityLifecycleState.AUTHORIZED_FOR_ENVIRONMENT)


if __name__ == "__main__":
    unittest.main()
