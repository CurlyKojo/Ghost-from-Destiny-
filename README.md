# Ghost from Destiny — a 3D-printed voice companion

A desk-sized Ghost that listens for "Hey Ghost", talks back in character, animates its eye, glows, and looks around. Alexa-shaped idea, Ghost-shaped personality.

![preview](hardware/preview.png)

The shell is built straight from the Bungie reference sheet: the same 8 pieces, the diamond with its X seams from the front, the X with blunt arm ends from the side, the central diamond and notches from the top.

![reference vs generated](docs/reference_vs_generated.png)

- **Print it** — 8 STL files, ~460 g of filament, ~28 h of printing. 180 mm tip to tip. Parametric generator included.
- **Build it** — Raspberry Pi 4, a round 1.28" LCD for the eye, I2S mic + amp, a 16-LED ring, two servos for pan/tilt. About $150.
- **Run it** — wake word + speech-to-text run offline on the Pi; the personality is Claude with emotion tags that drive the eye, the lights and the body; the voice is Piper with a "Ghost" filter chain.

## Repo layout

```
hardware/
  generate_stl.py      parametric generator (trimesh) - every dimension is a parameter
  stl/                 fin_x8, core_front, core_back, eye_bezel, arm, head_mount, base, base_lid
  preview.png          assembled render (front / side / top)
  parts.png            every part in print orientation
docs/
  01-hardware-bom.md   parts list with prices
  02-print-guide.md    settings, orientation, finishing
  03-wiring.md         pin map + wiring diagram
  04-assembly.md       step by step
  05-software-setup.md Pi setup, wake word training, troubleshooting
  06-voice-and-personality.md
software/
  ghost/               the Python package (main loop, brain, eye, lights, motion, tts, stt, wake, tools)
  tools/               preview_eye.py, chat.py, servo_calibrate.py
  install.sh           one-shot Pi setup
  ghost.service        systemd unit
  .env.example         configuration
```

## Quick start

```bash
# 1. print hardware/stl/*  (docs/02-print-guide.md)
# 2. wire it              (docs/03-wiring.md)
# 3. on the Pi:
git clone <this repo> ~/ghost && cd ~/ghost/software && bash install.sh
nano .env            # ANTHROPIC_API_KEY, your name, your city
sudo reboot && sudo systemctl start ghost
```

Then say **"Hey Ghost, what's the weather like?"**

No hardware yet? `python -m ghost.main --sim --mock` runs the whole pipeline on a laptop with a canned brain.

## How it works

```
 mic → openWakeWord → record → faster-whisper → Claude (personality + tools) → Piper + Ghost FX → speaker
                                                    │
                        [emotion] tags → eye animation (GC9A01) · LED ring · pan/tilt gestures
```

The reply streams: the first sentence is spoken while the rest is still being written, and every `[happy]`, `[curious]`, `[worried]` tag in the stream changes the eye, the ring colour and the body language. Local tools handle time, timers, weather, volume and (optionally) Home Assistant.

![eye moods](docs/eye_moods.png)

## Regenerating the STLs

```bash
pip install trimesh manifold3d numpy scipy shapely matplotlib
python3 hardware/generate_stl.py            # writes hardware/stl + previews, checks for collisions
python3 hardware/generate_stl.py --scale 0.95   # a slightly smaller Ghost
```

The generator also verifies that the shell pieces don't intersect each other, the core or the eye bezel, and that the head clears the arm through ±15° of tilt (the software's limit).

## Notes

- Destiny and the Ghost are Bungie's. This is a fan project; nothing here is affiliated with or endorsed by Bungie.
- The voice is a stock TTS voice with processing, not a clone of the game's voice actor.
- `docs/05-software-setup.md` explains the Pi 5 caveat (NeoPixel driver) and the 30-minute custom wake word training.
