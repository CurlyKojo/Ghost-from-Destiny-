#!/usr/bin/env python3
"""Sound for the Darksaber reel, synthesised from scratch (no samples, no film audio).

Reads timing.json so every sound sits on the picture: printer whirr, part snaps, solder
sizzle, the switch, then the blade: ignition, hum, the swing, and the title hit.
Writes assets/sfx.wav (48 kHz stereo).
"""
import json
import os
import wave

import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, "..", "timing.json")))
SR = 48000
N = int(T["duration"] * SR)
rng = np.random.default_rng(7)
dry = np.zeros(N); wet = np.zeros(N)            # wet = sent to the reverb


def put(buf, t, x, gain=1.0):
    i = int(round(t * SR))
    if i >= N or i + len(x) <= 0: return
    x = x[: N - i] if i >= 0 else x[-i:]
    buf[max(i, 0): max(i, 0) + len(x)] += x * gain


def tt(d): return np.arange(int(d * SR)) / SR
def noise(d): return rng.standard_normal(int(d * SR))
def bp(x, lo, hi, order=2): return signal.sosfilt(signal.butter(order, [lo, hi], "band", fs=SR, output="sos"), x)
def lp(x, f, order=2): return signal.sosfilt(signal.butter(order, f, "low", fs=SR, output="sos"), x)
def hp(x, f, order=2): return signal.sosfilt(signal.butter(order, f, "high", fs=SR, output="sos"), x)
def decay(d, tau): return np.exp(-tt(d) / tau)
def fade(x, a=0.004, r=0.01):
    n1, n2 = int(a * SR), int(r * SR); x = x.copy(); x[:n1] *= np.linspace(0, 1, n1); x[-n2:] *= np.linspace(1, 0, n2); return x


def sweep_noise(d, f0, f1, q=3.0):
    """Noise through a band-pass whose centre glides f0 -> f1 (a whoosh)."""
    x = noise(d); out = np.zeros_like(x); blk = 256
    for i in range(0, len(x), blk):
        k = i / len(x); fc = f0 * (f1 / f0) ** k
        sos = signal.butter(2, [fc / (1 + 1 / q), min(fc * (1 + 1 / q), SR / 2 - 100)], "band", fs=SR, output="sos")
        seg = signal.sosfilt(sos, x[max(i - 2048, 0): i + blk]); out[i: i + blk] = seg[-min(blk, len(x) - i):]
    return out


def thump(f=60, d=0.35, tau=0.09, drop=0.5):
    t = tt(d); ph = 2 * np.pi * np.cumsum(f * (1 + drop * np.exp(-t / 0.03))) / SR
    return np.sin(ph) * np.exp(-t / tau)


def click(f=2500, d=0.03): return fade(bp(noise(d), f * 0.6, f * 1.6) * decay(d, d / 4), 0.0005, 0.004)
def blip(f, d=0.05, tau=0.02): return fade(np.sin(2 * np.pi * f * tt(d)) * decay(d, tau), 0.001, 0.005)
def whoosh(d=0.22, f0=300, f1=3200): x = sweep_noise(d, f0, f1); return x * np.sin(np.pi * tt(d) / d) ** 2


# ---- hook: a blade strikes across the frame ---------------------------------------------------
put(dry, 0.0, whoosh(0.28, 500, 5200), 0.9); put(wet, 0.0, thump(70, 0.5, 0.14), 0.9)
put(dry, 0.0, fade(hp(noise(0.3), 3500) * decay(0.3, 0.05) * (rng.random(int(0.3 * SR)) > 0.6)), 0.35)

# ---- scene changes -------------------------------------------------------------------------------
for at in (T["print"][0], T["assemble"][0], T["solder"][0]):
    put(dry, at - 0.12, whoosh(0.2, 250, 2400), 0.45); put(wet, at, thump(85, 0.25, 0.06), 0.55)

# ---- print: stepper whirr that climbs with the part, then a finish chime ------------------------
g0, g1 = T["printGrow"]; d = g1 - g0; t = tt(d); u = t / d
f = 150 + 420 * np.floor(u * 14) / 14 + 14 * np.sin(2 * np.pi * 9.2 * t)
ph = 2 * np.pi * np.cumsum(f) / SR
whirr = lp(np.sign(np.sin(ph)) * 0.5 + np.sin(ph * 2) * 0.3, 1800) * (0.55 + 0.45 * np.abs(np.sin(2 * np.pi * 4.6 * t)))
put(dry, g0, fade(whirr, 0.03, 0.04), 0.16)
for k in np.arange(0, d, 0.055): put(dry, g0 + k, click(4200, 0.012), 0.10)
for fr, gain in ((1318.5, 0.22), (1975.5, 0.14)): put(wet, g1, blip(fr, 0.4, 0.11), gain)
for i in range(12): put(dry, T["partsPop"] + 0.05 + i * 0.014, blip(620 * 2 ** (i / 12), 0.03, 0.012), 0.13)

# ---- assemble: every part lands with a snap ----------------------------------------------------
for at in T["coreIn"]:
    put(dry, at + 0.1, click(3000, 0.02), 0.32); put(dry, at + 0.1, thump(180, 0.07, 0.02, 0.2), 0.25)
l0, l1 = T["led"]; d = l1 - l0; t = tt(d)
shim = np.sin(2 * np.pi * np.cumsum(500 * (3.4) ** (t / d)) / SR) * (0.6 + 0.4 * np.sin(2 * np.pi * 26 * t)) * np.sin(np.pi * t / d)
put(wet, l0, shim, 0.14)
for at in T["shellIn"]:
    put(dry, at + 0.1, click(1900, 0.03), 0.4); put(wet, at + 0.1, thump(110, 0.16, 0.045), 0.5)
put(wet, T["emitterIn"] + 0.1, thump(72, 0.3, 0.08), 0.8); put(dry, T["emitterIn"] + 0.1, click(1400, 0.04), 0.5)
put(dry, T["plugIn"] + 0.1, click(2600, 0.025), 0.4)

# ---- the 3D assembly: the real pieces seating, heavier as the big parts arrive ------------------
b0 = T["build"][0]
put(dry, b0 - 0.1, whoosh(0.3, 200, 2600), 0.55); put(wet, b0, thump(70, 0.35, 0.1), 0.6)
for at in T["buildCores"]:
    put(dry, at + 0.11, click(3400, 0.018), 0.36); put(dry, at + 0.11, thump(210, 0.06, 0.018, 0.2), 0.3)
l0, l1 = T["buildLed"]; d = l1 - l0; t = tt(d)
put(wet, l0, np.sin(2 * np.pi * np.cumsum(600 * 3.0 ** (t / d)) / SR) * (0.6 + 0.4 * np.sin(2 * np.pi * 30 * t)) * np.sin(np.pi * t / d), 0.12)
for at in T["buildShells"]:
    put(dry, at, whoosh(0.15, 900, 4200), 0.35); put(dry, at + 0.14, click(1700, 0.035), 0.5); put(wet, at + 0.14, thump(120, 0.18, 0.05), 0.6)
put(dry, T["buildPlug"] + 0.11, click(2600, 0.025), 0.45)
for key, f, g in (("buildEmitter", 78, 0.95), ("buildGuard", 96, 0.75), ("buildGrip", 70, 0.9), ("buildPommel", 60, 1.0)):
    put(wet, T[key] + 0.11, thump(f, 0.32, 0.085), g); put(dry, T[key] + 0.11, click(1300, 0.045), 0.55)
put(wet, T["buildLock"], thump(50, 0.6, 0.16, 0.7), 1.1)
for fr, gain in ((880, 0.12), (1320, 0.09), (1760, 0.06)): put(wet, T["buildLock"], blip(fr, 0.5, 0.14), gain)

# ---- solder: sizzle on each joint, the switch, power running up --------------------------------
for at in T["joints"]:
    d = 0.3; sz = hp(noise(d), 4200) * decay(d, 0.09) * (0.5 + 0.5 * (rng.random(int(d * SR)) > 0.75))
    put(dry, at, fade(sz, 0.002, 0.03), 0.3); put(dry, at, blip(2100, 0.05, 0.015), 0.12)
put(dry, T["switchOn"], click(1800, 0.02), 0.6); put(dry, T["switchOn"] + 0.035, click(2600, 0.02), 0.5)
d = 0.2; t = tt(d); put(wet, T["switchOn"] + 0.02, np.sin(2 * np.pi * np.cumsum(220 * 9 ** (t / d)) / SR) * np.sin(np.pi * t / d) ** 2, 0.2)

# ---- dark: the room drops out, a low swell builds, then a breath of silence ----------------------
d0, d1 = T["dark"]; d = d1 - d0 - 0.04; t = tt(d)
put(dry, d0, (np.sin(2 * np.pi * 41 * t) * 0.8 + lp(noise(d), 160) * 0.5) * (t / d) ** 2.2, 0.55)
put(dry, d0, sweep_noise(d, 180, 2600) * (t / d) ** 3, 0.3)

# ---- the blade ----------------------------------------------------------------------------------
ig = T["ignite"]; sw0, sw1 = T["swing"]
n0 = int(ig * SR); t = np.arange(N - n0) / SR
# swing: pitch lifts with blade speed, dips as it stops (a doppler feel), louder through the arc
u = np.clip((t + ig - sw0) / (sw1 - sw0), 0, 1); speed = np.sin(np.pi * u) ** 1.5
rise = 1 - 0.62 * np.exp(-t / 0.085)                                   # ignition: pitch climbs into the hum
f0 = 92.0 * rise * (1 + 0.38 * speed - 0.10 * np.sin(np.pi * np.clip(u * 1.6 - 0.6, 0, 1)) * (u > 0.4))
ph = 2 * np.pi * np.cumsum(f0) / SR
hum = sum(np.sin(k * ph + 0.3 * k) / k for k in range(1, 15)) * 0.5 + 0.35 * np.sin(1.5 * ph) + 0.25 * np.sin(0.5 * ph)
hum = lp(hum, 1300)
buzz = 1 + 0.22 * np.sin(2 * np.pi * 13.2 * t) + 0.12 * np.sin(2 * np.pi * 31 * t + 1) + 0.05 * lp(rng.standard_normal(len(t)), 9)
# the Darksaber's edge: a thin electric crackle riding on the hum
crack = hp(rng.standard_normal(len(t)), 2600) * (lp((rng.random(len(t)) > 0.9985).astype(float) * 60, 380) + 0.10)
level = (1 - np.exp(-t / 0.05)) * (0.62 + 0.5 * speed) * (1 + 0.5 * np.exp(-t / 0.25))
blade = (hum * buzz * 0.42 + bp(crack, 2600, 9000) * 0.05 * (1 + 2 * speed)) * level
fo = int(0.45 * SR); blade[-fo:] *= np.linspace(1, 0, fo) ** 1.5
dry[n0:] += blade * 0.62; wet[n0:] += blade * 0.20
# ignition transient: hiss sweeping up and settling, a sub hit, sparks
put(dry, ig, whoosh(0.42, 700, 6000) * 1.0 + sweep_noise(0.42, 5200, 1400) * decay(0.42, 0.16) * 0.6, 0.85)
put(wet, ig, thump(54, 0.9, 0.24, 0.8), 1.25)
put(dry, ig, fade(hp(noise(0.5), 3000) * decay(0.5, 0.07) * (rng.random(int(0.5 * SR)) > 0.55)), 0.5)
# swing air
put(dry, sw0 + 0.05, whoosh(sw1 - sw0, 240, 3400), 0.75); put(wet, sw1 - 0.06, thump(64, 0.4, 0.1), 0.6)

# ---- title -----------------------------------------------------------------------------------
put(wet, T["title"], thump(46, 1.3, 0.34, 0.9), 1.5); put(dry, T["title"], lp(noise(0.25), 500) * decay(0.25, 0.05), 0.5)
for fr, gain in ((311, 0.10), (466, 0.07), (622, 0.05)): put(wet, T["title"], blip(fr, 1.6, 0.5), gain)
put(wet, T["sub"], blip(1760, 0.3, 0.09), 0.10); put(wet, T["sub"], blip(2637, 0.3, 0.07), 0.05)

# ---- reverb (decaying-noise room) + stereo + master ------------------------------------------------
def room(seed, length=1.5, tau=0.36):
    r = np.random.default_rng(seed).standard_normal(int(length * SR)) * np.exp(-np.arange(int(length * SR)) / SR / tau)
    return lp(r, 5200) / 30
left = dry + wet + signal.fftconvolve(wet + dry * 0.12, room(1))[:N] * 0.75
right = dry + wet + signal.fftconvolve(wet + dry * 0.12, room(2))[:N] * 0.75
st = np.stack([left, right], axis=1)
st = np.tanh(st * 1.15)
st = st / np.abs(st).max() * 0.66
os.makedirs(os.path.join(HERE, "..", "assets"), exist_ok=True)
with wave.open(os.path.join(HERE, "..", "assets", "sfx.wav"), "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype("<i2").tobytes())
rms = lambda a, b: 20 * np.log10(np.sqrt(np.mean(st[int(a * SR): int(b * SR)] ** 2)) + 1e-9)
print(f"wrote assets/sfx.wav  {N / SR:.2f}s   build {rms(0.9, T["dark"][0]):.1f} dB   ignition {rms(T['ignite'], T['ignite'] + 0.5):.1f} dB   hum {rms(T["ignite"] + 0.8, T["ignite"] + 1.8):.1f} dB   title {rms(T['title'], T['title'] + 0.5):.1f} dB")
