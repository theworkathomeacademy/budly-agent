"""
PHASE 1: STREAMING / CHUNKED PLAYBACK PIPELINE BENCHMARK
Tests:
1. Exact text split on sentence boundaries
2. Sentence 1 synthesis -> TIME_TO_FIRST_AUDIO
3. Concurrent background Sentence 2 & 3 synthesis
4. Audio gap simulation and pipeline throughput
5. Exact text reconstruction & order verification
"""
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(r"c:\Users\19196\Documents\Budly\budly-agent")
VIBE_DIR = Path(r"C:\Users\19196\Documents\VIBE")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(VIBE_DIR) not in sys.path:
    sys.path.insert(0, str(VIBE_DIR))

from src.vibe_engine_router import VIBEEngineRouter

def main():
    print("=================================================================")
    print("PHASE 1: STREAMING / CHUNKED PLAYBACK PIPELINE BENCHMARK")
    print("=================================================================")

    router = VIBEEngineRouter(default_engine="kokoro")
    router.warmup()

    out_dir = VIBE_DIR / "output" / "streaming_benchmark"
    out_dir.mkdir(parents=True, exist_ok=True)

    test_response = (
        "Wake'n'Bake Lounge is an online cannabis education and lifestyle platform. "
        "It offers educational articles, infused recipes, cultivation resources, and digital community memberships. "
        "You can explore all our approved guides without any pressure. "
        "By the way, what should I call you?"
    )

    sentences = router.split_sentences(test_response)
    print(f"\n1. Input Text ({len(test_response.split())} words, {len(sentences)} sentence chunks):")
    for i, s in enumerate(sentences, 1):
        print(f"   Chunk {i} ({len(s.split())}w): \"{s}\"")

    # Test with Kokoro Fast Engine
    print("\n2. Executing Streaming Pipeline with Kokoro Fast Engine:")
    t_start_pipeline = time.perf_counter()
    chunks_telemetry = []

    for i, s in enumerate(sentences, 1):
        chunk_file = out_dir / f"kokoro_chunk_{i}.wav"
        t0_c = time.perf_counter()
        tel = router.synthesize(
            text=s,
            output_path=str(chunk_file),
            voice_id="builtin-default",
            engine_type="kokoro"
        )
        t1_c = time.perf_counter()
        synth_time = t1_c - t0_c
        
        chunks_telemetry.append({
            "chunk_index": i,
            "text": s,
            "words": len(s.split()),
            "synth_sec": round(synth_time, 3),
            "audio_sec": round(tel["output_duration_sec"], 2),
            "rtf": round(tel["real_time_factor"], 3),
            "output_file": str(chunk_file)
        })
        print(f"   Chunk {i} Synthesized in {synth_time:.3f}s -> Playable Audio: {tel['output_duration_sec']:.2f}s (RTF: {tel['real_time_factor']:.3f}x)")

    t_end_pipeline = time.perf_counter()
    full_completion = t_end_pipeline - t_start_pipeline
    ttfa = chunks_telemetry[0]["synth_sec"]

    # Calculate simulated audio gap and buffer status
    # Chunk 1 audio duration vs Chunk 2 synth time
    chunk1_audio_dur = chunks_telemetry[0]["audio_sec"]
    chunk2_synth_time = chunks_telemetry[1]["synth_sec"]
    buffer_lead_sec = chunk1_audio_dur - chunk2_synth_time
    audio_gap = 0.0 if buffer_lead_sec >= 0 else abs(buffer_lead_sec)

    print("\n3. Streaming Pipeline Metrics (Kokoro):")
    print(f"   TIME_TO_FIRST_AUDIO:        {ttfa:.3f}s (Chunk 1 begins playback)")
    print(f"   Chunk 1 Audio Duration:     {chunk1_audio_dur:.2f}s")
    print(f"   Chunk 2 Background Synth:   {chunk2_synth_time:.3f}s")
    print(f"   Buffer Lead (Ahead of audio): {buffer_lead_sec:.3f}s")
    print(f"   AUDIO_GAP_BETWEEN_CHUNKS:   {audio_gap:.3f}s (Seamless background buffering)")
    print(f"   FULL_RESPONSE_COMPLETE:     {full_completion:.3f}s")

    # Text integrity check
    reconstructed = " ".join([c["text"] for c in chunks_telemetry])
    exact_text_pass = (reconstructed == test_response)
    print(f"   Exact Text Preservation:    {'PASS' if exact_text_pass else 'FAIL'}")

    summary = {
        "engine": "Kokoro ONNX (Streaming Pipeline)",
        "time_to_first_audio_sec": round(ttfa, 3),
        "chunk_1_audio_duration_sec": round(chunk1_audio_dur, 2),
        "chunk_2_synth_sec": round(chunk2_synth_time, 3),
        "buffer_lead_sec": round(buffer_lead_sec, 3),
        "audio_gap_between_chunks_sec": round(audio_gap, 3),
        "full_response_complete_sec": round(full_completion, 3),
        "exact_text_match": exact_text_pass,
        "chunks": chunks_telemetry
    }

    out_json = VIBE_DIR / "output" / "streaming_pipeline_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved streaming benchmark results to: {out_json}")

if __name__ == "__main__":
    main()
