"""Text to speech.

Default engine is Piper (offline, fast on a Pi 4) using a warm male voice, then a light
"Ghost" filter chain: a small pitch lift, a presence boost, a very short metallic slap
delay and a soft limiter.  It lands in the neighbourhood of the game's Ghost without
cloning anyone's voice.  ElevenLabs is available as an optional cloud engine.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import Tuple

import numpy as np

from .config import CONFIG

log = logging.getLogger("ghost.tts")


# ---------------------------------------------------------------------------
# the Ghost filter
# ---------------------------------------------------------------------------
def ghost_fx(x: np.ndarray, rate: int, pitch: float = 1.0) -> np.ndarray:
    from scipy import signal

    y = x.astype(np.float32)
    # 1. pitch shift by resampling (also shortens; we keep it subtle, 1.03-1.08)
    if abs(pitch - 1.0) > 1e-3:
        n = int(len(y) / pitch)
        y = signal.resample(y, n).astype(np.float32)
    # 2. high-pass 140 Hz: the Ghost is small, no chest
    b, a = signal.butter(2, 140 / (rate / 2), "high")
    y = signal.lfilter(b, a, y)
    # 3. presence peak ~2.8 kHz (+4 dB) and a slight 5 kHz sheen
    for f0, gain_db, q in ((2800, 4.0, 1.2), (5000, 2.0, 1.5)):
        A = 10 ** (gain_db / 40)
        w0 = 2 * np.pi * f0 / rate
        alpha = np.sin(w0) / (2 * q)
        b = [1 + alpha * A, -2 * np.cos(w0), 1 - alpha * A]
        a = [1 + alpha / A, -2 * np.cos(w0), 1 - alpha / A]
        y = signal.lfilter(np.array(b) / a[0], np.array(a) / a[0], y)
    # 4. tiny metallic slapback (9 ms, -14 dB) + a whisper of a second tap
    d1, d2 = int(rate * 0.009), int(rate * 0.021)
    out = y.copy()
    out[d1:] += 0.20 * y[:-d1]
    out[d2:] += 0.08 * y[:-d2]
    # 5. soft limiter
    out = np.tanh(out * 1.6) / np.tanh(1.6)
    peak = np.max(np.abs(out)) or 1.0
    return (out / peak * 0.9).astype(np.float32)


# ---------------------------------------------------------------------------
class PiperTTS:
    def __init__(self):
        self.model = CONFIG.piper_model
        if not os.path.exists(self.model):
            raise FileNotFoundError(f"Piper voice not found: {self.model} (run install.sh)")
        self.rate = 22050
        cfg = self.model + ".json"
        if os.path.exists(cfg):
            import json
            with open(cfg) as f:
                self.rate = int(json.load(f).get("audio", {}).get("sample_rate", 22050))
        self.exe = shutil.which("piper") or os.path.join(os.path.dirname(os.sys.executable), "piper")

    def synth(self, text: str) -> Tuple[np.ndarray, int]:
        cmd = [self.exe, "--model", self.model, "--output-raw",
               "--length-scale", str(CONFIG.piper_length_scale), "--sentence-silence", "0.15"]
        p = subprocess.run(cmd, input=text.encode("utf-8"), capture_output=True, timeout=60)
        if p.returncode != 0:
            raise RuntimeError(f"piper failed: {p.stderr.decode(errors='ignore')[-300:]}")
        audio = np.frombuffer(p.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        return audio, self.rate


class ElevenLabsTTS:
    """Optional cloud voice.  Set GHOST_TTS=elevenlabs, ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID.
    Use a voice you designed or own; don't clone a real actor's voice."""

    def __init__(self):
        import requests  # noqa
        self.key = os.environ.get("ELEVENLABS_API_KEY", "")
        self.voice = CONFIG.elevenlabs_voice_id
        if not self.key or not self.voice:
            raise RuntimeError("ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID are required")
        self.rate = 22050

    def synth(self, text: str) -> Tuple[np.ndarray, int]:
        import requests
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice}",
            params={"output_format": "pcm_22050"},
            headers={"xi-api-key": self.key},
            json={"text": text, "model_id": "eleven_turbo_v2_5",
                  "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.35}},
            timeout=30)
        r.raise_for_status()
        audio = np.frombuffer(r.content, dtype=np.int16).astype(np.float32) / 32768.0
        return audio, self.rate


class Voice:
    """Engine + Ghost filter.  synth() returns (float32 audio, sample_rate)."""

    def __init__(self):
        if CONFIG.tts_engine == "elevenlabs":
            self.engine = ElevenLabsTTS()
        else:
            self.engine = PiperTTS()
        log.info("tts engine: %s", type(self.engine).__name__)

    def synth(self, text: str) -> Tuple[np.ndarray, int]:
        audio, rate = self.engine.synth(text)
        if CONFIG.voice_fx and len(audio) > 0:
            audio = ghost_fx(audio, rate, CONFIG.voice_pitch)
        return audio, rate
