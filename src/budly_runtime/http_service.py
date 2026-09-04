from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import time
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .config import ProductionSettings
from .production_runtime import ProductionConversationRuntime

MAX_BODY_BYTES = 16_384
SIGNATURE_WINDOW_SECONDS = 300
RUNTIME_VERSION = "1.8.0"


class RuntimeHTTPService:
    def __init__(self, runtime: ProductionConversationRuntime, shared_secret: str) -> None:
        self.runtime = runtime
        self.secret = shared_secret.encode("utf-8")
        self._seen: dict[str, float] = {}
        self._rates: dict[str, list[float]] = {}
        self._lock = threading.RLock()

    def authenticate(self, body: bytes, timestamp: str, signature: str, correlation_id: str) -> bool:
        try:
            sent = int(timestamp)
        except (TypeError, ValueError):
            return False
        now = int(time.time())
        if abs(now - sent) > SIGNATURE_WINDOW_SECONDS or not correlation_id:
            return False
        expected = hmac.new(self.secret, timestamp.encode("ascii") + b"." + body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return False
        with self._lock:
            self._prune(now)
            if correlation_id in self._seen:
                return False
            self._seen[correlation_id] = float(now)
            return True

    def rate_allowed(self, source: str) -> bool:
        now = time.monotonic()
        with self._lock:
            recent = [value for value in self._rates.get(source, []) if now - value < 60]
            if len(recent) >= 120:
                self._rates[source] = recent
                return False
            recent.append(now)
            self._rates[source] = recent
            return True

    def _prune(self, now: int) -> None:
        for key, value in list(self._seen.items()):
            if now - value > SIGNATURE_WINDOW_SECONDS:
                del self._seen[key]


class BudlyRuntimeHandler(BaseHTTPRequestHandler):
    service: RuntimeHTTPService
    server_version = "BudlyRuntime/1.0"

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/v1/health":
            self._json({"success": False, "error": {"code": "NOT_FOUND", "message": "Not found."}}, HTTPStatus.NOT_FOUND)
            return
        self._json({"success": True, "status": "healthy", "version": RUNTIME_VERSION, "durable_memory": False})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/conversation":
            self._json({"success": False, "error": {"code": "NOT_FOUND", "message": "Not found."}}, HTTPStatus.NOT_FOUND)
            return
        length = self.headers.get("Content-Length", "")
        if not length.isdigit() or int(length) < 2 or int(length) > MAX_BODY_BYTES:
            self._json({"success": False, "error": {"code": "INVALID_REQUEST", "message": "Request is invalid."}}, HTTPStatus.BAD_REQUEST)
            return
        body = self.rfile.read(int(length))
        timestamp = self.headers.get("X-Budly-Timestamp", "")
        signature = self.headers.get("X-Budly-Signature", "")
        correlation = self.headers.get("X-Correlation-ID", "")
        if not self.service.authenticate(body, timestamp, signature, correlation):
            self._json({"success": False, "error": {"code": "AUTHENTICATION_FAILED", "message": "Runtime request was not authorized."}}, HTTPStatus.UNAUTHORIZED)
            return
        if not self.service.rate_allowed(self.client_address[0]):
            self._json({"success": False, "error": {"code": "RATE_LIMITED", "message": "Please wait before trying again."}}, HTTPStatus.TOO_MANY_REQUESTS)
            return
        try:
            payload = json.loads(body.decode("utf-8"))
            if payload.get("correlation_id") != correlation:
                raise ValueError("correlation mismatch")
            result = self.service.runtime.turn(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self._json({"success": False, "error": {"code": "INVALID_REQUEST", "message": "Request is invalid."}}, HTTPStatus.BAD_REQUEST)
            return
        except Exception:
            self._json({"success": False, "error": {"code": "RUNTIME_UNAVAILABLE", "message": "The conversational runtime is temporarily unavailable."}}, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        self._json(result)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def make_server(settings: ProductionSettings, root: Path | None = None,
                runtime: ProductionConversationRuntime | None = None) -> ThreadingHTTPServer:
    project_root = root or Path(__file__).resolve().parents[2]
    configured_runtime = runtime or ProductionConversationRuntime(settings, project_root)
    service = RuntimeHTTPService(configured_runtime, settings.shared_secret)
    handler = type("ConfiguredBudlyRuntimeHandler", (BudlyRuntimeHandler,), {"service": service})
    return ThreadingHTTPServer((settings.bind_host, settings.port), handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the governed Budly Slice 1 runtime")
    parser.parse_args()
    settings = ProductionSettings.from_environment()
    server = make_server(settings)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
