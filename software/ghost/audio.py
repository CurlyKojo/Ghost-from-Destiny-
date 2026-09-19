"""Microphone capture with a simple energy VAD, and playback with a volume control."""
from __future__ import annotations

import logging
import queue
import threading
import time

import numpy as np

from .config import CONFIG

log = logging.getLogger("ghost.audio")

try:
    import sounddevice as sd
except Exception:  # pragma: no cover - desktop without PortAudio
    sd = None


def _device(name: str, kind: str):
    if not name or sd is None:
        return None
    try:
        return int(name)
    except ValueError:
        pass
    for i, d in enumerate(sd.query_devices()):
        if name.lower() in d["name"].lower() and d[f"max_{kind}_channels"] > 0:
            return i
    log.warning("audio %s device %r not found, using default", kind, name)
    return None


class Mic:
    """Continuous 16 kHz mono capture into a queue of 80 ms frames (1280 samples)."""

    FRAME = 1280

    def __init__(self):
        self.q: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=200)
        self._stream = None

    def start(self):
        if sd is None:
            raise RuntimeError("sounddevice is not available")
        self._stream = sd.InputStream(
            samplerate=CONFIG.sample_rate, channels=1, dtype="int16",
            blocksize=self.FRAME, device=_device(CONFIG.input_device, "input"),
            callback=self._cb)
        self._stream.start()

    def _cb(self, indata, frames, t, status):
        if status:
            log.debug("mic status: %s", status)
        try:
            self.q.put_nowait(indata[:, 0].copy())
        except queue.Full:
            pass

    def read(self, timeout: float | None = None) -> np.ndarray:
        return self.q.get(timeout=timeout)

    def drain(self):
        while not self.q.empty():
            try:
                self.q.get_nowait()
            except queue.Empty:
                break

    def record_utterance(self, on_level=None) -> np.ndarray | None:
        """Record until `vad_silence_s` of quiet after speech, or `vad_max_s` total.
        Returns float32 audio in [-1, 1], or None if nothing was said."""
        self.drain()
        frames, started, last_voice, t0 = [], False, None, time.time()
        while True:
            try:
                f = self.read(timeout=1.0)
            except queue.Empty:
                continue
            x = f.astype(np.float32) / 32768.0
            rms = float(np.sqrt(np.mean(x * x)))
            if on_level:
                on_level(rms)
            frames.append(x)
            now = time.time()
            if rms > CONFIG.vad_threshold:
                started, last_voice = True, now
            if started and last_voice and now - last_voice > CONFIG.vad_silence_s:
                break
            if not started and now - t0 > 4.0:      # nobody spoke
                return None
            if now - t0 > CONFIG.vad_max_s:
                break
        audio = np.concatenate(frames)
        return audio if started else None

    def stop(self):
        if self._stream:
            self._stream.stop(); self._stream.close(); self._stream = None


class Speaker:
    """Blocking playback with a shared volume and an amplitude meter for the eye."""

    def __init__(self):
        self.volume = CONFIG.volume
        self.level = 0.0            # last RMS, read by the eye animation
        self.playing = threading.Event()
        self._dev = _device(CONFIG.output_device, "output")

    def play(self, audio: np.ndarray, rate: int):
        """audio: float32 mono in [-1, 1]."""
        if sd is None:
            log.info("(no audio device) would play %.1fs", len(audio) / rate)
            return
        out = np.clip(audio * self.volume, -1, 1).astype(np.float32)
        self.playing.set()
        hop = rate // 50   # 20 ms meter updates
        try:
            with sd.OutputStream(samplerate=rate, channels=1, dtype="float32", device=self._dev) as s:
                for i in range(0, len(out), hop):
                    blk = out[i:i + hop]
                    self.level = float(np.sqrt(np.mean(blk * blk))) if len(blk) else 0.0
                    s.write(blk)
        finally:
            self.level = 0.0
            self.playing.clear()

    def chime(self, kind: str = "wake"):
        """Tiny synthesized cue: a two-note rising blip for wake, falling for done."""
        rate = 22050
        f = (660, 880) if kind == "wake" else (880, 660) if kind == "done" else (440, 440)
        t = np.linspace(0, 0.09, int(rate * 0.09), endpoint=False)
        env = np.exp(-t * 18)
        tone = np.concatenate([np.sin(2 * np.pi * f[0] * t) * env, np.sin(2 * np.pi * f[1] * t) * env])
        self.play(0.4 * tone.astype(np.float32), rate)
