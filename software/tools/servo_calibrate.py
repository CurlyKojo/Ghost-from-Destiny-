#!/usr/bin/env python3
"""Find your servo angles.  Type an angle for each servo until the Ghost looks straight
ahead and level (channels 0/1 -> GHOST_PAN_CENTER / GHOST_TILT_CENTER), and for the shell
spool (channel 2) find the angle where the pieces are just pulled snug (GHOST_SHELL_CLOSED)
and where the tendons go slack with the shell fully open (GHOST_SHELL_OPEN)."""
from adafruit_servokit import ServoKit
kit = ServoKit(channels=16)
for ch in (0, 1, 2):
    kit.servo[ch].set_pulse_width_range(500, 2500)
print("channel 0 = pan, 1 = tilt, 2 = shell spool.  Enter '<ch> <angle>' e.g. '1 95'.  Ctrl-C to quit.")
while True:
    try:
        ch, ang = input("> ").split()
        kit.servo[int(ch)].angle = float(ang)
    except (EOFError, KeyboardInterrupt):
        break
    except Exception as e:
        print("?", e)
