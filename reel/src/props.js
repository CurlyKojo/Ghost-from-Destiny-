// Everything in the reel that is NOT one of the 12 STLs: the bought-in electronics for the
// build sequence (simple stand-ins sized from docs/01-hardware-bom.md), the tendons and the
// Bowden cable, and the printer for the opening shot.  Units: mm.
import * as THREE from 'three';
import { silverPatch } from './ghost.js';

const std = (color, roughness = 0.5, metalness = 0, extra = {}) => new THREE.MeshStandardMaterial({ color, roughness, metalness, ...extra });
const box = (w, h, d, m) => new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
const cyl = (r, h, m, seg = 32, r2 = r) => new THREE.Mesh(new THREE.CylinderGeometry(r2, r, h, seg), m);
const at = (o, x, y, z) => { o.position.set(x, y, z); return o; };
const shadows = (g) => { g.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } }); return g; };

const M = {
  pcbGreen: std(0x0d4a2b, 0.7), pcbDark: std(0x14254a, 0.45), pcbBlue: std(0x1a3566, 0.45), pcbPurple: std(0x4a2f86, 0.45),
  chip: std(0x08080a, 0.35), can: std(0x9da1a8, 0.5, 1), gold: std(0xc9a44a, 0.35, 1),
  plastic: std(0x0b0b0d, 0.55), servo: new THREE.MeshPhysicalMaterial({ color: 0x23406f, roughness: 0.3, clearcoat: 0.6, clearcoatRoughness: 0.2 }),
  horn: std(0xdedede, 0.5), brass: std(0xb38a35, 0.32, 1), alu: std(0xa9adb3, 0.4, 1), steel: std(0xc8cbd0, 0.25, 1),
  ptfe: new THREE.MeshPhysicalMaterial({ color: 0xe9ecef, roughness: 0.35, clearcoat: 0.3 }),
  line: std(0xd8d2b0, 0.6), cone: std(0x0a0a0c, 0.75), bed: std(0x0b0b0d, 0.5, 0.0), sock: std(0x0d0d0f, 0.8),
};

// ---------------------------------------------------------------------------------------
function makePi() {
  // Raspberry Pi 4: 85 x 56 mm.  Local frame: x = long side, y up, origin at the board centre.
  const g = new THREE.Group(); g.name = 'pi';
  g.add(box(85, 1.4, 56, M.pcbGreen));
  g.add(at(box(15, 2.4, 15, M.can), -13.5, 1.9, 1));                 // SoC lid
  g.add(at(box(12, 1.4, 10, M.chip), 2.5, 1.4, -2));                 // RAM
  g.add(at(box(6, 1.2, 6, M.chip), 15, 1.3, 8));
  g.add(at(box(10, 1.6, 10, M.can), -31, 1.5, 13));                  // radio can
  for (const z of [0.5, 18.5]) g.add(at(box(17.5, 15.6, 13.2, M.can), 34.5, 8.5, z));   // USB
  g.add(at(box(21, 13.5, 16, M.can), 32.5, 7.4, -17.5));             // Ethernet
  g.add(at(box(51, 2.5, 5, M.plastic), -7.5, 1.9, -24.3));           // GPIO header
  for (let i = 0; i < 20; i++) for (const dz of [-1.27, 1.27]) g.add(at(box(0.6, 6, 0.6, M.gold), -31.6 + i * 2.54, 5, -24.3 + dz));
  for (const x of [-16, -2.5]) g.add(at(box(7, 3, 7.5, M.can), x, 2.2, 25));            // micro HDMI
  g.add(at(box(9, 3.2, 7.5, M.can), -31, 2.3, 25));                  // USB-C
  g.add(at(cyl(3, 12, M.plastic), 11.5, 2.3, 22.5));                 // audio jack
  g.children[g.children.length - 1].rotation.x = Math.PI / 2;
  return shadows(g);
}

function makeServo() {
  // MG90S.  Local frame: output shaft along +y, origin on the shaft axis at the top of the case.
  const g = new THREE.Group(); g.name = 'servo';
  g.add(at(box(22.8, 22.5, 12.2, M.servo), -5.5, -11.25, 0));
  g.add(at(box(32.4, 2.5, 12.2, M.servo), -5.5, -5.6, 0));           // mounting tabs
  g.add(at(cyl(5.9, 4.2, M.servo), 0, 2.1, 0));
  g.add(at(cyl(2.9, 4.2, M.servo), -8.2, 2.1, 0));
  g.add(at(cyl(2.4, 3.4, M.brass, 20), 0, 5.9, 0));                  // metal-gear output shaft
  g.add(at(box(8, 2.2, 5.6, M.plastic), -18.8, -19.5, 0));           // cable boot
  return shadows(g);
}

function makeMic() {
  // INMP441 breakout, ~14 mm round.  Local +y = the side with the port (faces the vent holes).
  const g = new THREE.Group(); g.name = 'mic';
  g.add(cyl(7, 1.2, M.pcbPurple, 40));
  g.add(at(box(3.8, 1.0, 4.7, M.can), 0, -1.1, 1.5));
  for (let i = 0; i < 6; i++) g.add(at(cyl(0.8, 0.2, M.gold, 12), -5 + i * 2, -0.7, -4.4));
  return shadows(g);
}

function makeAmp() {
  // MAX98357A breakout, ~18 x 18 mm, with its screw terminal for the speaker.
  const g = new THREE.Group(); g.name = 'amp';
  g.add(box(18, 1.6, 18, M.pcbBlue));
  g.add(at(box(3.2, 0.9, 3.2, M.chip), -1, 1.2, 1));
  g.add(at(box(7.6, 8, 7, std(0x27467e, 0.5)), 4.5, 4.8, -5));                // terminal block
  for (const x of [2.6, 6.4]) g.add(at(cyl(1.5, 0.4, M.can, 16), x, 9, -5));
  for (let i = 0; i < 7; i++) g.add(at(cyl(0.9, 0.3, M.gold, 12), -7.6 + i * 2.54, 0.95, 7.4));
  return shadows(g);
}

function makeSpeaker() {
  // 40 mm, 4 ohm.  Local +y = the direction it fires (up, into the lid grille).
  const g = new THREE.Group(); g.name = 'speaker';
  g.add(at(cyl(20, 2, M.can, 64), 0, -1, 0));
  g.add(at(cyl(7, 7, M.cone, 48, 18.2), 0, -5, 0));                  // basket
  g.add(at(cyl(11.5, 6, M.can, 48), 0, -11, 0));                     // magnet
  const cone = new THREE.Mesh(new THREE.ConeGeometry(17.5, 5, 64, 1, true), new THREE.MeshStandardMaterial({ color: 0x08080a, roughness: 0.7, side: THREE.DoubleSide }));
  cone.rotation.x = Math.PI; cone.position.y = -2.4; g.add(cone);
  g.add(at(new THREE.Mesh(new THREE.SphereGeometry(6, 32, 12, 0, Math.PI * 2, 0, Math.PI / 2.6), M.cone), 0, -6.6, 0));
  return shadows(g);
}

function lineTexture() {
  // rectilinear top fill: one bead every 0.42 mm
  const c = document.createElement('canvas'); c.width = 8; c.height = 64;
  const x = c.getContext('2d');
  for (let j = 0; j < 64; j++) { const v = 128 + 110 * Math.cos((j / 16) * Math.PI * 2); x.fillStyle = `rgb(${v},${v},${v})`; x.fillRect(0, j, 8, 1); }
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.colorSpace = THREE.NoColorSpace; t.anisotropy = 8;
  t.repeat.set(1 / 1.68, 1 / 1.68); t.rotation = Math.PI / 4;
  return t;
}

function hull2d(pts) {
  // Andrew's monotone chain
  pts.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lo = [], up = [];
  for (const p of pts) { while (lo.length >= 2 && cross(lo[lo.length - 2], lo[lo.length - 1], p) <= 0) lo.pop(); lo.push(p); }
  for (let i = pts.length - 1; i >= 0; i--) { const p = pts[i]; while (up.length >= 2 && cross(up[up.length - 2], up[up.length - 1], p) <= 0) up.pop(); up.push(p); }
  lo.pop(); up.pop(); return lo.concat(up);
}

// ---------------------------------------------------------------------------------------
export function buildProps(ghost, geo) {
  const meta = ghost.meta, P = {};
  const floorY = meta.base_bottom_y, bz = meta.base_center_z, y0 = meta.lid_top_y;
  const baseToWorld = (x, y, z) => new THREE.Vector3(x, z + floorY, bz - y);      // base frame: z up, +y toward the back

  // ---- in the base -----------------------------------------------------------------------
  P.pi = makePi();
  P.pi.position.copy(baseToWorld(10, -8, meta.base_wall + 6 + 0.7));
  ghost.root.add(P.pi);

  // shell servo mount: generate_stl.py does not place it, so it sits on the floor left of the Pi,
  // sheath post toward the back.  Mount frame (x along the servo shaft, z up) -> world.
  P.mount = new THREE.Group(); P.mount.name = 'shell_servo_mount';
  P.mount.matrixAutoUpdate = false;
  P.mount.matrix.makeBasis(new THREE.Vector3(0, 0, -1), new THREE.Vector3(-1, 0, 0), new THREE.Vector3(0, 1, 0))
    .setPosition(baseToWorld(-62, -8, meta.base_wall));
  const mountMesh = new THREE.Mesh(geo.shell_servo_mount, ghost.materials.black); mountMesh.castShadow = mountMesh.receiveShadow = true;
  P.mountMesh = mountMesh;
  P.shellServo = makeServo();
  P.shellServoHome = new THREE.Group();                                           // servo shaft (+y) -> mount +x
  P.shellServoHome.matrixAutoUpdate = false;
  P.shellServoHome.matrix.makeBasis(new THREE.Vector3(0, 1, 0), new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 0, -1)).setPosition(1.5, 0, 4 + 6.3);
  P.shellServoHome.add(P.shellServo);
  P.spool = new THREE.Group();                                                    // spool axis (STL z) -> mount +x
  const spoolMesh = new THREE.Mesh(geo.spool, std(0x9a9da3, 0.45)); spoolMesh.castShadow = true;
  P.spoolSpin = new THREE.Group(); P.spoolSpin.add(spoolMesh);
  const wrap = new THREE.Mesh(new THREE.TorusGeometry(meta.spool_r + 0.45, 0.5, 8, 48), M.steel); wrap.position.z = 5.2; P.spoolSpin.add(wrap);
  const hornDisc = cyl(10, 1.6, M.horn, 32); hornDisc.rotation.x = Math.PI / 2; hornDisc.position.z = 0.9; P.spoolSpin.add(hornDisc);
  P.spool.add(P.spoolSpin);
  P.spool.matrixAutoUpdate = false;
  P.spool.matrix.makeBasis(new THREE.Vector3(0, 1, 0), new THREE.Vector3(0, 0, 1), new THREE.Vector3(1, 0, 0)).setPosition(7.5, 0, 4 + 6.3);
  // wire from the spool rim to the sheath post (mount x = 28)
  const rimZ = 4 + 6.3 + meta.spool_r + 0.45;
  P.wire = cyl(0.5, 1, M.steel, 10); P.wire.rotation.z = Math.PI / 2;
  P.wire.scale.y = 28 - 12.7; P.wire.position.set((28 + 12.7) / 2, 0, rimZ);
  P.mount.add(mountMesh, P.shellServoHome, P.spool, P.wire);
  ghost.root.add(P.mount);
  // PTFE tube inside the base: from the post up to where it leaves through the lid
  const mw = (x, y, z) => new THREE.Vector3(x, y, z).applyMatrix4(P.mount.matrix);
  const lidExit = new THREE.Vector3(0, y0 - 1, -139);
  const innerPts = [mw(31, 0, rimZ), mw(40, 0, rimZ), mw(52, -6, rimZ + 3), new THREE.Vector3(-30, floorY + 26, -128), new THREE.Vector3(-8, y0 - 6, -138), lidExit.clone()];
  P.innerTube = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(innerPts), 80, 2, 12), M.ptfe);
  P.innerTube.castShadow = true; ghost.root.add(P.innerTube);

  P.amp = makeAmp(); P.amp.position.copy(baseToWorld(26, 44, meta.base_wall + 0.8)); P.amp.rotation.y = 0.35; ghost.root.add(P.amp);

  // ---- on the lid (these ride with it when it lifts) ---------------------------------------
  P.lidGroup = new THREE.Group(); P.lidGroup.name = 'lid_group';
  ghost.root.add(P.lidGroup); P.lidGroup.add(ghost.parts.lid);
  P.speaker = makeSpeaker(); P.speaker.position.set(-34, y0 - 3.1, bz + 34); P.lidGroup.add(P.speaker);
  P.panServo = makeServo(); P.panServo.rotation.y = Math.PI / 2;               // long axis front-to-back
  P.panServo.position.set(0, y0 - 6.6, meta.pan_axis[2]); P.lidGroup.add(P.panServo);

  // ---- on the arm ------------------------------------------------------------------------
  ghost.parts.tiltServo.visible = false; ghost.parts.tiltServo.userData.skip = true;   // replaced by the detailed servo
  P.tiltServo = makeServo();
  P.tiltServoHome = new THREE.Group(); P.tiltServoHome.matrixAutoUpdate = false;        // shaft (+y) -> +x, case toward the back
  P.tiltServoHome.matrix.makeBasis(new THREE.Vector3(0, 0, 1), new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 1, 0)).setPosition(10.6, meta.tilt_pivot[1], meta.tilt_pivot[2]);
  P.tiltServoHome.add(P.tiltServo);
  const horn = cyl(3.6, 1.6, M.horn, 24); horn.position.y = 7.2; P.tiltServo.add(horn);
  ghost.panInner.add(P.tiltServoHome);

  // ---- in the head -----------------------------------------------------------------------
  const zScreen = ghost.parts.screen.position.z;
  P.lcdPcb = box(36.5, 36.5, 1.6, M.pcbDark); P.lcdPcb.position.set(0, 0, zScreen - 1.9);
  P.lcdGlass = cyl(17.6, 1.4, std(0x030304, 0.15), 64); P.lcdGlass.rotation.x = Math.PI / 2; P.lcdGlass.position.set(0, 0, zScreen - 0.8);
  ghost.head.add(P.lcdPcb, P.lcdGlass);
  P.lcdSet = [ghost.parts.screen, ghost.parts.screenSurround, P.lcdPcb, P.lcdGlass];
  P.mic = makeMic();
  { const n = new THREE.Vector3(0, 0.75, -0.6).normalize();
    P.mic.position.copy(n).multiplyScalar(meta.core_r - meta.core_wall - 1.0);
    P.mic.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), n); P.micDir = n; }
  ghost.head.add(P.mic);

  // tendons: 8 braided lines from the pin caps to the spider ring (cylinders stretched per frame)
  P.tendons = [];
  for (let i = 0; i < 8; i++) { const m = cyl(0.32, 1, M.line, 6); m.castShadow = false; ghost.head.add(m); P.tendons.push(m); }
  const up = new THREE.Vector3(0, 1, 0), a = new THREE.Vector3(), b = new THREE.Vector3(), d = new THREE.Vector3();
  P.updateTendons = (grow = 1) => {
    const ring = ghost.parts.ring;
    for (let i = 0; i < 8; i++) {
      const pin = ghost.parts.pins[i], dir = pin.userData.dir;
      a.copy(pin.position).addScaledVector(dir, meta.pin_cap_t / 2);
      const az = Math.atan2(dir.y, dir.x) + (i < 4 ? -1 : 1) * Math.PI / 8;       // ring holes sit every 45 deg, offset 22.5
      b.set(meta.ring_tie_r * Math.cos(az), meta.ring_tie_r * Math.sin(az), meta.ring_t / 2).add(ring.position);
      d.subVectors(b, a); const len = d.length() * grow;
      const t = P.tendons[i];
      t.position.copy(a).addScaledVector(d.normalize(), len / 2); t.scale.set(1, Math.max(len, 0.001), 1);
      t.quaternion.setFromUnitVectors(up, d);
    }
  };

  // Bowden cable: neck socket -> over the tilt block -> down the back of the arm -> into the lid.
  // Rebuilt each frame because the neck end moves with the tilt.
  P.bowden = new THREE.Mesh(new THREE.BufferGeometry(), M.ptfe); P.bowden.castShadow = true; P.bowden.frustumCulled = false;
  ghost.panInner.add(P.bowden);
  P.grommet = new THREE.Mesh(new THREE.TorusGeometry(3.2, 1.1, 10, 24), M.plastic); P.grommet.rotation.x = Math.PI / 2; P.grommet.position.set(0, y0 + 0.4, -139);
  ghost.panInner.add(P.grommet);
  const piv = new THREE.Vector3().fromArray(meta.tilt_pivot), xAxis = new THREE.Vector3(1, 0, 0);
  const fixed = [[0, 27, -84], [0, 21, -108], [0, -6, -127], [0, -44, -137.5], [0, -96, -137.5], [0, y0 + 1, -139]].map((p) => new THREE.Vector3(...p));
  P.updateBowden = (draw = 1) => {
    const ang = ghost.tilt.rotation.x;
    const h = (x, y, z) => new THREE.Vector3(x, y, z).sub(piv).applyAxisAngle(xAxis, ang).add(piv);
    const curve = new THREE.CatmullRomCurve3([h(0, 0, -34), h(0, 0, -51), h(0, 13, -62), ...fixed], false, 'centripetal');
    P.bowden.geometry.dispose();
    const seg = 120, rad = 10;
    P.bowden.geometry = new THREE.TubeGeometry(curve, seg, 2, rad);
    P.bowden.geometry.setDrawRange(0, Math.round(seg * THREE.MathUtils.clamp(draw, 0, 1)) * rad * 6);
  };

  // ---- the printer (opening shot) ---------------------------------------------------------
  const pr = new THREE.Group(); pr.name = 'printer'; P.printer = pr; ghost.root.parent ? ghost.root.parent.add(pr) : null;
  const bedTop = floorY + 9;
  const bed = box(232, 5, 372, M.bed); bed.position.set(0, bedTop - 2.5, 0); bed.receiveShadow = true; pr.add(bed);
  const bedEdge = box(238, 3, 378, std(0x18191c, 0.35, 1)); bedEdge.position.set(0, bedTop - 6.5, 0); pr.add(bedEdge);
  P.bedTop = bedTop;
  // the 8 pieces, largest face down, exactly as fin_x8.stl sits on the bed
  P.clip = new THREE.Plane(new THREE.Vector3(0, -1, 0), 0);
  const printU = { uTipStart: { value: 1e9 }, uTipColor: { value: new THREE.Color(0xd08a2e) }, uTipAmount: { value: 0 }, uLayer: { value: 1 } };
  const sv = ghost.materials.silver;
  P.printMat = new THREE.MeshPhysicalMaterial({ color: sv.color, metalness: 1, roughness: 0.6, roughnessMap: sv.roughnessMap, anisotropy: 0.3, clippingPlanes: [P.clip], side: THREE.DoubleSide });
  P.printMat.onBeforeCompile = (sh) => silverPatch(sh, printU); P.printU = printU;
  const lines = lineTexture();
  P.capMat = new THREE.MeshPhysicalMaterial({ color: 0xd9dce1, metalness: 1, roughness: 0.42, bumpMap: lines, bumpScale: 0.3, roughnessMap: lines });
  const bedM = new THREE.Matrix4().fromArray(meta.fin_bed_matrix.flat()).transpose();
  const toYUp = new THREE.Matrix4().makeRotationX(-Math.PI / 2);
  // piece extents on the bed, to centre each one in its grid cell
  const bb = new THREE.Box3(), pos = geo.fin.attributes.position, v = new THREE.Vector3();
  const bedPts = new Float32Array(pos.count * 3);
  for (let i = 0; i < pos.count; i++) { v.fromBufferAttribute(pos, i).applyMatrix4(bedM); bb.expandByPoint(v); bedPts.set([v.x, v.y, v.z], i * 3); }
  const size = bb.getSize(new THREE.Vector3()); P.printHeight = size.z; P.bedPts = bedPts;
  P.printFins = []; P.caps = [];
  const capGeo = new THREE.BufferGeometry(); P.capGeo = capGeo;
  for (let i = 0; i < 8; i++) {
    const col = i % 2, row = Math.floor(i / 2);
    const cell = new THREE.Group();
    cell.position.set((col - 0.5) * 104, bedTop, (1.5 - row) * 88);
    cell.rotation.y = (col ? Math.PI : 0) + (row % 2 ? 0.0 : 0.0);
    const local = new THREE.Group(); local.matrixAutoUpdate = false;
    local.matrix.copy(toYUp).multiply(new THREE.Matrix4().makeTranslation(-bb.min.x - size.x / 2, -bb.min.y - size.y / 2, -bb.min.z));
    const fin = new THREE.Mesh(geo.fin, P.printMat); fin.matrixAutoUpdate = false; fin.matrix.copy(bedM); fin.castShadow = fin.receiveShadow = true;
    const cap = new THREE.Mesh(capGeo, P.capMat); cap.receiveShadow = true;
    local.add(fin, cap); cell.add(local); pr.add(cell);
    P.printFins.push({ cell, local, fin, cap, home: cell.position.clone(), rotY: cell.rotation.y });
  }
  // cross-section of the piece at height h above the bed -> cap polygon (bed frame, z = h)
  P.outline = [];
  P.setPrintHeight = (h) => {
    P.clip.constant = bedTop + h;
    const pts = [];
    for (let i = 0; i < bedPts.length; i += 9) {
      for (let e = 0; e < 3; e++) {
        const a0 = i + e * 3, b0 = i + ((e + 1) % 3) * 3, za = bedPts[a0 + 2] - h, zb = bedPts[b0 + 2] - h;
        if ((za < 0) !== (zb < 0)) { const k = za / (za - zb); pts.push([bedPts[a0] + (bedPts[b0] - bedPts[a0]) * k, bedPts[a0 + 1] + (bedPts[b0 + 1] - bedPts[a0 + 1]) * k]); }
      }
    }
    const hull = pts.length >= 3 ? hull2d(pts) : [];
    P.outline = hull;
    const n = hull.length, arr = new Float32Array(Math.max(n - 2, 0) * 9), uv = new Float32Array(Math.max(n - 2, 0) * 6), nor = new Float32Array(Math.max(n - 2, 0) * 9);
    for (let k = 1; k < n - 1; k++) {
      const tri = [hull[0], hull[k], hull[k + 1]];
      tri.forEach((p, j) => { arr.set([p[0], p[1], h - 0.02], (k - 1) * 9 + j * 3); uv.set([p[0], p[1]], (k - 1) * 6 + j * 2); nor.set([0, 0, 1], (k - 1) * 9 + j * 3); });
    }
    capGeo.setAttribute('position', new THREE.BufferAttribute(arr, 3));
    capGeo.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
    capGeo.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
    capGeo.computeBoundingSphere();
    for (const f of P.printFins) f.cap.visible = h < P.printHeight - 0.05 && n >= 3;
  };
  // point on the current layer's perimeter (fraction 0..1 round the outline), in world space, for piece `idx`
  P.outlinePoint = (idx, frac, h, out = new THREE.Vector3()) => {
    const hull = P.outline, n = hull.length; if (n < 2) return out.set(0, bedTop + h, 0);
    let total = 0; const seg = [];
    for (let i = 0; i < n; i++) { const a = hull[i], b = hull[(i + 1) % n]; const l = Math.hypot(b[0] - a[0], b[1] - a[1]); seg.push(l); total += l; }
    let dist = (((frac % 1) + 1) % 1) * total, i = 0;
    while (dist > seg[i] && i < n - 1) { dist -= seg[i]; i++; }
    const a = hull[i], b = hull[(i + 1) % n], k = seg[i] ? dist / seg[i] : 0;
    // pull 0.5 mm inside the wall so the nozzle sits on the bead, not off the edge
    let cx = 0, cy = 0; for (const p of hull) { cx += p[0] / n; cy += p[1] / n; }
    let x = a[0] + (b[0] - a[0]) * k, y = a[1] + (b[1] - a[1]) * k; const dl = Math.hypot(cx - x, cy - y) || 1;
    x += (cx - x) / dl * 0.5; y += (cy - y) / dl * 0.5;
    const f = P.printFins[idx]; f.cell.updateMatrixWorld(true);
    return out.set(x, y, h).applyMatrix4(f.local.matrix).applyMatrix4(f.cell.matrixWorld);
  };
  // hot end.  Origin at the nozzle tip, +y up.
  const nz = new THREE.Group(); nz.name = 'nozzle'; P.nozzle = nz; pr.add(nz);
  nz.add(at(cyl(0.45, 4.6, M.brass, 32, 3.3), 0, 2.3, 0));
  nz.add(at(cyl(4.3, 3.2, M.brass, 6), 0, 6.2, 0));
  nz.add(at(box(20, 11.5, 16, M.alu), 4.5, 13.6, 0));
  { const h = cyl(3, 20.5, M.steel, 20); h.rotation.x = Math.PI / 2; nz.add(at(h, 9.5, 14, 0)); }      // heater cartridge
  nz.add(at(cyl(3, 9, M.steel, 24), 0, 24.3, 0));
  const dark = std(0x15161a, 0.45, 1);
  nz.add(at(cyl(4.5, 30, dark, 24), 0, 43.5, 0));
  for (let i = 0; i < 10; i++) nz.add(at(cyl(11.5, 1.3, dark, 40), 0, 30 + i * 2.9, 0));
  nz.add(at(box(30, 34, 3, M.plastic), 0, 44, -13.5));                // carriage plate behind
  shadows(nz);

  P.buildOnly = [P.pi, P.mount, P.innerTube, P.amp, P.speaker, P.panServo, P.tiltServoHome, P.lcdPcb, P.lcdGlass, P.mic, ...P.tendons, P.bowden, P.grommet];
  return P;
}
