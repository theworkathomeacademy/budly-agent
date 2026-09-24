"""
Unified V.I.B.E. Multi-Engine Router (VIBE-PERF-001)
Supports pluggable voice synthesis backends:
1. 'kokoro' (Fast Local Engine - Apache 2.0, high-speed ONNX CPU inference)
2. 'chatterbox' (Offline Cloning Engine - MIT License, reference-conditioned CFM)
"""
import os
import re
import sys
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List

VIBE_DIR = Path(r"C:\Users\19196\Documents\VIBE")
VIBE_KILL_SWITCH = VIBE_DIR / "VIBE_DISABLED"
KOKORO_MODEL_DIR = VIBE_DIR / "models-kokoro"
KOKORO_MODEL = KOKORO_MODEL_DIR / "kokoro-v1.0.onnx"
KOKORO_VOICES = KOKORO_MODEL_DIR / "voices-v1.0.bin"

if str(VIBE_DIR) not in sys.path:
    sys.path.insert(0, str(VIBE_DIR))

# Voice presets mapping for fast local engine
KOKORO_VOICE_MAP = {
    "builtin-default": "am_michael",
    "test-voice-a": "am_adam",
    "test-voice-b": "af_bella",
    "test-voice-c": "af_heart",
    "am_michael": "am_michael",
    "am_adam": "am_adam",
    "af_bella": "af_bella",
    "af_heart": "af_heart"
}

class VIBEEngineRouter:
    def __init__(self, default_engine: str = "kokoro"):
        self.default_engine = default_engine
        self._chatterbox_engine = None
        self._kokoro_engine = None
        self._kokoro_lock = threading.Lock()
        self._chatterbox_lock = threading.Lock()
        self._chatterbox_cond_cache = {}

        # Initialize Kokoro if available
        try:
            from kokoro_onnx import Kokoro
            if KOKORO_MODEL.exists() and KOKORO_VOICES.exists():
                print(f"[VIBE Router] Initializing Kokoro ONNX CPU Engine ({KOKORO_MODEL.name})...")
                self._kokoro_engine = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
                print("[VIBE Router] Kokoro Engine loaded successfully.")
        except Exception as e:
            print(f"[VIBE Router] Kokoro init notice: {e}")

        # Initialize Chatterbox if available
        try:
            from synthesize import VIBEEngine
            self._chatterbox_engine = VIBEEngine(device="cpu")
            print("[VIBE Router] Chatterbox Engine initialized.")
        except Exception as e:
            print(f"[VIBE Router] Chatterbox init notice: {e}")

    def warmup(self):
        """Warm up available engines."""
        if self._kokoro_engine is not None:
            with self._kokoro_lock:
                try:
                    self._kokoro_engine.create("Hello.", voice="am_michael", speed=1.0, lang="en-us")
                    print("[VIBE Router] Kokoro Engine warmed up (sub-second ready).")
                except Exception as e:
                    print(f"[VIBE Router] Kokoro warmup notice: {e}")

        if self._chatterbox_engine is not None and not VIBE_KILL_SWITCH.exists():
            with self._chatterbox_lock:
                try:
                    import torch
                    torch.set_num_threads(6)
                    self._chatterbox_engine.load_model()
                    print("[VIBE Router] Chatterbox Engine resident in RAM.")
                except Exception as e:
                    print(f"[VIBE Router] Chatterbox warmup notice: {e}")

    def synthesize(
        self,
        text: str,
        output_path: str,
        voice_id: str = "builtin-default",
        engine_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synthesize speech using the requested engine (or default fast engine).
        """
        if VIBE_KILL_SWITCH.exists():
            raise RuntimeError(f"Safety Kill-Switch Active: {VIBE_KILL_SWITCH}")

        engine = (engine_type or self.default_engine).lower()
        t0 = time.perf_counter()

        # Engine 1: Fast Local Kokoro Engine
        if engine == "kokoro" and self._kokoro_engine is not None:
            import soundfile as sf
            kokoro_voice = KOKORO_VOICE_MAP.get(voice_id, "am_michael")
            clean_text = text.strip()
            
            with self._kokoro_lock:
                samples, sr = self._kokoro_engine.create(clean_text, voice=kokoro_voice, speed=1.0, lang="en-us")
            
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            sf.write(output_path, samples, sr)
            
            t1 = time.perf_counter()
            synth_dur = t1 - t0
            audio_dur = len(samples) / float(sr)
            rtf = synth_dur / audio_dur if audio_dur > 0 else 0.0

            return {
                "engine": "kokoro",
                "requested_voice_id": voice_id,
                "resolved_voice_id": kokoro_voice,
                "output_path": output_path,
                "text": clean_text,
                "synthesis_duration_sec": round(synth_dur, 4),
                "output_duration_sec": round(audio_dur, 4),
                "real_time_factor": round(rtf, 4),
                "status": "SUCCESS"
            }

        # Engine 2: Chatterbox Turbo (Tuned CPU)
        if self._chatterbox_engine is not None:
            import torch
            with self._chatterbox_lock:
                torch.set_num_threads(6)
                with torch.inference_mode():
                    tel = self._chatterbox_engine.synthesize(
                        text=text,
                        output_path=output_path,
                        voice_id=voice_id
                    )
            tel["engine"] = "chatterbox"
            return tel

        raise RuntimeError("No available voice synthesis engine configured")

    def split_sentences(self, text: str) -> List[str]:
        """Split text cleanly on sentence boundaries without altering punctuation or words."""
        # Split after ., !, ? while keeping punctuation attached
        raw_chunks = re.split(r"(?<=[.!?])\s+", text.strip())
        chunks = [c.strip() for c in raw_chunks if c.strip()]
        return chunks if chunks else [text.strip()]
