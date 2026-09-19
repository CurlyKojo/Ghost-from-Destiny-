"""The Ghost's eye: a 240x240 animation for the round GC9A01 display.

Everything is computed with numpy from a handful of parameters (iris size, squash,
colour, ring, spinner), so a Pi 4 renders it comfortably at 20-30 fps.  The same
renderer is used for the on-device display, for PNG previews, and for a desktop window.
"""
from __future__ import annotations

import logging
import math
import random
import threading
import time
from dataclasses import dataclass

import numpy as np
from PIL import Image

from .config import CONFIG

log = logging.getLogger("ghost.eye")

SIZE = 240

# emotion -> (colour rgb, iris radius, squash x, squash y, y offset, glow, spinner, ring)
# colour: the in-game Ghost is a cool white-blue; moods tint it.
MOODS = {
    "neutral":   ((120, 200, 255), 0.30, 1.00, 1.00,  0.00, 1.00, 0.0, 0.55),
    "happy":     ((140, 220, 255), 0.30, 1.10, 0.72,  0.05, 1.20, 0.0, 0.58),
    "excited":   ((170, 235, 255), 0.36, 1.05, 1.05,  0.00, 1.50, 0.0, 0.62),
    "curious":   ((120, 200, 255), 0.30, 0.92, 1.12, -0.04, 1.10, 0.0, 0.56),
    "thinking":  ((110, 180, 255), 0.26, 1.00, 1.00,  0.02, 0.90, 1.0, 0.52),
    "worried":   ((150, 170, 255), 0.27, 1.00, 0.80,  0.03, 0.85, 0.0, 0.50),
    "sad":       ((100, 140, 230), 0.25, 1.05, 0.65,  0.08, 0.60, 0.0, 0.48),
    "surprised": ((180, 240, 255), 0.40, 1.00, 1.00,  0.00, 1.60, 0.0, 0.66),
    "annoyed":   ((255, 150, 110), 0.26, 1.20, 0.55,  0.00, 1.00, 0.0, 0.52),
    "smug":      ((150, 210, 255), 0.28, 1.15, 0.60, -0.03, 1.05, 0.0, 0.55),
    "sleepy":    (( 70, 110, 180), 0.22, 1.10, 0.35,  0.06, 0.45, 0.0, 0.40),
    "listening": ((160, 230, 255), 0.33, 1.00, 1.00,  0.00, 1.35, 0.0, 0.70),
    "speaking":  ((130, 205, 255), 0.31, 1.00, 1.00,  0.00, 1.15, 0.0, 0.58),
    "offline":   ((120, 120, 130), 0.20, 1.00, 1.00,  0.00, 0.40, 0.0, 0.35),
}


@dataclass
class EyeState:
    mood: str = "neutral"
    level: float = 0.0        # speech amplitude 0..1
    listening_level: float = 0.0


class EyeRenderer:
    def __init__(self, size: int = SIZE):
        self.size = size
        ax = (np.arange(size) - (size - 1) / 2) / (size / 2)     # -1..1
        self.X, self.Y = np.meshgrid(ax, ax)
        self.R = np.sqrt(self.X ** 2 + self.Y ** 2)
        self.T = np.arctan2(self.Y, self.X)
        # static backdrop: dark blue-black vignette with a faint lens ring
        self.bg = np.zeros((size, size, 3), np.float32)
        v = np.clip(1.0 - self.R * 0.85, 0, 1) ** 1.5
        self.bg += (np.array([6, 10, 22]) / 255.0) * v[..., None]
        self._cur = {k: float(v) for k, v in zip(
            ("radius", "sx", "sy", "dy", "glow", "spin", "ring"), MOODS["neutral"][1:])}
        self._col = np.array(MOODS["neutral"][0], np.float32)
        self._blink = 1.0
        self._next_blink = time.time() + random.uniform(2, 6)
        self._blink_t0 = None
        self._t0 = time.time()

    # ------------------------------------------------------------------
    def frame(self, st: EyeState) -> Image.Image:
        t = time.time() - self._t0
        target = MOODS.get(st.mood, MOODS["neutral"])
        # ease toward the mood's parameters
        k = 0.18
        tc = np.array(target[0], np.float32)
        self._col += (tc - self._col) * k
        for name, val in zip(("radius", "sx", "sy", "dy", "glow", "spin", "ring"), target[1:]):
            self._cur[name] += (float(val) - self._cur[name]) * k
        c = self._cur

        # breathing + speech
        breathe = 1.0 + 0.03 * math.sin(t * 1.6)
        speak = 1.0 + 0.55 * st.level if st.mood == "speaking" else 1.0
        listen = 1.0 + 0.35 * st.listening_level if st.mood == "listening" else 1.0
        radius = c["radius"] * breathe * speak * listen

        # blink: a quick vertical squash
        blink = self._blink_factor(st.mood)

        sx, sy = c["sx"], c["sy"] * blink
        x = self.X / max(sx, 0.05)
        y = (self.Y - c["dy"]) / max(sy, 0.05)
        rr = np.sqrt(x * x + y * y) / radius

        # iris: hard-edged rounded hexagon core + soft glow halo
        hexa = np.cos(np.arctan2(y, x) * 6) * 0.06 + 1.0       # subtle hex facets
        core = np.clip((1.0 - (rr * hexa)) * 8.0, 0, 1)         # soft edge
        glow = np.exp(-((rr - 0.6) ** 2) * 2.0) * 0.55 * c["glow"]
        halo = np.exp(-rr * 1.3) * 0.35 * c["glow"]
        pupil = np.clip((0.38 - rr) * 12.0, 0, 1)               # bright white centre

        img = self.bg.copy()
        col = self._col / 255.0
        img += (core * 0.85 + glow + halo)[..., None] * col
        img += (pupil * 0.9)[..., None] * np.array([1, 1, 1], np.float32)

        # lens ring: thin, slightly brighter when listening
        ring_r = c["ring"] * 1.0
        ring = np.exp(-((self.R - ring_r) ** 2) * 900) * (0.25 + 0.4 * st.listening_level)
        img += ring[..., None] * col * 0.9

        # thinking spinner: three arc segments orbiting the iris
        if c["spin"] > 0.02:
            ang = (self.T + t * 3.0) % (2 * math.pi / 3)
            seg = (ang < 1.0).astype(np.float32)
            band = np.exp(-((self.R - radius * 1.55) ** 2) * 700)
            img += (band * seg * c["spin"] * 0.9)[..., None] * col

        # listening ripple: a ring expanding from the iris
        if st.mood == "listening":
            rip = (t * 0.6) % 1.0
            band = np.exp(-((self.R - (radius * 1.2 + rip * 0.5)) ** 2) * 500) * (1 - rip)
            img += (band * 0.5)[..., None] * col

        img = np.clip(img, 0, 1)
        return Image.fromarray((img * 255).astype(np.uint8), "RGB")

    def _blink_factor(self, mood: str) -> float:
        now = time.time()
        if mood in ("sleepy", "offline"):
            return 1.0
        if self._blink_t0 is None and now >= self._next_blink:
            self._blink_t0 = now
        if self._blink_t0 is not None:
            p = (now - self._blink_t0) / 0.16
            if p >= 1.0:
                self._blink_t0 = None
                self._next_blink = now + random.uniform(2.5, 7.0)
                return 1.0
            return max(0.08, 1.0 - math.sin(p * math.pi))
        return 1.0


# ---------------------------------------------------------------------------
# display back-ends
# ---------------------------------------------------------------------------
class NullDisplay:
    def show(self, img: Image.Image): pass
    def close(self): pass


class PngDisplay:
    """Writes the latest frame to /tmp/ghost_eye.png a few times a second (debugging)."""
    def __init__(self, path="/tmp/ghost_eye.png"):
        self.path, self._last = path, 0.0
    def show(self, img):
        if time.time() - self._last > 0.25:
            img.save(self.path); self._last = time.time()
    def close(self): pass


class GC9A01Display:
    """Waveshare / generic 1.28" 240x240 round LCD over SPI0.

    Prefers Adafruit's driver (pip install adafruit-circuitpython-rgb-display); falls back
    to a minimal spidev driver with the standard GC9A01 init sequence.
    """
    def __init__(self):
        try:
            import board, busio, digitalio
            from adafruit_rgb_display import gc9a01a
            spi = busio.SPI(clock=board.SCK, MOSI=board.MOSI)
            pin = lambda n: digitalio.DigitalInOut(getattr(board, f"D{n}"))
            self.disp = gc9a01a.GC9A01A(spi, cs=pin(CONFIG.display_cs), dc=pin(CONFIG.display_dc),
                                        rst=pin(CONFIG.display_rst), baudrate=40_000_000,
                                        rotation=CONFIG.display_rotation)
            bl = pin(CONFIG.display_bl); bl.direction = digitalio.Direction.OUTPUT; bl.value = True
            self._impl = "adafruit"
            log.info("display: adafruit gc9a01a")
        except Exception as e:
            log.info("adafruit driver unavailable (%s) - using spidev fallback", e)
            self.disp = _SpidevGC9A01()
            self._impl = "spidev"

    def show(self, img: Image.Image):
        if self._impl == "adafruit":
            self.disp.image(img)
        else:
            self.disp.image(img)

    def close(self):
        if self._impl == "spidev":
            self.disp.close()


class _SpidevGC9A01:
    INIT = [
        (0xEF, []), (0xEB, [0x14]), (0xFE, []), (0xEF, []), (0xEB, [0x14]), (0x84, [0x40]),
        (0x85, [0xFF]), (0x86, [0xFF]), (0x87, [0xFF]), (0x88, [0x0A]), (0x89, [0x21]),
        (0x8A, [0x00]), (0x8B, [0x80]), (0x8C, [0x01]), (0x8D, [0x01]), (0x8E, [0xFF]),
        (0x8F, [0xFF]), (0xB6, [0x00, 0x20]), (0x36, [0x08]), (0x3A, [0x05]),
        (0x90, [0x08, 0x08, 0x08, 0x08]), (0xBD, [0x06]), (0xBC, [0x00]),
        (0xFF, [0x60, 0x01, 0x04]), (0xC3, [0x13]), (0xC4, [0x13]), (0xC9, [0x22]),
        (0xBE, [0x11]), (0xE1, [0x10, 0x0E]), (0xDF, [0x21, 0x0C, 0x02]),
        (0xF0, [0x45, 0x09, 0x08, 0x08, 0x26, 0x2A]), (0xF1, [0x43, 0x70, 0x72, 0x36, 0x37, 0x6F]),
        (0xF2, [0x45, 0x09, 0x08, 0x08, 0x26, 0x2A]), (0xF3, [0x43, 0x70, 0x72, 0x36, 0x37, 0x6F]),
        (0xED, [0x1B, 0x0B]), (0xAE, [0x77]), (0xCD, [0x63]),
        (0x70, [0x07, 0x07, 0x04, 0x0E, 0x0F, 0x09, 0x07, 0x08, 0x03]), (0xE8, [0x34]),
        (0x62, [0x18, 0x0D, 0x71, 0xED, 0x70, 0x70, 0x18, 0x0F, 0x71, 0xEF, 0x70, 0x70]),
        (0x63, [0x18, 0x11, 0x71, 0xF1, 0x70, 0x70, 0x18, 0x13, 0x71, 0xF3, 0x70, 0x70]),
        (0x64, [0x28, 0x29, 0xF1, 0x01, 0xF1, 0x00, 0x07]),
        (0x66, [0x3C, 0x00, 0xCD, 0x67, 0x45, 0x45, 0x10, 0x00, 0x00, 0x00]),
        (0x67, [0x00, 0x3C, 0x00, 0x00, 0x00, 0x01, 0x54, 0x10, 0x32, 0x98]),
        (0x74, [0x10, 0x85, 0x80, 0x00, 0x00, 0x4E, 0x00]), (0x98, [0x3E, 0x07]),
        (0x35, []), (0x21, []), (0x11, []), (0x29, []),
    ]

    def __init__(self):
        import spidev
        from gpiozero import DigitalOutputDevice
        self.spi = spidev.SpiDev(); self.spi.open(0, 0 if CONFIG.display_cs == 8 else 1)
        self.spi.max_speed_hz = 40_000_000; self.spi.mode = 0
        self.dc = DigitalOutputDevice(CONFIG.display_dc)
        self.rst = DigitalOutputDevice(CONFIG.display_rst)
        self.bl = DigitalOutputDevice(CONFIG.display_bl)
        self.rst.on(); time.sleep(0.01); self.rst.off(); time.sleep(0.01); self.rst.on(); time.sleep(0.12)
        for cmd, data in self.INIT:
            self._cmd(cmd)
            if data:
                self._data(bytes(data))
            if cmd == 0x11:
                time.sleep(0.12)
        time.sleep(0.02)
        self.bl.on()

    def _cmd(self, c):
        self.dc.off(); self.spi.writebytes([c])

    def _data(self, b: bytes):
        self.dc.on()
        for i in range(0, len(b), 4096):
            self.spi.writebytes2(b[i:i + 4096])

    def image(self, img: Image.Image):
        a = np.asarray(img.convert("RGB"), np.uint16)
        rgb565 = ((a[..., 0] & 0xF8) << 8) | ((a[..., 1] & 0xFC) << 3) | (a[..., 2] >> 3)
        buf = rgb565.astype(">u2").tobytes()
        self._cmd(0x2A); self._data(bytes([0, 0, 0, 239]))
        self._cmd(0x2B); self._data(bytes([0, 0, 0, 239]))
        self._cmd(0x2C); self._data(buf)

    def close(self):
        self.bl.off(); self.spi.close()


def make_display():
    mode = CONFIG.display
    if mode == "none":
        return NullDisplay()
    if mode == "png":
        return PngDisplay()
    try:
        return GC9A01Display()
    except Exception as e:
        log.warning("no display (%s); eye frames go to /tmp/ghost_eye.png", e)
        return PngDisplay()


class Eye(threading.Thread):
    """Background thread that renders the eye at a steady frame rate."""

    def __init__(self, display=None):
        super().__init__(daemon=True, name="eye")
        self.state = EyeState()
        self.renderer = EyeRenderer()
        self.display = display or make_display()
        self._stop = threading.Event()

    def set(self, mood: str | None = None, level: float | None = None, listening_level: float | None = None):
        if mood is not None:
            self.state.mood = mood
        if level is not None:
            self.state.level = max(0.0, min(1.0, level))
        if listening_level is not None:
            self.state.listening_level = max(0.0, min(1.0, listening_level))

    def run(self):
        dt = 1.0 / max(5, CONFIG.display_fps)
        while not self._stop.is_set():
            t = time.time()
            try:
                self.display.show(self.renderer.frame(self.state))
            except Exception as e:
                log.error("eye frame failed: %s", e); time.sleep(1)
            time.sleep(max(0.0, dt - (time.time() - t)))
        self.display.close()

    def stop(self):
        self._stop.set()
