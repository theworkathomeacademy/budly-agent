"""Targeted tests for Commercial Snapshot HTTP endpoints in http_service.py."""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
import urllib.request
import urllib.error
from pathlib import Path
from uuid import uuid4

import pytest

from budly_runtime.config import ProductionSettings
from budly_runtime.http_service import make_server, RUNTIME_VERSION

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def http_server(tmp_path: Path):
    """Run Budly HTTP server in background thread for testing."""
    settings = ProductionSettings(
        environment="staging",
        bind_host="127.0.0.1",
        port=8792,
        shared_secret="test-secret-key-1234567890abcdef",
        model_provider="openai",
        model_name="mock-model",
        model_api_key="mock-key",
        knowledge_path=Path("config"),
        request_timeout_seconds=5.0,
        provider_retry_count=1,
        commercial_snapshot_enabled=True,
    )
    server = make_server(settings, root=ROOT)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)
    yield server, settings
    server.shutdown()
    server.server_close()


def test_health_endpoint(http_server):
    _, _ = http_server
    req = urllib.request.Request("http://127.0.0.1:8792/v1/health")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data["success"] is True
        assert data["status"] == "healthy"
        assert data["version"] == RUNTIME_VERSION


def test_commercial_status_endpoint(http_server):
    _, _ = http_server
    req = urllib.request.Request("http://127.0.0.1:8792/v1/commercial/status")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data["success"] is True
        assert data["commercial_snapshot_enabled"] is True
        assert data["snapshot_loaded"] is True
        assert data["public_record_count"] == 73
        assert data["validation_status"] == "PASSED"
        assert data["visibility_policy"] == "CCS-006 v0.1"


def test_commercial_reload_authenticated(http_server):
    _, settings = http_server
    body = b"{}"
    ts = str(int(time.time()))
    corr = str(uuid4())
    sig = hmac.new(settings.shared_secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()

    req = urllib.request.Request(
        "http://127.0.0.1:8792/v1/commercial/reload",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Budly-Timestamp": ts,
            "X-Budly-Signature": sig,
            "X-Correlation-ID": corr,
        },
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data["success"] is True
        assert data["reloaded"] is True
        assert data["record_count"] == 73


def test_commercial_reload_unauthenticated_fails_closed(http_server):
    _, _ = http_server
    req = urllib.request.Request(
        "http://127.0.0.1:8792/v1/commercial/reload",
        data=b"{}",
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.status == 401
