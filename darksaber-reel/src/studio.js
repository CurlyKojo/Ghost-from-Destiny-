// (Shared with the Ghost reel.)  The studio: image-based lighting from softboxes built in code, a strong rim light, a soft
// fill, a dark reflective floor, haze, and the post chain (bloom, depth of field, grade).
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { Reflector } from 'three/addons/objects/Reflector.js';

function gradientPanel(w, h, intensity, tint = [1, 1, 1], soft = 0.35) {
  // a softbox: bright core, feathered edges (so reflections on the silver roll off softly)
  const c = document.createElement('canvas'); c.width = 128; c.height = 128;
  const x = c.getContext('2d'), img = x.createImageData(128, 128);
  for (let j = 0; j < 128; j++) for (let i = 0; i < 128; i++) {
    const u = Math.abs(i / 127 - 0.5) * 2, v = Math.abs(j / 127 - 0.5) * 2;
    const f = (t) => 1 - THREE.MathUtils.smoothstep(t, 1 - soft * 2, 1);
    const a = f(u) * f(v) * 255, k = (j * 128 + i) * 4;
    img.data[k] = img.data[k + 1] = img.data[k + 2] = a; img.data[k + 3] = 255;
  }
  x.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.NoColorSpace;
  const m = new THREE.MeshBasicMaterial({ map: t, color: new THREE.Color(tint[0] * intensity, tint[1] * intensity, tint[2] * intensity), side: THREE.DoubleSide, toneMapped: false });
  return new THREE.Mesh(new THREE.PlaneGeometry(w, h), m);
}

export function buildEnvironment(renderer, k = 1) {
  const s = new THREE.Scene();
  s.add(new THREE.Mesh(new THREE.SphereGeometry(40, 32, 16), new THREE.MeshBasicMaterial({ color: new THREE.Color(0.030, 0.034, 0.042), side: THREE.BackSide })));
  const add = (w, h, I, pos, tint, soft) => { const p = gradientPanel(w, h, I * k, tint, soft); p.position.set(...pos); p.lookAt(0, 0, 0); s.add(p); return p; };
  add(4, 16, 20, [-13, 5, -10], [0.86, 0.93, 1.0], 0.3);     // rim, back left: the strong one
  add(4, 12, 5.0, [14, 3, -8], [0.80, 0.90, 1.0], 0.3);      // kicker, back right
  add(18, 12, 0.85, [1, 15, 3], [1.0, 0.98, 0.96], 0.45);    // overhead softbox
  add(24, 20, 0.72, [7, 2, 16], [1.0, 1.0, 1.0], 0.45);      // front fill, big and dim
  add(1.4, 14, 2.6, [-12, 0, 11], [1.0, 0.97, 0.94], 0.3);   // thin strip: edge pings on the bevels
  add(1.2, 12, 1.6, [13, 1, 10], [0.9, 0.95, 1.0], 0.3);     // its twin on the right
  add(30, 5, 0.45, [0, -7, 12], [0.7, 0.8, 1.0], 0.4);       // low bounce off the floor
  const pm = new THREE.PMREMGenerator(renderer);
  const rt = pm.fromScene(s, 0.012, 0.1, 100);
  pm.dispose();
  return rt.texture;
}

function backdrop(floorY, horizon) {
  // a dome whose colour depends on elevation: haze sitting on the horizon, black overhead
  const m = new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, fog: false,
    uniforms: { uHorizon: { value: horizon.clone() }, uTop: { value: new THREE.Color(0.0012, 0.0016, 0.0024) }, uY: { value: floorY }, uGain: { value: 1 } },
    vertexShader: 'varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position,1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }',
    fragmentShader: `uniform vec3 uHorizon, uTop; uniform float uY, uGain; varying vec3 vW;
      void main(){ vec3 d = normalize(vW - vec3(cameraPosition.x, uY, cameraPosition.z)); float e = abs(d.y);
        vec3 c = mix(uHorizon, uTop, smoothstep(0.0, 0.5, e)); c += uHorizon * 0.9 * exp(-e * 14.0); gl_FragColor = vec4(c * uGain, 1.0); }`,
  });
  const dome = new THREE.Mesh(new THREE.SphereGeometry(6000, 48, 24), m); dome.userData.noDepth = true; dome.name = 'backdrop';
  return dome;
}

function hazeSprite(color, size, opacity) {
  const c = document.createElement('canvas'); c.width = c.height = 256;
  const x = c.getContext('2d');
  const g = x.createRadialGradient(128, 128, 0, 128, 128, 128);
  for (let i = 0; i <= 16; i++) { const r = i / 16; g.addColorStop(r, `rgba(255,255,255,${Math.exp(-r * r * 5.5) * (1 - r * r)})`); }
  x.fillStyle = g; x.fillRect(0, 0, 256, 256);
  const m = new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), color, opacity, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, fog: false });
  const sp = new THREE.Sprite(m); sp.scale.setScalar(size); return sp;
}

const FLOOR_SHADER = {
  name: 'GlossFloor',
  uniforms: {
    color: { value: null }, tDiffuse: { value: null }, textureMatrix: { value: null },
    uTexel: { value: new THREE.Vector2(1 / 512, 1 / 512) }, uBlur: { value: 2.2 }, uReflect: { value: 0.7 },
    uPool: { value: new THREE.Color(0.040, 0.050, 0.068) }, uPoolR: { value: 460 }, uCenter: { value: new THREE.Vector2(0, 0) },
    uFloorY: { value: 0 }, uFade: { value: 1400 }, uFog: { value: new THREE.Color() }, uFogD: { value: 0.00042 },
    uHorizon: { value: new THREE.Color() }, uTop: { value: new THREE.Color(0.0012, 0.0016, 0.0024) }, uSkyGain: { value: 1 },
  },
  vertexShader: /* glsl */`
    uniform mat4 textureMatrix; varying vec4 vUv; varying vec3 vWorld;
    void main() { vUv = textureMatrix * vec4(position, 1.0); vec4 w = modelMatrix * vec4(position, 1.0); vWorld = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`,
  fragmentShader: /* glsl */`
    uniform vec3 color; uniform sampler2D tDiffuse; varying vec4 vUv; varying vec3 vWorld;
    uniform vec2 uTexel; uniform float uBlur, uReflect, uPoolR, uFade, uFogD; uniform vec3 uPool, uFog, uHorizon, uTop; uniform vec2 uCenter; uniform float uSkyGain;
    float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
    void main() {
      vec2 uv = vUv.xy / vUv.w;
      float d = length(vWorld.xz - uCenter);
      // glossy, not mirror: blur grows with distance from the object, with a little grain in the taps
      float rad = uBlur * (0.8 + d / 260.0);
      float rot = hash(gl_FragCoord.xy) * 6.2831;
      vec4 acc = vec4(0.0); float ws = 0.0;
      for (int i = 0; i < 16; i++) {
        float fi = float(i);
        float r = sqrt((fi + 0.5) / 16.0) * rad, a = fi * 2.39996 + rot;
        vec2 o = vec2(cos(a), sin(a) * 1.6) * r * uTexel;
        float w = 1.0 - 0.5 * (fi / 16.0);
        acc += texture2D(tDiffuse, uv + o) * w; ws += w;
      }
      vec3 V = normalize(cameraPosition - vWorld);
      float e = abs(V.y);
      vec3 sky = (mix(uHorizon, uTop, smoothstep(0.0, 0.5, e)) + uHorizon * 0.9 * exp(-e * 14.0)) * uSkyGain;
      vec4 r4 = acc / ws;
      vec3 refl = r4.rgb + sky * (1.0 - clamp(r4.a, 0.0, 1.0));
      float F = 0.05 + 0.95 * pow(1.0 - clamp(V.y, 0.0, 1.0), 4.0);
      float pool = exp(-(d * d) / (uPoolR * uPoolR));
      float fade = exp(-d / uFade);
      vec3 c = color + uPool * pool + refl * uReflect * mix(0.45, 1.0, F) * mix(1.0, fade, clamp(r4.a, 0.0, 1.0));
      float fd = length(cameraPosition - vWorld) * uFogD;
      c = mix(uFog * uSkyGain, c, exp(-fd * fd));
      gl_FragColor = vec4(c, 1.0);
    }`,
};

export function buildStudio(renderer, scene, { floorY, width, height }) {
  const horizon = new THREE.Color(0.0085, 0.012, 0.019);
  scene.background = null;
  const dome = backdrop(floorY, horizon); dome.layers.set(1); scene.add(dome);
  scene.fog = new THREE.FogExp2(horizon.getHex(), 0.00042);
  scene.environment = buildEnvironment(renderer);
  scene.environmentIntensity = 1.0;

  // ---- direct lights --------------------------------------------------------------------
  const rim = new THREE.DirectionalLight(0xdcecff, 3.0);
  rim.position.set(-420, 330, -520); rim.target.position.set(0, -20, -30);
  rim.castShadow = true; rim.shadow.mapSize.set(1024, 1024); rim.shadow.radius = 5; rim.shadow.blurSamples = 10;
  Object.assign(rim.shadow.camera, { left: -260, right: 260, top: 260, bottom: -260, near: 100, far: 1600 });
  rim.shadow.bias = -0.0006; rim.shadow.normalBias = 0.6;
  const kicker = new THREE.DirectionalLight(0xbfd8ff, 0.9);
  kicker.position.set(520, 180, -380); kicker.target.position.set(0, -20, -30);
  const fill = new THREE.DirectionalLight(0xfff4ea, 0.7);
  fill.position.set(260, 220, 600); fill.target.position.set(0, -30, 0);
  const top = new THREE.DirectionalLight(0xffffff, 0.3);
  top.position.set(40, 700, 60); top.target.position.set(0, -100, -40);
  top.castShadow = false; top.shadow.mapSize.set(1024, 1024); top.shadow.radius = 9; top.shadow.blurSamples = 16;
  Object.assign(top.shadow.camera, { left: -260, right: 260, top: 260, bottom: -260, near: 100, far: 1200 });
  top.shadow.bias = -0.0006; top.shadow.normalBias = 0.6;
  scene.add(rim, rim.target, kicker, kicker.target, fill, fill.target, top, top.target);

  // ---- floor ----------------------------------------------------------------------------
  const sh = { ...FLOOR_SHADER, uniforms: THREE.UniformsUtils.clone(FLOOR_SHADER.uniforms) };
  const rw = Math.round(width * 0.6), rh = Math.round(height * 0.6);
  sh.uniforms.uTexel.value.set(1 / rw, 1 / rh);
  const floor = new Reflector(new THREE.PlaneGeometry(9000, 9000), { textureWidth: rw, textureHeight: rh, color: 0x020304, shader: sh, clipBias: 0.5, multisample: 0 });
  floor.rotation.x = -Math.PI / 2; floor.position.y = floorY; floor.name = 'floor';
  floor.material.uniforms.uFog.value.copy(horizon).multiplyScalar(1.9 * 1.0);
  floor.material.uniforms.uHorizon.value.copy(horizon);
  scene.add(floor);
  const shadowCatcher = new THREE.Mesh(new THREE.PlaneGeometry(2400, 2400), new THREE.ShadowMaterial({ opacity: 0.55, color: 0x000000 }));
  shadowCatcher.rotation.x = -Math.PI / 2; shadowCatcher.position.y = floorY + 0.15; shadowCatcher.receiveShadow = true;

  // ---- haze -----------------------------------------------------------------------------
  const haze = new THREE.Group();
  const h1 = hazeSprite(0x7890b4, 1250, 0.17); h1.position.set(-60, 40, -700);
  const h2 = hazeSprite(0x4a6283, 2600, 0.035); h2.position.set(300, -60, -1000);
  const h3 = hazeSprite(0x9fb8dc, 900, 0.05); h3.position.set(-330, 330, -560);
  haze.add(h1, h2, h3); haze.children.forEach((h) => h.layers.set(1)); scene.add(haze);

  // one dial for the whole studio: 1 = the approved look, 0 = lights off (only the Ghost's own glow)
  const base = { rim: rim.intensity, kicker: kicker.intensity, fill: fill.intensity, top: top.intensity,
    pool: floor.material.uniforms.uPool.value.clone(), haze: haze.children.map((h) => h.material.opacity) };
  function setLevel(k, { rimK = k, hazeK = k, envK = k } = {}) {
    rim.intensity = base.rim * rimK; kicker.intensity = base.kicker * rimK; fill.intensity = base.fill * k; top.intensity = base.top * k;
    scene.environmentIntensity = envK;
    floor.material.uniforms.uPool.value.copy(base.pool).multiplyScalar(k);
    dome.material.uniforms.uGain.value = hazeK;
    floor.material.uniforms.uSkyGain.value = hazeK;
    haze.children.forEach((h, i) => (h.material.opacity = base.haze[i] * hazeK));
  }
  return { rim, kicker, fill, top, floor, floorU: floor.material.uniforms, haze, dome, setLevel };
}

// ---------------------------------------------------------------------------------------
// post
// ---------------------------------------------------------------------------------------
const DOF_SHADER = {
  name: 'Dof',
  uniforms: {
    tDiffuse: { value: null }, tDepth: { value: null }, uNear: { value: 1 }, uFar: { value: 10 },
    uFocus: { value: 800 }, uAperture: { value: 0 }, uMaxBlur: { value: 14 }, uTexel: { value: new THREE.Vector2() },
  },
  vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }',
  fragmentShader: /* glsl */`
    #include <packing>
    uniform sampler2D tDiffuse, tDepth; uniform float uNear, uFar, uFocus, uAperture, uMaxBlur; uniform vec2 uTexel; varying vec2 vUv;
    float viewZ(vec2 uv) { return -perspectiveDepthToViewZ(texture2D(tDepth, uv).x, uNear, uFar); }
    float coc(float z) { return clamp(uAperture * abs(z - uFocus) / z, 0.0, uMaxBlur); }
    float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
    void main() {
      float z0 = viewZ(vUv), c0 = coc(z0);
      vec3 acc = texture2D(tDiffuse, vUv).rgb; float ws = 1.0;
      if (uAperture > 0.0) {
        for (int i = 0; i < 36; i++) {
          float fi = float(i) + 0.5;
          float r = sqrt(fi / 36.0), a = fi * 2.39996;
          vec2 o = vec2(cos(a), sin(a)) * r;
          // gather: a sample contributes if its own blur reaches this pixel (keeps sharp edges sharp)
          vec2 uv = vUv + o * uMaxBlur * uTexel;
          float zs = viewZ(uv), cs = coc(zs);
          float reach = (zs < z0) ? cs : min(cs, c0);
          float w = smoothstep(0.0, 1.0, reach - r * uMaxBlur + 1.0);
          vec3 s = texture2D(tDiffuse, uv).rgb;
          w *= 1.0 + 0.6 * max(max(s.r, s.g), s.b);          // bright spots become bokeh
          acc += s * w; ws += w;
        }
      }
      gl_FragColor = vec4(acc / ws, 1.0);
    }`,
};

const GRADE_SHADER = {
  name: 'Grade',
  uniforms: {
    tDiffuse: { value: null }, uExposure: { value: 1.0 }, uVignette: { value: 0.78 }, uGrain: { value: 0.03 },
    uTime: { value: 0 }, uSat: { value: 1.0 }, uLift: { value: new THREE.Vector3(0.004, 0.007, 0.013) }, uCA: { value: 0.0012 },
    uFade: { value: 1.0 }, uContrast: { value: 0.18 }, uFlash: { value: 0.0 },
  },
  vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }',
  fragmentShader: /* glsl */`
    uniform sampler2D tDiffuse; uniform float uExposure, uVignette, uGrain, uTime, uSat, uCA, uFade, uContrast, uFlash; uniform vec3 uLift; varying vec2 vUv;
    vec3 RRTAndODTFit(vec3 v) { vec3 a = v * (v + 0.0245786) - 0.000090537; vec3 b = v * (0.983729 * v + 0.4329510) + 0.238081; return a / b; }
    vec3 aces(vec3 color) {
      const mat3 I = mat3(0.59719, 0.07600, 0.02840, 0.35458, 0.90834, 0.13383, 0.04823, 0.01566, 0.83777);
      const mat3 O = mat3(1.60475, -0.10208, -0.00327, -0.53108, 1.10813, -0.07276, -0.07367, -0.00605, 1.07602);
      color *= uExposure / 0.6; color = I * color; color = RRTAndODTFit(color); color = O * color; return clamp(color, 0.0, 1.0);
    }
    float hash(vec2 p) { p = fract(p * vec2(443.897, 441.423)); p += dot(p, p.yx + 19.19); return fract((p.x + p.y) * p.x); }
    void main() {
      vec2 d = vUv - 0.5;
      vec3 c;
      c.r = texture2D(tDiffuse, vUv + d * uCA).r; c.g = texture2D(tDiffuse, vUv).g; c.b = texture2D(tDiffuse, vUv - d * uCA).b;
      float v = 1.0 - uVignette * smoothstep(0.25, 0.95, length(d * vec2(1.0, 0.78)) * 1.35);
      c *= v;
      c += uFlash * vec3(0.55, 0.8, 1.0);
      c = aces(c);
      float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
      c = mix(vec3(l), c, uSat);
      c = pow(max(c, 0.0), vec3(1.0 / 2.2));
      c = mix(c, c * c * (3.0 - 2.0 * c), uContrast);        // gentle S-curve, keeps hue in the shadows
      c = c + uLift * (1.0 - l);
      float g = hash(gl_FragCoord.xy + fract(uTime) * 91.7) - 0.5;
      c += g * uGrain * (1.0 - 0.5 * l);
      gl_FragColor = vec4(c * uFade, 1.0);
    }`,
};

export function buildPost(renderer, scene, camera, width, height, { samples = 4 } = {}) {
  const depthTexture = new THREE.DepthTexture(width, height); depthTexture.type = THREE.UnsignedIntType;
  // scene colour (MSAA) -> resolved; depth comes from a second, cheap depth-only target
  const rt = new THREE.WebGLRenderTarget(width, height, { type: THREE.HalfFloatType, samples });
  const composer = new EffectComposer(renderer, rt);
  composer.setPixelRatio(1); composer.setSize(width, height);
  const renderPass = new RenderPass(scene, camera);
  composer.addPass(renderPass);

  const depthRT = new THREE.WebGLRenderTarget(width, height, { depthTexture, depthBuffer: true });
  const depthMat = new THREE.MeshBasicMaterial({ colorWrite: false });
  const depthClipped = new Map();          // one depth material per set of clipping planes
  function renderDepth() {
    const hidden = [], swapped = [];
    scene.traverse((o) => {
      if (!o.visible) return;
      if (o.isSprite || o.userData.noDepth || (o.material && o.material.transparent)) { hidden.push(o); o.visible = false; return; }
      if (o.isMesh && o.material && !Array.isArray(o.material)) {
        let m = depthMat; const cp = o.material.clippingPlanes;
        if (cp && cp.length) { m = depthClipped.get(cp); if (!m) { m = new THREE.MeshBasicMaterial({ colorWrite: false, clippingPlanes: cp, side: THREE.DoubleSide }); depthClipped.set(cp, m); } }
        swapped.push([o, o.material]); o.material = m;
      }
    });
    renderer.setRenderTarget(depthRT); renderer.clear(); renderer.render(scene, camera); renderer.setRenderTarget(null);
    for (const [o, m] of swapped) o.material = m;
    hidden.forEach((o) => (o.visible = true));
  }

  const dof = new ShaderPass(DOF_SHADER);
  dof.uniforms.tDepth.value = depthTexture; dof.uniforms.uTexel.value.set(1 / width, 1 / height);
  composer.addPass(dof);
  const bloom = new UnrealBloomPass(new THREE.Vector2(width, height), 0.5, 0.7, 1.15);
  composer.addPass(bloom);
  const grade = new ShaderPass(GRADE_SHADER);
  composer.addPass(grade);

  function render(t) {
    dof.enabled = dof.uniforms.uAperture.value > 0;
    if (dof.enabled) { dof.uniforms.uNear.value = camera.near; dof.uniforms.uFar.value = camera.far; renderDepth(); }
    grade.uniforms.uTime.value = t;
    composer.render();
  }
  return { composer, bloom, dof, grade, render };
}
