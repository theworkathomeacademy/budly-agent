"""Acceptance and unit tests for BAE Pilot 001 Step B3 Canonical Tool Gateway Enforcement & Bypass Prevention."""

import unittest
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
from src.budly_runtime.tool_gateway import (
    Actor,
    ActorPermission,
    AdapterContext,
    AuditEvent,
    AuditSink,
    CapabilityDefinition,
    CapabilityRef,
    ErrorClass,
    GatewayExecutionContext,
    KnowledgeRetrieveInput,
    LocalKnowledgeAdapter,
    PermissionDecision,
    ResultStatus,
    ToolGateway,
    ToolRegistry,
    ToolRequest,
)


class TestBAEStepB3ToolGatewayEnforcement(unittest.TestCase):
    """Verifies canonical Tool Gateway integration, default-deny enforcement, and bypass prevention."""

    def setUp(self):
        self.fixtures = [
            {
                "knowledge_id": "KB-POLICY-001",
                "title": "Return Policy",
                "version": "1.0",
                "domain": "customer_policy",
                "status": "Active",
                "classification": "Public",
                "source_reference": "POLICY-DOC-001",
                "content": "30-day return policy for unopened items.",
            }
        ]
        self.adapter = LocalKnowledgeAdapter(self.fixtures)
        self.certified_cap = CapabilityRecord(
            capability_id="BAE-OPS-OBSERVE-001",
            capability_version="1.0",
            capability_name="Observation",
            wave=PilotWave.WAVE_1,
            authority_class=AuthorityClass.L1,
            current_certified_maturity=AutonomyMaturity.M3,
            target_pilot_entry_maturity=AutonomyMaturity.M3,
            maximum_governable_maturity=AutonomyMaturity.M5,
            approval_level=ApprovalLevel.A0,
            tool_authority=ToolAuthorityClass.T0,
            lifecycle_state=CapabilityLifecycleState.AUTHORIZED_FOR_ENVIRONMENT,
            certification_signature="SIG-OBSERVE-VALID",
            allowed_environments=frozenset({"development", "automated_test"}),
            allowed_purposes=frozenset({"customer_education", "internal_test"}),
            allowed_channels=frozenset({"system_internal", "internal_test"}),
        )
        self.kill_switches = BAEKillSwitchRegistry()
        self.evaluator = DeterministicPolicyEvaluator(
            BAECapabilityRegistry([self.certified_cap]),
            self.kill_switches,
        )
        self.cap_def = CapabilityDefinition(
            capability_id="BAE-OPS-OBSERVE-001",
            capability_version="1.0",
            bros_level=1,
            tool_class="T0",
            enabled=True,
            allowed_environments=frozenset({"automated_test", "development", "prototype"}),
            allowed_purposes=frozenset({"customer_education", "internal_test"}),
            allowed_channels=frozenset({"website_chat", "system_internal", "internal_test"}),
        )
        self.registry = ToolRegistry(self.cap_def, self.adapter)
        self.audit = AuditSink()
        self.permissions = {
            "budly_service": ActorPermission("budly_service", frozenset({"customer_policy"}), frozenset({"Public", "PUBLIC"}), frozenset({"customer_education", "internal_test"}), frozenset({"website_chat", "internal_test"})),
            "bae_steward": ActorPermission("bae_steward", frozenset({"customer_policy"}), frozenset({"Public", "PUBLIC", "Internal", "INTERNAL"}), frozenset({"customer_education", "internal_test"}), frozenset({"system_internal", "internal_test"})),
        }
        self.gateway = ToolGateway(self.registry, self.audit, {"BAE-OPS-OBSERVE-001": self.permissions}, policy_evaluator=self.evaluator)

    def _sample_auth_decision(self, permitted=True, step_number=1, objective_id=None, capability_id="BAE-OPS-OBSERVE-001"):
        obj_id = objective_id or str(uuid4())
        if permitted:
            req = AuthorizationRequest(
                request_id=str(uuid4()),
                correlation_id=str(uuid4()),
                objective_id=obj_id,
                step_number=step_number,
                actor_id="bae-steward-001",
                actor_type="bae_steward",
                capability_id=capability_id,
                capability_version="1.0",
                environment="development",
                channel="system_internal",
                purpose="internal_test",
                requested_tool_authority=ToolAuthorityClass.T0,
                prior_step_token=f"TOKEN-{obj_id}-{step_number-1}" if step_number > 1 else None,
            )
            # If step > 1, first evaluate step 1
            if step_number > 1:
                req1 = AuthorizationRequest(
                    request_id=str(uuid4()),
                    correlation_id=str(uuid4()),
                    objective_id=obj_id,
                    step_number=1,
                    actor_id="bae-steward-001",
                    actor_type="bae_steward",
                    capability_id=capability_id,
                    capability_version="1.0",
                    environment="development",
                    channel="system_internal",
                    purpose="internal_test",
                    requested_tool_authority=ToolAuthorityClass.T0,
                )
                self.evaluator.evaluate(req1)
            return self.evaluator.evaluate(req)
        return AuthorizationDecision(
            status=AuthorizationDecisionStatus.DENIED,
            permitted=False,
            requires_approval=False,
            approval_level=None,
            denial_reason=AuthorizationDenialReason.KILL_SWITCH_ACTIVE,
            reason_detail="Execution blocked by kill switch",
            step_token=None,
        )

    def test_b3_01_valid_authorization_reaches_canonical_gateway_path(self):
        """A valid PERMITTED B2 authorization decision enables successful execution through canonical Gateway."""
        auth_decision = self._sample_auth_decision(permitted=True)
        req = ToolRequest(
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            actor=Actor("bae-steward-001", "bae_steward"),
            capability=CapabilityRef("BAE-OPS-OBSERVE-001", "1.0"),
            purpose="internal_test",
            channel="system_internal",
            environment="development",
            input=KnowledgeRetrieveInput(query="return policy", domain="customer_policy", max_results=5),
            bae_authorization=auth_decision,
        )
        result = self.gateway.execute(req)
        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertIsNotNone(result.result)
        self.assertIn("items", result.result)
        self.assertEqual(len(result.result["items"]), 1)

    def test_b3_02_denied_authorization_never_reaches_tool(self):
        """A DENIED B2 authorization decision is immediately blocked by Gateway without invoking tool adapter."""
        auth_decision = self._sample_auth_decision(permitted=False)
        req = ToolRequest(
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            actor=Actor("bae-steward-001", "bae_steward"),
            capability=CapabilityRef("BAE-OPS-OBSERVE-001", "1.0"),
            purpose="internal_test",
            channel="system_internal",
            environment="development",
            input=KnowledgeRetrieveInput(query="return policy", domain="customer_policy", max_results=5),
            bae_authorization=auth_decision,
        )
        result = self.gateway.execute(req)
        self.assertEqual(result.status, ResultStatus.DENIED)
        self.assertEqual(result.error["classification"], ErrorClass.BAE_AUTHORIZATION_DENIED.value)

    def test_b3_03_missing_bae_authorization_for_bae_actor_denied(self):
        """Invocation by bae_steward without bae_authorization is denied with BAE_AUTHORIZATION_REQUIRED."""
        req = ToolRequest(
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            actor=Actor("bae-steward-001", "bae_steward"),
            capability=CapabilityRef("BAE-OPS-OBSERVE-001", "1.0"),
            purpose="internal_test",
            channel="system_internal",
            environment="development",
            input=KnowledgeRetrieveInput(query="return policy", domain="customer_policy", max_results=5),
            bae_authorization=None,
        )
        result = self.gateway.execute(req)
        self.assertEqual(result.status, ResultStatus.DENIED)
        self.assertEqual(result.error["classification"], ErrorClass.BAE_AUTHORIZATION_REQUIRED.value)

    def test_b3_04_missing_gateway_route_denies(self):
        """Invocation for an unregistered capability route denies gracefully in Gateway."""
        auth_decision = self._sample_auth_decision(permitted=True)
        req = ToolRequest(
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            actor=Actor("bae-steward-001", "bae_steward"),
            capability=CapabilityRef("unregistered.tool.capability", "1.0"),
            purpose="internal_test",
            channel="system_internal",
            environment="development",
            input=KnowledgeRetrieveInput(query="return policy", domain="customer_policy", max_results=5),
            bae_authorization=auth_decision,
        )
        result = self.gateway.execute(req)
        self.assertEqual(result.status, ResultStatus.DENIED)
        self.assertEqual(result.error["classification"], ErrorClass.UNKNOWN_CAPABILITY.value)

    def test_b3_05_direct_bypass_prevention_on_raw_invocation(self):
        """execute_raw with invalid or bypassed request schema is denied with audit logging."""
        raw_payload = {
            "request_id": str(uuid4()),
            "correlation_id": str(uuid4()),
            "actor": {"actor_id": "malicious_actor", "actor_type": "bae_steward"},
            "capability": {"capability_id": "BAE-OPS-OBSERVE-001", "capability_version": "1.0"},
            "purpose": "internal_test",
            "channel": "system_internal",
            "environment": "development",
            "input": {"query": "test", "domain": "customer_policy", "max_results": 5},
            "bae_authorization": None,  # Missing continuous auth token
        }
        result = self.gateway.execute_raw(raw_payload)
        self.assertEqual(result.status, ResultStatus.DENIED)
        self.assertEqual(result.error["classification"], ErrorClass.BAE_AUTHORIZATION_REQUIRED.value)

    def test_b3_06_stale_or_invalid_step_token_denied_in_gateway(self):
        """If step token is tampered or lacks material fingerprint for step > 1, Gateway denies execution."""
        obj_id = str(uuid4())
        invalid_token = ContinuousAuthorizationToken(
            token_id=str(uuid4()),
            objective_id=obj_id,
            step_number=2,
            capability_id="BAE-OPS-OBSERVE-001",
            issued_at=utc_now(),
            expires_at=utc_now(),
            actor_id="bae-steward-001",
            environment="development",
            checksum="",  # Missing checksum
            material_state_fingerprint="",
        )
        auth_decision = AuthorizationDecision(
            status=AuthorizationDecisionStatus.PERMITTED,
            permitted=True,
            requires_approval=False,
            approval_level=ApprovalLevel.A0,
            denial_reason=None,
            reason_detail="Permitted",
            step_token=invalid_token,
        )
        req = ToolRequest(
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            actor=Actor("bae-steward-001", "bae_steward"),
            capability=CapabilityRef("BAE-OPS-OBSERVE-001", "1.0"),
            purpose="internal_test",
            channel="system_internal",
            environment="development",
            input=KnowledgeRetrieveInput(query="return policy", domain="customer_policy", max_results=5),
            bae_authorization=auth_decision,
        )
        result = self.gateway.execute(req)
        self.assertEqual(result.status, ResultStatus.DENIED)
        self.assertEqual(result.error["classification"], ErrorClass.BAE_STEP_TOKEN_INVALID.value)

    def test_b3_07_changed_governing_state_forces_reauthorization_failure(self):
        """If governing state changes (e.g. kill switch triggered) prior to gateway execution, new evaluation denies tool access."""
        # 1. First step succeeds
        auth_req_1 = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            objective_id=str(uuid4()),
            step_number=1,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="BAE-OPS-OBSERVE-001",
            capability_version="1.0",
            environment="development",
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        dec_1 = self.evaluator.evaluate(auth_req_1)
        self.assertTrue(dec_1.permitted)

        # 2. Kill switch triggered in governing state
        self.kill_switches.trigger(KillSwitchScope.GLOBAL, "GLOBAL", "Global emergency halt")

        # 3. Subsequent step evaluation denies
        auth_req_2 = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            objective_id=auth_req_1.objective_id,
            step_number=2,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="BAE-OPS-OBSERVE-001",
            capability_version="1.0",
            environment="development",
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T0,
            prior_step_token=dec_1.step_token.checksum,
        )
        dec_2 = self.evaluator.evaluate(auth_req_2)
        self.assertFalse(dec_2.permitted)
        self.assertEqual(dec_2.denial_reason, AuthorizationDenialReason.KILL_SWITCH_ACTIVE)

        # 4. Attempting gateway execution with denied dec_2 fails
        req = ToolRequest(
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            actor=Actor("bae-steward-001", "bae_steward"),
            capability=CapabilityRef("BAE-OPS-OBSERVE-001", "1.0"),
            purpose="internal_test",
            channel="system_internal",
            environment="development",
            input=KnowledgeRetrieveInput(query="return policy", domain="customer_policy", max_results=5),
            bae_authorization=dec_2,
        )
        result = self.gateway.execute(req)
        self.assertEqual(result.status, ResultStatus.DENIED)
        self.assertEqual(result.error["classification"], ErrorClass.BAE_AUTHORIZATION_DENIED.value)

    def test_b3_08_tool_gateway_permission_and_environment_restrictions_still_apply(self):
        """Even with valid BAE authorization, Tool Gateway environment restrictions are strictly enforced."""
        auth_decision = self._sample_auth_decision(permitted=True)
        # Attempting tool execution in unauthorized environment (e.g. production)
        req = ToolRequest(
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            actor=Actor("bae-steward-001", "bae_steward"),
            capability=CapabilityRef("BAE-OPS-OBSERVE-001", "1.0"),
            purpose="internal_test",
            channel="system_internal",
            environment="production",  # Prohibited environment
            input=KnowledgeRetrieveInput(query="return policy", domain="customer_policy", max_results=5),
            bae_authorization=auth_decision,
        )
        result = self.gateway.execute(req)
        self.assertEqual(result.status, ResultStatus.DENIED)
        self.assertEqual(result.error["classification"], ErrorClass.ENVIRONMENT_DENIED.value)

    def test_b3_09_direct_adapter_bypass_attempt_is_prevented_outside_gateway(self):
        """Direct instantiation and invocation of adapter.retrieve() outside Gateway execution context raises PermissionError before side effects."""
        raw_adapter = LocalKnowledgeAdapter(self.fixtures)
        untrusted_context = AdapterContext(
            query="return policy",
            domain="customer_policy",
            max_results=5,
            access_classifications=frozenset({"Public"}),
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            gateway_execution_context=None,  # No gateway-owned execution context
        )
        with self.assertRaises(PermissionError) as ctx:
            raw_adapter.retrieve(untrusted_context)
        self.assertIn("Direct adapter execution prohibited", str(ctx.exception))

    def test_b3_10_lmat_dimensions_strictly_independent_in_gateway_execution(self):
        """Verifies that approval requirements are determined by capability definition and not inferred mappings."""
        # Capability definition with L1 but explicit approval requirement
        l1_approval_cap = CapabilityDefinition(
            capability_id="BAE-OPS-OBSERVE-001",
            capability_version="1.0",
            bros_level=2,  # Requires human approval
            tool_class="T0",
            enabled=True,
            allowed_environments=frozenset({"development"}),
            allowed_purposes=frozenset({"internal_test"}),
            allowed_channels=frozenset({"system_internal"}),
        )
        gw = ToolGateway(ToolRegistry(l1_approval_cap, self.adapter), self.audit, {"BAE-OPS-OBSERVE-001": self.permissions}, policy_evaluator=self.evaluator)
        auth_decision = self._sample_auth_decision(permitted=True)
        req = ToolRequest(
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            actor=Actor("bae-steward-001", "bae_steward"),
            capability=CapabilityRef("BAE-OPS-OBSERVE-001", "1.0"),
            purpose="internal_test",
            channel="system_internal",
            environment="development",
            input=KnowledgeRetrieveInput(query="return policy", domain="customer_policy", max_results=5),
            bae_authorization=auth_decision,
        )
        result = gw.execute(req)
        self.assertEqual(result.status, ResultStatus.DENIED)
        self.assertEqual(result.error["classification"], ErrorClass.PERMISSION_DENIED.value)

    def test_b3_11_seed_capabilities_deny_in_gateway(self):
        """All 9 seed capabilities are non-executable in B2 evaluation and therefore blocked by Gateway."""
        seed_registry = BAECapabilityRegistry.load_seed()
        seed_evaluator = DeterministicPolicyEvaluator(seed_registry, self.kill_switches)
        for seed_cap in seed_registry.list_all():
            auth_req = AuthorizationRequest(
                request_id=str(uuid4()),
                correlation_id=str(uuid4()),
                objective_id=str(uuid4()),
                step_number=1,
                actor_id="bae-steward-001",
                actor_type="bae_steward",
                capability_id=seed_cap.capability_id,
                capability_version="1.0",
                environment="development",
                channel="system_internal",
                purpose="internal_test",
                requested_tool_authority=seed_cap.tool_authority or ToolAuthorityClass.T0,
            )
            dec = seed_evaluator.evaluate(auth_req)
            self.assertFalse(dec.permitted)

            # Gateway invocation with this decision denies
            req = ToolRequest(
                request_id=str(uuid4()),
                correlation_id=str(uuid4()),
                actor=Actor("bae-steward-001", "bae_steward"),
                capability=CapabilityRef("BAE-OPS-OBSERVE-001", "1.0"),
                purpose="internal_test",
                channel="system_internal",
                environment="development",
                input=KnowledgeRetrieveInput(query="return policy", domain="customer_policy", max_results=5),
                bae_authorization=dec,
            )
            res = self.gateway.execute(req)
            self.assertEqual(res.status, ResultStatus.DENIED)

    def test_b3_12_audit_event_logged_on_bae_denial(self):
        """BAE authorization denials are recorded in the audit sink."""
        initial_events = len(self.audit.events)
        req = ToolRequest(
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            actor=Actor("bae-steward-001", "bae_steward"),
            capability=CapabilityRef("BAE-OPS-OBSERVE-001", "1.0"),
            purpose="internal_test",
            channel="system_internal",
            environment="development",
            input=KnowledgeRetrieveInput(query="return policy", domain="customer_policy", max_results=5),
            bae_authorization=None,
        )
        self.gateway.execute(req)
        self.assertEqual(len(self.audit.events), initial_events + 1)
        last_event = self.audit.events[-1]
        self.assertEqual(last_event.permission_decision, "DENY")
        self.assertEqual(last_event.error_classification, ErrorClass.BAE_AUTHORIZATION_REQUIRED.value)

    def test_b3_13_forged_authorization_object_is_rejected(self):
        """A forged object claiming status=PERMITTED and permitted=True not issued by trusted B2 verifier is rejected."""
        fake_token = ContinuousAuthorizationToken(
            token_id=str(uuid4()),
            objective_id=str(uuid4()),
            step_number=1,
            capability_id="BAE-OPS-OBSERVE-001",
            issued_at=utc_now(),
            expires_at=utc_now(),
            actor_id="bae-steward-001",
            environment="development",
            checksum=f"TOKEN-{uuid4()}-1",
            material_state_fingerprint="forged_fingerprint",
        )
        forged_decision = AuthorizationDecision(
            status=AuthorizationDecisionStatus.PERMITTED,
            permitted=True,
            requires_approval=False,
            approval_level=ApprovalLevel.A0,
            denial_reason=None,
            reason_detail="Forged decision",
            step_token=fake_token,
        )
        req = ToolRequest(
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            actor=Actor("bae-steward-001", "bae_steward"),
            capability=CapabilityRef("BAE-OPS-OBSERVE-001", "1.0"),
            purpose="internal_test",
            channel="system_internal",
            environment="development",
            input=KnowledgeRetrieveInput(query="return policy", domain="customer_policy", max_results=5),
            bae_authorization=forged_decision,
        )
        result = self.gateway.execute(req)
        self.assertEqual(result.status, ResultStatus.DENIED)
        self.assertEqual(result.error["classification"], ErrorClass.BAE_AUTHORIZATION_DENIED.value)

    def test_b3_14_cross_request_reuse_rejected(self):
        """Reusing an authorization decision issued for objective A on objective B is rejected."""
        auth_decision = self._sample_auth_decision(permitted=True)
        # Attempt to use auth_decision for a different actor
        req = ToolRequest(
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            actor=Actor("other-steward-999", "bae_steward"),
            capability=CapabilityRef("BAE-OPS-OBSERVE-001", "1.0"),
            purpose="internal_test",
            channel="system_internal",
            environment="development",
            input=KnowledgeRetrieveInput(query="return policy", domain="customer_policy", max_results=5),
            bae_authorization=auth_decision,
        )
        result = self.gateway.execute(req)
        self.assertEqual(result.status, ResultStatus.DENIED)
        self.assertEqual(result.error["classification"], ErrorClass.BAE_AUTHORIZATION_DENIED.value)

    def test_b3_15_capability_mismatch_rejected(self):
        """Using an authorization issued for capability A to execute capability B is rejected."""
        auth_decision = self._sample_auth_decision(permitted=True)
        # Register a second capability
        cap2 = CapabilityDefinition(
            capability_id="BAE-OPS-ANALYZE-001",
            capability_version="1.0",
            bros_level=1,
            tool_class="T0",
            enabled=True,
            allowed_environments=frozenset({"development"}),
            allowed_purposes=frozenset({"internal_test"}),
            allowed_channels=frozenset({"system_internal"}),
        )
        self.registry.register(cap2, self.adapter)
        self.permissions["bae_steward"] = ActorPermission("bae_steward", frozenset({"customer_policy"}), frozenset({"Public", "PUBLIC", "Internal", "INTERNAL"}), frozenset({"internal_test"}), frozenset({"system_internal"}))
        self.gateway.permission_sets["BAE-OPS-ANALYZE-001"] = self.permissions

        req = ToolRequest(
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            actor=Actor("bae-steward-001", "bae_steward"),
            capability=CapabilityRef("BAE-OPS-ANALYZE-001", "1.0"),
            purpose="internal_test",
            channel="system_internal",
            environment="development",
            input=KnowledgeRetrieveInput(query="return policy", domain="customer_policy", max_results=5),
            bae_authorization=auth_decision,  # Issued for BAE-OPS-OBSERVE-001
        )
        result = self.gateway.execute(req)
        self.assertEqual(result.status, ResultStatus.DENIED)
        self.assertEqual(result.error["classification"], ErrorClass.BAE_AUTHORIZATION_DENIED.value)

    def test_b3_16_altered_material_state_fingerprint_rejected(self):
        """If request channel or purpose is altered from what was authorized in the token, verifier denies execution."""
        auth_decision = self._sample_auth_decision(permitted=True)
        # Invocation uses a different channel than authorized ("website_chat" vs "system_internal")
        req = ToolRequest(
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            actor=Actor("bae-steward-001", "bae_steward"),
            capability=CapabilityRef("BAE-OPS-OBSERVE-001", "1.0"),
            purpose="internal_test",
            channel="website_chat",  # Altered channel
            environment="development",
            input=KnowledgeRetrieveInput(query="return policy", domain="customer_policy", max_results=5),
            bae_authorization=auth_decision,
        )
    def test_b3_17_capability_version_mismatch_rejected(self):
        """Using an authorization for version 1.0 against an unsupported or mismatched version is rejected by trusted verifier."""
        auth_decision = self._sample_auth_decision(permitted=True)
        req = ToolRequest(
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            actor=Actor("bae-steward-001", "bae_steward"),
            capability=CapabilityRef("BAE-OPS-OBSERVE-001", "2.0"),  # Mismatched version
            purpose="internal_test",
            channel="system_internal",
            environment="development",
            input=KnowledgeRetrieveInput(query="return policy", domain="customer_policy", max_results=5),
            bae_authorization=auth_decision,
        )
        result = self.gateway.execute(req)
        self.assertEqual(result.status, ResultStatus.DENIED)

    def test_b3_18_execute_raw_cannot_synthesize_gateway_execution_context(self):
        """execute_raw with raw JSON payload cannot forge gateway_execution_token or trusted B2 decision."""
        raw_payload = {
            "request_id": str(uuid4()),
            "correlation_id": str(uuid4()),
            "actor": {"actor_id": "bae-steward-001", "actor_type": "bae_steward"},
            "capability": {"capability_id": "BAE-OPS-OBSERVE-001", "capability_version": "1.0"},
            "purpose": "internal_test",
            "channel": "system_internal",
            "environment": "development",
            "input": {"query": "return policy", "domain": "customer_policy", "max_results": 5},
            "bae_authorization": {
                "status": "PERMITTED",
                "permitted": True,
                "requires_approval": False,
                "approval_level": "A0",
                "denial_reason": None,
                "reason_detail": "Forged raw JSON decision",
                "step_token": {
                    "token_id": str(uuid4()),
                    "objective_id": str(uuid4()),
                    "step_number": 1,
                    "capability_id": "BAE-OPS-OBSERVE-001",
                    "issued_at": utc_now(),
                    "expires_at": utc_now(),
                    "actor_id": "bae-steward-001",
                    "environment": "development",
                    "checksum": "TOKEN-FORGED",
                    "material_state_fingerprint": "fake_fingerprint",
                },
            },
        }
        result = self.gateway.execute_raw(raw_payload)
        self.assertEqual(result.status, ResultStatus.DENIED)
        self.assertEqual(result.error["classification"], ErrorClass.BAE_AUTHORIZATION_DENIED.value)

    def test_b3_19_forged_gw_exec_string_fails(self):
        """Passing a fake or fabricated GatewayExecutionContext with invalid signature fails provenance verification."""
        forged_context = GatewayExecutionContext(
            execution_id="fake_exec_id",
            event_id="GW-EXEC-fake",
            request_id=str(uuid4()),
            capability_id="knowledge.retrieve",
            hmac_signature="forged_signature_hex_12345",
            is_trusted_internal=False,
        )
        adapter = LocalKnowledgeAdapter(self.fixtures)
        ctx = AdapterContext(
            query="policy", domain="customer_policy", max_results=5,
            access_classifications=frozenset({"Public"}),
            request_id=forged_context.request_id, correlation_id=str(uuid4()),
            gateway_execution_context=forged_context,
        )
        with self.assertRaises(PermissionError) as cm:
            adapter.retrieve(ctx)
        self.assertIn("verification failed", str(cm.exception))

    def test_b3_20_replay_and_cross_execution_reuse_fails(self):
        """A valid GatewayExecutionContext cannot be reused across executions (retired on first use)."""
        valid_exec_context = GatewayExecutionContext.create(
            event_id=f"EVT-{uuid4()}",
            request_id=str(uuid4()),
            capability_id="knowledge.retrieve",
        )
        adapter = LocalKnowledgeAdapter(self.fixtures)
        ctx = AdapterContext(
            query="policy", domain="customer_policy", max_results=5,
            access_classifications=frozenset({"Public"}),
            request_id=valid_exec_context.request_id, correlation_id=str(uuid4()),
            gateway_execution_context=valid_exec_context,
        )
        # First retrieval succeeds
        res1 = adapter.retrieve(ctx)
        self.assertIsInstance(res1, list)

        # Immediate replay with same context fails
        with self.assertRaises(PermissionError) as cm:
            adapter.retrieve(ctx)
        self.assertIn("verification failed", str(cm.exception))

    def test_b3_21_postgres_activity_adapter_direct_call_fails_without_provenance(self):
        """PostgresActivityAdapter directly invoked without authentic GatewayExecutionContext raises PermissionError."""
        from src.budly_runtime.postgres_activity import PostgresActivityAdapter
        from src.budly_runtime.tool_gateway import ActivityAdapterContext, SubjectRef, SourceRef

        # Mock adapter without database connect needed before provenance check
        adapter = PostgresActivityAdapter.__new__(PostgresActivityAdapter)
        adapter.environment = "development"
        adapter.schema = "tg_p04"

        untrusted_ctx = ActivityAdapterContext(
            activity_type="order_placed",
            subject=SubjectRef("synthetic_person", "P-TEST-001"),
            source=SourceRef("test_harness", "s_test_001"),
            channel="system_internal",
            purpose="internal_test",
            occurred_at=utc_now(),
            idempotency_key=f"IDEMP-{uuid4()}",
            properties={},
            fact_classification="PUBLIC",
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            allowed_activity_types=frozenset({"order_placed"}),
            gateway_execution_context=None,  # Missing execution capability
        )
        req = ToolRequest(
            request_id=untrusted_ctx.request_id, correlation_id=untrusted_ctx.correlation_id,
            actor=Actor("bae-steward-001", "bae_steward"),
            capability=CapabilityRef("activity.record", "1.0"),
            purpose="internal_test", channel="system_internal", environment="development",
            input=untrusted_ctx,
        )
        with self.assertRaises(PermissionError) as cm:
            adapter.execute_durable(
                context=untrusted_ctx, request=req, definition=CapabilityDefinition(),
                permission_version="1.0", started_at=utc_now(), audit_event_id=str(uuid4()),
            )
        self.assertIn("Direct adapter execution prohibited", str(cm.exception))

    def test_b3_22_postgres_preference_adapter_direct_call_fails_without_provenance(self):
        """PostgresPreferenceAdapter directly invoked without authentic GatewayExecutionContext raises PermissionError."""
        from src.budly_runtime.postgres_preference import PostgresPreferenceAdapter
        from src.budly_runtime.tool_gateway import PreferenceAdapterContext, PreferenceValue, PreferenceSource, MemoryAuthorization, SubjectRef

        adapter = PostgresPreferenceAdapter.__new__(PostgresPreferenceAdapter)
        adapter.environment = "development"
        adapter.schema = "tg_p05a"

        untrusted_ctx = PreferenceAdapterContext(
            subject=SubjectRef("synthetic_person", "P-TEST-001"),
            preference=PreferenceValue("comm_pref", "email", "COMMUNICATION"),
            source=PreferenceSource("conversation", "C-TEST-001", "S-TEST-001"),
            memory_authorization=MemoryAuthorization("ACTIVE", "support"),
            stated_at=utc_now(),
            idempotency_key=f"IDEMP-{uuid4()}",
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            channel="website_chat",
            gateway_execution_context=None,
        )
        req = ToolRequest(
            request_id=untrusted_ctx.request_id, correlation_id=untrusted_ctx.correlation_id,
            actor=Actor("bae-steward-001", "bae_steward"),
            capability=CapabilityRef("customer.preference.record", "1.0"),
            purpose="support", channel="website_chat", environment="development",
            input=untrusted_ctx,
        )
        with self.assertRaises(PermissionError) as cm:
            adapter.execute_durable(
                context=untrusted_ctx, request=req, definition=CapabilityDefinition(),
                permission_version="1.0", started_at=utc_now(), audit_event_id=str(uuid4()),
            )
        self.assertIn("Direct adapter execution prohibited", str(cm.exception))

    def test_b3_23_postgres_relationship_fact_adapter_direct_call_fails_without_provenance(self):
        """PostgresRelationshipFactAdapter directly invoked without authentic GatewayExecutionContext raises PermissionError."""
        from src.budly_runtime.postgres_relationship_fact import PostgresRelationshipFactAdapter
        from src.budly_runtime.tool_gateway import RelationshipFactAdapterContext, RelationshipFactValue, RelationshipSource, MemoryAuthorization, SubjectRef

        adapter = PostgresRelationshipFactAdapter.__new__(PostgresRelationshipFactAdapter)
        adapter.environment = "development"
        adapter.schema = "tg_p05b"

        untrusted_ctx = RelationshipFactAdapterContext(
            subject=SubjectRef("synthetic_person", "P-TEST-001"),
            relationship_fact=RelationshipFactValue("related_person_first_name", {"first_name": "Alice", "relationship": "sister"}, "FAMILY", "EXPLICIT"),
            source=RelationshipSource("conversation", "C-TEST-001", "S-TEST-001", "conversation about family milestones"),
            memory_authorization=MemoryAuthorization("ACTIVE", "support_continuity"),
            stated_at=utc_now(),
            idempotency_key=f"IDEMP-{uuid4()}",
            request_id=str(uuid4()),
            correlation_id=str(uuid4()),
            channel="website_chat",
            gateway_execution_context=None,
        )
        req = ToolRequest(
            request_id=untrusted_ctx.request_id, correlation_id=untrusted_ctx.correlation_id,
            actor=Actor("bae-steward-001", "bae_steward"),
            capability=CapabilityRef("customer.relationship_fact.record", "1.0"),
            purpose="support", channel="website_chat", environment="development",
            input=untrusted_ctx,
        )
        with self.assertRaises(PermissionError) as cm:
            adapter.execute_durable(
                context=untrusted_ctx, request=req, definition=CapabilityDefinition(),
                permission_version="1.0", started_at=utc_now(), audit_event_id=str(uuid4()),
            )
        self.assertIn("Direct adapter execution prohibited", str(cm.exception))

    def test_b3_24_postgres_memory_recall_adapter_direct_call_fails_without_provenance(self):
        """PostgresMemoryRecallAdapter directly invoked without authentic GatewayExecutionContext raises PermissionError."""
        from src.budly_runtime.postgres_memory_recall import PostgresMemoryRecallAdapter
        from src.budly_runtime.tool_gateway import MemoryRecallAdapterContext, VerifiedMemorySubject, SessionMemoryUse, MemoryCurrentContext, MemoryLimits

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
            gateway_execution_context=None,
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
                context=untrusted_ctx, request=req, definition=CapabilityDefinition(),
                permission_version="1.0", started_at=utc_now(), audit_event_id=str(uuid4()),
            )
        self.assertIn("Direct adapter execution prohibited", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
