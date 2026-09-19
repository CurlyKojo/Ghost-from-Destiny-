# 04 · Assembly

Read [03-wiring](03-wiring.md) first and pre-wire the head modules with 40 cm leads before anything goes in the sphere.

![assembled](../hardware/preview.png)

## 1. Eye stack (bezel)

1. Press the **NeoPixel ring** into the pocket behind the bezel lip, LEDs facing the lip. The ring's solder pads face the slot marked for the FPC. A dab of hot glue on the back holds it.
2. Set the **display** glass-down into the tube behind the ring, then the PCB into the square pocket of the backplate. Route the FPC/header out the notch. Tape it.
3. Optional: 33 mm clear acrylic disc glued into the lip window.
4. Test now: `GHOST_DISPLAY=gc9a01 python -m ghost.main --sim --mock` on the Pi with the display wired. If you see the eye, keep going.

## 2. Core

1. Slide the bezel into the front hemisphere's bore from the inside. Friction fit; CA glue the rim.
2. Stick the **INMP441** to the inside of the back hemisphere right behind the four vent holes on top (foam tape). The holes are the mic's acoustic port.
3. Feed all leads out the cable hole beside the neck pad.
4. Mate the halves: the back half's lip goes into the front half. Three M2 screws through the front half into the pilot holes in the lip (or CA glue if you never want to open it).

## 3. Fins

1. Test-fit a fin on a peg. The socket is 10.8 mm for a 10 mm peg. Sand the peg if tight.
2. Orient each fin so its **flat front plate faces forward** (front fins) or **backward** (back fins) and the plate's right-angle corner points outward. Sight down the assembled Ghost: from the front you should see a clean diamond; from the side an X.
3. CA glue each fin on its peg.

## 4. Stand

1. Drop the **pan servo** into the pocket in the lid, shaft up, two M2 screws through the tabs from underneath. Centre it (`tools/servo_calibrate.py`, or just power it and set 90°).
2. Screw a round servo horn to the bottom disc of the **arm** (4 holes at 7 mm radius), then press the horn onto the pan servo shaft with the arm pointing straight back and secure with the horn screw.
3. Press the **tilt servo** into the pocket at the top of the arm, shaft toward +x (the side with the open face), screws through the tabs along x.
4. Fit a single-arm horn to the **head_mount** plate (3 holes) and mount it on the tilt servo at 90°.
5. Head goes on: the head_mount's round stub plugs into the socket on the core's neck pad. CA glue once you're happy with the angle (level, eye straight ahead).

## 5. Base electronics

1. Pi on the four standoffs (M2.5). USB/HDMI toward the slot in the rear wall.
2. DC jack in the 8 mm hole. Terminal block next to it.
3. Speaker under the lid grille (hot glue or tape), MAX98357A next to it.
4. PCA9685 anywhere it fits; short leads to the servos.
5. Route the head ribbon through the lid slot beside the pan servo, down the back of the arm's channel, and leave the service loop at the top.
6. Lid on, four M3 screws.

## 6. First power-up checklist

- [ ] `sudo i2cdetect -y 1` shows `40` (PCA9685)
- [ ] `aplay -l` shows the voice HAT card; `speaker-test -c1 -t sine` makes noise
- [ ] `arecord -d 3 -f S16_LE -r 16000 test.wav && aplay test.wav` plays your voice
- [ ] `python -m ghost.main --sim --mock` shows the eye and lights the ring
- [ ] `.env` has the API key, then `python -m ghost.main`
- [ ] Say "Hey Ghost" (or "Hey Jarvis" until your custom wake model is in place)

## Balance note

The head is ~200 g and the tilt pivot sits 66 mm behind the core centre. MG90S handles it, but if tilt sags, either move to an MG996R-class servo (edit `servo_body` in the generator) or add 30–40 g of weight in the back of the core (coins, hot-glued).
