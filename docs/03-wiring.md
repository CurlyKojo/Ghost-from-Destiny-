# 03 · Wiring

Everything hangs off the Pi 4's 40-pin header. The I2S pins (18/19/20/21) are shared by the amp and the mic, which is exactly the Google Voice HAT layout, so a stock overlay drives both. The LED ring uses GPIO12 (the other PWM0 pin) so it does not fight I2S.

```
                         ┌─────────────── HEAD (core) ───────────────┐
                         │  GC9A01 eye   INMP441 mic   NeoPixel ×16   │
                         └──────┬──────────────┬───────────┬─────────┘
                                │   ~15-wire ribbon down the arm       
   ┌────────────── BASE ────────┼──────────────┼───────────┼──────────────────────────┐
   │                            │              │           │                          │
   │  5V 5A ──► DC jack ──► terminal block ──► Pi 5V pin 2 + GND pin 6                │
   │                              │  ├────────► PCA9685 V+ (servo power)              │
   │                              │  ├────────► NeoPixel 5V  (+1000 µF cap)           │
   │                              │  └────────► MAX98357A VIN                        │
   │                                                                                  │
   │  Pi 4 ── SPI0 ──► display      Pi 4 ── I2S ──► MAX98357A ──► 40 mm speaker       │
   │       ── I2S  ◄── INMP441             ── I2C ──► PCA9685 ──► pan servo, tilt servo│
   │       ── GPIO12 ─(470 Ω / 74AHCT125)─► NeoPixel DIN                              │
   └──────────────────────────────────────────────────────────────────────────────────┘
```

## Pin map

| Module pin | Pi pin (BCM) | Header pin | Notes |
|---|---|---|---|
| **GC9A01 display** | | | SPI0 |
| VCC | 3.3 V | 1 | |
| GND | GND | 9 | |
| DIN (MOSI) | GPIO10 | 19 | |
| CLK (SCLK) | GPIO11 | 23 | |
| CS | GPIO8 (CE0) | 24 | |
| DC | GPIO25 | 22 | `GHOST_DISPLAY_DC` |
| RST | GPIO27 | 13 | `GHOST_DISPLAY_RST` |
| BL | GPIO24 | 18 | `GHOST_DISPLAY_BL` (or tie to 3.3 V to save a wire) |
| **MAX98357A amp** | | | I2S out |
| VIN | 5 V | 2 | from the terminal block |
| GND | GND | 6 | |
| BCLK | GPIO18 | 12 | shared with mic SCK |
| LRC | GPIO19 | 35 | shared with mic WS |
| DIN | GPIO21 | 40 | |
| GAIN | leave open | | 9 dB. Tie to GND for 12 dB if it's too quiet |
| SD | leave open | | |
| **INMP441 mic** | | | I2S in |
| VDD | 3.3 V | 17 | |
| GND | GND | 25 | |
| SCK | GPIO18 | 12 | |
| WS | GPIO19 | 35 | |
| SD | GPIO20 | 38 | |
| L/R | GND | | left channel |
| **NeoPixel ring** | | | |
| 5 V | 5 V rail | | 1000 µF cap across 5 V/GND at the ring |
| GND | GND | | |
| DIN | GPIO12 | 32 | through 470 Ω (and ideally a 74AHCT125 to make it 5 V logic) |
| **PCA9685** | | | I2C |
| VCC | 3.3 V | 1 | logic |
| SDA | GPIO2 | 3 | |
| SCL | GPIO3 | 5 | |
| GND | GND | | |
| V+ | 5 V rail | | **servo power from the supply, not the Pi** |
| ch 0 | pan servo | | `GHOST_SERVO_PAN` |
| ch 1 | tilt servo | | `GHOST_SERVO_TILT` |

Everything shares one ground.

## Powering the Pi from the header

Feeding 5 V into header pins 2/4 bypasses the Pi's USB-C input protection. That's normal for embedded builds but it means **use a decent supply** and add the 1000 µF cap. If you'd rather keep the protection, use a USB-C pigtail from the terminal block into the Pi's USB-C port instead.

## The ribbon up the arm

Wires that must reach the head (share the power/ground lines):

| Signal | Count |
|---|---|
| 3.3 V, 5 V, GND | 3 |
| Display: MOSI, SCLK, CS, DC, RST, BL | 6 (5 if BL is tied to 3.3 V) |
| Mic: SCK, WS, SD | 3 |
| LED: DIN | 1 |
| **Total** | **13** |

A 16-way ribbon or a bundle of 28 AWG silicone wire fits the 8×6 mm channel down the back of the arm and the 10 mm cable slot in the lid. Leave a 60 mm service loop at the tilt joint so the head can move.

## I2S overlay

`install.sh` adds this to `/boot/firmware/config.txt`:

```
dtparam=audio=off
dtoverlay=googlevoicehat-soundcard
```

That single overlay exposes the MAX98357A as playback and the INMP441 as capture on `hw:0,0`. Check with `aplay -l` and `arecord -l` after a reboot.
