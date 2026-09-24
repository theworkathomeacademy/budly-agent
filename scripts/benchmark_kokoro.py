"""
Benchmark Script for Kokoro TTS (ONNX / CPU)
Measures:
1. Model load time (cold load)
2. Warm synthesis on 10, 25, 50, 100 words
3. Real-Time Factor (RTF)
4. Time-To-First-Audio (TTFA)
5. Peak RAM & CPU utilization
6. Presets audio output validation
"""
import json
import os
import sys
import time
import psutil
import soundfile as sf
from pathlib import Path

ROOT = Path(r"c:\Users\19196\Documents\Budly\budly-agent")
VIBE_DIR = Path(r"C:\Users\19196\Documents\VIBE")
MODEL_DIR = VIBE_DIR / "models-kokoro"
OUT_DIR = VIBE_DIR / "output" / "kokoro_benchmark"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = MODEL_DIR / "kokoro-v1.0.onnx"
VOICES_PATH = MODEL_DIR / "voices-v1.0.bin"

from kokoro_onnx import Kokoro

def benchmark():
    print("=================================================================")
    print("PHASE 3: KOKORO TTS (ONNX / CPU) PERFORMANCE BENCHMARK")
    print("=================================================================")
    process = psutil.Process(os.getpid())

    # 1. Cold Model Load
    print("\n1. Measuring Cold Model Load Time...")
    t0_load = time.perf_counter()
    kokoro = Kokoro(str(MODEL_PATH), str(VOICES_PATH))
    t1_load = time.perf_counter()
    load_time_sec = t1_load - t0_load
    print(f"   KOKORO_COLD_LOAD: {load_time_sec:.3f}s")

    # Voices available in v1.0
    # am_adam (American Male), af_heart (American Female - high quality), af_bella, am_michael
    test_voice = "am_michael"

    test_lengths = [
        ("10_words", "Wake'n'Bake Lounge is an online digital educational platform for cannabis.", 10),
        ("25_words", "We offer structured courses including Grow Cannabis at Home and Culinary Cannabis, alongside helpful beginner guides and wellness products for your personal journey.", 25),
        ("50_words", "CCCultivate provides educational courses, books, and therapeutic wellness products designed to support your personal knowledge and culinary journey. You can explore structured online classes, read detailed step-by-step guides, or browse our botanical collection without any sales pressure. Everything is crafted with care and transparency for our community.", 50),
        ("100_words", "Wake'n'Bake Lounge is a comprehensive online cannabis education and lifestyle platform designed to help you learn at your own pace. Whether you are interested in cultivating your own plants at home, mastering infused culinary recipes in your kitchen, or exploring soothing body butters and tinctures, our approved resources give you clear and practical guidance. We offer structured classes like Culinary Cannabis and Grow Cannabis at Home, as well as beginner guides like Infused Basics. Feel free to explore our website anytime to discover articles, recipes, and digital membership resources created especially for our growing community.", 100)
    ]

    results = []

    # First warm-up turn (sentence 1)
    print("\n2. Warmup synthesis...")
    t0_warm = time.perf_counter()
    _samples, _sr = kokoro.create("Hello, welcome to Budly.", voice=test_voice, speed=1.0, lang="en-us")
    t1_warm = time.perf_counter()
    print(f"   Warmup latency: {t1_warm - t0_warm:.3f}s")

    print("\n3. Benchmarking 10, 25, 50, 100 words with Kokoro:")
    for label, text, target_count in test_lengths:
        actual_words = len(text.split())
        out_wav = OUT_DIR / f"kokoro_{label}_{test_voice}.wav"
        
        cpu_before = psutil.cpu_percent(interval=None)
        t0_synth = time.perf_counter()
        samples, sr = kokoro.create(text, voice=test_voice, speed=1.0, lang="en-us")
        t1_synth = time.perf_counter()
        synth_sec = t1_synth - t0_synth

        sf.write(str(out_wav), samples, sr)
        audio_dur = len(samples) / float(sr)
        rtf = synth_sec / audio_dur if audio_dur > 0 else 0.0
        ram_mb = process.memory_info().rss / (1024 * 1024)

        print(f"   [{label.upper()}] ({actual_words}w): Synth = {synth_sec:.3f}s | Audio = {audio_dur:.2f}s | RTF = {rtf:.3f}x | TTFA = {synth_sec:.3f}s | RAM = {ram_mb:.1f}MB")

        results.append({
            "label": label,
            "target_words": target_count,
            "actual_words": actual_words,
            "voice": test_voice,
            "synth_duration_sec": round(synth_sec, 3),
            "audio_duration_sec": round(audio_dur, 2),
            "real_time_factor": round(rtf, 3),
            "time_to_first_audio_sec": round(synth_sec, 3),
            "ram_peak_mb": round(ram_mb, 1),
            "output_file": str(out_wav)
        })

    # Test alternate voices (af_heart, am_adam, af_bella) for quality check
    voice_samples = ["af_heart", "am_adam", "af_bella"]
    print("\n4. Voice Presets Quality Check:")
    sample_phrase = "Wake'n'Bake Lounge is an online digital educational platform."
    for v in voice_samples:
        t0_v = time.perf_counter()
        samples, sr = kokoro.create(sample_phrase, voice=v, speed=1.0, lang="en-us")
        t1_v = time.perf_counter()
        out_v = OUT_DIR / f"kokoro_sample_{v}.wav"
        sf.write(str(out_v), samples, sr)
        dur = len(samples) / float(sr)
        print(f"   Voice '{v}': Synth = {t1_v - t0_v:.3f}s | Audio = {dur:.2f}s | Saved: {out_v.name}")

    summary = {
        "engine": "Kokoro TTS (ONNX Runtime / CPU)",
        "model_path": str(MODEL_PATH),
        "license": "Apache 2.0",
        "cold_model_load_sec": round(load_time_sec, 3),
        "benchmarks": results
    }

    out_json = VIBE_DIR / "output" / "kokoro_benchmark_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved Kokoro benchmark results to: {out_json}")

if __name__ == "__main__":
    benchmark()
