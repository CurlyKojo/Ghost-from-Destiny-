// The edit.  110 BPM, 14 bars, every cut on a beat.  apply(t) poses the whole scene for
// time t (seconds) as a pure function, so frames can be rendered in any order.
import * as THREE from 'three';

export const BPM = 110, BEAT = 60 / BPM, BAR = 4 * BEAT, BARS = 14, FPS = 30;
export const DURATION = BARS * BAR, FRAMES = Math.round(DURATION * FPS);
export const DROP_BEAT = 32;                      // bar 9, beat 1 = 17.45 s

const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, k) => a + (b - a) * k;
const smooth = (x) => { x = clamp(x); return x * x * (3 - 2 * x); };
const easeOut = (x) => 1 - Math.pow(1 - clamp(x), 3);
const easeIn = (x) => Math.pow(clamp(x), 3);
const easeInOut = (x) => { x = clamp(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const easeOutBack = (x, s = 1.9) => { x = clamp(x); return 1 + (s + 1) * Math.pow(x - 1, 3) + s * Math.pow(x - 1, 2); };
// a part arriving: 1 = still away, 0 = seated.  Lands `dur` s after `s0`, with a small settle.
const arrive = (s, s0 = 0, dur = 0.2) => 1 - easeOutBack((s - s0) / dur, 1.4);
const noise = (t, k) => Math.sin(t * 91.7 + k * 1.3) * 0.6 + Math.sin(t * 57.3 + k * 4.1) * 0.4;
const deg = THREE.MathUtils.degToRad;

// Shots: [first beat, last beat (exclusive), name].  Bar n starts at beat 4*(n-1).
export const SHOTS = [
  [0, 8, 'print'],          // bars 1-2   hook, then the pieces rise off the bed (one continuous move)
  [8, 10, 'brain'],         // bar 3      Pi drops into the base
  [10, 12, 'moves'],        //            3 servos seat
  [12, 14, 'sees'],         // bar 4      LCD
  [14, 16, 'glows'],        //            LED ring + bezel
  [16, 17, 'listens'],      // bar 5      mic
  [17, 18, 'amp'],          //            amp
  [18, 19, 'talks'],        //            speaker
  [19, 20, 'lid'],          //            lid closes
  [20, 22, 'pins'],         // bar 6      8 slider pins, one per 16th
  [22, 23, 'springs'],      //            springs
  [23, 24, 'tendons'],      //            tendons tie to the spider ring
  [24, 26, 'cable'],        // bar 7      Bowden cable threads down the arm
  [26, 28, 'shell'],        //            8 shell pieces, one per 16th
  [28, 30, 'wind'],         // bar 8      dark: the spool winds
  [30, 32, 'still'],        //            the shell draws shut and holds; "Hey Ghost" on beat 4
  [32, 34, 'drop'],         // bar 9      hero
  [34, 35, 'hit1'], [35, 36, 'hit2'],
  [36, 37, 'hit3'], [37, 38, 'hit4'], [38, 40, 'look'],     // bar 10
  [40, 44, 'weather'],      // bar 11
  [44, 48, 'timer'],        // bar 12
  [48, 52, 'lights'],       // bar 13
  [52, 56, 'end'],          // bar 14
];
export const LABELS = { brain: 'the brain', moves: 'moves', sees: 'sees', glows: 'glows', listens: 'listens', talks: 'talks', springs: 'springs push', cable: 'one cable pulls' };
export const CHAT = [
  // [bar start beat, user line, ghost line]
  [40, 'Hey Ghost, what’s the weather?', 'Clear skies, seventy-one.'],
  [44, 'Set a timer for 10 minutes.', 'Ten minutes. I’m counting.'],
  [48, 'Turn off the lights.', 'Lights out. I’ll keep watch.'],
];

export function createTimeline({ scene, camera, ghost, props: P, studio, post, voice }) {
  const meta = ghost.meta, G = ghost.parts, floorY = meta.base_bottom_y;
  const V = (x, y, z) => new THREE.Vector3(x, y, z);

  // ---- home poses -------------------------------------------------------------------------
  const tracked = [];
  const remember = (root) => root.traverse((o) => {
    if (o.userData.skip) return;
    tracked.push(o); o.userData.home = { p: o.position.clone(), q: o.quaternion.clone(), s: o.scale.clone() };
  });
  remember(ghost.root); remember(P.printer);
  const always = [P.speaker, P.panServo, P.wire, P.spool, P.shellServoHome];
  const reset = () => {
    for (const o of tracked) { const h = o.userData.home; o.position.copy(h.p); o.quaternion.copy(h.q); o.scale.copy(h.s); }
    for (const o of always) o.visible = true;
    P.tiltServoHome.matrix.elements[13] = meta.tilt_pivot[1];
  };

  const S = {
    base: [G.base], guts: [P.pi, P.mount, P.innerTube, P.amp], lid: [P.lidGroup], arm: [G.arm, P.tiltServoHome],
    core: [G.coreFront, G.coreBack], lcd: P.lcdSet, ring: [G.ledGroup], bezel: [G.bezel], mount: [G.headMount], mic: [P.mic],
    pins: G.pins, springs: G.springs, spider: [G.ring], tendons: P.tendons, fins: G.fins, cable: [P.bowden, P.grommet],
    printer: [P.printer],
  };
  const everything = Object.values(S).flat();
  const show = (...sets) => { for (const s of sets) for (const o of s) o.visible = true; };
  const ASSEMBLED = () => show(S.base, S.lid, S.arm, S.core, S.lcd, S.ring, S.bezel, S.mount, S.pins, S.springs, S.spider, S.fins, S.cable);

  const cam = { pos: V(0, 0, 1000), tgt: V(0, 0, 0), fov: 24, near: 50, aperture: 0, focus: null, maxBlur: 14, shift: 0 };
  const orbit = (tgt, azDeg, elDeg, d) => {
    const az = deg(azDeg), el = deg(elDeg);
    cam.tgt.copy(tgt); cam.pos.set(tgt.x + d * Math.sin(az) * Math.cos(el), tgt.y + d * Math.sin(el), tgt.z + d * Math.cos(az) * Math.cos(el));
  };
  const env = (t) => { const e = voice.envelope, x = t * voice.fps, i = Math.floor(x); return i < 0 || i >= e.length - 1 ? 0 : lerp(e[i], e[i + 1], x - i); };
  const lineAt = (t) => voice.lines.find((l) => t >= l.start && t < l.start + l.duration + 0.05);
  const macroLight = new THREE.PointLight(0xcfe2ff, 0, 0, 2); scene.add(macroLight);
  const camFill = new THREE.DirectionalLight(0xe8f0ff, 0); scene.add(camFill, camFill.target);     // rides with the camera
  const zSplit = (dz) => { for (const o of ghost.frontSet) o.position.z += dz; for (const o of ghost.backSet) o.position.z -= dz; };
  const tmp = V(0, 0, 0), tmp2 = V(0, 0, 0);

  // ---- the frame --------------------------------------------------------------------------
  function apply(t) {
    t = clamp(t, 0, DURATION - 1e-4);
    const b = t / BEAT;
    const shot = SHOTS.find((s) => b >= s[0] && b < s[1]) || SHOTS[SHOTS.length - 1];
    const name = shot[2], s = (b - shot[0]) * BEAT, u = (b - shot[0]) / (shot[1] - shot[0]), len = (shot[1] - shot[0]) * BEAT;

    reset();
    for (const o of everything) o.visible = false;
    ghost.pan.rotation.y = 0; ghost.tilt.rotation.x = 0;
    let open = 0, perPiece = null;
    const L = ghost.look;
    Object.assign(L, { moodA: 'neutral', moodB: 'neutral', mix: 0, eyePower: 0, ledLevel: 0, glow: 0.5, speak: 0, speaking: 0, timer: -1, blink: 1, ledChase: 0, ledChasePos: 0 });
    Object.assign(cam, { fov: 24, near: 50, aperture: 0, focus: null, maxBlur: 14, shift: 0 });
    const g = { camFill: 0, level: 0.8, rimK: null, hazeK: null, envK: null, bloom: 0.38, exposure: 1.0, sat: 1.0, vignette: 0.78, punch: 0, shake: 0, flash: 0 };
    const ov = { hook: 0, label: null, bubbles: [], end: 0, heyGhost: 0, scrimTop: 0, scrimBottom: 0 };
    macroLight.intensity = 0; P.clip.constant = 1e6; ghost.tipU.uTipAmount.value = 1;
    let bowdenDraw = 1, needTendons = false, tendonGrow = 1, pan = 0, tilt = 0;
    const buildCam = (tgt, az, el, d, push = 0.04) => { orbit(tgt, az + u * 2.5, el, d * (1 - push * u)); cam.fov = 30; cam.shift = 0.09; g.camFill = 0.95; g.level = 1.0; g.rimK = 0.7; g.envK = 1.3; g.exposure = 1.1; };

    switch (name) {
      // ================================================================= bars 1-2: print
      case 'print': {
        show(S.printer);
        const idx = 1, H = P.printHeight;
        const lift0 = 5.6;                                           // beat the pieces leave the bed
        // layer height: creeps during the hook, then a time-lapse to the top
        const h = b < 4 ? 14 + 0.5 * t : lerp(14 + 0.5 * 4 * BEAT, H, easeInOut((b - 4) / 1.55));
        P.setPrintHeight(Math.min(h, H));
        if (h >= H - 0.01) P.clip.constant = 1e6;
        // nozzle runs the perimeter; speeds up in the time-lapse; leaves when the print is done
        const frac = 0.10 + 0.05 * Math.min(t, 4 * BEAT) + (b > 4 ? 1.9 * Math.pow(Math.min(b - 4, 1.6), 1.6) : 0);
        const tip = P.outlinePoint(idx, frac, Math.min(h, H) + 0.15, tmp);
        const away = easeIn((b - 5.45) / 1.3);
        P.nozzle.position.set(tip.x, tip.y + 340 * away, tip.z - 90 * away);
        for (const [i, f] of P.printFins.entries()) {
          const k = easeInOut((b - lift0 - i * 0.07) / 3.4), drift = Math.max(0, b - lift0 - i * 0.07);
          f.cell.position.y = f.home.y + 150 * k + 6 * drift * k;
          f.cell.rotation.y = f.rotY + 0.5 * k * (i % 2 ? 1 : -1);
          f.cell.rotation.z = 0.22 * k * (i % 2 ? -1 : 1); f.cell.rotation.x = 0.16 * k * (i < 4 ? 1 : -1);
        }
        // camera: macro on the nozzle for bar 1 (seen from outside the wall it is laying), then one long pull-back
        const k = easeInOut((b - 4) / 4);
        const tm = Math.min(t, 4 * BEAT), hm = 14 + 0.5 * tm + 0.15;
        const follow = P.outlinePoint(idx, 0.10 + 0.05 * Math.max(tm - 0.12, 0), hm, tmp2);
        const cc = P.printFins[idx].cell.position, outAz = THREE.MathUtils.radToDeg(Math.atan2(follow.x - cc.x, follow.z - cc.z));
        const rise = 150 * easeInOut((b - lift0) / 3.4);
        const macroT = V(follow.x, follow.y + 7.5, follow.z), wideT = V(0, P.bedTop + 50 + rise * 0.85, 0);
        const az = lerp(outAz - 24 + 5 * (tm / BAR), 22 + 5 * k, k), el = lerp(13, 17, k), d = lerp(128 - 10 * (tm / BAR), 800, k);
        orbit(macroT.lerp(wideT, k), az, el, d);
        cam.near = lerp(4, 40, smooth(k * 3)); cam.fov = lerp(24, 27, k);
        cam.aperture = lerp(30, 1.5, smooth(k * 1.8)); cam.maxBlur = 16; cam.focus = d;
        macroLight.position.set(follow.x + 70, follow.y + 55, follow.z + 90); macroLight.intensity = 0.9e4 * (1 - smooth(k * 2.2));
        g.level = lerp(0.7, 0.62, k); g.rimK = lerp(0.42, 0.62, k); g.hazeK = 0.9; g.bloom = 0.3; g.vignette = 0.9;
        ov.hook = 1 - smooth((b - 4.15) / 0.9); ov.scrimTop = ov.hook;
        break;
      }
      // ================================================================= bar 3
      case 'brain': {
        show(S.base);
        P.pi.visible = true; P.pi.position.y += 120 * arrive(s, 0.02, 0.24);
        buildCam(V(4, floorY + 4, meta.base_center_z + 2), 30, 44, 540);
        cam.aperture = 1.2; ov.label = { text: LABELS.brain, s };
        break;
      }
      case 'moves': {
        show(S.base, S.lid, S.arm); P.pi.visible = true; P.mount.visible = true; P.wire.visible = false; P.speaker.visible = false;
        // exploded: lid and arm float above the base; three servos land on 8th notes
        P.lidGroup.position.y += 44; G.arm.position.y += 88;
        P.shellServo.position.z -= 70 * arrive(s, 0.0, 0.2); P.spool.visible = false;
        P.panServo.position.y += 80 * arrive(s, BEAT / 2, 0.2);
        P.tiltServo.position.y += 80 * arrive(s, BEAT, 0.2);
        P.tiltServoHome.matrix.elements[13] = meta.tilt_pivot[1] + 88;
        buildCam(V(-10, floorY + 104, -86), 50, 17, 760, 0.03); cam.shift = 0.03;
        ov.label = { text: LABELS.moves, s };
        break;
      }
      // ================================================================= bar 4
      case 'sees': {
        show(S.core, S.lcd);
        const k = arrive(s, 0.02, 0.26);
        for (const o of P.lcdSet) o.position.z += 110 * k;
        // screen boots once it is seated: a couple of flickers, then a faint iris
        const on = s > 0.36 ? (s < 0.44 ? 0.9 : s < 0.5 ? 0.1 : s < 0.58 ? 0.7 : 0.55 + 0.1 * Math.sin(s * 20) * Math.exp(-(s - 0.58) * 6)) : 0;
        L.eyePower = on * 0.75; L.glow = 0.55;
        buildCam(V(0, -12, 22), 34, 12, 265, 0.06); cam.aperture = 1.6;
        ov.label = { text: LABELS.sees, s };
        break;
      }
      case 'glows': {
        show(S.core, S.lcd, S.ring, S.bezel);
        G.ledGroup.position.z += 110 * arrive(s, 0.02, 0.24);
        G.bezel.position.z += 120 * arrive(s, BEAT - 0.1, 0.18); G.bezel.visible = s > BEAT - 0.11;
        L.eyePower = 0.5; L.glow = 0.6;
        const lit = clamp((s - 0.24) / 0.1);
        L.ledLevel = 0.9 * lit; L.ledChase = 1 - smooth((s - BEAT - 0.1) / 0.3); L.ledChasePos = s * 2.4;
        buildCam(V(0, -12, 24), -30, 10, 265, 0.06); cam.aperture = 1.6;
        ov.label = { text: LABELS.glows, s };
        break;
      }
      // ================================================================= bar 5
      case 'listens': {
        show([G.coreBack], S.mic);
        P.mic.position.addScaledVector(P.micDir, -70 * arrive(s, 0.0, 0.2));
        buildCam(V(0, 12, -18), 16, -20, 205, 0.05); cam.aperture = 1.4;
        macroLight.position.set(20, -20, 60); macroLight.intensity = 9e3;
        ov.label = { text: LABELS.listens, s };
        break;
      }
      case 'amp': {
        show(S.base); P.pi.visible = true; P.mount.visible = true; P.wire.visible = false; P.amp.visible = true;
        P.amp.position.y += 90 * arrive(s, 0.0, 0.2);
        buildCam(V(24, floorY + 6, meta.base_center_z - 40), 24, 56, 250, 0.05); cam.aperture = 1.0; cam.shift = 0.02;
        macroLight.position.set(90, floorY + 120, -40); macroLight.intensity = 3.5e4;
        break;
      }
      case 'talks': {
        show(S.lid); P.panServo.visible = true;
        P.lidGroup.position.y += 70;
        P.speaker.position.y -= 75 * arrive(s, 0.0, 0.2);
        buildCam(V(-26, floorY + 96, meta.base_center_z + 30), -34, -15, 430, 0.05); cam.aperture = 1.2;
        macroLight.position.set(-120, floorY + 30, 120); macroLight.intensity = 2.2e4;
        ov.label = { text: LABELS.talks, s };
        break;
      }
      case 'lid': {
        show(S.base, S.lid, S.arm); P.pi.visible = true; P.mount.visible = true; P.amp.visible = true; P.wire.visible = false;
        const k = arrive(s, 0.0, 0.22);
        P.lidGroup.position.y += 70 * k; G.arm.position.y += 70 * k;
        P.tiltServoHome.matrix.elements[13] = meta.tilt_pivot[1] + 70 * k;
        buildCam(V(-4, floorY + 62, -84), -42, 20, 640, 0.03);
        break;
      }
      // ================================================================= bar 6
      case 'pins': case 'springs': case 'tendons': {
        show(S.core, S.lcd, S.ring, S.bezel, S.pins, S.mic);
        open = 1; ghost.setOpen(1);
        const SPLIT = 44;
        let split = SPLIT;
        if (name === 'tendons') split = SPLIT * arrive(s, 0.30, 0.2);
        zSplit(split);
        if (name === 'pins') {
          // one pin per 16th note, shot out from the middle into its guide tube
          for (let i = 0; i < 8; i++) {
            const order = [0, 4, 1, 5, 2, 6, 3, 7].indexOf(i), s0 = order * BEAT / 4;
            const k = arrive(s, s0, 0.11), pin = G.pins[i], dz = (i < 4 ? 1 : -1) * split;
            pin.visible = s >= s0 - 0.02;
            pin.position.addScaledVector(pin.userData.dir, -26 * k); pin.position.z -= dz * k * 0.9;
          }
          buildCam(V(0, -18, 0), 66, 17, 560, 0.04); macroLight.position.set(120, 60, 0); macroLight.intensity = 6e4;
        } else {
          show(S.springs);
          if (name === 'springs') {
            for (let i = 0; i < 8; i++) { const sp = G.springs[i]; sp.position.addScaledVector(sp.userData.dir, 85 * arrive(s, i * 0.012, 0.2)); }
            buildCam(V(0, -18, 0), 48, 22, 520, 0.04); macroLight.position.set(120, 60, 0); macroLight.intensity = 6e4;
            ov.label = { text: LABELS.springs, s };
          } else {
            show(S.spider, S.tendons); needTendons = true; tendonGrow = easeOut((s - 0.03) / 0.2);
            G.ring.scale.setScalar(easeOutBack(s / 0.12));
            buildCam(V(0, -14, 0), 78, 12, 480, 0.05); macroLight.position.set(120, 60, 0); macroLight.intensity = 6e4;
          }
        }
        L.eyePower = 0.35; L.ledLevel = 0.25; L.glow = 0.5; cam.aperture = 1.0;
        break;
      }
      // ================================================================= bar 7
      case 'cable': {
        show(S.base, S.lid, S.arm, S.core, S.lcd, S.ring, S.bezel, S.mount, S.pins, S.springs, S.spider, S.cable);
        open = 1; bowdenDraw = easeInOut((s - 0.06) / 0.82);
        P.grommet.visible = bowdenDraw > 0.97;
        buildCam(V(0, -58, -84), 205, 15, 690, 0.04);
        g.rimK = 0.5; L.eyePower = 0; L.ledLevel = 0;
        ov.label = { text: LABELS.cable, s };
        break;
      }
      case 'shell': {
        ASSEMBLED(); open = 1; perPiece = new Array(8).fill(1);
        ghost.setOpen(1);
        const order = [0, 6, 1, 7, 2, 4, 3, 5];
        for (let n = 0; n < 8; n++) {
          const i = order[n], s0 = n * BEAT / 4, f = G.fins[i], k = arrive(s, s0, 0.11);
          f.visible = s >= s0 - 0.03; f.position.addScaledVector(f.userData.dir, 190 * k);
        }
        orbit(V(-8, -30, -30), 12 + 3 * u, 1, 1060 - 40 * u); cam.fov = 24; cam.shift = 0.04;
        g.level = 0.8; g.camFill = 0.5; L.eyePower = 0.3; L.ledLevel = 0.2; L.glow = 0.45;
        perPiece = null;
        break;
      }
      // ================================================================= bar 8: dark
      case 'wind': {
        show(S.base); P.pi.visible = true; P.mount.visible = true; P.innerTube.visible = true; P.amp.visible = true;
        const k = easeInOut(s / (2 * BEAT + 0.25));
        open = 1 - 0.62 * k;
        const spoolW = V(7.5 + 5, 0, 4 + 6.3).applyMatrix4(P.mount.matrix);
        orbit(spoolW, -52 - 5 * u, 36, 150 - 8 * u); cam.near = 6; cam.fov = 24; cam.aperture = 26; cam.maxBlur = 16;
        macroLight.position.set(spoolW.x - 50, spoolW.y + 60, spoolW.z - 70); macroLight.intensity = 1.3e4;
        g.level = 0.05; g.rimK = 0.5; g.hazeK = 0.25; g.bloom = 0.25; g.vignette = 1.0;
        break;
      }
      case 'still': {
        ASSEMBLED();
        open = 0.38 * (1 - easeOut(s / 0.5));
        orbit(V(-8, -24, -30), 15.5, 0, 1060 - 55 * easeOut(u)); cam.fov = 24;
        g.level = 0.045; g.rimK = 0.42; g.hazeK = 0.3; g.envK = 0.1; g.bloom = 0.25; g.vignette = 1.0;
        ov.heyGhost = b >= 31 ? easeOutBack((b - 31) * BEAT / 0.14) : 0; ov.heyS = (b - 31) * BEAT;
        break;
      }
      // ================================================================= bars 9-10: alive
      case 'drop': case 'hit1': case 'hit2': case 'hit3': case 'hit4': case 'look': {
        ASSEMBLED();
        const sd = (b - DROP_BEAT) * BEAT;                           // seconds since the drop
        // spool lets go: springs throw the pieces to the hard stop, they chatter and settle at 12 mm
        open = 1 - Math.exp(-11 * sd) * Math.abs(Math.cos(26 * sd));
        L.eyePower = 1; L.ledLevel = 1; L.moodA = 'surprised'; L.moodB = 'excited'; L.mix = smooth(sd / 0.6);
        L.glow = 1.0 + 1.0 * Math.exp(-4.5 * sd);
        g.level = 1.05; g.rimK = 0.72; g.hazeK = 1.55; g.sat = 1.16; g.bloom = 0.46 + 0.45 * Math.exp(-5 * sd); g.exposure = 1 + 0.3 * Math.exp(-8 * sd);
        g.flash = Math.exp(-13 * sd) * 0.16;
        g.punch = 0.11 * Math.exp(-7 * s); g.shake = 11 * Math.exp(-6.5 * s);
        const hero = V(-8, -24, -30);
        const snap = (x) => easeOutBack(x / 0.2, 2.2);
        if (name === 'drop') { orbit(hero, 15.5, 0, 985 - 30 * u); }
        if (name === 'hit1') { pan = -40 * snap(s); orbit(V(0, -34, -40), -52, 6, 930); }
        if (name === 'hit2') { pan = -40 + 52 * snap(s); tilt = 15 * snap(s); orbit(V(0, -30, -30), 28, -6, 860); }
        if (name === 'hit3') { pan = 12 + 30 * snap(s); tilt = 15 - 15 * snap(s); orbit(V(0, -34, -40), 62, 8, 930); }
        if (name === 'hit4') { pan = 42 - 30 * snap(s); tilt = -13 * snap(s); orbit(V(0, -14, -10), 16, 27, 720); }
        if (name === 'look') {
          // snaps round to the viewer and holds; on beat 4 the shell flexes
          pan = 12 - 12 * snap(s); tilt = -13 + 13 * snap(s);
          orbit(V(0, -16, 0), 0, 1, 760 - 30 * u);
          const s4 = s - BEAT;
          if (s4 >= 0) { open = 1 - 0.5 * Math.exp(-9 * s4) * Math.abs(Math.sin(13 * s4 + 1.57)) * (s4 < 0.5 ? 1 : 0); g.punch = 0.08 * Math.exp(-7 * s4); g.shake = 7 * Math.exp(-6.5 * s4); }
          L.moodA = 'excited'; L.moodB = 'happy'; L.mix = smooth(s / 0.3);
        }
        break;
      }
      // ================================================================= bars 11-13: what it will do
      case 'weather': case 'timer': case 'lights': {
        ASSEMBLED(); open = 1;
        L.eyePower = 1; L.ledLevel = 1; L.glow = 1.0;
        g.level = 1.02; g.rimK = 0.72; g.hazeK = 1.35; g.sat = 1.14; g.bloom = 0.46;
        g.punch = 0.05 * Math.exp(-8 * s); g.shake = 3 * Math.exp(-7 * s);
        const ask = smooth(s / 0.25), sr = s - BEAT;                   // sr: seconds since the reply starts
        L.speaking = lineAt(t) ? 1 : 0; L.speak = env(t);
        if (name === 'weather') {
          L.moodA = 'happy'; L.moodB = 'curious'; L.mix = ask;
          if (sr > 0) { L.moodA = 'curious'; L.moodB = 'happy'; L.mix = smooth((sr - 1.3) / 0.3); }
          pan = -9 * ask + 9 * smooth((sr - 0.1) / 0.3); tilt = 9 * ask - 5 * smooth((sr - 0.1) / 0.3);
          orbit(V(-4, -34, -30), -17 + 2 * u, 2, 1040 - 30 * u); cam.shift = 0.13;
        }
        if (name === 'timer') {
          L.moodA = 'happy'; L.moodB = 'neutral'; L.mix = ask;
          if (sr > 0) L.timer = smooth(sr / 0.32) * (1 - 0.055 * clamp((sr - 0.32) / (len - BEAT - 0.32)));   // ring draws on, then starts to drain
          pan = 5 * ask; tilt = -3 * ask;
          orbit(V(0, -2, 20), 13 - 2 * u, 3, 470 - 16 * u); cam.aperture = 1.8; cam.shift = 0.14;
        }
        if (name === 'lights') {
          L.moodA = 'neutral'; L.moodB = 'smug'; L.mix = smooth(sr / 0.4);
          const off = sr > 0 ? easeInOut(sr / 0.55) : 0;                // scene lights go; only the Ghost's glow is left
          g.level = lerp(1.02, 0.0, off); g.rimK = lerp(0.72, 0.05, off); g.hazeK = lerp(1.35, 0.12, off); g.envK = lerp(1.02, 0.03, off);
          g.bloom = lerp(0.46, 0.6, off); L.glow = lerp(1.0, 1.25, off);
          pan = 7 * ask - 7 * smooth(sr / 0.3); tilt = 4 * ask;
          orbit(V(-6, -34, -30), 9 - 2 * u, 1, 1150 - 30 * u); cam.shift = 0.13;
        }
        const chat = CHAT.find((c) => c[0] === shot[0]);
        ov.bubbles.push({ who: 'user', text: chat[1], s });
        if (sr >= 0) ov.bubbles.push({ who: 'ghost', text: chat[2], s: sr });
        ov.scrimBottom = 0.75;
        break;
      }
      // ================================================================= bar 14: end card
      case 'end': {
        ASSEMBLED(); open = 1;
        L.eyePower = 1; L.ledLevel = 1; L.glow = 1.0; L.moodA = 'happy'; L.moodB = 'neutral'; L.mix = smooth(s / 0.8);
        const up = smooth(s / 0.35);
        g.level = lerp(0.0, 1.0, up); g.rimK = lerp(0.05, 0.72, up); g.hazeK = lerp(0.12, 1.3, up); g.envK = lerp(0.03, 1.0, up); g.sat = 1.12; g.bloom = 0.46;
        orbit(V(-4, -34, -30), -22 + 30 * easeInOut(u * 0.9 + 0.05), 3, 1150); cam.aperture = 0.6; cam.shift = 0.12;
        ov.end = smooth(s / 0.25); ov.scrimBottom = ov.end; ov.endS = s;
        break;
      }
    }

    // the "I'm here." bubble rides over the cuts of bar 9
    const here = voice.lines[0];
    if (b >= DROP_BEAT && t >= here.start && t < DROP_BEAT * BEAT + BAR) {
      ov.bubbles.push({ who: 'ghost', text: here.text, s: t - here.start, big: true }); ov.scrimBottom = 0.5;
      if (lineAt(t)) { L.speaking = 1; L.speak = env(t); }
    }

    // ---- commit rig -------------------------------------------------------------------------
    if (name !== 'pins' && name !== 'springs' && name !== 'tendons' && name !== 'shell') ghost.setOpen(open, perPiece);
    ghost.pan.rotation.y = deg(pan); ghost.tilt.rotation.x = deg(-tilt);          // +tilt = nose up
    if (needTendons) P.updateTendons(tendonGrow);
    if (P.bowden.visible) P.updateBowden(bowdenDraw);
    // spool angle follows the shell: 10.4 mm of wire on an 8 mm spool = 74.5 degrees
    P.spoolSpin.rotation.z = -(1 - ghost.open) * (meta.ring_z_open - meta.ring_z_closed) / meta.spool_r;

    // ---- commit camera ----------------------------------------------------------------------
    camera.fov = cam.fov * (1 - g.punch); camera.near = cam.near; camera.far = 14000;
    camera.position.copy(cam.pos);
    if (g.shake > 0) camera.position.add(tmp.set(noise(t, 1), noise(t, 2), noise(t, 3) * 0.3).multiplyScalar(g.shake));
    camera.lookAt(cam.tgt); camera.updateProjectionMatrix();
    // lens shift: move the picture up by cam.shift of the frame height, to leave the lower third for text
    camera.projectionMatrix.elements[9] = -2 * cam.shift; camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
    const D = post.dof.uniforms;
    D.uAperture.value = cam.aperture; D.uMaxBlur.value = cam.maxBlur; D.uFocus.value = cam.focus ?? cam.pos.distanceTo(cam.tgt);

    // ---- commit lights and grade ------------------------------------------------------------
    camFill.intensity = g.camFill; camFill.position.copy(cam.pos).add(tmp.set(-0.35, 0.5, 0).multiplyScalar(cam.pos.distanceTo(cam.tgt))); camFill.target.position.copy(cam.tgt);
    studio.setLevel(g.level, { rimK: g.rimK ?? g.level, hazeK: g.hazeK ?? g.level, envK: g.envK ?? g.level });
    post.bloom.strength = g.bloom;
    const U = post.grade.uniforms;
    U.uExposure.value = g.exposure; U.uSat.value = g.sat; U.uVignette.value = g.vignette; U.uFlash.value = g.flash;

    return { t, beat: b, shot: name, ov };
  }

  return { apply };
}
