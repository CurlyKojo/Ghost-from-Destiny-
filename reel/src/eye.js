// The eye, ported line for line from software/ghost/eye.py (EyeRenderer.frame) to GLSL so
// it can animate on the 3D screen.  Mood parameters and LED colours are copied from
// software/ghost/eye.py MOODS and software/ghost/lights.py COLORS.

// emotion -> colour rgb, iris radius, squash x, squash y, y offset, glow, spinner, ring
const M = (col, radius, sx, sy, dy, glow, spin, ring) => ({ col, radius, sx, sy, dy, glow, spin, ring });
export const MOODS = {
  neutral:   M([120, 200, 255], 0.30, 1.00, 1.00,  0.00, 1.00, 0.0, 0.55),
  happy:     M([140, 220, 255], 0.30, 1.10, 0.72,  0.05, 1.20, 0.0, 0.58),
  excited:   M([170, 235, 255], 0.36, 1.05, 1.05,  0.00, 1.50, 0.0, 0.62),
  curious:   M([120, 200, 255], 0.30, 0.92, 1.12, -0.04, 1.10, 0.0, 0.56),
  thinking:  M([110, 180, 255], 0.26, 1.00, 1.00,  0.02, 0.90, 1.0, 0.52),
  worried:   M([150, 170, 255], 0.27, 1.00, 0.80,  0.03, 0.85, 0.0, 0.50),
  sad:       M([100, 140, 230], 0.25, 1.05, 0.65,  0.08, 0.60, 0.0, 0.48),
  surprised: M([180, 240, 255], 0.40, 1.00, 1.00,  0.00, 1.60, 0.0, 0.66),
  annoyed:   M([255, 150, 110], 0.26, 1.20, 0.55,  0.00, 1.00, 0.0, 0.52),
  smug:      M([150, 210, 255], 0.28, 1.15, 0.60, -0.03, 1.05, 0.0, 0.55),
  sleepy:    M([ 70, 110, 180], 0.22, 1.10, 0.35,  0.06, 0.45, 0.0, 0.40),
  listening: M([160, 230, 255], 0.33, 1.00, 1.00,  0.00, 1.35, 0.0, 0.70),
  speaking:  M([130, 205, 255], 0.31, 1.00, 1.00,  0.00, 1.15, 0.0, 0.58),
  offline:   M([120, 120, 130], 0.20, 1.00, 1.00,  0.00, 0.40, 0.0, 0.35),
};

export const LED_COLORS = {
  neutral: [60, 140, 255], happy: [80, 180, 255], excited: [120, 220, 255],
  curious: [60, 150, 255], thinking: [40, 110, 255], worried: [90, 90, 255],
  sad: [30, 60, 200], surprised: [160, 230, 255], annoyed: [255, 90, 40],
  smug: [90, 170, 255], sleepy: [10, 20, 60], listening: [110, 210, 255],
  speaking: [80, 170, 255], offline: [40, 40, 45],
};

export const EYE_VERT = /* glsl */`
varying vec2 vUv;
void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;

export const EYE_FRAG = /* glsl */`
precision highp float;
varying vec2 vUv;
uniform vec3 uCol;            // linear
uniform float uRadius, uSx, uSy, uDy, uGlow, uSpin, uRing, uBlink, uTime, uListen, uIsListening, uPower, uTimer;
uniform vec2 uLook;
const float PI = 3.14159265;
vec3 toSRGB(vec3 c) { return pow(max(c, 0.0), vec3(1.0 / 2.2)); }
vec3 toLinear(vec3 c) { return pow(max(c, 0.0), vec3(2.2)); }
void main() {
  // image coordinates as in numpy: x right, y DOWN, -1..1
  vec2 P = vec2(vUv.x * 2.0 - 1.0, 1.0 - vUv.y * 2.0);
  float R = length(P);
  float T = atan(P.y, P.x);
  vec3 col = toSRGB(uCol);                                  // eye.py works in display space
  vec3 img = vec3(6.0, 10.0, 22.0) / 255.0 * pow(clamp(1.0 - R * 0.85, 0.0, 1.0), 1.5);

  float breathe = 1.0 + 0.03 * sin(uTime * 1.6);
  float listen = 1.0 + 0.35 * uListen * uIsListening;
  float radius = uRadius * breathe * listen;
  float sx = uSx, sy = uSy * uBlink;
  float x = (P.x - uLook.x) / max(sx, 0.05);
  float y = (P.y - uDy - uLook.y) / max(sy, 0.05);
  float rr = sqrt(x * x + y * y) / radius;

  float hexa = cos(atan(y, x) * 6.0) * 0.06 + 1.0;
  float core = clamp((1.0 - rr * hexa) * 8.0, 0.0, 1.0);
  float glow = exp(-pow(rr - 0.6, 2.0) * 2.0) * 0.55 * uGlow;
  float halo = exp(-rr * 1.3) * 0.35 * uGlow;
  float pupil = clamp((0.38 - rr) * 12.0, 0.0, 1.0);
  img += (core * 0.85 + glow + halo) * col;
  img += pupil * 0.9;

  float ring = exp(-pow(R - uRing, 2.0) * 900.0) * (0.25 + 0.4 * uListen);
  if (uTimer >= 0.0) {
    // timer face (reel only): the lens ring becomes a countdown arc, clockwise from 12 o'clock
    float a = mod(atan(P.x, -P.y) + 2.0 * PI, 2.0 * PI) / (2.0 * PI);
    float arc = exp(-pow(R - 0.74, 2.0) * 420.0);
    float on = smoothstep(uTimer + 0.004, uTimer - 0.004, a);
    img += arc * (0.10 + 1.25 * on) * col;
  } else {
    img += ring * col * 0.9;
  }
  if (uSpin > 0.02) {
    float ang = mod(T + uTime * 3.0, 2.0 * PI / 3.0);
    float seg = step(ang, 1.0);
    float band = exp(-pow(R - radius * 1.55, 2.0) * 700.0);
    img += band * seg * uSpin * 0.9 * col;
  }
  if (uIsListening > 0.5) {
    float rip = fract(uTime * 0.6);
    float band = exp(-pow(R - (radius * 1.2 + rip * 0.5), 2.0) * 500.0) * (1.0 - rip);
    img += band * 0.5 * col;
  }
  img = clamp(img, 0.0, 1.0);
  float mask = smoothstep(1.0, 0.985, R);                   // round panel
  gl_FragColor = vec4(toLinear(img) * mask * uPower, 1.0);
}`;
