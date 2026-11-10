// The Ghost rig: the 12 printed parts (from assets/ghost.bin, built from hardware/stl by
// prep/build_assets.py) plus the bought-in parts that are not STLs (screen, LED ring,
// springs, servos...).  Units are millimetres, frame is the generator's: +y up, +z = eye.
import * as THREE from 'three';
import { EYE_FRAG, EYE_VERT, MOODS, LED_COLORS } from './eye.js';

const V3 = (a) => new THREE.Vector3(a[0], a[1], a[2]);

export async function loadAssets(base = 'assets/') {
  const [meta, buf] = await Promise.all([
    fetch(base + 'ghost.json').then((r) => r.json()),
    fetch(base + 'ghost.bin').then((r) => r.arrayBuffer()),
  ]);
  const f32 = new Float32Array(buf);
  const geo = {};
  for (const [name, p] of Object.entries(meta.parts)) {
    const g = new THREE.BufferGeometry();
    const n = p.count;
    g.setAttribute('position', new THREE.BufferAttribute(f32.subarray(p.offset, p.offset + n * 3), 3));
    g.setAttribute('normal', new THREE.BufferAttribute(f32.subarray(p.offset + n * 3, p.offset + n * 6), 3));
    if (p.tangents) g.setAttribute('tangent', new THREE.BufferAttribute(f32.subarray(p.offset + n * 6, p.offset + n * 10), 4));
    g.computeBoundingSphere(); g.computeBoundingBox();
    geo[name] = g;
  }
  return { meta, geo };
}

// ---------------------------------------------------------------------------------------
// textures made in code
// ---------------------------------------------------------------------------------------
function brushedTexture() {
  // long streaks along u: drives roughness so the silver reads as brushed, not chrome
  const w = 1024, h = 1024;
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  const x = c.getContext('2d');
  x.fillStyle = 'rgb(128,128,128)'; x.fillRect(0, 0, w, h);
  let s = 7;
  const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < 26000; i++) {
    const y = rnd() * h, len = 200 + rnd() * 900, x0 = rnd() * w - 200;
    const v = 128 + (rnd() - 0.5) * 120;
    x.strokeStyle = `rgba(${v},${v},${v},${0.05 + rnd() * 0.10})`;
    x.lineWidth = 0.5 + rnd() * 1.1;
    x.beginPath(); x.moveTo(x0, y); x.lineTo(x0 + len, y + (rnd() - 0.5) * 2); x.stroke();
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 8;
  t.colorSpace = THREE.NoColorSpace;
  return t;
}

function bezelGlowTexture() {
  // what the 16 LEDs look like through 2 mm of white plastic: a soft ring with 16 hot spots
  const s = 512, c = document.createElement('canvas'); c.width = c.height = s;
  const x = c.getContext('2d');
  x.fillStyle = '#000'; x.fillRect(0, 0, s, s);
  const R = 26, px = (mm) => (mm / (2 * R)) * s;      // texture spans +-26 mm
  x.globalCompositeOperation = 'lighter';
  const g0 = x.createRadialGradient(s / 2, s / 2, px(13), s / 2, s / 2, px(25));
  g0.addColorStop(0, 'rgba(255,255,255,0)'); g0.addColorStop(0.45, 'rgba(255,255,255,0.42)');
  g0.addColorStop(0.75, 'rgba(255,255,255,0.30)'); g0.addColorStop(1, 'rgba(255,255,255,0.10)');
  x.fillStyle = g0; x.fillRect(0, 0, s, s);
  for (let i = 0; i < 16; i++) {
    const a = (i * 22.5 * Math.PI) / 180, cx = s / 2 + px(19.5) * Math.cos(a), cy = s / 2 - px(19.5) * Math.sin(a);
    const g = x.createRadialGradient(cx, cy, 0, cx, cy, px(6.5));
    g.addColorStop(0, 'rgba(255,255,255,0.85)'); g.addColorStop(0.35, 'rgba(255,255,255,0.4)'); g.addColorStop(1, 'rgba(255,255,255,0)');
    x.fillStyle = g; x.fillRect(0, 0, s, s);
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function planarUV(geometry, scale, ox = 0.5, oy = 0.5) {
  const p = geometry.attributes.position, uv = new Float32Array(p.count * 2);
  for (let i = 0; i < p.count; i++) { uv[i * 2] = p.getX(i) * scale + ox; uv[i * 2 + 1] = p.getY(i) * scale + oy; }
  geometry.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
}

function brushedUV(geometry) {
  // u runs along the brushing direction (the tangent), v across it
  const p = geometry.attributes.position, n = geometry.attributes.normal, t = geometry.attributes.tangent;
  const uv = new Float32Array(p.count * 2);
  const P = new THREE.Vector3(), N = new THREE.Vector3(), T = new THREE.Vector3(), B = new THREE.Vector3();
  for (let i = 0; i < p.count; i++) {
    P.fromBufferAttribute(p, i); N.fromBufferAttribute(n, i); T.set(t.getX(i), t.getY(i), t.getZ(i));
    B.crossVectors(N, T);
    uv[i * 2] = P.dot(T) / 70; uv[i * 2 + 1] = P.dot(B) / 30;
  }
  geometry.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
}

const SPRING_L = 15;
const TIP_LEN = 8;      // mm of orange at the end of each shell piece
function springGeometry(coils = 6.5, radius = 5.7, wire = 0.55) {
  // helix along +z at a nominal 15 mm, scaled in z to the live spring length (9 mm shut, 21 mm open)
  class Helix extends THREE.Curve {
    getPoint(u, target = new THREE.Vector3()) {
      const a = u * coils * Math.PI * 2;
      return target.set(Math.cos(a) * radius, Math.sin(a) * radius, u * SPRING_L);
    }
  }
  return new THREE.TubeGeometry(new Helix(), 260, wire, 8, false);
}

// ---------------------------------------------------------------------------------------
export function buildGhost({ meta, geo }) {
  const root = new THREE.Group(); root.name = 'ghost';
  const brushed = brushedTexture();

  // ---- materials ----------------------------------------------------------------------
  const silver = new THREE.MeshPhysicalMaterial({
    color: 0xe4e6ea, metalness: 1.0, roughness: 0.66, roughnessMap: brushed,
    anisotropy: 0.5, envMapIntensity: 1.0,
  });
  // painted tips: the last TIP_LEN mm of each piece, measured along the piece's own axis
  const tipU = { uTipStart: { value: 1e9 }, uTipColor: { value: new THREE.Color(0xd08a2e) }, uTipAmount: { value: 1 } };
  silver.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, tipU);
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nattribute float axial;\nvarying float vAxial;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvAxial = axial;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying float vAxial;\nuniform float uTipStart, uTipAmount;\nuniform vec3 uTipColor;')
      .replace('#include <color_fragment>', '#include <color_fragment>\nfloat tipK = smoothstep(-fwidth(vAxial), fwidth(vAxial), vAxial - uTipStart) * uTipAmount;\ndiffuseColor.rgb = mix(diffuseColor.rgb, uTipColor, tipK);')
      .replace('#include <roughnessmap_fragment>', '#include <roughnessmap_fragment>\nroughnessFactor = mix(roughnessFactor, 0.42, tipK);')
      .replace('#include <metalnessmap_fragment>', '#include <metalnessmap_fragment>\nmetalnessFactor = mix(metalnessFactor, 0.0, tipK);');
  };
  const black = new THREE.MeshPhysicalMaterial({ color: 0x111113, metalness: 0.0, roughness: 0.62, envMapIntensity: 0.9 });
  const blackSatin = new THREE.MeshPhysicalMaterial({ color: 0x0a0a0c, metalness: 0.0, roughness: 0.48, envMapIntensity: 1.0 });
  const hidden = new THREE.MeshPhysicalMaterial({ color: 0x101012, metalness: 0.0, roughness: 0.5 });   // pins, ring, spool: "any" filament
  const steel = new THREE.MeshPhysicalMaterial({ color: 0xd9dce2, metalness: 1.0, roughness: 0.22, envMapIntensity: 1.6 });
  const bezelMat = new THREE.MeshPhysicalMaterial({
    color: 0xdcdfe4, metalness: 0.0, roughness: 0.46, clearcoat: 0.2, clearcoatRoughness: 0.4,
    emissive: new THREE.Color(0x000000), emissiveMap: bezelGlowTexture(), emissiveIntensity: 1.0,
  });
  const pcbBlack = new THREE.MeshStandardMaterial({ color: 0x050506, roughness: 0.6 });

  const mesh = (g, m, name) => { const o = new THREE.Mesh(g, m); o.name = name; o.castShadow = o.receiveShadow = true; return o; };

  // ---- stand --------------------------------------------------------------------------
  const base = mesh(geo.base, black, 'base');
  const lid = mesh(geo.base_lid, black, 'base_lid');
  root.add(base, lid);

  const pan = new THREE.Group(); pan.name = 'pan';
  pan.position.set(0, 0, meta.pan_axis[2]);
  const panInner = new THREE.Group(); panInner.position.set(0, 0, -meta.pan_axis[2]); pan.add(panInner);
  root.add(pan);
  const arm = mesh(geo.arm, blackSatin, 'arm'); panInner.add(arm);

  const tilt = new THREE.Group(); tilt.name = 'tilt';
  tilt.position.copy(V3(meta.tilt_pivot));
  const head = new THREE.Group(); head.name = 'head'; head.position.copy(V3(meta.tilt_pivot)).negate(); tilt.add(head);
  panInner.add(tilt);

  // tilt servo (MG90S) in the arm's pocket: body + horn that carries the head mount
  const servoMat = new THREE.MeshPhysicalMaterial({ color: 0x10141c, roughness: 0.35, metalness: 0.0, clearcoat: 0.4 });
  const tiltServo = new THREE.Group();
  const sb = mesh(new THREE.BoxGeometry(26.6, 12.2, 22.8), servoMat, 'tilt_servo');
  sb.position.set(-0.2, -4, meta.tilt_pivot[2] - 5.5);
  const horn = mesh(new THREE.CylinderGeometry(3.4, 3.4, 2.2, 24), new THREE.MeshStandardMaterial({ color: 0xe8e8e8, roughness: 0.5 }), 'tilt_horn');
  horn.rotation.z = Math.PI / 2; horn.position.set(14.0, -4, meta.tilt_pivot[2]);
  tiltServo.add(sb, horn); panInner.add(tiltServo);

  // ---- head ---------------------------------------------------------------------------
  const headMount = mesh(geo.head_mount, blackSatin, 'head_mount');
  const coreFront = mesh(geo.core_front, black, 'core_front');
  const coreBack = mesh(geo.core_back, black, 'core_back');
  planarUV(geo.eye_bezel, 1 / 52);
  const bezel = mesh(geo.eye_bezel, bezelMat, 'eye_bezel');
  head.add(headMount, coreFront, coreBack, bezel);

  // screen: GC9A01, drawn by the same maths as software/ghost/eye.py (see eye.js)
  const zF = meta.bezel_front_z;                       // front face of the lens lip
  const eyeRT = new THREE.WebGLRenderTarget(512, 512, { type: THREE.HalfFloatType, colorSpace: THREE.LinearSRGBColorSpace, depthBuffer: false });
  const eyeU = {
    uCol: { value: new THREE.Color() }, uRadius: { value: 0.3 }, uSx: { value: 1 }, uSy: { value: 1 }, uDy: { value: 0 },
    uGlow: { value: 1 }, uSpin: { value: 0 }, uRing: { value: 0.55 }, uBlink: { value: 1 }, uTime: { value: 0 },
    uListen: { value: 0 }, uIsListening: { value: 0 }, uPower: { value: 1 }, uTimer: { value: -1 }, uLook: { value: new THREE.Vector2() },
  };
  const eyeScene = new THREE.Scene();
  const eyeCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  eyeScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({ uniforms: eyeU, vertexShader: EYE_VERT, fragmentShader: EYE_FRAG, depthTest: false })));
  const screenMat = new THREE.MeshPhysicalMaterial({
    color: 0x020203, roughness: 0.32, metalness: 0.0,
    emissive: 0xffffff, emissiveMap: eyeRT.texture, emissiveIntensity: 1.0, envMapIntensity: 0.6,
  });
  const screen = mesh(new THREE.CircleGeometry(16.2, 96), screenMat, 'screen');
  screen.position.set(0, 0, zF - meta.bezel_len + 0.15); screen.castShadow = false;
  const screenSurround = mesh(new THREE.RingGeometry(16.2, 22.4, 96), pcbBlack, 'screen_surround');
  screenSurround.position.copy(screen.position);
  head.add(screen, screenSurround);

  // LED ring: 16 WS2812B on a 44 mm ring, right behind the lens lip
  const ledGroup = new THREE.Group(); ledGroup.name = 'led_ring';
  const ringPcb = mesh(new THREE.RingGeometry(16.6, 22.2, 96), pcbBlack, 'led_pcb');
  ringPcb.position.z = zF - meta.bezel_lip_t - 2.2;
  const ringWall = mesh(new THREE.CylinderGeometry(16.6, 16.6, 1.6, 96, 1, true), new THREE.MeshStandardMaterial({ color: 0x050506, roughness: 0.6, side: THREE.DoubleSide }), 'led_pcb_edge');
  ringWall.rotation.x = Math.PI / 2; ringWall.position.z = ringPcb.position.z - 0.8;
  ledGroup.add(ringPcb, ringWall);
  const ledMat = new THREE.MeshBasicMaterial({ color: 0x000000, toneMapped: false });
  const leds = [];
  const ledGeo = new THREE.BoxGeometry(4.6, 4.6, 1.5);
  for (let i = 0; i < 16; i++) {
    const a = (i * 22.5 * Math.PI) / 180;
    const m = new THREE.Mesh(ledGeo, ledMat.clone());
    m.position.set(19.5 * Math.cos(a), 19.5 * Math.sin(a), zF - meta.bezel_lip_t - 1.2); m.rotation.z = a;
    ledGroup.add(m); leds.push(m);
  }
  head.add(ledGroup);

  // light the eye throws on the shell, the stand and the floor
  const eyeLight = new THREE.PointLight(0x78c8ff, 0, 0, 2);
  eyeLight.position.set(0, 0, zF + 90); head.add(eyeLight);
  const wellLight = new THREE.PointLight(0x78c8ff, 0, 45, 2);
  wellLight.position.set(0, 0, zF - meta.bezel_len + 3.5); head.add(wellLight);

  // ---- shell: 8 pieces on 8 slider pins with 8 springs -------------------------------------
  brushedUV(geo.fin);
  {
    const p = geo.fin.attributes.position, ax = V3(meta.fin_axis0), a = new Float32Array(p.count), v = new THREE.Vector3();
    let mx = -1e9;
    for (let i = 0; i < p.count; i++) { a[i] = v.fromBufferAttribute(p, i).dot(ax); mx = Math.max(mx, a[i]); }
    geo.fin.setAttribute('axial', new THREE.BufferAttribute(a, 1));
    tipU.uTipStart.value = mx - TIP_LEN;
  }
  const fins = [], pins = [], springs = [];
  const springGeo = springGeometry();
  const zAxis = new THREE.Vector3(0, 0, 1);
  for (let i = 0; i < 8; i++) {
    const M = new THREE.Matrix4().fromArray(meta.fin_matrices[i].flat()).transpose();
    const d = V3(meta.fin_dirs[i]);
    const f = mesh(geo.fin, silver, 'fin' + i);
    f.quaternion.setFromRotationMatrix(M); f.userData.dir = d;
    const q = new THREE.Quaternion().setFromUnitVectors(zAxis, d);
    const pn = mesh(geo.slider_pin, hidden, 'pin' + i); pn.quaternion.copy(q); pn.userData.dir = d;
    const sp = mesh(springGeo, steel, 'spring' + i); sp.quaternion.copy(q); sp.userData.dir = d;
    head.add(f, pn, sp); fins.push(f); pins.push(pn); springs.push(sp);
  }
  const ring = mesh(geo.spider_ring, hidden, 'spider_ring'); head.add(ring);

  // ---- state --------------------------------------------------------------------------
  const st = { open: 0, mood: 'neutral', eyePower: 1, ledLevel: 1, glow: 1 };
  const cur = { col: new THREE.Color(), led: new THREE.Color() };
  const tmp = new THREE.Color();

  function setOpen(f, perPiece) {
    st.open = f;
    for (let i = 0; i < 8; i++) {
      const fi = perPiece ? perPiece[i] : f;
      const d = fins[i].userData.dir, travel = meta.shell_travel * fi;
      fins[i].position.copy(d).multiplyScalar(travel);
      pins[i].position.copy(d).multiplyScalar(meta.pin_cap_closed + travel);
      const r0 = meta.core_r - 0.3, r1 = meta.core_r + meta.closed_gap + meta.spring_seat_depth + travel;
      springs[i].position.copy(d).multiplyScalar(r0); springs[i].scale.set(1, 1, (r1 - r0) / SPRING_L);
    }
    ring.position.set(0, 0, THREE.MathUtils.lerp(meta.ring_z_closed, meta.ring_z_open, f) - meta.ring_t / 2);
  }

  // mood: name from software/ghost/eye.py MOODS; eye colour and LED colour come from there
  function setMood(name, k = 1) {
    st.mood = name;
    const m = MOODS[name] || MOODS.neutral, l = LED_COLORS[name] || LED_COLORS.neutral;
    tmp.setRGB(m.col[0] / 255, m.col[1] / 255, m.col[2] / 255, THREE.SRGBColorSpace);
    const u = eyeU;
    if (k >= 1) cur.col.copy(tmp); else cur.col.lerp(tmp, k);
    for (const [key, un] of [['radius', 'uRadius'], ['sx', 'uSx'], ['sy', 'uSy'], ['dy', 'uDy'], ['glow', 'uGlow'], ['spin', 'uSpin'], ['ring', 'uRing']])
      u[un].value += (m[key] - u[un].value) * Math.min(k, 1);
    u.uIsListening.value = name === 'listening' ? 1 : 0;
    tmp.setRGB(l[0] / 255, l[1] / 255, l[2] / 255, THREE.SRGBColorSpace);
    if (k >= 1) cur.led.copy(tmp); else cur.led.lerp(tmp, k);
  }

  // eyePower 0..1 (screen backlight), ledLevel 0..1 (ring brightness), glow = how hard both hit the scene
  function setGlow({ eyePower = st.eyePower, ledLevel = st.ledLevel, glow = st.glow } = {}) {
    st.eyePower = eyePower; st.ledLevel = ledLevel; st.glow = glow;
  }

  function update(renderer, t) {
    const u = eyeU;
    u.uTime.value = t; u.uCol.value.copy(cur.col); u.uPower.value = st.eyePower;
    const prev = renderer.getRenderTarget();
    renderer.setRenderTarget(eyeRT); renderer.render(eyeScene, eyeCam); renderer.setRenderTarget(prev);
    screenMat.emissiveIntensity = 0.62 * st.glow;
    // lights.py: k = 0.6 + 0.15*sin(t*1.6 + phase) for the resting moods
    for (let i = 0; i < 16; i++) {
      const k = (0.6 + 0.15 * Math.sin(t * 1.6 + (i / 16) * Math.PI * 2)) * st.ledLevel;
      leds[i].material.color.copy(cur.led).multiplyScalar(k * 7.0 * st.glow);
    }
    bezelMat.emissive.copy(cur.led); bezelMat.emissiveIntensity = 0.8 * st.ledLevel * st.glow;
    eyeLight.color.copy(cur.led).lerp(cur.col, 0.5);
    eyeLight.intensity = 1.0e4 * st.glow * (0.55 * st.ledLevel + 0.45 * st.eyePower);
    wellLight.color.copy(cur.col); wellLight.intensity = 150 * st.glow * st.eyePower;
  }

  setOpen(0); setMood('neutral', 1);
  return {
    root, pan, tilt, head, meta, st, eyeU,
    parts: { base, lid, arm, headMount, coreFront, coreBack, bezel, screen, ledGroup, fins, pins, springs, ring, tiltServo },
    materials: { silver, black, blackSatin, bezelMat, screenMat, hidden, steel }, tipU,
    setOpen, setMood, setGlow, update,
  };
}
