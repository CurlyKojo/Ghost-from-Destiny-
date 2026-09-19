#!/usr/bin/env python3
"""Find your pan/tilt centre angles.  Type an angle for each servo until the Ghost looks
straight ahead and level, then put the numbers in .env as GHOST_PAN_CENTER / GHOST_TILT_CENTER."""
from adafruit_servokit import ServoKit
kit = ServoKit(channels=16)
for ch in (0, 1):
    kit.servo[ch].set_pulse_width_range(500, 2500)
print("channel 0 = pan, 1 = tilt.  Enter '<ch> <angle>' e.g. '1 95'.  Ctrl-C to quit.")
while True:
    try:
        ch, ang = input("> ").split()
        kit.servo[int(ch)].angle = float(ang)
    except (EOFError, KeyboardInterrupt):
        break
    except Exception as e:
        print("?", e)
