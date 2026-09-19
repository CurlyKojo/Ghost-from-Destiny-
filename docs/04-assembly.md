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

## 3. The spreading shell

How it works: every piece is glued to a **slider pin** that runs through a guide tube in the core. A **spring** on the pin, trapped between the core surface and the piece, pushes the piece out. A **fishing-line tendon** tied to the cap on the pin's inner end runs to a small **spider ring** on the eye axis inside the core. A **Bowden cable** (PTFE tube + wire) runs from that ring out through the hollow neck, down the arm, to a **spool** on a servo in the base. Wind the spool and the ring pulls all eight tendons: the pieces slide in against the springs (closed, the normal look). Unwind and the springs spread the shell open, the pieces separating along their own axes like the in-game scan. The generator solves the ring geometry so the front and back groups close together: the ring travels 10 mm, front tendons are 28 mm and back tendons 16 mm (cap centre to ring hole).

![open](../hardware/preview_open.png)

Do this **before** joining the core halves:

1. Push the 8 **slider pins** through the guide tubes **from the inside**, caps inward. The caps stop against the tubes so the pins can't fall out.
2. Crimp or knot the Bowden **wire** through the centre hole of the **spider ring**, then feed the wire out through the 4.4 mm hole in the neck socket at the back of `core_back`.
3. Tie the tendons. With every pin pushed fully out (open) and the ring held 11 mm behind the core centre (a mark on the wire helps: the generator's `ring_travel()` gives the exact numbers), tie a line from each cap hole to a ring hole: the **front four at 28 mm**, the **back four at 16 mm**, cap centre to ring hole, plus a hair of slack. Braided line and a drop of CA on each knot.
4. Pull the wire 10 mm: every pin should slide in flush. If one lags, re-tie it a touch shorter.
5. Join the core halves (section 2, step 4). The ring floats on its eight tendons; it needs no guide.
6. Feed the **PTFE tube** through the head mount's bore into the neck socket until it seats against the core, then thread the wire through the tube. The tube runs down the arm's channel with the ribbon, through the lid slot, to the `shell_servo_mount` in the base.
7. In the base: screw the 20 mm round horn to the **spool**, fit the spool on the **shell servo**, drop the servo into the mount's cradle (shaft along the mount), and seat the tube's end in the post. Set the servo to the open angle (`tools/servo_calibrate.py`, channel 2), pull the wire snug through the spool's hole and tie it off. Winding the servo to the closed angle (about 140° of travel on an 8 mm spool is 20 mm, more than the 10 mm needed) closes the shell; `GHOST_SHELL_CLOSED` is wherever the pieces are just snug.

## 4. Pieces

1. Slide a **spring** over each pin from the outside, then test-fit a piece: the socket is 10 mm for the 9.6 mm pin, and the 6 mm deep counterbore swallows the spring when closed (only 3 mm of gap shows). Sand the pin if tight.
2. All 8 pieces are identical. Orientation, for a front piece: the **blunt tip edge points outward**, the **ridge (crease) faces the front**, and the two **wings sit on the mid-plane** (level with the core's equator seam, one each side). The two short inner edges frame the eye. Back pieces are the same with the ridge facing backward. With the shell closed, neighbouring pieces should nearly touch along the diagonal edges from the eye ring to the wings.
3. Sight down the assembled Ghost against `docs/reference_vs_generated.png`: from the front a clean diamond with thin X seams, from the side an X with blunt arm ends, from the top the central diamond with a notch on each side.
4. CA glue each piece onto its pin with the shell **closed** (wire pulled) so the closed look is the tight one. Let it cure before releasing.
5. Release the servo: the shell should spring open about 12 mm on every piece and pull shut cleanly. If a piece sticks, its pin needs more sanding or grease.

## 5. Stand

1. Drop the **pan servo** into the pocket in the lid, shaft up, two M2 screws through the tabs from underneath. Centre it (`tools/servo_calibrate.py`, or just power it and set 90°).
2. Screw a round servo horn to the bottom disc of the **arm** (4 holes at 7 mm radius), then press the horn onto the pan servo shaft with the arm pointing straight back and secure with the horn screw.
3. Press the **tilt servo** into the pocket at the top of the arm, shaft toward +x (the side with the open face), screws through the tabs along x.
4. Fit a single-arm horn to the **head_mount** plate (3 holes) and mount it on the tilt servo at 90°.
5. Head goes on: the head_mount's round stub plugs into the socket on the core's neck pad. CA glue once you're happy with the angle (level, eye straight ahead).

## 6. Base electronics

1. Pi on the four standoffs (M2.5). USB/HDMI toward the slot in the rear wall.
2. DC jack in the 8 mm hole. Terminal block next to it.
3. Speaker under the lid grille (hot glue or tape), MAX98357A next to it.
4. PCA9685 anywhere it fits; short leads to the servos.
5. Route the head ribbon through the lid slot beside the pan servo, down the back of the arm's channel, and leave the service loop at the top.
6. Lid on, four M3 screws.

## 7. First power-up checklist

- [ ] `sudo i2cdetect -y 1` shows `40` (PCA9685)
- [ ] `aplay -l` shows the voice HAT card; `speaker-test -c1 -t sine` makes noise
- [ ] `arecord -d 3 -f S16_LE -r 16000 test.wav && aplay test.wav` plays your voice
- [ ] `python -m ghost.main --sim --mock` shows the eye, lights the ring, and the shell flares open and shut
- [ ] `.env` has the API key, then `python -m ghost.main`
- [ ] Say "Hey Ghost" (or "Hey Jarvis" until your custom wake model is in place)

## Power-off behaviour

The springs win when the servo is unpowered, so the Ghost sits with its shell open whenever it's off. The software parks it closed on shutdown; a hard power cut leaves it open. That's how the mechanism stays simple (tendons only pull). Because the servo lives in the base, pan and tilt flex the Bowden tube slightly; leave a gentle loop of tube at the tilt joint and it won't bind.

## Balance note

The head is ~350 g with the shell mechanism and the tilt pivot sits 70 mm behind the core centre. MG90S handles it, but if tilt sags, either move to an MG996R-class servo (edit `servo_body` in the generator) or add 30–40 g of weight in the back of the core (coins, hot-glued).
