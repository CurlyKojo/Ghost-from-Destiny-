"""Pan/tilt gestures through a PCA9685 servo driver (I2C).

Gestures are tiny scripted moves with easing, run on a background thread so they never
block speech.  Tilt is clamped to +-tilt_range: the printed arm clears +-15 degrees.
"""
from __future__ import annotations

import logging
import math
import random
import threading
import time

from .config import CONFIG

log = logging.getLogger("ghost.motion")


class Body(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="motion")
        self.kit = None
        self._q: list[tuple[str, float]] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self.pan, self.tilt = 0.0, 0.0            # degrees from centre
        if CONFIG.servos:
            try:
                from adafruit_servokit import ServoKit
                self.kit = ServoKit(channels=16)
                for ch in (CONFIG.servo_pan_ch, CONFIG.servo_tilt_ch):
                    self.kit.servo[ch].set_pulse_width_range(500, 2500)
                self._write(0, 0)
                log.info("servos ready on PCA9685")
            except Exception as e:
                log.warning("no servos (%s)", e)

    # ------------------------------------------------------------------
    def gesture(self, name: str, strength: float = 1.0):
        with self._lock:
            self._q.append((name, strength))

    def mood(self, emotion: str):
        """Map an emotion tag to body language."""
        table = {
            "happy": "bounce", "excited": "wiggle", "curious": "tilt_curious", "thinking": "look_up",
            "worried": "shrink", "sad": "droop", "surprised": "recoil", "annoyed": "shake",
            "smug": "tilt_curious", "sleepy": "droop", "listening": "lean_in", "neutral": "center",
        }
        g = table.get(emotion)
        if g:
            self.gesture(g)

    # ------------------------------------------------------------------
    def _write(self, pan: float, tilt: float):
        pan = max(-CONFIG.pan_range, min(CONFIG.pan_range, pan))
        tilt = max(-CONFIG.tilt_range, min(CONFIG.tilt_range, tilt))
        self.pan, self.tilt = pan, tilt
        if self.kit:
            try:
                self.kit.servo[CONFIG.servo_pan_ch].angle = CONFIG.pan_center + pan
                self.kit.servo[CONFIG.servo_tilt_ch].angle = CONFIG.tilt_center + tilt
            except Exception as e:
                log.debug("servo write failed: %s", e)

    def _move(self, pan: float, tilt: float, dur: float):
        p0, t0 = self.pan, self.tilt
        steps = max(2, int(dur * 50))
        for i in range(1, steps + 1):
            s = i / steps
            s = s * s * (3 - 2 * s)                     # smoothstep
            self._write(p0 + (pan - p0) * s, t0 + (tilt - t0) * s)
            time.sleep(dur / steps)

    def _run_gesture(self, name: str, k: float):
        R, T = CONFIG.pan_range, CONFIG.tilt_range
        if name == "center":
            self._move(0, 0, 0.6)
        elif name == "bounce":
            self._move(self.pan, T * 0.5 * k, 0.18); self._move(self.pan, -T * 0.2 * k, 0.18); self._move(self.pan, 0, 0.25)
        elif name == "wiggle":
            for _ in range(2):
                self._move(R * 0.25 * k, T * 0.3, 0.14); self._move(-R * 0.25 * k, -T * 0.3, 0.14)
            self._move(0, 0, 0.25)
        elif name == "tilt_curious":
            self._move(R * 0.15 * random.choice((-1, 1)), -T * 0.6 * k, 0.4)
        elif name == "look_up":
            self._move(R * 0.2 * random.choice((-1, 1)), -T * 0.9, 0.5)
        elif name == "lean_in":
            self._move(0, T * 0.5, 0.35)
        elif name == "shrink":
            self._move(0, T * 0.6, 0.4)
        elif name == "droop":
            self._move(self.pan * 0.5, T * 0.95, 0.9)
        elif name == "recoil":
            self._move(0, -T, 0.12); time.sleep(0.2); self._move(0, 0, 0.5)
        elif name == "shake":
            for _ in range(2):
                self._move(R * 0.35 * k, self.tilt, 0.13); self._move(-R * 0.35 * k, self.tilt, 0.13)
            self._move(0, self.tilt, 0.2)
        elif name == "nod":
            for _ in range(2):
                self._move(self.pan, T * 0.7, 0.16); self._move(self.pan, -T * 0.2, 0.16)
            self._move(self.pan, 0, 0.2)
        elif name == "idle":
            self._move(random.uniform(-R * 0.3, R * 0.3), random.uniform(-T * 0.3, T * 0.3), random.uniform(1.2, 2.5))

    def run(self):
        last_idle = time.time()
        while not self._stop.is_set():
            with self._lock:
                item = self._q.pop(0) if self._q else None
            if item:
                try:
                    self._run_gesture(*item)
                except Exception as e:
                    log.debug("gesture failed: %s", e)
                last_idle = time.time()
            elif time.time() - last_idle > random.uniform(6, 14):
                self._run_gesture("idle", 1.0)
                last_idle = time.time()
            else:
                time.sleep(0.05)

    def stop(self):
        self._stop.set()
