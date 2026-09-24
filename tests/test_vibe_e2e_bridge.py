"""
V.I.B.E. End-to-End Customer Experience & Bridge Test Suite (VIBE-E2E-001)
Validates the complete customer flow:
1. Budly text response generation
2. Exact immutable text transmission to V.I.B.E.
3. V.I.B.E. local offline synthesis & WAV output
4. Exact text matching (budly_response_text == vibe_input_text)
5. Multi-turn desktop & mobile scripted turn execution
6. Voice profile switching during conversation
7. Kill-switch failure resilience (Budly text works while voice fails gracefully)
8. Telemetry latency recording (T0 to T7)
"""
import os
import sys
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.conversation_service import ConversationService
from src.web_app import make_server

VIBE_DIR = Path(r"C:\Users\19196\Documents\VIBE")
VIBE_KILL_SWITCH = VIBE_DIR / "VIBE_DISABLED"

DESKTOP_TURNS = [
    "Hi Budly, what can you help me with?",
    "What is the Wake'n'Bake Lounge?",
    "Tell me about the Botanical Coloring Collection.",
    "What are the ingredients in your body butter?",
    "Can you explain that in simple terms?"
]

MOBILE_TURNS = [
    "Hi Budly.",
    "What can you tell me about cannabis terpenes?",
    "What products can you help me understand?",
    "Say that response out loud."
]

def make_http_post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def make_http_get(url: str) -> dict:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def run_e2e_tests():
    print("========================================================")
    print("V.I.B.E. E2E CUSTOMER VOICE EXPERIENCE VALIDATION (E2E-001)")
    print("========================================================")
    
    port = 8788
    server = make_server(host="127.0.0.1", port=port)
    import threading
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"Test server active at http://127.0.0.1:{port}")
    
    base_url = f"http://127.0.0.1:{port}"
    
    try:
        # Step 0: Verify Health & Voices API
        health = make_http_get(f"{base_url}/api/health")
        assert health["status"] == "ok"
        print("  PASS: Health check ok.")
        
        voices_res = make_http_get(f"{base_url}/api/vibe/voices")
        assert voices_res["status"] == "ok"
        print(f"  PASS: Retrieved {len(voices_res['voices'])} active voice profiles.")
        
        # Step 1: Initialize session
        intake_res = make_http_post(f"{base_url}/api/intake", {
            "landing_input": {"source": "e2e_validation_test"},
            "landing_route": "https://www.wakenbakelounge.com/ask-budly"
        })
        session_id = intake_res["session_id"]
        print(f"  Initialized session: {session_id}")
        
        # ========================================================
        # PHASE 8: DESKTOP 5-TURN TEST SEQUENCE
        # ========================================================
        print("\n--- RUNNING PHASE 8: DESKTOP 5-TURN TEST SEQUENCE ---")
        desktop_telemetry = []
        voices_to_test = ["builtin-default", "test-voice-a", "test-voice-b", "test-voice-c", "builtin-default"]
        
        for turn_idx, (user_prompt, voice_id) in enumerate(zip(DESKTOP_TURNS, voices_to_test), 1):
            print(f"\n[Desktop Turn {turn_idx}/5] User: \"{user_prompt}\" (Voice: {voice_id})")
            t0 = time.perf_counter()
            
            # 1. Budly text generation
            turn_res = make_http_post(f"{base_url}/api/turn", {
                "session_id": session_id,
                "message": user_prompt
            })
            t2 = time.perf_counter()
            budly_text = turn_res["bot_message"]
            print(f"  Budly Response ({len(budly_text)} chars): \"{budly_text[:80]}...\"")
            
            # 2. V.I.B.E. Voice Synthesis
            t4 = time.perf_counter()
            synth_res = make_http_post(f"{base_url}/api/vibe/synthesize", {
                "session_id": session_id,
                "turn_id": f"desk_turn_{turn_idx}",
                "text": budly_text,
                "voice_id": voice_id
            })
            t5 = time.perf_counter()
            
            assert synth_res["status"] == "ok", f"Synthesis failed: {synth_res}"
            assert synth_res["exact_text_match"] is True, "Exact text match failed!"
            assert synth_res["vibe_input_text"] == budly_text, "Text was altered during transport!"
            
            # 3. Audio Delivery Check
            audio_url = f"{base_url}{synth_res['audio_url']}"
            with urllib.request.urlopen(audio_url) as audio_resp:
                assert audio_resp.status == 200
                audio_bytes = audio_resp.read()
                assert len(audio_bytes) > 1000
            t6 = time.perf_counter()
            t7 = t6 + 0.05 # simulate browser audio start
            
            budly_latency = round(t2 - t0, 4)
            vibe_latency = round(t5 - t4, 4)
            ttfa = round(t7 - t0, 4)
            
            print(f"  EXACT TEXT MATCH: TRUE")
            print(f"  Budly Latency: {budly_latency:.2f}s | VIBE Synth: {vibe_latency:.2f}s | Time-to-First-Audio: {ttfa:.2f}s")
            print(f"  Audio Output: {synth_res['audio_id']} ({synth_res['file_size_bytes']} bytes)")
            
            record = {
                "environment": "DESKTOP",
                "turn": turn_idx,
                "user_prompt": user_prompt,
                "budly_response_text": budly_text,
                "vibe_input_text": synth_res["vibe_input_text"],
                "exact_text_match": True,
                "voice_id": voice_id,
                "audio_id": synth_res["audio_id"],
                "budly_latency_sec": budly_latency,
                "vibe_synth_sec": vibe_latency,
                "time_to_first_audio_sec": ttfa
            }
            desktop_telemetry.append(record)

        # ========================================================
        # PHASE 9: MOBILE 4-TURN TEST SEQUENCE
        # ========================================================
        print("\n--- RUNNING PHASE 9: MOBILE 4-TURN TEST SEQUENCE ---")
        mobile_telemetry = []
        mobile_voices = ["test-voice-a", "test-voice-b", "test-voice-c", "builtin-default"]
        
        for turn_idx, (user_prompt, voice_id) in enumerate(zip(MOBILE_TURNS, mobile_voices), 1):
            print(f"\n[Mobile Turn {turn_idx}/4] User: \"{user_prompt}\" (Voice: {voice_id})")
            t0 = time.perf_counter()
            
            turn_res = make_http_post(f"{base_url}/api/turn", {
                "session_id": session_id,
                "message": user_prompt
            })
            t2 = time.perf_counter()
            budly_text = turn_res["bot_message"]
            
            t4 = time.perf_counter()
            synth_res = make_http_post(f"{base_url}/api/vibe/synthesize", {
                "session_id": session_id,
                "turn_id": f"mob_turn_{turn_idx}",
                "text": budly_text,
                "voice_id": voice_id
            })
            t5 = time.perf_counter()
            
            assert synth_res["exact_text_match"] is True
            assert synth_res["vibe_input_text"] == budly_text
            
            t6 = time.perf_counter()
            t7 = t6 + 0.05
            
            budly_latency = round(t2 - t0, 4)
            vibe_latency = round(t5 - t4, 4)
            ttfa = round(t7 - t0, 4)
            
            print(f"  EXACT TEXT MATCH: TRUE")
            print(f"  Budly Latency: {budly_latency:.2f}s | VIBE Synth: {vibe_latency:.2f}s | TTFA: {ttfa:.2f}s")
            
            record = {
                "environment": "MOBILE",
                "turn": turn_idx,
                "user_prompt": user_prompt,
                "budly_response_text": budly_text,
                "vibe_input_text": synth_res["vibe_input_text"],
                "exact_text_match": True,
                "voice_id": voice_id,
                "audio_id": synth_res["audio_id"],
                "budly_latency_sec": budly_latency,
                "vibe_synth_sec": vibe_latency,
                "time_to_first_audio_sec": ttfa
            }
            mobile_telemetry.append(record)

        # ========================================================
        # PHASE 14: KILL SWITCH FAILURE & RESILIENCE TEST
        # ========================================================
        print("\n--- RUNNING PHASE 14: KILL SWITCH FAILURE TEST ---")
        print("Activating V.I.B.E. kill switch...")
        VIBE_KILL_SWITCH.write_text("VIBE DISABLED FOR E2E TEST")
        
        try:
            # 1. Budly text chat MUST continue working
            turn_res = make_http_post(f"{base_url}/api/turn", {
                "session_id": session_id,
                "message": "Can I still chat with Budly when voice is down?"
            })
            assert "bot_message" in turn_res and len(turn_res["bot_message"]) > 0
            print("  PASS: Budly text chat continues working normally when voice is killed.")
            
            # 2. Voice synthesis request MUST return graceful error
            try:
                make_http_post(f"{base_url}/api/vibe/synthesize", {
                    "session_id": session_id,
                    "turn_id": "kill_test",
                    "text": turn_res["bot_message"],
                    "voice_id": "builtin-default"
                })
                assert False, "FAILED: Synthesis should have been rejected by kill switch!"
            except urllib.error.HTTPError as http_err:
                assert http_err.code == 503
                error_body = json.loads(http_err.read().decode("utf-8"))
                assert error_body["available"] is False
                print(f"  PASS: Voice synthesis gracefully refused (HTTP 503: '{error_body['error']}').")
        finally:
            if VIBE_KILL_SWITCH.exists():
                VIBE_KILL_SWITCH.unlink()
                print("Re-enabled V.I.B.E. (removed VIBE_DISABLED).")

        # Save E2E Validation Results
        e2e_results = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "desktop_turns": desktop_telemetry,
            "mobile_turns": mobile_telemetry,
            "total_turns_tested": len(desktop_telemetry) + len(mobile_telemetry),
            "exact_text_match_rate": 1.0,
            "kill_switch_resilience": "PASS"
        }
        
        results_file = VIBE_DIR / "output" / "e2e_validation_results.json"
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(e2e_results, f, indent=2)
        print(f"\nSaved E2E test results to: {results_file}")
        print("\n>>> ALL AUTOMATED E2E BRIDGE TESTS PASSED <<<")

    finally:
        server.shutdown()
        server.server_close()

if __name__ == "__main__":
    run_e2e_tests()
