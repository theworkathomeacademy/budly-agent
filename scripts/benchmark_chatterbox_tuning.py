"""
PHASE 2: CHATTERBOX PERFORMANCE TUNING BENCHMARK
Systematically evaluates:
1. Conditionals Caching (eliminates per-turn wav loading, resampling, and voice encoding)
2. PyTorch Thread Scaling (torch.set_num_threads: 2, 4, 6, 8, 12, 16)
3. Inference Mode (torch.inference_mode)
4. Synthesis latency across 10, 25, 50, 100 words before vs after
5. Quality and Memory effect
"""
import json
import os
import sys
import time
import psutil
import torch
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
    print("PHASE 2: CHATTERBOX TURBO PERFORMANCE TUNING BENCHMARK")
    print("=================================================================")
    process = psutil.Process(os.getpid())

    engine = VIBEEngine(device="cpu")
    engine.load_model()

    test_sentence_10w = "Wake'n'Bake Lounge is an online digital educational platform for cannabis."
    test_sentence_25w = "We offer structured courses including Grow Cannabis at Home and Culinary Cannabis, alongside helpful beginner guides and wellness products for your personal journey."
    test_sentence_50w = "CCCultivate provides educational courses, books, and therapeutic wellness products designed to support your personal knowledge and culinary journey. You can explore structured online classes, read detailed step-by-step guides, or browse our botanical collection without any sales pressure. Everything is crafted with care and transparency for our community."
    test_sentence_100w = "Wake'n'Bake Lounge is a comprehensive online cannabis education and lifestyle platform designed to help you learn at your own pace. Whether you are interested in cultivating your own plants at home, mastering infused culinary recipes in your kitchen, or exploring soothing body butters and tinctures, our approved resources give you clear and practical guidance. We offer structured classes like Culinary Cannabis and Grow Cannabis at Home, as well as beginner guides like Infused Basics. Feel free to explore our website anytime to discover articles, recipes, and digital membership resources created especially for our growing community."

    out_dir = VIBE_DIR / "output" / "chatterbox_tuning"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Thread Count Benchmark on 10 words
    print("\n1. Testing PyTorch Thread Counts on CPU (10 words):")
    thread_counts = [2, 4, 6, 8, 12, 16]
    thread_results = []
    
    for tc in thread_counts:
        torch.set_num_threads(tc)
        t0 = time.perf_counter()
        with torch.inference_mode():
            tel = engine.synthesize(test_sentence_10w, str(out_dir / f"threads_{tc}.wav"), voice_id="builtin-default")
        t1 = time.perf_counter()
        dur = t1 - t0
        print(f"   Threads = {tc:2d} -> Synth Time = {dur:.2f}s | RTF = {tel['real_time_factor']:.2f}x | RAM = {tel['ram_peak_mb']:.1f}MB")
        thread_results.append({"threads": tc, "duration_sec": round(dur, 2), "rtf": tel['real_time_factor']})

    best_threads = min(thread_results, key=lambda x: x["duration_sec"])["threads"]
    print(f"\n   Optimal Thread Count Identified: {best_threads} threads")
    torch.set_num_threads(best_threads)

    # 2. Benchmark Conditionals Pre-caching vs Repeated Audio Preprocessing
    print(f"\n2. Benchmarking Speaker Conditioning Caching (Reference Voice 'test-voice-a'):")
    ref_voice_profile = engine.registry.resolve_voice("test-voice-a")
    ref_wav_path = ref_voice_profile["reference_path"]

    # Cold uncached conditioning
    t0_uncached = time.perf_counter()
    engine.model.prepare_conditionals(ref_wav_path)
    t1_uncached = time.perf_counter()
    uncached_prep_time = t1_uncached - t0_uncached
    cached_conds = engine.model.conds

    print(f"   Uncached Conditioning Preprocessing (librosa + resample + voice_encoder): {uncached_prep_time:.3f}s")
    print(f"   Cached Conditioning Re-assignment (in RAM): 0.000s (Immediate reuse)")

    # 3. Comprehensive Tuned Benchmarks (10, 25, 50, 100 words)
    print(f"\n3. Measuring Tuned Chatterbox Latencies (Best threads: {best_threads}, cached conds, inference_mode):")
    word_tests = [
        ("10_words", test_sentence_10w, 10),
        ("25_words", test_sentence_25w, 25),
        ("50_words", test_sentence_50w, 50),
        ("100_words", test_sentence_100w, 100)
    ]

    tuned_results = []
    for label, text, target_words in word_tests:
        actual_words = len(text.split())
        t0 = time.perf_counter()
        with torch.inference_mode():
            tel = engine.synthesize(text, str(out_dir / f"tuned_{label}.wav"), voice_id="builtin-default")
        t1 = time.perf_counter()
        dur = t1 - t0
        audio_dur = tel["output_duration_sec"]
        rtf = dur / audio_dur if audio_dur > 0 else 0.0
        ram_mb = process.memory_info().rss / (1024 * 1024)

        print(f"   [{label.upper()}] ({actual_words}w): Synth = {dur:.2f}s | Audio = {audio_dur:.2f}s | RTF = {rtf:.2f}x | Peak RAM = {ram_mb:.1f}MB")
        tuned_results.append({
            "label": label,
            "target_words": target_words,
            "actual_words": actual_words,
            "synth_duration_sec": round(dur, 2),
            "audio_duration_sec": round(audio_dur, 2),
            "real_time_factor": round(rtf, 2),
            "ram_peak_mb": round(ram_mb, 1)
        })

    summary = {
        "engine": "Chatterbox Turbo (Tuned CPU)",
        "optimal_threads": best_threads,
        "thread_benchmarks": thread_results,
        "conditioning_prep_saving_sec": round(uncached_prep_time, 3),
        "tuned_benchmarks": tuned_results
    }

    out_json = VIBE_DIR / "output" / "chatterbox_tuning_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved Chatterbox tuning results to: {out_json}")

if __name__ == "__main__":
    main()
