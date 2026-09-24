"""
STAGE A — REAL BUDLY TEXT CONVERSATION ONLY
Voice is completely DISABLED. No Chatterbox, no WAV, no VIBEEngine.
Tests:
Turn 1: "What is the Wake'n'Bake Lounge?"
Turn 2: "Tell me about the Botanical Coloring Collection."
Turn 3: "What are the ingredients in your body butter?"
Turn 4: "What can you help me with?"
Turn 5: "Tell me more about the book."
"""
import json
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(r"c:\Users\19196\Documents\Budly\budly-agent")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.budly_runtime.config import ProductionSettings
from src.budly_runtime.production_runtime import ProductionConversationRuntime, RuntimeTurnRequest

def main():
    print("=================================================================")
    print("STAGE A — REAL BUDLY TEXT CONVERSATION VALIDATION (VOICE DISABLED)")
    print("=================================================================")

    # 1. Initialize Runtime
    env_file = ROOT / ".env"
    env_dict = dict(os.environ)
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_dict[k.strip()] = v.strip()
    settings = ProductionSettings.from_environment(env_dict)
    runtime = ProductionConversationRuntime(settings, ROOT)
    print(f"Runtime Initialized: Model={settings.model_name}, Provider={settings.model_provider}, Env={settings.environment}")

    conversation_id = f"conv_stage_a_{uuid.uuid4().hex[:12]}"
    print(f"Active Conversation ID: {conversation_id}\n")

    turns = [
        ("Turn 1", "What is the Wake'n'Bake Lounge?"),
        ("Turn 2", "Tell me about the Botanical Coloring Collection."),
        ("Turn 3", "What are the ingredients in your body butter?"),
        ("Turn 4", "What can you help me with?"),
        ("Turn 5", "Tell me more about the book.")
    ]

    results = []

    for turn_name, user_msg in turns:
        print(f"-----------------------------------------------------------------")
        print(f"[{turn_name}] CUSTOMER: \"{user_msg}\"")
        print(f"-----------------------------------------------------------------")

        # Capture retrieval info
        domain = runtime._knowledge_domain(user_msg)
        session = runtime.sessions.acquire(conversation_id)
        if not domain:
            domain = runtime._session_knowledge_domain(session)
        
        t0 = time.perf_counter()
        req = RuntimeTurnRequest(
            conversation_id=conversation_id,
            message=user_msg,
            correlation_id=str(uuid.uuid4()),
            channel="ccc_website"
        )
        res = runtime.turn(req)
        t1 = time.perf_counter()
        latency = t1 - t0

        resp = res.get("response", {})
        text = resp.get("text", "")
        intent = resp.get("intent", "")
        journey = resp.get("journey")
        action = resp.get("resulting_action")
        evidence = res.get("evidence", {})
        knowledge_used = evidence.get("knowledge_used", False)
        
        fallback_invoked = bool(
            action == "legacy_guided_flow" or 
            intent == "safe_fallback" or
            "The guided Budly experience is still available" in text or
            "I couldn’t validate that answer" in text
        )

        generic_canned = ("I'm here to help you explore products. What would you like to focus on?" in text)

        print(f"Budly Response ({len(text)} chars, {len(text.split())} words | {latency:.2f}s):")
        print(f"  \"{text}\"")
        print(f"\nDiagnostics:")
        print(f"  Conversation ID:  {conversation_id}")
        print(f"  Runtime Path:     ProductionConversationRuntime.turn")
        print(f"  Model Provider:   {settings.model_provider} ({settings.model_name})")
        print(f"  Retrieval Domain: {domain}")
        print(f"  Knowledge Used:   {knowledge_used}")
        print(f"  Intent:           {intent}")
        print(f"  Journey:          {journey}")
        print(f"  Action:           {action}")
        print(f"  Fallback Invoked: {'YES' if fallback_invoked else 'NO'}")
        print(f"  Canned Repetition:{'DETECTED' if generic_canned else 'NO'}")

        turn_data = {
            "turn": turn_name,
            "customer_input": user_msg,
            "budly_response": text,
            "response_latency_sec": round(latency, 2),
            "conversation_id": conversation_id,
            "runtime_path": "ProductionConversationRuntime.turn",
            "model_provider": f"{settings.model_provider}:{settings.model_name}",
            "retrieval_domain": domain,
            "knowledge_used": knowledge_used,
            "intent": intent,
            "journey": journey,
            "resulting_action": action,
            "validation_result": "PASS" if not fallback_invoked else "FALLBACK",
            "fallback_invoked": fallback_invoked,
            "generic_canned": generic_canned
        }
        results.append(turn_data)

        # Fail fast conditions
        if generic_canned:
            print(f"\n[FAIL FAST] Generic canned response detected on {turn_name}!")
            break
        if turn_name in {"Turn 1", "Turn 2"} and fallback_invoked:
            print(f"\n[FAIL FAST] Turn 1 or Turn 2 failed validation/fallback!")
            break

    # Summary
    all_passed = len(results) == 5 and all(not r["fallback_invoked"] and not r["generic_canned"] for r in results)
    print("\n=================================================================")
    print(f"STAGE A SUMMARY: {'REAL_BUDLY_TEXT_CONVERSATION = PASS' if all_passed else 'REAL_BUDLY_TEXT_CONVERSATION = FAIL'}")
    print("=================================================================")
    
    out_file = ROOT / "scratch" / "stage_a_results.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"status": "PASS" if all_passed else "FAIL", "results": results}, f, indent=2)
    print(f"Stage A results saved to: {out_file}")

if __name__ == "__main__":
    main()
