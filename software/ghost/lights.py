"""16-LED NeoPixel ring behind the eye bezel.  Uses GPIO12 (PWM0) so the I2S audio pins
stay free.  Needs root for rpi_ws281x - run the service as root or use `sudo`."""
from __future__ import annotations

import logging
import math
import threading
import time

from .config import CONFIG

log = logging.getLogger("ghost.lights")

COLORS = {
    "neutral": (60, 140, 255), "happy": (80, 180, 255), "excited": (120, 220, 255),
    "curious": (60, 150, 255), "thinking": (40, 110, 255), "worried": (90, 90, 255),
    "sad": (30, 60, 200), "surprised": (160, 230, 255), "annoyed": (255, 90, 40),
    "smug": (90, 170, 255), "sleepy": (10, 20, 60), "listening": (110, 210, 255),
    "speaking": (80, 170, 255), "offline": (40, 40, 45),
}


class Ring(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="lights")
        self.mood = "neutral"
        self.level = 0.0
        self._stop = threading.Event()
        self._px = None
        try:
            import board, neopixel
            pin = getattr(board, f"D{CONFIG.led_pin}")
            self._px = neopixel.NeoPixel(pin, CONFIG.led_count, brightness=CONFIG.led_brightness,
                                         auto_write=False, pixel_order=neopixel.GRB)
            log.info("neopixel ring on GPIO%d", CONFIG.led_pin)
        except Exception as e:
            log.warning("no LED ring (%s)", e)

    def set(self, mood: str | None = None, level: float | None = None):
        if mood: self.mood = mood
        if level is not None: self.level = level

    def run(self):
        if self._px is None:
            return
        n, t0 = CONFIG.led_count, time.time()
        cur = [0.0, 0.0, 0.0]
        while not self._stop.is_set():
            t = time.time() - t0
            tgt = COLORS.get(self.mood, COLORS["neutral"])
            cur = [c + (g - c) * 0.15 for c, g in zip(cur, tgt)]
            for i in range(n):
                ph = i / n
                if self.mood == "thinking":
                    k = 0.15 + 0.85 * max(0.0, math.cos((ph - t * 0.8) * 2 * math.pi)) ** 3
                elif self.mood == "listening":
                    k = 0.5 + 0.5 * math.sin(t * 5.0) * 0.4 + 0.3 * self.level
                elif self.mood == "speaking":
                    k = 0.35 + 0.65 * self.level
                elif self.mood == "sleepy":
                    k = 0.3 + 0.2 * math.sin(t * 0.7)
                else:
                    k = 0.6 + 0.15 * math.sin(t * 1.6 + ph * 2 * math.pi)
                self._px[i] = tuple(int(max(0, min(255, c * k))) for c in cur)
            try:
                self._px.show()
            except Exception as e:
                log.debug("led show failed: %s", e)
            time.sleep(1 / 40)
        self._px.fill((0, 0, 0)); self._px.show()

    def stop(self):
        self._stop.set()
