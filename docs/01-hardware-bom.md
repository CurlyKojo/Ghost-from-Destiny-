# 01 · Bill of materials

Reference build: **Raspberry Pi 4** in the base, everything else in the head, one ribbon up the arm.
Prices are typical 2026 US street prices. Total is roughly **$140–170** plus filament.

## Electronics

| # | Part | Qty | ~Price | Notes |
|---|------|-----|--------|-------|
| 1 | Raspberry Pi 4 Model B, 2 GB (4 GB is nicer) | 1 | $45–55 | Pi 5 works too but see the LED note in [05-software-setup](05-software-setup.md#raspberry-pi-5) |
| 2 | microSD card, 32 GB, A1/A2 | 1 | $8 | |
| 3 | 5 V 5 A power supply, 5.5×2.1 mm barrel | 1 | $12 | One supply feeds Pi + servos + LEDs + amp |
| 4 | Panel-mount 5.5×2.1 mm DC jack | 1 | $3 | Fits the 8 mm hole in the base wall |
| 5 | 1.28" round IPS LCD, **GC9A01**, 240×240, SPI (Waveshare "1.28inch LCD Module" or clone) | 1 | $15 | The eye. 36.5 mm square PCB, 32.4 mm active area |
| 6 | **MAX98357A** I2S 3 W amplifier breakout | 1 | $6 | Adafruit or clone |
| 7 | Speaker, 40 mm, 4 Ω, 3 W | 1 | $5 | Sits under the grille in the base lid |
| 8 | **INMP441** I2S MEMS microphone breakout | 1 | $5 | Mounted in the head behind the vent holes |
| 9 | NeoPixel / WS2812B ring, **16 LEDs, 44 mm OD** | 1 | $8 | Glows through the eye bezel |
| 10 | **PCA9685** 16-channel PWM servo driver (I2C) | 1 | $6 | Jitter-free servos, works on any Pi |
| 11 | **MG90S** metal-gear micro servo | 2 | $8 | Pan + tilt. SG90 fits the same pocket but strips faster |
| 12 | 74AHCT125 level shifter | 1 | $2 | Optional but recommended for the LED data line |
| 13 | 1000 µF ≥6.3 V electrolytic capacitor | 1 | $1 | Across 5 V/GND at the LED ring |
| 14 | 470 Ω resistor | 1 | — | In series with LED data |
| 15 | 2-position screw terminal or Wago for 5 V distribution | 1 | $2 | |

## Wire and connectors

| Part | Qty | Notes |
|------|-----|-------|
| 26–28 AWG silicone wire, assorted colours | ~5 m | Or a 16-way ribbon cable for the arm run |
| Dupont / JST-XH connectors + crimper | — | Makes the head detachable |
| 2.54 mm female header for the Pi GPIO | 1 | Or a GPIO breakout / "cobbler" |

## Fasteners and misc.

| Part | Qty | Used for |
|------|-----|----------|
| M2 × 6 mm self-tapping screws | 10 | Core halves (3), servo tabs (4), servo horns (3) |
| M2.5 × 6 mm screws | 4 | Pi to the standoffs in the base |
| M3 × 10 mm screws | 4 | Base lid |
| Servo horn screws (come with the servos) | — | |
| CA glue (super glue) + hot glue | — | Shell pieces to pegs, bezel, LED ring |
| Double-sided foam tape | — | Display, mic, amp |
| Sandpaper 220/400, filler primer, paint (see print guide) | — | Optional finish |

## Filament

About **460 g** total.

| Colour | Parts | ~Grams |
|--------|-------|--------|
| Silver / light grey PLA or PETG | 8 × shell piece | 240 |
| Black or dark grey | core_front, core_back, arm, head_mount, base, base_lid | 215 |
| White or natural/translucent | eye_bezel | 8 |

## Optional upgrades

- **Clear lens**: a 33 mm clear acrylic disc (1–2 mm) in front of the display looks great and protects the glass.
- **Bigger speaker**: a 50 mm 4 Ω driver fits if you scale the base radius in `hardware/generate_stl.py` (`base_r`).
- **ReSpeaker 2-Mic HAT** instead of the INMP441 + MAX98357A: it has both mic and amp on one HAT. You lose the head-mounted mic (it sits on the Pi in the base) but the setup is one overlay.
- **Pi Zero 2 W** in the base works for the eye/LEDs/servos, but Whisper speech-to-text will be slow (5–8 s). Keep the Pi 4 unless you move STT to the cloud.
