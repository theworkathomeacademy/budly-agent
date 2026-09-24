"""
Remediation Verification Script for VIBE-E2E-001 Round 1
Tests:
1. Real Budly Conversational Runtime (5 scripted turns)
2. In-memory Resident VIBE Engine synthesis speed (Warm RAM vs cold)
3. Sentence/text latency benchmarks
4. Exact text fidelity
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(r"c:\Users\19196\Documents\Budly\budly-agent")
VIBE_DIR = Path(r"C:\Users\19196\Documents\VIBE")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(VIBE_DIR) not in sys.path:
    sys.path.insert(0, str(VIBE_DIR))

from src.web_app import init_production_runtime, vibe_engine, vibe_lock
from src.budly_runtime.production_runtime import RuntimeTurnRequest

def main():
    print("=================================================================")
    print("VIBE-E2E-001 REMEDIATION: 5-TURN HUMAN SCRIPT VERIFICATION")
    print("=================================================================")

    # Initialize Runtime
    runtime = init_production_runtime(ROOT)
    if runtime is None:
        print("FATAL: Could not initialize ProductionConversationRuntime")
        sys.exit(1)

    # Pre-warm VIBE
    print("\n[VIBE] Pre-warming VIBE Engine...")
    t_w0 = time.perf_counter()
    with vibe_lock:
        load_time = vibe_engine.load_model()
    t_w1 = time.perf_counter()
    print(f"[VIBE] VIBE Engine ready in {load_time:.2f}s (Warmup elapsed: {t_w1 - t_w0:.2f}s)")

    conversation_id = f"conv_e2e_remediation_{int(time.time())}"
    
    script_turns = [
        ("Turn 1", "What is the Wake'n'Bake Lounge?", "test-voice-a"),
        ("Turn 2", "Tell me about the Botanical Coloring Collection.", "test-voice-b"),
        ("Turn 3", "What are the ingredients in your body butter?", "test-voice-c"),
        ("Turn 4", "What can you help me with?", "builtin-default"),
        ("Turn 5", "Tell me more about the book.", "test-voice-a"),
    ]

    out_dir = VIBE_DIR / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    turn_results = []

    for turn_name, user_query, voice_id in script_turns:
        print(f"\n-------------------------------------------------------------")
        print(f"[{turn_name}] USER: \"{user_query}\" (Voice: {voice_id})")
        print(f"-------------------------------------------------------------")

        # 1. Budly Conversational Turn
        t_llm_start = time.perf_counter()
        req = RuntimeTurnRequest(
            conversation_id=conversation_id,
            message=user_query,
            correlation_id=f"00000000-0000-0000-0000-{int(time.time()*1000)%1000000000000:012d}",
            channel="ccc_website"
        )
        res = runtime.turn(req)
        t_llm_end = time.perf_counter()
        llm_latency = t_llm_end - t_llm_start

        response_payload = res.get("response", {})
        bot_text = response_payload.get("text", "")
        intent = response_payload.get("intent", "")
        journey = response_payload.get("journey", "")
        action = response_payload.get("resulting_action", "")
        links = response_payload.get("links", [])
        word_count = len(bot_text.split())

        print(f"Budly Text ({len(bot_text)} chars, {word_count} words | {llm_latency:.2f}s):")
        print(f"  \"{bot_text}\"")
        print(f"Intent: {intent} | Journey: {journey} | Action: {action}")
        if links:
            print(f"Links: {[l['url'] for l in links]}")

        # Check for canned generic failure
        generic_canned_phrase = "I'm here to help you explore products. What would you like to focus on?"
        assert generic_canned_phrase not in bot_text, f"FAILED: Canned generic response detected on {turn_name}!"

        # 2. Resident In-Memory VIBE Voice Synthesis
        out_wav = out_dir / f"remediation_{turn_name.lower().replace(' ', '_')}_{voice_id}.wav"
        t_synth_start = time.perf_counter()
        with vibe_lock:
            telemetry = vibe_engine.synthesize(
                text=bot_text,
                output_path=str(out_wav),
                voice_id=voice_id
            )
        t_synth_end = time.perf_counter()
        synth_latency = t_synth_end - t_synth_start

        audio_len = telemetry.get("output_duration_sec", 0.0)
        rtf = telemetry.get("real_time_factor", 0.0)
        ttfa = llm_latency + synth_latency

        print(f"\nVIBE Voice Synthesis ({voice_id}):")
        print(f"  Output WAV: {out_wav.name} ({out_wav.stat().st_size} bytes)")
        print(f"  Audio Duration: {audio_len:.2f}s")
        print(f"  Synthesis Latency: {synth_latency:.2f}s (RTF: {rtf:.2f}x)")
        print(f"  Time-to-First-Audio (TTFA): {ttfa:.2f}s")
        print(f"  Exact Text Fidelity: {'TRUE' if telemetry['text'] == bot_text else 'FALSE'}")

        turn_results.append({
            "turn": turn_name,
            "query": user_query,
            "voice_id": voice_id,
            "response_text": bot_text,
            "word_count": word_count,
            "char_count": len(bot_text),
            "llm_latency_sec": round(llm_latency, 2),
            "vibe_synth_sec": round(synth_latency, 2),
            "audio_duration_sec": round(audio_len, 2),
            "real_time_factor": round(rtf, 2),
            "time_to_first_audio_sec": round(ttfa, 2),
            "exact_text_match": telemetry['text'] == bot_text,
            "audio_file": out_wav.name
        })

    # Summary table
    print("\n=================================================================")
    print("5-TURN VERIFICATION SUMMARY TABLE")
    print("=================================================================")
    print(f"{'Turn':<8} | {'Voice':<16} | {'Words':<6} | {'LLM(s)':<7} | {'Synth(s)':<8} | {'Audio(s)':<8} | {'RTF':<6} | {'TTFA(s)':<7}")
    print("-" * 80)
    for r in turn_results:
        print(f"{r['turn']:<8} | {r['voice_id']:<16} | {r['word_count']:<6} | {r['llm_latency_sec']:<7.2f} | {r['vibe_synth_sec']:<8.2f} | {r['audio_duration_sec']:<8.2f} | {r['real_time_factor']:<6.2f} | {r['time_to_first_audio_sec']:<7.2f}")

    # Save summary JSON
    summary_file = VIBE_DIR / "output" / "remediation_round1_results.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(turn_results, f, indent=2)
    print(f"\nSaved remediation results to: {summary_file}")

if __name__ == "__main__":
    main()
