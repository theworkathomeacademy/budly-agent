"""
STAGE B — VOICE PERFORMANCE ONLY
No repeated LLM calls. Tests VIBEEngine resident in-memory model persistence,
word-count benchmarks (10, 25, 50, 100 words), and sentence-boundary chunking.
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

from synthesize import VIBEEngine

def main():
    print("=================================================================")
    print("STAGE B — V.I.B.E. VOICE PERFORMANCE & RESIDENCY BENCHMARK")
    print("=================================================================")

    out_dir = VIBE_DIR / "output" / "stage_b"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Measure Service Startup & Cold Model Load
    t0_startup = time.perf_counter()
    engine = VIBEEngine(device="cpu")
    t1_startup = time.perf_counter()
    startup_sec = t1_startup - t0_startup

    print(f"\n1. Cold Model Loading...")
    t0_load = time.perf_counter()
    load_duration = engine.load_model()
    t1_load = time.perf_counter()
    cold_model_load_sec = t1_load - t0_load
    print(f"   COLD_MODEL_LOAD = {cold_model_load_sec:.2f}s (Internal: {load_duration:.2f}s)")

    # 2. Sequential Synthesis on Same In-Memory Instance (Testing Model Persistence)
    test_sentence = "Welcome to Wake'n'Bake Lounge, where you can explore recipes and guides."
    
    print(f"\n2. Testing Sequential Syntheses for Model Persistence...")
    # First Synth
    t0_s1 = time.perf_counter()
    tel1 = engine.synthesize(text=test_sentence, output_path=str(out_dir / "test_synth_1.wav"), voice_id="builtin-default")
    t1_s1 = time.perf_counter()
    first_synth_sec = t1_s1 - t0_s1
    print(f"   FIRST_SYNTH = {first_synth_sec:.2f}s (Audio: {tel1['output_duration_sec']:.2f}s, Load reported: {tel1['load_duration_sec']:.2f}s)")

    # Second Warm Synth
    t0_s2 = time.perf_counter()
    tel2 = engine.synthesize(text=test_sentence, output_path=str(out_dir / "test_synth_2.wav"), voice_id="builtin-default")
    t1_s2 = time.perf_counter()
    second_warm_synth_sec = t1_s2 - t0_s2
    print(f"   SECOND_WARM_SYNTH = {second_warm_synth_sec:.2f}s (Audio: {tel2['output_duration_sec']:.2f}s, Load reported: {tel2['load_duration_sec']:.2f}s)")

    # Third Warm Synth
    t0_s3 = time.perf_counter()
    tel3 = engine.synthesize(text=test_sentence, output_path=str(out_dir / "test_synth_3.wav"), voice_id="builtin-default")
    t1_s3 = time.perf_counter()
    third_warm_synth_sec = t1_s3 - t0_s3
    print(f"   THIRD_WARM_SYNTH = {third_warm_synth_sec:.2f}s (Audio: {tel3['output_duration_sec']:.2f}s, Load reported: {tel3['load_duration_sec']:.2f}s)")

    persistent_model_pass = (tel2['load_duration_sec'] == 0.0 and tel3['load_duration_sec'] == 0.0)
    print(f"\n   PERSISTENT_MODEL = {'PASS' if persistent_model_pass else 'FAIL'} (No model reload observed)")

    # 3. Word Count Benchmarks (10, 25, 50, 100 words)
    print(f"\n3. Word Count Benchmarks (Warm In-Memory Engine):")
    benchmarks = [
        ("10_words", "Wake'n'Bake Lounge is an online digital educational platform for cannabis.", 10),
        ("25_words", "We offer structured courses including Grow Cannabis at Home and Culinary Cannabis, alongside helpful beginner guides and wellness products for your personal journey.", 25),
        ("50_words", "CCCultivate provides educational courses, books, and therapeutic wellness products designed to support your personal knowledge and culinary journey. You can explore structured online classes, read detailed step-by-step guides, or browse our botanical collection without any sales pressure. Everything is crafted with care and transparency for our community.", 50),
        ("100_words", "Wake'n'Bake Lounge is a comprehensive online cannabis education and lifestyle platform designed to help you learn at your own pace. Whether you are interested in cultivating your own plants at home, mastering infused culinary recipes in your kitchen, or exploring soothing body butters and tinctures, our approved resources give you clear and practical guidance. We offer structured classes like Culinary Cannabis and Grow Cannabis at Home, as well as beginner guides like Infused Basics. Feel free to explore our website anytime to discover articles, recipes, and digital membership resources created especially for our growing community.", 100)
    ]

    word_bench_results = []
    for label, text_sample, target_words in benchmarks:
        actual_words = len(text_sample.split())
        t0_w = time.perf_counter()
        tel_w = engine.synthesize(text=text_sample, output_path=str(out_dir / f"bench_{label}.wav"), voice_id="builtin-default")
        t1_w = time.perf_counter()
        synth_time = t1_w - t0_w
        audio_dur = tel_w["output_duration_sec"]
        rtf = tel_w["real_time_factor"]
        
        print(f"   [{label.upper()}] ({actual_words} words): Synth = {synth_time:.2f}s | Audio = {audio_dur:.2f}s | RTF = {rtf:.2f}x")
        word_bench_results.append({
            "target": target_words,
            "actual_words": actual_words,
            "synth_duration_sec": round(synth_time, 2),
            "audio_duration_sec": round(audio_dur, 2),
            "real_time_factor": round(rtf, 2)
        })

    # 4. Chunking Test (Sentence Boundary Split)
    print(f"\n4. Sentence-Boundary Chunking Test:")
    multi_sentence_text = (
        "Wake'n'Bake Lounge is an online cannabis education platform. "
        "It features educational articles, infused recipes, and cultivation resources. "
        "You can explore all our guides without any pressure."
    )
    
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", multi_sentence_text) if s.strip()]
    print(f"   Total sentences to chunk: {len(sentences)}")
    for i, s in enumerate(sentences, 1):
        print(f"     S{i} ({len(s.split())} words): \"{s}\"")

    t0_chunk = time.perf_counter()
    chunk_timings = []
    chunk_files = []

    for i, s in enumerate(sentences, 1):
        t_s0 = time.perf_counter()
        chunk_file = str(out_dir / f"chunk_sentence_{i}.wav")
        tel_s = engine.synthesize(text=s, output_path=chunk_file, voice_id="builtin-default")
        t_s1 = time.perf_counter()
        dur = t_s1 - t_s0
        chunk_timings.append({
            "sentence_index": i,
            "text": s,
            "words": len(s.split()),
            "synth_sec": round(dur, 2),
            "audio_sec": round(tel_s["output_duration_sec"], 2),
            "file": chunk_file
        })
        chunk_files.append(chunk_file)

    t1_chunk = time.perf_counter()
    total_chunked_time = t1_chunk - t0_chunk
    time_to_first_playable = chunk_timings[0]["synth_sec"]

    print(f"\n   CHUNKED TIMINGS:")
    print(f"     TIME_TO_FIRST_PLAYABLE_AUDIO = {time_to_first_playable:.2f}s (Sentence 1 ready for playback)")
    for ct in chunk_timings:
        print(f"     Sentence {ct['sentence_index']}: {ct['synth_sec']:.2f}s synth -> {ct['audio_sec']:.2f}s audio")
    print(f"     FULL_AUDIO_COMPLETE = {total_chunked_time:.2f}s")

    # Verify chunk fidelity
    reconstructed_text = " ".join([ct["text"] for ct in chunk_timings])
    exact_chunk_match = (reconstructed_text == multi_sentence_text)
    print(f"     Exact Chunk Text Match: {'PASS' if exact_chunk_match else 'FAIL'}")

    stage_b_summary = {
        "PERSISTENT_MODEL": "PASS" if persistent_model_pass else "FAIL",
        "COLD_MODEL_LOAD_SEC": round(cold_model_load_sec, 2),
        "FIRST_SYNTH_SEC": round(first_synth_sec, 2),
        "SECOND_WARM_SYNTH_SEC": round(second_warm_synth_sec, 2),
        "THIRD_WARM_SYNTH_SEC": round(third_warm_synth_sec, 2),
        "WARM_SYNTHESIS_BENCHMARKS": word_bench_results,
        "CHUNKED_FIRST_AUDIO_SEC": round(time_to_first_playable, 2),
        "FULL_AUDIO_COMPLETE_SEC": round(total_chunked_time, 2),
        "CHUNK_TEXT_FIDELITY": "PASS" if exact_chunk_match else "FAIL"
    }

    out_file = ROOT / "scratch" / "stage_b_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(stage_b_summary, f, indent=2)
    print(f"\nStage B results saved to: {out_file}")

if __name__ == "__main__":
    main()
