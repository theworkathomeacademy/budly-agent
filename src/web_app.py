"""Zero-dependency local web app for the Budly Sales conversation."""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .conversation_service import ConversationService

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "web"


class BudlyHandler(SimpleHTTPRequestHandler):
    service: ConversationService

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/health":
            self._json({"status": "ok", "agent": "Budly Sales"})
            return
        if self.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        try:
            payload = self._payload()
            if self.path == "/api/start":
                result = self.service.start(name=payload["name"], email=payload["email"])
            elif self.path == "/api/route":
                result = self.service.route(
                    customer_id=payload["customer_id"], shopping_goal=payload["shopping_goal"]
                )
            elif self.path == "/api/complete":
                result = self.service.complete(**payload)
            else:
                self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
                return
            self._json(result)
        except (KeyError, TypeError, ValueError) as error:
            self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception:
            self._json({"error": "The conversation could not continue. Please try again."}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _payload(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 100_000:
            raise ValueError("Request is too large")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def make_server(host: str = "127.0.0.1", port: int = 8787, db_path: str | Path | None = None) -> ThreadingHTTPServer:
    handler = type("ConfiguredBudlyHandler", (BudlyHandler,), {"service": ConversationService(db_path)})
    return ThreadingHTTPServer((host, port), handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Budly Sales customer chat")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8787, type=int)
    args = parser.parse_args()
    server = make_server(args.host, args.port)
    print(f"Budly Sales is ready at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
