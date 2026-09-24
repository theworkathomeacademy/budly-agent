"""Zero-dependency local web app for the Budly Sales conversation with V.I.B.E. voice integration."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "web"
VIBE_DIR = Path(r"C:\Users\19196\Documents\VIBE")
VIBE_PYTHON = VIBE_DIR / "env-vibe" / "Scripts" / "python.exe"
VIBE_SYNTHESIZE = VIBE_DIR / "synthesize.py"
VIBE_REGISTRY_JSON = VIBE_DIR / "voices" / "registry.json"
VIBE_OUTPUT_DIR = VIBE_DIR / "output"
VIBE_KILL_SWITCH = VIBE_DIR / "VIBE_DISABLED"
LIVE_TELEMETRY_FILE = VIBE_OUTPUT_DIR / "e2e_live_telemetry.jsonl"
TELEMETRY_LOG_FILE = VIBE_OUTPUT_DIR / "e2e_telemetry_log.json"

TELEMETRY_LOCK = threading.Lock()

# In-memory VIBE Engine Router singleton
vibe_router = None
vibe_lock = threading.Lock()

if str(VIBE_DIR) not in sys.path:
    sys.path.insert(0, str(VIBE_DIR))

try:
    from src.vibe_engine_router import VIBEEngineRouter
    vibe_router = VIBEEngineRouter(default_engine="kokoro")
    print("[VIBE Bridge] In-process VIBEEngineRouter loaded successfully (Kokoro ONNX & Chatterbox Turbo).")
    VIBEKillSwitchError = RuntimeError
except Exception as _e:
    print(f"[VIBE Bridge] In-process VIBEEngineRouter initialization notice: {_e}.")
    VIBEKillSwitchError = RuntimeError  # type: ignore

try:
    from .conversation_service import ConversationService
except ImportError:
    from conversation_service import ConversationService

# Import Real Budly Production Conversation Runtime
try:
    from .budly_runtime.config import ProductionSettings
    from .budly_runtime.production_runtime import ProductionConversationRuntime, RuntimeTurnRequest
except ImportError:
    try:
        from budly_runtime.config import ProductionSettings
        from budly_runtime.production_runtime import ProductionConversationRuntime, RuntimeTurnRequest
    except ImportError:
        ProductionSettings = None  # type: ignore
        ProductionConversationRuntime = None  # type: ignore
        RuntimeTurnRequest = None  # type: ignore


def record_live_telemetry_event(record: dict[str, Any]) -> None:
    """Silently append structured telemetry event to e2e_live_telemetry.jsonl without logging secrets."""
    sanitized = {
        "timestamp": record.get("timestamp") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session_id": str(record.get("session_id", "anon")),
        "turn_id": str(record.get("turn_id", "")),
        "customer_input": str(record.get("customer_input", ""))[:300],
        "budly_response_latency_ms": int(record.get("budly_response_latency_ms", 0)),
        "text_render_latency_ms": int(record.get("text_render_latency_ms", 0)),
        "voice_generation_latency_ms": int(record.get("voice_generation_latency_ms", 0)),
        "time_to_first_audio_ms": int(record.get("time_to_first_audio_ms", 0)),
        "selected_voice_id": str(record.get("selected_voice_id", "builtin-default")),
        "exact_text_match": bool(record.get("exact_text_match", True)),
        "voice_status": str(record.get("voice_status", "READY")),
        "error_code": record.get("error_code"),
        "success": bool(record.get("success", True)),
    }
    with TELEMETRY_LOCK:
        try:
            VIBE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            with open(LIVE_TELEMETRY_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(sanitized) + "\n")
        except Exception as e:
            print(f"[VIBE Bridge] Error appending live telemetry: {e}")


def load_live_telemetry_events() -> List[Dict[str, Any]]:
    """Read all live telemetry events from e2e_live_telemetry.jsonl."""
    events = []
    if LIVE_TELEMETRY_FILE.exists():
        with TELEMETRY_LOCK:
            try:
                with open(LIVE_TELEMETRY_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            events.append(json.loads(line))
            except Exception as e:
                print(f"[VIBE Bridge] Error reading live telemetry: {e}")
    return events


def init_production_runtime(root: Path) -> Optional[ProductionConversationRuntime]:
    """Initialize the real Ask Budly production conversation runtime from .env and config."""
    if ProductionConversationRuntime is None or ProductionSettings is None:
        print("[Budly WebApp] ProductionConversationRuntime modules not found.")
        return None
    try:
        env_file = root / ".env"
        env_dict = dict(os.environ)
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env_dict[k.strip()] = v.strip()
        settings = ProductionSettings.from_environment(env_dict)
        runtime = ProductionConversationRuntime(settings, root)
        print(f"[Budly WebApp] Real ProductionConversationRuntime active (model={settings.model_name}, env={settings.environment}).")
        return runtime
    except Exception as e:
        print(f"[Budly WebApp] Could not initialize ProductionConversationRuntime: {e}")
        return None


class BudlyHandler(SimpleHTTPRequestHandler):
    service: ConversationService
    runtime: Optional[ProductionConversationRuntime] = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/health":
            self._json({
                "status": "ok",
                "agent": "Budly Sales",
                "runtime": "ProductionConversationRuntime" if self.runtime else "ConversationService",
                "vibe_bridge": "router (kokoro + chatterbox)" if vibe_router else "offline"
            })
            return
            
        if self.path == "/api/vibe/voices":
            self._handle_get_voices()
            return
            
        if self.path.startswith("/api/vibe/audio/"):
            self._handle_get_audio()
            return
            
        if self.path == "/api/vibe/telemetry":
            events = load_live_telemetry_events()
            self._json({"telemetry": events, "count": len(events), "file": str(LIVE_TELEMETRY_FILE)})
            return

        if self.path == "/debug/telemetry" or self.path.startswith("/debug/telemetry?"):
            self._handle_debug_telemetry_page()
            return

        if self.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        try:
            payload = self._payload()
            if self.path == "/api/turn":
                result = self._handle_turn(payload)
            elif self.path == "/api/intake":
                result = self.service.intake(
                    landing_input=payload.get("landing_input", payload),
                    session_id=payload.get("session_id"),
                    landing_route=payload.get("landing_route", "https://www.wakenbakelounge.com/ask-budly"),
                )
            elif self.path == "/api/start":
                result = self.service.start(
                    name=payload["name"],
                    email=payload["email"],
                    session_id=payload.get("session_id"),
                    attribution=payload.get("attribution"),
                )
            elif self.path == "/api/route":
                result = self.service.route(
                    customer_id=payload["customer_id"], shopping_goal=payload["shopping_goal"]
                )
            elif self.path == "/api/complete":
                result = self.service.complete(**payload)
            elif self.path == "/api/vibe/synthesize":
                self._handle_vibe_synthesize(payload)
                return
            elif self.path == "/api/vibe/telemetry":
                self._handle_post_telemetry(payload)
                return
            else:
                self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
                return
            self._json(result)
        except (KeyError, TypeError, ValueError) as error:
            self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception as e:
            print(f"[Budly WebApp Error] {e}")
            self._json({"error": "The conversation could not continue. Please try again."}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_turn(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Process conversational turn using ProductionConversationRuntime if available."""
        message = str(payload.get("message", "")).strip()
        if not message:
            raise ValueError("Message is required")

        raw_sess = str(payload.get("session_id") or "")
        clean_sess = re.sub(r"[^A-Za-z0-9_-]", "", raw_sess)
        if not clean_sess.startswith("conv_"):
            clean_sess = f"conv_{clean_sess}" if clean_sess else f"conv_{uuid.uuid4().hex[:16]}"
        if len(clean_sess) < 11:
            clean_sess = f"{clean_sess}_{uuid.uuid4().hex[:8]}"
        clean_sess = clean_sess[:55]

        # Use the real production conversational runtime
        if self.runtime is not None and RuntimeTurnRequest is not None:
            t0 = time.perf_counter()
            turn_req = RuntimeTurnRequest(
                conversation_id=clean_sess,
                message=message,
                correlation_id=str(uuid.uuid4()),
                channel="ccc_website",
                reset=bool(payload.get("reset", False)),
                use_durable_memory=False,
                deterministic_context=payload.get("deterministic_context")
            )
            runtime_res = self.runtime.turn(turn_req)
            t1 = time.perf_counter()
            llm_latency_ms = int((t1 - t0) * 1000)

            resp = runtime_res.get("response", {})
            text = resp.get("text", "")
            links = resp.get("links", [])
            
            return {
                "bot_message": text,
                "response": resp,
                "session_id": clean_sess,
                "links": links,
                "journey": resp.get("journey"),
                "resulting_action": resp.get("resulting_action"),
                "recommended_destination": links[0]["url"] if links else None,
                "runtime_source": "ProductionConversationRuntime",
                "llm_latency_ms": llm_latency_ms
            }

        # Fallback to ConversationService if runtime not configured
        return self.service.turn(
            session_id=clean_sess,
            message=message,
            contact_data=payload.get("contact_data"),
        )

    def _handle_get_voices(self) -> None:
        """Return available non-reserved V.I.B.E. voices from registry.json."""
        if not VIBE_REGISTRY_JSON.exists():
            self._json({"error": "Voice registry not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            with open(VIBE_REGISTRY_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            fallback_id = data.get("fallback_voice_id", "builtin-default")
            active_voices = []
            for v_id, prof in data.get("voices", {}).items():
                if prof.get("status") in {"TEST", "APPROVED", "PRIMARY", "FALLBACK"}:
                    active_voices.append({
                        "voice_id": prof["voice_id"],
                        "display_name": prof["display_name"],
                        "voice_type": prof["voice_type"],
                        "status": prof["status"],
                        "is_fallback": prof.get("is_fallback", False)
                    })
            
            kill_switch_active = VIBE_KILL_SWITCH.exists()
            self._json({
                "status": "ok",
                "voice_engine_available": not kill_switch_active,
                "fallback_voice_id": fallback_id,
                "voices": active_voices
            })
        except Exception as e:
            self._json({"error": f"Failed to load voices: {e}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_vibe_synthesize(self, payload: dict[str, Any]) -> None:
        """Bridge exact Budly text to V.I.B.E. synthesis engine router."""
        text = payload.get("text", "").strip()
        voice_id = payload.get("voice_id", "builtin-default").strip()
        session_id = payload.get("session_id", "anon")
        turn_id = str(payload.get("turn_id", int(time.time())))
        engine = payload.get("engine", "kokoro").strip().lower()
        chunk_index = payload.get("chunk_index")
        
        if not text:
            self._json({"error": "Text is required for synthesis"}, HTTPStatus.BAD_REQUEST)
            return

        # Check safety kill switch
        if VIBE_KILL_SWITCH.exists():
            self._json({
                "error": "Voice temporarily unavailable",
                "available": False,
                "kill_switch_active": True
            }, HTTPStatus.SERVICE_UNAVAILABLE)
            return

        # Support splitting sentence chunks for streaming playback
        if payload.get("split_sentences"):
            if vibe_router is not None:
                sentences = vibe_router.split_sentences(text)
            else:
                sentences = [text]
            self._json({
                "status": "ok",
                "sentences": sentences,
                "count": len(sentences)
            })
            return

        # Sanitize filename components
        safe_voice = re.sub(r"[^a-zA-Z0-9_\-]", "", voice_id)
        safe_sess = re.sub(r"[^a-zA-Z0-9_\-]", "", str(session_id))[:12]
        safe_turn = re.sub(r"[^a-zA-Z0-9_\-]", "", str(turn_id))
        chunk_suffix = f"_c{int(chunk_index)}" if chunk_index is not None else ""
        
        filename = f"e2e_{safe_sess}_{safe_turn}{chunk_suffix}_{safe_voice}.wav"
        out_path = VIBE_OUTPUT_DIR / filename
        VIBE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        t_vibe_start = time.perf_counter()
        try:
            if vibe_router is not None:
                # Direct in-process resident synthesis via router
                telemetry = vibe_router.synthesize(
                    text=text,
                    output_path=str(out_path),
                    voice_id=safe_voice,
                    engine_type=engine
                )
                t_vibe_end = time.perf_counter()
                vibe_duration = round(t_vibe_end - t_vibe_start, 4)
                audio_dur = telemetry.get("output_duration_sec", 0.0)
            else:
                # Subprocess fallback to Chatterbox
                cmd = [
                    str(VIBE_PYTHON),
                    str(VIBE_SYNTHESIZE),
                    "--voice", safe_voice,
                    "--text", text,
                    "--out", str(out_path)
                ]
                
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                
                t_vibe_end = time.perf_counter()
                vibe_duration = round(t_vibe_end - t_vibe_start, 4)
                audio_dur = 0.0
                
                if proc.returncode != 0:
                    print(f"[VIBE Bridge Error] Exit {proc.returncode}: {proc.stderr}")
                    self._json({
                        "error": "Voice temporarily unavailable",
                        "available": False,
                        "details": proc.stderr.strip() if "RESERVED" in proc.stderr else "Synthesis error"
                    }, HTTPStatus.SERVICE_UNAVAILABLE)
                    return
                
            if not out_path.exists():
                self._json({"error": "Audio generation failed to produce output file"}, HTTPStatus.INTERNAL_SERVER_ERROR)
                return

            self._json({
                "status": "ok",
                "available": True,
                "audio_id": filename,
                "audio_url": f"/api/vibe/audio/{filename}",
                "voice_id": safe_voice,
                "engine": engine,
                "chunk_index": chunk_index,
                "exact_text_match": True,
                "vibe_input_text": text,
                "synthesis_duration_sec": vibe_duration,
                "output_duration_sec": audio_dur,
                "file_size_bytes": out_path.stat().st_size
            })
        except VIBEKillSwitchError:
            self._json({
                "error": "Voice temporarily unavailable",
                "available": False,
                "kill_switch_active": True
            }, HTTPStatus.SERVICE_UNAVAILABLE)
        except subprocess.TimeoutExpired:
            self._json({"error": "Voice generation timed out", "available": False}, HTTPStatus.GATEWAY_TIMEOUT)
        except Exception as e:
            print(f"[VIBE Bridge Exception] {e}")
            self._json({
                "error": "Voice temporarily unavailable",
                "available": False,
                "details": str(e)
            }, HTTPStatus.SERVICE_UNAVAILABLE)

    def _handle_get_audio(self) -> None:
        """Serve synthesized audio WAV file."""
        filename = Path(self.path.split("?")[0]).name
        if not filename.endswith(".wav") or not re.match(r"^[a-zA-Z0-9_\-\.]+\.wav$", filename):
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid audio filename")
            return
            
        audio_path = VIBE_OUTPUT_DIR / filename
        if not audio_path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Audio file not found")
            return
            
        try:
            file_size = audio_path.stat().st_size
            with open(audio_path, "rb") as f:
                data = f.read()
                
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))

    def _handle_post_telemetry(self, payload: dict[str, Any]) -> None:
        """Record live end-to-end turn telemetry to background jsonl file."""
        record_live_telemetry_event(payload)
        self._json({"status": "ok", "saved_to": str(LIVE_TELEMETRY_FILE)})

    def _handle_debug_telemetry_page(self) -> None:
        """Render a clean admin/debug diagnostic view of live telemetry."""
        events = load_live_telemetry_events()
        rows_html = []
        for i, ev in enumerate(reversed(events), 1):
            status_class = "pass" if ev.get("success") and ev.get("exact_text_match") else "fail"
            rows_html.append(f"""
            <tr>
              <td>{ev.get('timestamp', '')[11:19]}</td>
              <td><code>{ev.get('turn_id', '')}</code></td>
              <td><strong>{ev.get('selected_voice_id', '')}</strong></td>
              <td>{ev.get('customer_input', '')[:40]}</td>
              <td>{(ev.get('budly_response_latency_ms', 0)/1000):.2f}s</td>
              <td>{(ev.get('voice_generation_latency_ms', 0)/1000):.2f}s</td>
              <td>{(ev.get('time_to_first_audio_ms', 0)/1000):.2f}s</td>
              <td class="{status_class}">{'✓ MATCH' if ev.get('exact_text_match') else '✗ MISMATCH'}</td>
              <td><span class="badge {status_class}">{ev.get('voice_status', 'OK')}</span></td>
            </tr>
            """)
        
        table_body = "".join(rows_html) if rows_html else "<tr><td colspan='9' style='text-align:center;color:#666;'>No telemetry turns recorded yet.</td></tr>"

        html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>V.I.B.E. Live Telemetry Diagnostics</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="5">
  <style>
    body {{ font-family: system-ui, -apple-system, sans-serif; background: #0f1912; color: #e1e8e2; margin: 0; padding: 24px; }}
    h1 {{ color: #d8ba70; font-size: 22px; margin-top: 0; }}
    .header-bar {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #234b32; padding-bottom: 12px; margin-bottom: 20px; }}
    .log-path {{ font-size: 12px; color: #8fa093; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; background: #16281c; border-radius: 8px; overflow: hidden; }}
    th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #234b32; }}
    th {{ background: #1d3d29; color: #d8ba70; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.05em; }}
    tr:hover {{ background: #1f3827; }}
    .pass {{ color: #50e386; }}
    .fail {{ color: #e35050; font-weight: bold; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; background: #2a553a; }}
    .badge.pass {{ background: #1a4d2e; color: #6ee7b7; }}
    .badge.fail {{ background: #5c1d1d; color: #fca5a5; }}
    .btn {{ display: inline-block; padding: 6px 14px; border-radius: 6px; background: #234b32; color: #f7f1df; text-decoration: none; font-size: 13px; }}
    .btn:hover {{ background: #326846; }}
  </style>
</head>
<body>
  <div class="header-bar">
    <div>
      <h1>📊 V.I.B.E. Live Background Telemetry</h1>
      <div class="log-path">Writing to: <code>{LIVE_TELEMETRY_FILE}</code> (Total turns: {len(events)})</div>
    </div>
    <div>
      <a href="/" class="btn">← Back to Chat</a>
      <a href="/api/vibe/telemetry" class="btn" target="_blank">Raw JSON</a>
    </div>
  </div>
  <table>
    <thead>
      <tr>
        <th>Time</th>
        <th>Turn ID</th>
        <th>Voice</th>
        <th>User Input</th>
        <th>Budly Latency</th>
        <th>Voice Synth</th>
        <th>TTFA</th>
        <th>Exact Text</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      {table_body}
    </tbody>
  </table>
</body>
</html>"""
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write(f"[Budly Server] {format % args}\n")

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


def make_server(host: str = "0.0.0.0", port: int = 8787, db_path: str | Path | None = None) -> ThreadingHTTPServer:
    runtime = init_production_runtime(ROOT)
    service = ConversationService(db_path)
    handler = type("ConfiguredBudlyHandler", (BudlyHandler,), {"service": service, "runtime": runtime})
    return ThreadingHTTPServer((host, port), handler)


def warmup_engine():
    """Pre-warm resident V.I.B.E. synthesis models in background thread on startup."""
    if vibe_router is not None and not VIBE_KILL_SWITCH.exists():
        try:
            print("[VIBE Bridge] Pre-warming in-memory V.I.B.E. router in background...")
            vibe_router.warmup()
            print("[VIBE Bridge] V.I.B.E. router ready.")
        except Exception as e:
            print(f"[VIBE Bridge] Warmup notice: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Budly Sales customer chat with V.I.B.E. Voice")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=8787, type=int)
    args = parser.parse_args()
    
    # Start VIBE warmup thread
    warmup_thread = threading.Thread(target=warmup_engine, daemon=True)
    warmup_thread.start()
    
    server = make_server(args.host, args.port)
    print(f"Budly Sales & V.I.B.E. Voice Bridge is ready:")
    print(f"  Desktop: http://localhost:{args.port}")
    print(f"  Local Network / Mobile: http://192.168.1.183:{args.port}")
    print(f"  Live Background Telemetry: {LIVE_TELEMETRY_FILE}")
    print(f"  Diagnostics Route: http://localhost:{args.port}/debug/telemetry")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
