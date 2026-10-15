from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from src.budly_runtime.http_service import RuntimeHTTPService, make_server


ROOT = Path(__file__).resolve().parents[1]
SHARED_SECRET = "mx5c-local-integration-secret-0001"


class RecordingRuntime:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    def turn(self, payload: dict) -> dict:
        self.requests.append(payload)
        return {
            "success": True,
            "conversation_id": payload["conversation_id"],
            "response": {
                "text": "Grounded Wake'n'Bake Lounge staging response.",
                "intent": "membership_guidance",
                "journey": "membership",
                "resulting_action": "continue_conversation",
                "selected_product_id": None,
                "requires_human": False,
                "links": [
                    {
                        "label": "Explore Lounge Community",
                        "url": "https://cccultivate.com/wakenbake-lounge-community/",
                    }
                ],
            },
            "evidence": {
                "correlation_id": payload["correlation_id"],
                "knowledge_used": True,
            },
        }


class LocalSettings:
    bind_host = "127.0.0.1"
    port = 0
    shared_secret = SHARED_SECRET


class TestMX5CProxyRuntimeRoundTrip(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = RecordingRuntime()
        self.server = make_server(LocalSettings(), ROOT, runtime=self.runtime)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1/conversation"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    @staticmethod
    def _payload(correlation_id: str) -> bytes:
        return json.dumps(
            {
                "conversation_id": "conv_mx5c_local_roundtrip",
                "message": "What can I explore here, and how do I become a member?",
                "correlation_id": correlation_id,
                "channel": "ccc_website",
                "reset": False,
                "use_durable_memory": False,
                "deterministic_context": {
                    "journey": "membership",
                    "outcome": "conversation",
                    "selected_product_id": None,
                    "resulting_action": "continue_conversation",
                },
                "page_context": {
                    "schema_version": "1.0",
                    "surface": "wakenbake_lounge",
                    "view": "home",
                    "source_host": "cccultivate.com",
                },
            },
            separators=(",", ":"),
        ).encode("utf-8")

    def _request(self, body: bytes, correlation_id: str, signature: str | None = None):
        timestamp = str(int(time.time()))
        calculated = hmac.new(
            SHARED_SECRET.encode("utf-8"),
            timestamp.encode("ascii") + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        return urllib.request.Request(
            self.url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Budly-Timestamp": timestamp,
                "X-Budly-Signature": signature or calculated,
                "X-Correlation-ID": correlation_id,
            },
        )

    def test_signed_lounge_context_reaches_runtime_and_response_is_correlated(self) -> None:
        correlation_id = "00000000-0000-4000-8000-000000000501"
        body = self._payload(correlation_id)
        with urllib.request.urlopen(self._request(body, correlation_id), timeout=5) as response:
            self.assertEqual(response.status, 200)
            result = json.loads(response.read().decode("utf-8"))

        self.assertEqual(len(self.runtime.requests), 1)
        received = self.runtime.requests[0]
        self.assertEqual(received["page_context"]["surface"], "wakenbake_lounge")
        self.assertEqual(received["page_context"]["view"], "home")
        self.assertEqual(received["page_context"]["source_host"], "cccultivate.com")
        self.assertFalse(received["use_durable_memory"])
        self.assertEqual(result["evidence"]["correlation_id"], correlation_id)
        self.assertTrue(result["evidence"]["knowledge_used"])

    def test_bad_signature_and_replay_fail_closed(self) -> None:
        bad_correlation = "00000000-0000-4000-8000-000000000502"
        bad_body = self._payload(bad_correlation)
        with self.assertRaises(urllib.error.HTTPError) as bad_context:
            urllib.request.urlopen(
                self._request(bad_body, bad_correlation, signature="0" * 64), timeout=5
            )
        self.assertEqual(bad_context.exception.code, 401)
        self.assertEqual(len(self.runtime.requests), 0)

        replay_correlation = "00000000-0000-4000-8000-000000000503"
        replay_body = self._payload(replay_correlation)
        replay_request = self._request(replay_body, replay_correlation)
        with urllib.request.urlopen(replay_request, timeout=5) as response:
            self.assertEqual(response.status, 200)
        with self.assertRaises(urllib.error.HTTPError) as replay_context:
            urllib.request.urlopen(replay_request, timeout=5)
        self.assertEqual(replay_context.exception.code, 401)
        self.assertEqual(len(self.runtime.requests), 1)

    def test_header_body_correlation_mismatch_is_rejected(self) -> None:
        body_correlation = "00000000-0000-4000-8000-000000000504"
        header_correlation = "00000000-0000-4000-8000-000000000505"
        body = self._payload(body_correlation)
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(self._request(body, header_correlation), timeout=5)
        self.assertEqual(context.exception.code, 400)
        self.assertEqual(len(self.runtime.requests), 0)


class TestMX5CProtocolParity(unittest.TestCase):
    def test_runtime_authenticator_accepts_wordpress_signature_contract(self) -> None:
        service = RuntimeHTTPService(RecordingRuntime(), SHARED_SECRET)
        body = b'{"page_context":{"surface":"wakenbake_lounge"}}'
        timestamp = str(int(time.time()))
        correlation_id = "00000000-0000-4000-8000-000000000506"
        signature = hmac.new(
            SHARED_SECRET.encode("utf-8"),
            timestamp.encode("ascii") + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        self.assertTrue(service.authenticate(body, timestamp, signature, correlation_id))


if __name__ == "__main__":
    unittest.main()
