# 05 · Software setup

## What runs where

```
 mic ──► openWakeWord ("hey ghost") ──► record until silence ──► faster-whisper (STT)
                                                                        │
      speaker ◄── Ghost FX ◄── Piper TTS ◄── sentence stream ◄── Claude (personality + tools)
                                                   │
                              eye animation, LED ring, pan/tilt gestures  ◄── [emotion] tags
```

Everything except the Claude call runs **on the Pi, offline**. The Claude call is what gives the Ghost a personality and general knowledge; the tools (time, timers, weather, volume, Home Assistant) run locally.

## Install

1. Flash **Raspberry Pi OS Lite (64-bit, Bookworm)** with the Pi Imager. Set your Wi-Fi and SSH in the imager.
2. Clone and install:

   ```bash
   sudo apt-get install -y git
   git clone <this repo> ~/ghost
   cd ~/ghost/software
   bash install.sh        # ~15 min: apt, SPI/I2C/I2S, venv, Python deps, Piper voice
   ```

3. Edit `~/ghost/software/.env`:

   ```
   ANTHROPIC_API_KEY=sk-ant-...
   GHOST_GUARDIAN_NAME=Kojo      # what he calls you
   GHOST_CITY=Denver             # default city for weather
   GHOST_TZ=America/Denver
   ```

4. `sudo reboot` (activates the audio overlay), then:

   ```bash
   sudo systemctl start ghost
   journalctl -u ghost -f
   ```

## Try it without hardware

Works on a laptop too (Python 3.10+):

```bash
cd software
python3 -m venv .venv && source .venv/bin/activate
pip install anthropic numpy scipy pillow requests
python -m ghost.main --sim --mock      # canned brain, eye frames to /tmp/ghost_eye.png
python -m ghost.main --sim             # real brain, type instead of talk (needs API key)
python tools/chat.py                   # brain only, shows tool calls
python tools/preview_eye.py --live     # eye window; space cycles the moods
```

## The "Hey Ghost" wake word

openWakeWord ships with a few phrases ("hey jarvis", "alexa", "hey mycroft") and the Ghost falls back to **hey jarvis** until you give it a custom model. Training "hey ghost" takes about 30 minutes and no recordings:

1. Open openWakeWord's training notebook in Google Colab: `https://github.com/dscripka/openWakeWord` → *notebooks/automatic_model_training.ipynb* → "Open in Colab".
2. Set `target_word = "hey ghost"`, keep the defaults (it synthesizes thousands of TTS samples and trains on them). Run all cells. ~20–40 min on a free GPU.
3. Download the resulting `hey_ghost.onnx` and copy it to `software/models/hey_ghost.onnx`.
4. `sudo systemctl restart ghost`. Tune `GHOST_WAKE_THRESHOLD` (0.5 default; raise it if it false-triggers, lower it if it misses).

## Speech-to-text

`faster-whisper` **base.en** (int8) is the default: ~2 s for a short sentence on a Pi 4, good accuracy. Options:

| `GHOST_WHISPER_MODEL` | Pi 4 latency | notes |
|---|---|---|
| `tiny.en` | ~1 s | fine for short commands |
| `base.en` | ~2 s | default |
| `small.en` | ~6 s | better with accents/noise; use on a Pi 5 |

## Latency you can expect (Pi 4, base.en, Piper medium, Claude Opus 5 at low effort)

| stage | time |
|---|---|
| wake word → chime | 0.1 s |
| end of speech → transcript | 1.5–2.5 s |
| transcript → first spoken sentence | 1–2 s (streams; speech starts at the first sentence) |
| each following sentence | overlaps with playback |

## Raspberry Pi 5

Everything works except `rpi_ws281x` (the NeoPixel driver) which does not support the Pi 5's RP1 I/O chip. Options: drive the ring from SPI with `adafruit-circuitpython-neopixel-spi` (then move the display to `CE1` and set `GHOST_DISPLAY_CS=7`), or hang the ring off a $4 QT Py / Trinket over USB serial. Or just build on a Pi 4, which has plenty of headroom for this.

## Troubleshooting

- **No audio devices**: `aplay -l` / `arecord -l` must list the voice HAT card. Check `dtoverlay=googlevoicehat-soundcard` is in `/boot/firmware/config.txt` and `dtparam=audio=off`.
- **Mic level**: run `python -m ghost.main -v` and watch the RMS in the debug log; set `GHOST_VAD_THRESHOLD` a bit above the room's noise floor.
- **Display is white / blank**: check DC/RST pins and `GHOST_DISPLAY_CS`. `GHOST_DISPLAY=png` writes frames to `/tmp/ghost_eye.png` so you can separate rendering from wiring problems.
- **LEDs dead**: the service must run as root (it does), and GPIO12 must not be used by anything else. Try `GHOST_LED_BRIGHTNESS=0.6`.
- **Servos buzz at rest**: set the centres properly (`tools/servo_calibrate.py`) and make sure V+ is from the 5 V supply, not the Pi's 3.3 V.
- **"lost my link to the Tower"**: that's the Ghost telling you the API call failed. Check the key, the network, and `journalctl -u ghost`.
