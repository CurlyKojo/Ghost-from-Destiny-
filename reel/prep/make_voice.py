#!/usr/bin/env python3
"""The Ghost's lines for the reel, in the project's own voice.

Same chain as the device: Piper `en_US-ryan-medium`, then `ghost_fx()` from
software/ghost/tts.py (loaded from that file, not copied).  No game audio, no cloned voice.

Writes assets/voice.wav (the whole 14-bar track, silent except for the lines) and
assets/voice.json (line timings plus a 30 fps loudness envelope that drives the eye and
the LED ring, the way `level` does on the device).
"""
import json
import os
import subprocess
import sys
import tarfile
import urllib.request
import wave

import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(HERE, "..", "assets")
VOICE_DIR = os.path.join(OUT, "voice")
MODEL = os.path.join(VOICE_DIR, "en-us-ryan-medium.onnx")
# same voice install.sh fetches from Hugging Face; this is the upstream release mirror
URL = "https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-en-us-ryan-medium.tar.gz"

BPM, FPS, BARS, RATE = 110.0, 30, 14, 48000
BEAT = 60.0 / BPM
# (beat index from the start of the reel, text).  Bar n starts at beat 4*(n-1).
LINES = [
    (34, "I'm here."),                       # bar 9, beat 3: right after the drop
    (41, "Clear skies, seventy-one."),       # bar 11, beat 2
    (45, "Ten minutes. I'm counting."),      # bar 12, beat 2
    (49, "Lights out. I'll keep watch."),    # bar 13, beat 2
]


def ghost_fx_from_repo():
    src = open(os.path.join(REPO, "software", "ghost", "tts.py")).read()
    a = src.index("def ghost_fx")
    ns = {"np": np}
    exec(src[a:src.index("# ---", a)], ns)
    return ns["ghost_fx"]


def main():
    os.makedirs(VOICE_DIR, exist_ok=True)
    if not os.path.exists(MODEL):
        tgz = os.path.join(VOICE_DIR, "voice.tar.gz")
        if len(sys.argv) > 1:
            tgz = sys.argv[1]
        else:
            subprocess.run(["curl", "-sSL", "-o", tgz, URL], check=True)
        with tarfile.open(tgz) as t:
            t.extractall(VOICE_DIR)
    from piper import PiperVoice
    voice = PiperVoice.load(MODEL)
    fx = ghost_fx_from_repo()
    src_rate = voice.config.sample_rate
    total = int(round(BARS * 4 * BEAT * RATE))
    track = np.zeros(total, np.float32)
    info = []
    for beat, text in LINES:
        raw = np.concatenate([c.audio_float_array for c in voice.synthesize(text)])
        y = fx(raw, src_rate, 1.06)                       # GHOST_VOICE_PITCH default
        y = signal.resample_poly(y, RATE, src_rate).astype(np.float32)
        loud = np.where(np.abs(y) > 0.02)[0]
        y = y[max(loud[0] - int(0.01 * RATE), 0): loud[-1] + int(0.12 * RATE)]
        fade = int(0.01 * RATE)
        y[:fade] *= np.linspace(0, 1, fade); y[-fade:] *= np.linspace(1, 0, fade)
        start = int(round(beat * BEAT * RATE))
        track[start:start + len(y)] += y[: total - start]
        info.append({"beat": beat, "text": text, "start": beat * BEAT, "duration": len(y) / RATE})
        print(f"  beat {beat:2d}  {beat * BEAT:6.2f}s  {len(y) / RATE:.2f}s  {text}")
    track = np.clip(track * 0.95, -1, 1)
    with wave.open(os.path.join(OUT, "voice.wav"), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(RATE)
        st = np.repeat((track * 32767).astype("<i2")[:, None], 2, axis=1)
        w.writeframes(st.tobytes())
    # loudness envelope per video frame, 0..1
    n = int(np.ceil(BARS * 4 * BEAT * FPS))
    hop = RATE / FPS
    env = np.array([np.sqrt(np.mean(track[int(i * hop): int((i + 1) * hop)] ** 2) + 1e-12) for i in range(n)])
    env = np.clip(env / (np.percentile(env[env > 0.01], 90) if (env > 0.01).any() else 1), 0, 1)
    json.dump({"fps": FPS, "lines": info, "envelope": [round(float(v), 3) for v in env]},
              open(os.path.join(OUT, "voice.json"), "w"))
    print(f"wrote assets/voice.wav ({total / RATE:.2f}s) and voice.json")


if __name__ == "__main__":
    main()
