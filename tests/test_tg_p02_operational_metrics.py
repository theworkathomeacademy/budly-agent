import io
import json
import unittest
from pathlib import Path
from uuid import uuid4

from src.budly_runtime.tool_gateway import (
    Actor, AuditSink, CapabilityDefinition, CapabilityRef, ErrorClass,
    KnowledgeRetrieveInput, LocalKnowledgeAdapter, LocalOperationalMetricsAdapter,
    OperationalMetricsRetrieveInput, RequestValidationError, ResultStatus,
    ToolGateway, ToolHealth, ToolRegistry, ToolRequest,
)

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_FIXTURES = json.loads((ROOT / "config/tool_gateway/tg-p01-knowledge-fixtures.json").read_text(encoding="utf-8"))
METRIC_FIXTURES = json.loads((ROOT / "config/tool_gateway/tg-p02-operational-metrics-fixtures.json").read_text(encoding="utf-8"))


def metrics_definition(enabled=True):
    return CapabilityDefinition(
        capability_id="operational.metrics.retrieve", capability_version="1.0", bros_level=1,
        tool_class="T0", enabled=enabled,
        allowed_purposes=frozenset({"operational_status", "system_health_review", "internal_test", "admin_review"}),
        allowed_channels=frozenset({"website_chat", "internal_test", "admin_console"}),
    )


def request(actor_type="administrator", domain="revenue_operations", metric_names=("revenue.events.accepted",), **changes):
    values = {
        "request_id": str(uuid4()), "correlation_id": str(uuid4()),
        "actor": Actor("admin-test" if actor_type == "administrator" else "budly-service-test", actor_type),
        "capability": CapabilityRef("operational.metrics.retrieve", "1.0"),
        "purpose": "admin_review" if actor_type == "administrator" else "operational_status",
        "channel": "admin_console" if actor_type == "administrator" else "website_chat",
        "environment": "prototype",
        "input": OperationalMetricsRetrieveInput(domain, tuple(metric_names), "current_snapshot", 10),
    }
    values.update(changes)
    return ToolRequest(**values)


def gateway(*, enabled=True, health=ToolHealth.HEALTHY, fail=False, fixtures=None):
    knowledge = LocalKnowledgeAdapter(list(KNOWLEDGE_FIXTURES))
    registry = ToolRegistry(CapabilityDefinition(), knowledge)
    metrics = LocalOperationalMetricsAdapter(list(METRIC_FIXTURES if fixtures is None else fixtures), state=health, fail=fail)
    registry.register(metrics_definition(enabled), metrics)
    audit = AuditSink()
    return ToolGateway(registry, audit), metrics, audit


class TGP02AcceptanceTests(unittest.TestCase):
    def test_t01_unknown_actor(self):
        gw, adapter, _ = gateway()
        result = gw.execute(request(actor_type="anonymous_actor"))
        self.assertEqual((result.status, result.error["classification"]), (ResultStatus.DENIED, ErrorClass.UNKNOWN_ACTOR.value))
        self.assertIsNone(adapter.last_context)

    def test_t02_production_environment(self):
        gw, adapter, _ = gateway()
        result = gw.execute(request(environment="production"))
        self.assertEqual(result.error["classification"], ErrorClass.ENVIRONMENT_DENIED.value)
        self.assertIsNone(adapter.last_context)

    def test_t03_unknown_capability(self):
        gw, _, _ = gateway()
        result = gw.execute(request(capability=CapabilityRef("unknown.metrics", "1.0")))
        self.assertEqual(result.error["classification"], ErrorClass.UNKNOWN_CAPABILITY.value)

    def test_t04_caller_cannot_select_metrics_provider(self):
        raw = self.raw_request(); raw["provider"] = "supabase"
        with self.assertRaises(RequestValidationError): ToolRequest.from_dict(raw)

    def test_t05_authorized_administrator_retrieval(self):
        gw, _, audit = gateway(); req = request()
        result = gw.execute(req)
        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(result.result["items"][0]["metric_name"], "revenue.events.accepted")
        self.assertEqual(result.implementation, {"tool_id": "local_operational_metrics", "tool_version": "1.0"})
        self.assertEqual(result.evidence_reference, audit.events[-1].audit_event_id)
        self.assertEqual(audit.events[-1].permission_version, "TG-P02-permissions-1.0")

    def test_t06_authorized_budly_bounded_retrieval(self):
        gw, _, _ = gateway()
        result = gw.execute(request(actor_type="budly_service", domain="system_health", metric_names=("system.health.status",)))
        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual([item["metric_name"] for item in result.result["items"]], ["system.health.status"])
        self.assertEqual(result.result_classification, "PUBLIC")

    def test_t07_restricted_metric_denied_to_budly(self):
        gw, _, _ = gateway()
        result = gw.execute(request(actor_type="budly_service", domain="system_health", metric_names=("infrastructure.secret_error_detail",)))
        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(result.result, {"items": []})
        self.assertNotIn("synthetic restricted diagnostic", json.dumps(result.to_dict()))

    def test_t08_restricted_metric_allowed_to_administrator(self):
        gw, _, _ = gateway()
        result = gw.execute(request(domain="system_health", metric_names=("infrastructure.secret_error_detail",)))
        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(result.result["items"][0]["classification"], "RESTRICTED")

    def test_t09_unauthorized_domain(self):
        gw, _, _ = gateway()
        result = gw.execute(request(actor_type="budly_service", domain="revenue_operations"))
        self.assertEqual(result.error["classification"], ErrorClass.DATA_SCOPE_DENIED.value)

    def test_t10_malformed_input(self):
        gw, adapter, audit = gateway(); raw = self.raw_request(); raw["input"]["max_results"] = 0
        result = gw.execute_raw(raw)
        self.assertEqual((result.status, result.error["classification"]), (ResultStatus.DENIED, ErrorClass.INPUT_VALIDATION_FAILED.value))
        self.assertIsNone(adapter.last_context)
        self.assertEqual(audit.events[-1].metric_domain, "revenue_operations")

    def test_t11_superseded_metric_excluded(self):
        gw, _, _ = gateway()
        result = gw.execute(request(domain="workflow_operations", metric_names=("deprecated.metric",)))
        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(result.result, {"items": []})

    def test_t12_missing_provenance(self):
        malformed = [dict(METRIC_FIXTURES[0])]; malformed[0].pop("source_reference")
        gw, _, _ = gateway(fixtures=malformed)
        result = gw.execute(request())
        self.assertEqual((result.status, result.error["classification"]), (ResultStatus.FAILED, ErrorClass.OUTPUT_VALIDATION_FAILED.value))
        self.assertIsNone(result.result)

    def test_t13_adapter_failure(self):
        gw, _, _ = gateway(fail=True)
        result = gw.execute(request())
        self.assertEqual((result.status, result.error["classification"]), (ResultStatus.FAILED, ErrorClass.ADAPTER_FAILURE.value))
        self.assertIsNone(result.result)

    def test_t14_unavailable_adapter(self):
        gw, _, _ = gateway(health=ToolHealth.UNAVAILABLE)
        result = gw.execute(request())
        self.assertEqual((result.status, result.error["classification"]), (ResultStatus.UNAVAILABLE, ErrorClass.TOOL_UNAVAILABLE.value))
        self.assertIsNone(result.result)

    def test_t15_empty_valid_result(self):
        gw, _, _ = gateway()
        result = gw.execute(request(metric_names=("revenue.events.persistence_failure",)))
        self.assertEqual((result.status, result.result), (ResultStatus.SUCCESS, {"items": []}))

    def test_t16_result_limit(self):
        gw, _, _ = gateway()
        req = request(metric_names=("revenue.events.accepted", "revenue.events.duplicate"), input=OperationalMetricsRetrieveInput("revenue_operations", ("revenue.events.accepted", "revenue.events.duplicate"), "current_snapshot", 1))
        result = gw.execute(req)
        self.assertLessEqual(len(result.result["items"]), 1)

    def test_t17_correlation_preservation(self):
        gw, _, audit = gateway(); req = request(); result = gw.execute(req)
        self.assertEqual(req.correlation_id, result.correlation_id)
        self.assertEqual(req.correlation_id, audit.events[-1].correlation_id)
        self.assertEqual(audit.events[-1].metric_domain, "revenue_operations")

    def test_t18_context_injection_does_not_reach_adapter(self):
        gw, adapter, _ = gateway(); raw = self.raw_request(); raw["input"]["customer_email"] = "synthetic@example.invalid"
        result = gw.execute_raw(raw)
        self.assertEqual(result.error["classification"], ErrorClass.INPUT_VALIDATION_FAILED.value)
        self.assertIsNone(adapter.last_context)

    def test_t19_disabled_capability(self):
        gw, adapter, _ = gateway(enabled=False)
        result = gw.execute(request())
        self.assertEqual(result.error["classification"], ErrorClass.CAPABILITY_DISABLED.value)
        self.assertIsNone(adapter.last_context)

    def test_t20_tg_p01_regression_preservation(self):
        from tests.test_tg_p01_tool_gateway import TGP01AcceptanceTests
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(TGP01AcceptanceTests)
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        self.assertEqual(result.testsRun, 20)
        self.assertTrue(result.wasSuccessful())

    @staticmethod
    def raw_request():
        req = request()
        return {
            "request_id": req.request_id, "correlation_id": req.correlation_id,
            "actor": {"actor_id": req.actor.actor_id, "actor_type": req.actor.actor_type},
            "capability": {"capability_id": req.capability.capability_id, "capability_version": req.capability.capability_version},
            "purpose": req.purpose, "channel": req.channel, "environment": req.environment,
            "input": {"domain": req.input.domain, "metric_names": list(req.input.metric_names), "time_window": req.input.time_window, "max_results": req.input.max_results},
        }


if __name__ == "__main__":
    unittest.main()
