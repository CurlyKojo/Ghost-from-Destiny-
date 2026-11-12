// The Darksaber for the 3D shots.  Blade shells, core strips, emitter and plug are the
// project's own STLs (assets/saber.bin, built by prep/build_assets.py).  The handle and the
// guard are NOT: the original hilt files are not part of the project folder, so those two
// are simple stand-ins shaped after the project's own render.
// Saber frame: x along the blade toward the tip (mm), y up, z toward the viewer.
import * as THREE from 'three';

export async function loadSaber(base = 'assets/') {
  const [meta, buf, outlines] = await Promise.all([
    fetch(base + 'saber.json').then((r) => r.json()),
    fetch(base + 'saber.bin').then((r) => r.arrayBuffer()),
    fetch(base + 'outlines.json').then((r) => r.json()),
  ]);
  const f32 = new Float32Array(buf), geo = {};
  for (const [name, p] of Object.entries(meta.parts)) {
    const g = new THREE.BufferGeometry(), n = p.count;
    g.setAttribute('position', new THREE.BufferAttribute(f32.subarray(p.offset, p.offset + n * 3), 3));
    g.setAttribute('normal', new THREE.BufferAttribute(f32.subarray(p.offset + n * 3, p.offset + n * 6), 3));
    g.computeBoundingSphere(); geo[name] = g;
  }
  return { meta, geo, outlines };
}

// Light pattern of the blade, shared by the real shell material and the swing ghosts.
// The COB strip sits on the edge of the black core and faces out, so the shell glows in the
// band between core and edge and round the tip, and stays dark over the core: the Darksaber look.
const BLADE_GLSL = /* glsl */`
  uniform float uFront, uPower, uTime, uCoreX1, uFake;
  varying vec3 vSaber;
  float hash1(float n) { return fract(sin(n) * 43758.5453); }
  float vnoise(float x) { float i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f); return mix(hash1(i), hash1(i + 1.0), f); }
  // signed distance to the core strip (negative inside), side view
  float coreSd(vec2 p) { return max(max(abs(p.y) - 8.0, (p.x - p.y - uCoreX1) * 0.7071), 80.0 - p.x); }
  float bladeGlow(vec3 p) {
    float sd = coreSd(p.xy);
    float band = smoothstep(-0.6, 1.2, sd) * mix(1.0, 0.72, clamp(sd / 7.0, 0.0, 1.0));     // lit gap
    float spill = 0.12 * exp(sd / 2.6) * step(sd, 0.0);                                      // a little light over the core
    float lit = smoothstep(uFront, uFront - 26.0, p.x);                                      // ignition front, base to tip
    float head = exp(-max(uFront - p.x, 0.0) / 34.0) * step(p.x, uFront) * smoothstep(730.0, 690.0, uFront);
    float flick = 0.90 + 0.10 * vnoise(p.x * 0.045 - uTime * 17.0) + 0.05 * vnoise(p.x * 0.31 + uTime * 43.0);
    return (band + spill) * lit * flick * uPower * (1.0 + 1.6 * head);
  }`;

export function buildSaber({ meta, geo }) {
  const root = new THREE.Group(); root.name = 'saber';        // origin = swing pivot
  const body = new THREE.Group(); root.add(body);              // twist about the blade axis
  const PIVOT_X = 40;
  const inner = new THREE.Group(); inner.position.x = -PIVOT_X; body.add(inner);
  const mesh = (g, m, name) => { const o = new THREE.Mesh(g, m); o.name = name; o.castShadow = o.receiveShadow = true; inner.add(o); return o; };

  const U = { uFront: { value: 0 }, uPower: { value: 0 }, uTime: { value: 0 }, uCoreX1: { value: 685 - 9 * Math.SQRT2 }, uFake: { value: 1 } };
  // ---- blade shell: frosted white PETG; emissive pattern from the strip inside ----------------
  const shellMat = new THREE.MeshPhysicalMaterial({ color: 0xc9ced6, roughness: 0.42, metalness: 0, clearcoat: 0.35, clearcoatRoughness: 0.35 });
  shellMat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, U);
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vSaber;').replace('#include <begin_vertex>', '#include <begin_vertex>\nvSaber = position;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\n' + BLADE_GLSL)
      .replace('#include <color_fragment>', '#include <color_fragment>\ndiffuseColor.rgb *= mix(1.0, mix(0.16, 1.0, smoothstep(-1.5, 1.0, coreSd(vSaber.xy))), uFake) * mix(1.0, 0.02, clamp(uPower, 0.0, 1.0) * smoothstep(uFront, uFront - 26.0, vSaber.x));')      // the black core shows through
      .replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\ntotalEmissiveRadiance += vec3(0.86, 0.93, 1.0) * bladeGlow(vSaber) * 4.4;');
  };
  const shells = ['shell1', 'shell2', 'shell3'].map((n) => mesh(geo[n], shellMat, n));
  const coreMat = new THREE.MeshStandardMaterial({ color: 0x050506, roughness: 0.6 });
  const cores = Object.keys(geo).filter((k) => k.startsWith('core')).map((n) => mesh(geo[n], coreMat, n));
  for (const c of cores) c.castShadow = false;

  // ---- hilt -------------------------------------------------------------------------------
  const hiltMat = new THREE.MeshPhysicalMaterial({ color: 0x24262a, roughness: 0.42, metalness: 0.55, clearcoat: 0.15 });
  const hiltLite = new THREE.MeshPhysicalMaterial({ color: 0x3b3e44, roughness: 0.38, metalness: 0.6 });
  const emitter = mesh(geo.emitter, hiltMat, 'emitter');
  const plug = mesh(geo.plug, hiltLite, 'plug');
  // stand-ins -------------------------------------------------------------------------------
  const standIn = new THREE.Group(); standIn.name = 'hilt_stand_in'; inner.add(standIn);
  const grip = new THREE.Group(), pommel = new THREE.Group(); standIn.add(grip, pommel);
  const oct = (parent, x0, x1, hy, hz, mat) => {            // octagonal bar along x
    const g = new THREE.CylinderGeometry(1, 1, x1 - x0, 8, 1); g.rotateY(Math.PI / 8); g.rotateZ(Math.PI / 2);
    const k = Math.cos(Math.PI / 8); g.scale(1, hy / k, hz / k);
    const m = new THREE.Mesh(g, mat); m.position.set((x0 + x1) / 2, 0, 0); m.castShadow = m.receiveShadow = true; parent.add(m); return m;
  };
  oct(grip, -118, 8, 15, 12.6, hiltMat);
  for (const z of [12.9, -12.9]) for (const [x0, x1, y] of [[-104, -8, 6.5], [-92, -8, 0], [-80, -8, -6.5]]) {
    const st = new THREE.Mesh(new THREE.BoxGeometry(x1 - x0, 1.6, 0.9), hiltLite); st.position.set((x0 + x1) / 2, y, z); grip.add(st);
  }
  oct(pommel, -214, -118, 13.2, 11, hiltMat);                        // ringed section's core
  for (let i = 0; i < 6; i++) oct(pommel, -212 + i * 16, -212 + i * 16 + 9.5, 17, 14.6, i % 2 ? hiltMat : hiltLite);
  oct(pommel, -228, -214, 15.5, 13, hiltLite);
  // guard: a slanted racetrack plate the hilt passes through, parallel to the emitter's rear face
  const cap = new THREE.Shape(); const GL = 150, GW = 46, r = GW / 2;
  cap.moveTo(-GL / 2 + r, -r); cap.lineTo(GL / 2 - r, -r); cap.absarc(GL / 2 - r, 0, r, -Math.PI / 2, Math.PI / 2, false);
  cap.lineTo(-GL / 2 + r, r); cap.absarc(-GL / 2 + r, 0, r, Math.PI / 2, Math.PI * 1.5, false);
  const guardMesh = new THREE.Mesh(new THREE.ExtrudeGeometry(cap, { depth: 5, bevelEnabled: true, bevelThickness: 1.6, bevelSize: 1.6, bevelSegments: 3, curveSegments: 24 }), hiltLite);
  guardMesh.geometry.translate(0, 0, -2.5);
  const u = new THREE.Vector3(30, -51.2, 0).normalize(), w = new THREE.Vector3(0, 0, 1), nrm = new THREE.Vector3().crossVectors(u, w);
  guardMesh.matrixAutoUpdate = false; guardMesh.matrix.makeBasis(u, w, nrm).setPosition(9, -3, 0); guardMesh.castShadow = guardMesh.receiveShadow = true;
  const guard = new THREE.Group(); guard.add(guardMesh); standIn.add(guard);

  // LED strip on the core's edge (bought part): a thin ribbon that can be drawn on
  const ledCurve = new THREE.CatmullRomCurve3(meta.led.map((p) => new THREE.Vector3(p[0], p[1] + Math.sign(p[1]) * 0.9, 0)), false, 'catmullrom', 0.0);
  const LED_SEG = 400, LED_RAD = 6;
  const ledGeo = new THREE.TubeGeometry(ledCurve, LED_SEG, 1.5, LED_RAD); ledGeo.scale(1, 1, 1.7);
  const strip = mesh(ledGeo, new THREE.MeshStandardMaterial({ color: 0xe9dc8a, roughness: 0.45, emissive: 0x2a2610 }), 'led_strip'); strip.castShadow = false;
  const setStrip = (k) => ledGeo.setDrawRange(0, Math.round(LED_SEG * Math.min(1, Math.max(0, k))) * LED_RAD * 6);

  // ---- light the blade throws ---------------------------------------------------------------
  const lights = [];
  for (const [x, y, z] of [[150, 40, 170], [330, -40, 190], [520, 40, 170], [240, 0, -190], [520, 0, -190]]) { const l = new THREE.PointLight(0xdcecff, 0, 0, 2); l.position.set(x, y, z); l.userData.x = x; inner.add(l); lights.push(l); }
  const back = new THREE.PointLight(0xdcecff, 0, 0, 2); back.position.set(60, 90, 120); inner.add(back);

  // ---- swing ghosts: the blade's light smeared along its arc ------------------------------------
  const ghostMat = (k) => {
    const u2 = { ...U, uGhost: { value: k } };
    return new THREE.ShaderMaterial({
      uniforms: u2, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
      vertexShader: 'varying vec3 vSaber; void main(){ vSaber = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
      fragmentShader: BLADE_GLSL + 'uniform float uGhost; void main(){ gl_FragColor = vec4(vec3(0.86, 0.93, 1.0) * bladeGlow(vSaber) * 0.5 * uGhost, 1.0); }',
    });
  };
  const ghosts = [];
  for (let i = 0; i < 20; i++) {
    const g = new THREE.Group(), tw = new THREE.Group(), inn = new THREE.Group(); inn.position.x = -PIVOT_X; g.add(tw); tw.add(inn);
    const mat = ghostMat(1);
    for (const n of ['shell1', 'shell2', 'shell3']) { const m = new THREE.Mesh(geo[n], mat); m.frustumCulled = false; inn.add(m); }
    g.userData = { mat, tw }; g.visible = false; ghosts.push(g);
  }

  function setBlade({ front, power, time }) {
    U.uFront.value = front; U.uPower.value = power; U.uTime.value = time;
    const flick = 0.93 + 0.07 * Math.sin(time * 61) * Math.sin(time * 23.7);
    for (const l of lights) l.intensity = 1.7e5 * power * flick * THREE.MathUtils.smoothstep(front, l.userData.x - 30, l.userData.x + 30);
    back.intensity = 7e4 * power * flick * THREE.MathUtils.smoothstep(front, 200, 420);
  }
  // shell look: 'clear' = see-through PETG for the assembly shot, 'lit' = the approved blade look
  function setShellMode(mode) {
    const clear = mode === 'clear';
    if (shellMat.transparent !== clear) { shellMat.transparent = clear; shellMat.needsUpdate = true; }
    shellMat.opacity = clear ? 0.78 : 1; shellMat.depthWrite = !clear; U.uFake.value = clear ? 0 : 1;
    shellMat.color.set(clear ? 0xf2f6fb : 0xc9ced6); shellMat.roughness = clear ? 0.2 : 0.42; shellMat.clearcoat = clear ? 0.8 : 0.35;
    for (const sh of shells) sh.renderOrder = clear ? 5 : 0;
    strip.visible = clear;
  }
  const coreByName = Object.fromEntries(cores.map((c) => [c.name, c]));
  const pieces = { shells, cores: coreByName, emitter, plug, guard, grip, pommel, strip };
  return { root, body, inner, shells, cores, emitter, plug, standIn, lights, ghosts, U, setBlade, setShellMode, setStrip, pieces, PIVOT_X, materials: { shellMat, hiltMat, hiltLite } };
}
