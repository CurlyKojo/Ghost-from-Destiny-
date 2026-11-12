// The 2D half of the reel: line art drawn on a canvas, frame by frame, from the real part
// outlines (assets/outlines.json).  Everything is a pure function of time.
// Stage is 1080 x 1920.  Parts are drawn blade-up: x along the blade -> screen up,
// y (blade width) -> screen left, the same way round as the 3D saber when it stands vertical.

const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, k) => a + (b - a) * k;
const smooth = (x) => { x = clamp(x); return x * x * (3 - 2 * x); };
const easeOut = (x) => 1 - Math.pow(1 - clamp(x), 3);
const easeIn = (x) => Math.pow(clamp(x), 3);
const easeInOut = (x) => { x = clamp(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const back = (x, s = 1.7) => { x = clamp(x); return 1 + (s + 1) * Math.pow(x - 1, 3) + s * Math.pow(x - 1, 2); };
const hash = (n) => { const s = Math.sin(n * 127.1) * 43758.5453; return s - Math.floor(s); };

const WHITE = '#f4f8ff', ICE = '#bfe6ff', HOT = '#ffb347', BG = '#030509';
const STEPS = ['PRINT', 'ASSEMBLE', 'SOLDER', 'IGNITE'];

export function create2D(canvas, O, T, scale) {
  const ctx = canvas.getContext('2d');
  const W = 1080, H = 1920;

  // ---- drawing helpers ----------------------------------------------------------------------
  // tf: {cx, y0, x0, s, rot?}: saber mm -> px.  Blade-up: X = cx - y*s, Y = y0 - (x - x0)*s
  // tf.rot (radians, optional) turns the whole drawing clockwise about (cx, y0)
  const P = (tf, x, y) => {
    const dx = -y * tf.s, dy = -(x - tf.x0) * tf.s;
    if (!tf.rot) return [tf.cx + dx, tf.y0 + dy];
    const c = Math.cos(tf.rot), sn = Math.sin(tf.rot); return [tf.cx + dx * c - dy * sn, tf.y0 + dx * sn + dy * c];
  };
  function trace(tf, poly, holes = true) {
    ctx.beginPath();
    for (const ring of [poly.outer, ...(holes ? poly.holes : [])]) {
      ring.forEach((p, i) => { const [X, Y] = P(tf, p[0], p[1]); i ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y); });
      ctx.closePath();
    }
  }
  function glowStroke(width = 3, color = WHITE, glow = 16, alpha = 1) {
    ctx.save(); ctx.globalAlpha *= alpha; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    ctx.strokeStyle = color; ctx.lineWidth = width; ctx.shadowColor = color; ctx.shadowBlur = glow; ctx.stroke();
    ctx.restore();
  }
  function text(str, x, y, font, { color = WHITE, alpha = 1, align = 'left', spacing = 0, glow = 0 } = {}) {
    ctx.save(); ctx.globalAlpha *= alpha; ctx.font = font; ctx.fillStyle = color; ctx.textAlign = align; ctx.textBaseline = 'alphabetic';
    ctx.letterSpacing = spacing + 'px'; if (glow) { ctx.shadowColor = color; ctx.shadowBlur = glow; }
    ctx.fillText(str, x, y); ctx.restore();
  }
  const mono = (px, w = 700) => `${w} ${px}px "JetBrains Mono"`;
  const anton = (px) => `400 ${px}px Anton`;
  const inter = (px, w = 800) => `${w} ${px}px "Inter Tight"`;

  function background(t, dim = 1) {
    ctx.fillStyle = BG; ctx.fillRect(0, 0, W, H);
    ctx.save(); ctx.globalAlpha = 0.11 * dim; ctx.fillStyle = '#9fc4ff';
    const off = (t * 14) % 60;
    for (let y = -60 + off; y < H + 60; y += 60) for (let x = 30; x < W; x += 60) ctx.fillRect(x - 1.5, y - 1.5, 3, 3);
    ctx.restore();
    const g = ctx.createRadialGradient(W / 2, 800, 200, W / 2, 800, 1250);
    g.addColorStop(0, 'rgba(60,90,140,0.10)'); g.addColorStop(0.5, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,0.75)');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  }

  // step tracker along the top + the big word bottom-left
  function tracker(t, active, alpha = 1) {
    let x = 64; const y = 300;
    STEPS.forEach((s, i) => {
      const label = `0${i + 1} ${s}`; ctx.font = mono(24);
      const w = ctx.measureText(label).width + 3 * label.length;
      const a = i === active ? 1 : i < active ? 0.55 : 0.26;
      text(label, x, y, mono(24), { alpha: a * alpha, spacing: 3, color: i === active ? WHITE : '#c9d6ea' });
      if (i === active) { ctx.save(); ctx.globalAlpha = alpha; ctx.fillStyle = ICE; ctx.shadowColor = ICE; ctx.shadowBlur = 14; ctx.fillRect(x, y + 14, w - 3, 5); ctx.restore(); }
      x += w + 30;
    });
  }
  function bigWord(word, sub, s, len) {
    const inK = back(s / 0.2, 1.2), outK = easeIn((s - (len - 0.1)) / 0.1);
    ctx.save(); ctx.beginPath(); ctx.rect(0, 1235, W, 235); ctx.clip();
    text(word, 60, 1452 + (1 - inK) * 240 - outK * 240, anton(232), { spacing: 2 });
    ctx.restore();
    text(sub, 66, 1222, mono(27), { alpha: 0.72 * clamp(s / 0.12) * (1 - outK), spacing: 4, color: ICE });
  }
  function ping(x, y, s, r = 46, color = WHITE) {            // expanding ring where a part lands
    if (s < 0 || s > 0.3) return; const k = s / 0.3;
    ctx.save(); ctx.globalAlpha = (1 - k) * 0.9; ctx.strokeStyle = color; ctx.lineWidth = 3 * (1 - k) + 1;
    ctx.beginPath(); ctx.arc(x, y, 8 + r * easeOut(k), 0, Math.PI * 2); ctx.stroke(); ctx.restore();
  }
  // a blade drawn in 2D: dark core, two white edges (the Darksaber's signature)
  function blade2d(x0, y0, x1, y1, w, alpha, t) {
    const dx = x1 - x0, dy = y1 - y0, L = Math.hypot(dx, dy) || 1, nx = -dy / L, ny = dx / L;
    ctx.save(); ctx.globalAlpha *= alpha; ctx.lineCap = 'butt';
    for (const [lw, a, blur] of [[w * 2.6, 0.10, 60], [w * 1.5, 0.22, 34]]) {
      ctx.strokeStyle = ICE; ctx.globalAlpha = alpha * a; ctx.lineWidth = lw; ctx.shadowColor = ICE; ctx.shadowBlur = blur;
      ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
    }
    ctx.globalAlpha = alpha; ctx.shadowBlur = 22; ctx.shadowColor = WHITE; ctx.strokeStyle = WHITE; ctx.lineWidth = w * 0.26;
    for (const sgn of [-1, 1]) {
      ctx.beginPath();
      const n = 22;
      for (let i = 0; i <= n; i++) {
        const k = i / n, j = (hash(i * 7.3 + Math.floor(t * 40) * 1.7 + sgn) - 0.5) * w * 0.10;
        const X = x0 + dx * k + nx * (sgn * w * 0.36 + j), Y = y0 + dy * k + ny * (sgn * w * 0.36 + j);
        i ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y);
      }
      ctx.stroke();
    }
    ctx.shadowBlur = 0; ctx.strokeStyle = '#020305'; ctx.lineWidth = w * 0.42;
    ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
    ctx.restore();
  }

  // ---- parts list (for the line-up) ------------------------------------------------------------
  const B = O.blade;
  const parts = [];
  O.shells.forEach((p, i) => parts.push({ id: 'shell' + (i + 1), poly: p, kind: 'shell' }));
  for (const [n, p] of Object.entries(O.cores)) parts.push({ id: n, poly: p, kind: 'core' });
  parts.push({ id: 'emitter', poly: O.emitter, kind: 'emitter' }, { id: 'plug', poly: O.plugCut, kind: 'plug' });
  for (const p of parts) {
    const xs = p.poly.outer.map((q) => q[0]), ys = p.poly.outer.map((q) => q[1]);
    p.x0 = Math.min(...xs); p.x1 = Math.max(...xs); p.ymin = Math.min(...ys); p.ymax = Math.max(...ys);
    p.w = p.ymax - p.ymin; p.yc = (p.ymin + p.ymax) / 2;
  }
  // line-up: all 12 standing on one base line
  const LS = 2.72, LBASE = 1150, GAP = 14;
  { let x = (W - (parts.reduce((a, p) => a + p.w * LS, 0) + GAP * (parts.length - 1))) / 2;
    for (const p of parts) { p.line = { cx: x + p.w * LS / 2 + p.yc * LS, y0: LBASE, x0: p.x0, s: LS }; x += p.w * LS + GAP; } }
  const tfLerp = (a, b, k) => ({ cx: lerp(a.cx, b.cx, k), y0: lerp(a.y0, b.y0, k), x0: lerp(a.x0, b.x0, k), s: lerp(a.s, b.s, k) });
  const strokePart = (p, tf, alpha = 1, width = 3, fill = null) => {
    ctx.save(); ctx.globalAlpha *= alpha; trace(tf, p.poly);
    if (fill) { ctx.fillStyle = fill; ctx.fill('evenodd'); }
    glowStroke(width, p.kind === 'core' ? '#cdd6e4' : WHITE, p.kind === 'core' ? 8 : 14); ctx.restore();
  };

  // =================================================================================== HOOK
  function hook(t) {
    const [t0, t1] = T.hook, s = t - t0, len = t1 - t0;
    background(t, 0.5);
    // a blade strikes across the frame, then folds down into the first printed line
    const k = easeOut(s / 0.14), out = easeInOut((s - (len - 0.2)) / 0.2);
    const ax = lerp(-60, 420, out), ay = lerp(1500, 372, out), bx = lerp(-60 + 1240 * k, 660, out), by = lerp(1500 - 1150 * k, 372, out);
    blade2d(ax, ay, bx, by, lerp(74, 10, out), 1 - 0.55 * out, t);
    const flash = Math.exp(-s * 16);
    if (flash > 0.01) { ctx.fillStyle = `rgba(215,235,255,${0.55 * flash})`; ctx.fillRect(0, 0, W, H); }
    const a = clamp((s - 0.05) / 0.07) * (1 - easeIn((s - (len - 0.16)) / 0.14));
    const sc = 1 + 0.22 * (1 - back((s - 0.05) / 0.2, 1.4));
    ctx.save(); ctx.translate(540, 900); ctx.scale(sc, sc); ctx.translate(-540, -900);
    ctx.shadowColor = 'rgba(0,0,0,0.9)'; ctx.shadowBlur = 30;
    text('3D PRINTING', 60, 860, anton(196), { alpha: a, spacing: 2 });
    text('A LIGHTSABER', 60, 1060, anton(196), { alpha: a, spacing: 2 });
    ctx.restore();
    text('THAT ACTUALLY LIGHTS UP', 66, 1128, mono(30), { alpha: a * clamp((s - 0.22) / 0.1), spacing: 5, color: ICE });
  }

  // =================================================================================== PRINT
  const tip = parts.find((p) => p.id === 'shell3');
  const PR = { cx: 540 + tip.yc * 4.3, y0: 1150, x0: tip.x0, s: 4.3 };
  function print(t) {
    const [t0, t1] = T.print, s = t - t0, len = t1 - t0;
    background(t);
    tracker(t, 0, clamp(s / 0.15)); bigWord('PRINT', '12 PARTS · 0.4 MM NOZZLE', s, len);
    const g = easeInOut((t - T.printGrow[0]) / (T.printGrow[1] - T.printGrow[0]));
    const Ltip = tip.x1 - tip.x0, hmm = g * Ltip, topY = PR.y0 - hmm * PR.s;
    const pop = t - T.partsPop;
    // bed
    const bedA = 1 - smooth(pop / 0.12);
    ctx.save(); ctx.globalAlpha = bedA; ctx.strokeStyle = '#8fa3bd'; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(300, 1154); ctx.lineTo(780, 1154); ctx.stroke();
    ctx.lineWidth = 2; for (let x = 320; x < 780; x += 40) { ctx.beginPath(); ctx.moveTo(x, 1158); ctx.lineTo(x - 12, 1172); ctx.stroke(); } ctx.restore();

    if (pop < 0) {
      // printed part so far: outline + layer hatch, clipped at the current layer
      ctx.save(); ctx.beginPath(); ctx.rect(0, topY, W, H - topY); ctx.clip();
      trace(PR, tip.poly); ctx.save(); ctx.clip();
      ctx.strokeStyle = 'rgba(190,215,245,0.34)'; ctx.lineWidth = 2;
      for (let y = PR.y0 - 5; y > topY; y -= 9) { ctx.beginPath(); ctx.moveTo(380, y); ctx.lineTo(700, y); ctx.stroke(); }
      ctx.restore(); trace(PR, tip.poly); glowStroke(3.5, WHITE, 14); ctx.restore();
      // the layer being laid + nozzle
      const S = tip.x0 + hmm, yLo = Math.max(-B.half, S - (B.tip - B.half)), xa = PR.cx - B.half * PR.s, xb = PR.cx - yLo * PR.s;
      const done = t >= T.printGrow[1];
      if (!done && g > 0.002) {
        ctx.beginPath(); ctx.moveTo(xa, topY); ctx.lineTo(xb, topY); glowStroke(5, WHITE, 22);
        const ph = Math.sin(t * 58), nx = lerp(xa, xb, 0.5 + 0.5 * ph);
        for (const [dx, a] of [[-26 * Math.cos(t * 58), 0.18], [-13 * Math.cos(t * 58), 0.35], [0, 1]]) nozzle(nx + dx, topY - 3, a);
        ctx.save(); ctx.globalAlpha = 0.4; ctx.strokeStyle = '#cfe0f5'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(nx, topY - 92); ctx.lineTo(nx, 330); ctx.stroke(); ctx.restore();
      } else if (done) {
        const f = Math.exp(-(t - T.printGrow[1]) * 22);
        trace(PR, tip.poly); ctx.fillStyle = `rgba(230,242,255,${0.8 * f})`; ctx.fill();
        nozzle(PR.cx, topY - 3 - 900 * easeIn((t - T.printGrow[1]) / 0.12), 1);
      }
      // read-out
      const layers = Math.round(g * Ltip / 0.2), total = Math.round(Ltip / 0.2);
      text('LAYER', 742, 640, mono(24), { alpha: 0.6, spacing: 5, color: ICE });
      text(String(layers).padStart(3, '0'), 738, 712, mono(66), {});
      text('/ ' + total, 742, 752, mono(24), { alpha: 0.6, spacing: 3 });
      ctx.fillStyle = 'rgba(160,185,220,0.25)'; ctx.fillRect(742, 778, 240, 8); ctx.fillStyle = WHITE; ctx.fillRect(742, 778, 240 * g, 8);
    } else {
      // the finished piece shrinks into its place and the other eleven pop in beside it
      const out = easeIn((s - (len - 0.1)) / 0.1);
      parts.forEach((p, i) => {
        if (p === tip) { strokePart(p, tfLerp(PR, p.line, easeInOut(pop / 0.2)), 1 - out, 3.2); return; }
        const s0 = 0.05 + i * 0.014, k = back((pop - s0) / 0.16, 2.0);
        if (pop < s0) return;
        const tf = { ...p.line, s: p.line.s * k, cx: p.line.cx, y0: p.line.y0 + (1 - k) * 30 };
        strokePart(p, tf, clamp((pop - s0) / 0.05) * (1 - out), 3);
      });
      const n = Math.min(12, Math.floor(pop / 0.014 / 1.6) + 1);
      text('×' + String(n).padStart(2, '0'), 1016, 470, anton(150), { align: 'right', alpha: clamp(pop / 0.06) * (1 - out) });
    }
  }
  function nozzle(x, y, alpha) {
    ctx.save(); ctx.globalAlpha *= alpha; ctx.strokeStyle = WHITE; ctx.fillStyle = BG; ctx.lineWidth = 3; ctx.lineJoin = 'round';
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - 15, y - 26); ctx.lineTo(x + 15, y - 26); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.rect(x - 30, y - 62, 60, 36); ctx.fill(); ctx.stroke();
    for (let i = 0; i < 3; i++) { ctx.beginPath(); ctx.moveTo(x - 24, y - 72 - i * 9); ctx.lineTo(x + 24, y - 72 - i * 9); ctx.stroke(); }
    ctx.fillStyle = HOT; ctx.shadowColor = HOT; ctx.shadowBlur = 16; ctx.beginPath(); ctx.arc(x, y + 1, 4, 0, 7); ctx.fill();
    ctx.restore();
  }

  // =================================================================================== ASSEMBLE
  // camera for the build: zooms out from the core to the whole blade
  const ASM_ROT = 0.87;      // the build lies on a diagonal (it is 700 mm long: this fills the frame)
  const asmTf = (t) => { const k = easeInOut((t - T.assemble[0] - 0.1) / 0.75); const s = lerp(2.15, 1.7, k); return { cx: 540, y0: 770, x0: lerp(300, 335, k), s, rot: ASM_ROT }; };
  const byId = Object.fromEntries(parts.map((p) => [p.id, p]));
  const coreOrder = ['coreA1', 'coreB1', 'coreA2', 'coreB2', 'coreA3', 'coreB3', 'coreB4'];
  function ledPath(tf, frac) {
    const pts = O.led, seg = []; let total = 0;
    for (let i = 1; i < pts.length; i++) { const l = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); seg.push(l); total += l; }
    let left = total * clamp(frac), head = P(tf, pts[0][0], pts[0][1]);
    ctx.beginPath(); ctx.moveTo(...head);
    for (let i = 1; i < pts.length && left > 0; i++) {
      const k = Math.min(1, left / seg[i - 1]); left -= seg[i - 1];
      head = P(tf, lerp(pts[i - 1][0], pts[i][0], k), lerp(pts[i - 1][1], pts[i][1], k)); ctx.lineTo(...head);
    }
    return head;
  }
  function assembled(t, tf, { alpha = 1, led = 1, ledGlow = 1, shells = [1, 1, 1], emitter = 1, plug = 1, cores = null } = {}) {
    ctx.save(); ctx.globalAlpha *= alpha;
    coreOrder.forEach((id, i) => { const k = cores ? cores[i] : 1; if (k > 0) { const p = byId[id], side = id[4] === 'A' ? -1 : 1; const o = side * 430 * (1 - k), r = tf.rot || 0; strokePart(p, { ...tf, cx: tf.cx + o * Math.cos(r), y0: tf.y0 + o * Math.sin(r) }, clamp(k * 3), 2.6, 'rgba(8,10,14,0.92)'); } });
    if (led > 0) { const head = ledPath(tf, led); glowStroke(3.4, ICE, 20 * ledGlow, 0.95); if (led < 1) { ctx.fillStyle = WHITE; ctx.shadowColor = WHITE; ctx.shadowBlur = 26; ctx.beginPath(); ctx.arc(head[0], head[1], 6, 0, 7); ctx.fill(); ctx.shadowBlur = 0; } }
    ['shell1', 'shell2', 'shell3'].forEach((id, i) => { if (shells[i] > 0) { const o = 760 * (1 - shells[i]), r = tf.rot || 0; strokePart(byId[id], { ...tf, cx: tf.cx + o * Math.sin(r), y0: tf.y0 - o * Math.cos(r) }, clamp(shells[i] * 3), 3.4, 'rgba(190,220,255,0.07)'); } });
    if (emitter > 0) { const o = 520 * (1 - emitter), r = tf.rot || 0; strokePart(byId.emitter, { ...tf, cx: tf.cx - o * Math.sin(r), y0: tf.y0 + o * Math.cos(r) }, clamp(emitter * 3), 3.2, 'rgba(8,10,14,0.85)'); }
    if (plug > 0) { const o = 300 * (1 - plug), r = tf.rot || 0; strokePart(byId.plug, { ...tf, cx: tf.cx + o * Math.cos(r), y0: tf.y0 + o * Math.sin(r) }, clamp(plug * 3), 2.4); }
    ctx.restore();
  }
  function callout(label, tf, x, y, tx, ty, a) {
    if (a <= 0) return; const [X, Y] = P(tf, x, y);
    ctx.save(); ctx.globalAlpha = a; ctx.strokeStyle = ICE; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(X, Y); ctx.lineTo(tx - 12, ty - 8); ctx.lineTo(tx - 12 + 30 * a, ty - 8); ctx.stroke();
    ctx.fillStyle = ICE; ctx.beginPath(); ctx.arc(X, Y, 5, 0, 7); ctx.fill(); ctx.restore();
    text(label, tx + 26, ty, mono(25), { alpha: a, spacing: 3 });
  }
  function assemble(t) {
    const [t0, t1] = T.assemble, s = t - t0, len = t1 - t0;
    background(t);
    tracker(t, 1); bigWord('ASSEMBLE', 'CORE · 1.2 M LED · SHELL', s, len);
    // the line-up drops away
    const gone = easeIn(s / 0.12);
    if (gone < 1) parts.forEach((p) => strokePart(p, { ...p.line, y0: p.line.y0 + 260 * gone }, 1 - gone, 3));
    const tf0 = asmTf(t);
    // punch in toward the emitter at the very end (hands over to the solder shot)
    const z = easeIn((s - (len - 0.14)) / 0.14), tf = { cx: 540, y0: lerp(tf0.y0, 770, z), x0: lerp(tf0.x0, 58, z), s: lerp(tf0.s, 3.4, z), rot: ASM_ROT * (1 - z) };
    const arrive = (at, d = 0.13) => back((t - at) / d, 1.5);
    const cores = T.coreIn.map((at) => (t < at ? 0 : arrive(at)));
    const led = t < T.led[0] ? 0 : easeInOut((t - T.led[0]) / (T.led[1] - T.led[0]));
    const shells = T.shellIn.map((at) => (t < at ? 0 : arrive(at)));
    const em = t < T.emitterIn ? 0 : arrive(T.emitterIn), pl = t < T.plugIn ? 0 : arrive(T.plugIn);
    assembled(t, tf, { cores, led, shells, emitter: em, plug: pl, alpha: 1 - 0.4 * z });
    // landing pings
    coreOrder.forEach((id, i) => { const p = byId[id], [X, Y] = P(tf, (p.x0 + p.x1) / 2, 0); ping(X, Y, t - T.coreIn[i] - 0.1, 34, ICE); });
    T.shellIn.forEach((at, i) => { const p = byId['shell' + (i + 1)], [X, Y] = P(tf, p.x0, 0); ping(X, Y, t - at - 0.1, 60); });
    { const [X, Y] = P(tf, 76, 0); ping(X, Y, t - T.emitterIn - 0.1, 90); }
    // callouts on the right
    const ca = (at) => clamp((t - at) / 0.1) * (1 - z);
    callout('BLACK CORE', tf, 250, -8, 660, 1100, ca(T.coreIn[3]));
    callout('COB LED STRIP', tf, 410, -8.5, 660, 1020, ca(T.led[0] + 0.1));
    callout('CLEAR SHELL', tf, 560, -15, 660, 940, ca(T.shellIn[1]));
  }

  // =================================================================================== SOLDER
  const SO = { cx: 300, y0: 790, x0: 58, s: 5.2 };           // the emitter cut-away, left
  const PANEL = { x: 560, y: 420, w: 440, h: 700 };         // the wiring, right
  const comp = [                                              // bottom to top: the real chain
    { id: 'LIPO 1S', y: 990, h: 110 }, { id: 'USB-C CHARGER', y: 820, h: 96 }, { id: 'SWITCH', y: 664, h: 82 }, { id: 'LED STRIP', y: 500, h: 76 },
  ];
  const jointY = [938, 780, 624];                             // wire gaps between them
  function solder(t) {
    const [t0, t1] = T.solder, s = t - t0, len = t1 - t0;
    background(t);
    tracker(t, 2); bigWord('SOLDER', 'LIPO · USB-C · SWITCH', s, len);
    const zin = easeOut(s / 0.2), fade = 1 - smooth((s - (len - 0.14)) / 0.14);
    const tf = { cx: lerp(540, SO.cx, zin), y0: lerp(770, SO.y0, zin), x0: 58, s: lerp(3.4, SO.s, zin) };
    ctx.save(); ctx.globalAlpha = fade;
    // emitter cut-away: wall section hatched, bay glowing
    trace(tf, O.emitterCut); ctx.fillStyle = 'rgba(150,175,215,0.13)'; ctx.fill('evenodd'); glowStroke(3, WHITE, 14);
    trace(tf, O.plugCut); ctx.fillStyle = 'rgba(190,230,255,0.20)'; ctx.fill(); glowStroke(2.4, ICE, 10);
    for (const id of ['shell1', 'coreA1']) { ctx.save(); ctx.beginPath(); ctx.rect(0, P(tf, 150, 0)[1], W, H); ctx.clip(); strokePart(byId[id], tf, 0.9, 2.6); ctx.restore(); }
    const bay = [P(tf, O.bay.x1 - 1, 13), P(tf, O.bay.x0 + 1, -17)];
    const pulse = 0.5 + 0.5 * Math.sin(t * 9);
    ctx.fillStyle = `rgba(191,230,255,${(0.10 + 0.10 * pulse) * clamp((s - 0.1) / 0.15)})`;
    ctx.fillRect(bay[0][0], bay[0][1], bay[1][0] - bay[0][0], bay[1][1] - bay[0][1]);
    text('ELECTRONICS BAY', tf.cx - 128, P(tf, 0, 0)[1] + 64, mono(22), { alpha: 0.75 * clamp((s - 0.15) / 0.1), spacing: 3, color: ICE });
    // zoom lines from the bay to the wiring panel
    const pa = clamp((s - 0.1) / 0.16);
    ctx.save(); ctx.globalAlpha = 0.5 * pa * fade; ctx.strokeStyle = ICE; ctx.lineWidth = 2; ctx.setLineDash([8, 8]);
    ctx.beginPath(); ctx.moveTo(bay[1][0], bay[0][1]); ctx.lineTo(PANEL.x, PANEL.y); ctx.moveTo(bay[1][0], bay[1][1]); ctx.lineTo(PANEL.x, PANEL.y + PANEL.h); ctx.stroke(); ctx.restore();
    ctx.save(); ctx.globalAlpha = pa * fade; ctx.beginPath(); ctx.roundRect(PANEL.x, PANEL.y, PANEL.w, PANEL.h * easeOut(pa), 26);
    ctx.fillStyle = 'rgba(6,10,18,0.88)'; ctx.fill(); glowStroke(2.5, ICE, 12, 0.9); ctx.restore();

    const cx = PANEL.x + PANEL.w / 2, joined = T.joints.map((j) => t >= j), on = t >= T.switchOn;
    // wires (two per hop), lit once their joint is made and the chain below is live
    for (let i = 0; i < 3; i++) {
      const a = comp[i], b = comp[i + 1], yA = a.y - a.h / 2, yB = b.y + b.h / 2, vis = clamp((s - 0.3 - i * 0.04) / 0.1);
      const live = joined[i] && (i < 2 || on) && joined.slice(0, i).every(Boolean);
      for (const dx of [-36, 36]) {
        ctx.save(); ctx.globalAlpha = vis * fade;
        ctx.beginPath(); ctx.moveTo(cx + dx, yA); ctx.lineTo(cx + dx, jointY[i] + 9); if (joined[i]) ctx.lineTo(cx + dx, yB); else { ctx.moveTo(cx + dx, jointY[i] - 9); ctx.lineTo(cx + dx, yB); }
        glowStroke(live ? 5 : 3.5, live ? WHITE : '#8ea2bd', live ? 20 : 4); ctx.restore();
      }
    }
    // components
    comp.forEach((c, i) => {
      const k = back((s - 0.2 - i * 0.05) / 0.16, 1.8); if (s < 0.2 + i * 0.05) return;
      ctx.save(); ctx.globalAlpha = clamp(k * 2) * fade; ctx.translate(cx, c.y); ctx.scale(k, k);
      const w = i === 0 ? 250 : i === 3 ? 120 : 210;
      ctx.beginPath(); ctx.roundRect(-w / 2, -c.h / 2, w, c.h, i === 0 ? 20 : 10); ctx.fillStyle = 'rgba(10,16,28,0.95)'; ctx.fill();
      const lit = i === 3 && on;
      glowStroke(3, lit ? WHITE : '#e6eefb', lit ? 26 : 8);
      if (i === 1) { ctx.beginPath(); ctx.roundRect(-34, c.h / 2 - 12, 68, 22, 9); ctx.fillStyle = BG; ctx.fill(); glowStroke(2.5, WHITE, 6); }       // USB-C port
      if (i === 2) { const kx = lerp(-22, 22, easeOut((t - T.switchOn) / 0.08)); ctx.beginPath(); ctx.roundRect(-52, -14, 104, 28, 6); glowStroke(2.5, WHITE, 6); ctx.fillStyle = on ? WHITE : '#9db0cc'; ctx.beginPath(); ctx.roundRect(kx - 22, -11, 44, 22, 5); ctx.fill(); }
      if (i === 3 && lit) { ctx.fillStyle = `rgba(235,246,255,${0.85})`; ctx.shadowColor = WHITE; ctx.shadowBlur = 40; ctx.beginPath(); ctx.roundRect(-w / 2 + 8, -c.h / 2 + 8, w - 16, c.h - 16, 6); ctx.fill(); }
      ctx.restore();
      text(c.id, cx + w / 2 + 16 > PANEL.x + PANEL.w - 10 ? cx : cx, c.y + (i === 2 ? 44 : 9), mono(i === 2 ? 19 : 21), { alpha: clamp(k * 2) * fade * (i === 3 && lit ? 0 : 0.92), align: 'center', spacing: 2, color: i === 2 ? ICE : WHITE });
    });
    // the iron: travels joint to joint, sparks on contact
    const jt = [T.solder[0] + 0.3, ...T.joints, T.switchOn + 0.1];
    let ix = cx + 190, iy = jointY[0] - 160, away = 1;
    for (let i = 0; i < 3; i++) if (t >= jt[i] && t < jt[i + 1] + (i === 2 ? 0 : 0)) {
      const k = easeInOut((t - jt[i]) / Math.max(0.12, (jt[i + 1] - jt[i]) * 0.7)); const py = i ? jointY[i - 1] : jointY[0] + 200;
      iy = lerp(py, jointY[i], k); ix = cx + (i % 2 ? -36 : 36); away = i === 0 ? 1 - k : 0;
    }
    if (t >= T.joints[2]) { const k = easeIn((t - T.joints[2] - 0.08) / 0.14); iy = jointY[2] - 500 * k; ix = cx - 36 + 300 * k; away = 0; }
    if (s > 0.3) iron(ix + away * 160, iy - away * 30, fade);
    T.joints.forEach((j, i) => {
      const d = t - j, x0 = cx + (i % 2 ? -36 : 36);
      if (d >= 0) for (const dx of [-36, 36]) { ctx.fillStyle = WHITE; ctx.shadowColor = d < 0.25 ? HOT : WHITE; ctx.shadowBlur = 18; ctx.globalAlpha = fade; ctx.beginPath(); ctx.arc(cx + dx, jointY[i], 9, 0, 7); ctx.fill(); ctx.shadowBlur = 0; ctx.globalAlpha = 1; }
      if (d >= 0 && d < 0.26) {
        const k = d / 0.26;
        ctx.save(); ctx.globalAlpha = fade * (1 - k); ctx.lineCap = 'round';
        for (let n = 0; n < 14; n++) { const a = hash(n * 3.1 + i * 17) * Math.PI * 2, r0 = 12 + 30 * k, r1 = r0 + (26 + 60 * hash(n + i * 5)) * (1 - k * 0.5);
          ctx.strokeStyle = n % 3 ? HOT : WHITE; ctx.shadowColor = HOT; ctx.shadowBlur = 14; ctx.lineWidth = 4 * (1 - k) + 1;
          ctx.beginPath(); ctx.moveTo(x0 + Math.cos(a) * r0, jointY[i] + Math.sin(a) * r0); ctx.lineTo(x0 + Math.cos(a) * r1, jointY[i] + Math.sin(a) * r1 + 40 * k * k); ctx.stroke(); }
        ctx.fillStyle = `rgba(255,220,170,${0.9 * (1 - k)})`; ctx.beginPath(); ctx.arc(x0, jointY[i], 26 * (1 - k) + 6, 0, 7); ctx.fill(); ctx.restore();
      }
      if (d >= 0.02 && d < 0.6) {                                   // smoke
        const k = d / 0.6; ctx.save(); ctx.globalAlpha = 0.5 * (1 - k) * fade; ctx.strokeStyle = '#c8d6ea'; ctx.lineWidth = 2.5; ctx.beginPath();
        for (let q = 0; q <= 16; q++) { const u = q / 16, yy = jointY[i] - 14 - u * 150 * k, xx = x0 + Math.sin(u * 7 + d * 9 + i) * 12 * u; q ? ctx.lineTo(xx, yy) : ctx.moveTo(xx, yy); }
        ctx.stroke(); ctx.restore();
      }
    });
    // power runs up the chain once the switch is thrown, and out of the top toward the blade
    if (on) {
      const k = (t - T.switchOn) / 0.16, y = lerp(comp[0].y, PANEL.y - 400, easeIn(k));
      ctx.save(); ctx.globalAlpha = fade; ctx.fillStyle = WHITE; ctx.shadowColor = WHITE; ctx.shadowBlur = 50; ctx.beginPath(); ctx.ellipse(cx, y, 10, 44, 0, 0, 7); ctx.fill(); ctx.restore();
      text('ON', cx + 78, comp[2].y + 8, mono(24), { alpha: fade, color: WHITE, glow: 14 });
    }
    ctx.restore();
  }
  function iron(x, y, alpha) {
    ctx.save(); ctx.globalAlpha *= alpha; ctx.translate(x, y); ctx.rotate(-0.62);
    ctx.fillStyle = BG; ctx.strokeStyle = WHITE; ctx.lineWidth = 3; ctx.lineJoin = 'round';
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(60, -9); ctx.lineTo(60, 9); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.roundRect(60, -13, 70, 26, 4); ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.roundRect(130, -22, 190, 44, 14); ctx.fill(); ctx.stroke();
    ctx.fillStyle = HOT; ctx.shadowColor = HOT; ctx.shadowBlur = 20; ctx.beginPath(); ctx.arc(3, 0, 5, 0, 7); ctx.fill();
    ctx.restore();
  }

  // =================================================================================== DARK
  // proj(x, y): saber mm -> stage px through the 3D camera, so the outline sits exactly where
  // the rendered saber is about to appear
  function dark(t, proj) {
    const [t0, t1] = T.dark, s = t - t0, len = t1 - t0;
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
    tracker(t, 3, (0.55 + 0.45 * Math.sin(t * 40)) * (1 - smooth((s - 0.3) / 0.15)));
    const a = smooth(s / 0.18) * (1 - smooth((s - (len - 0.12)) / 0.12));
    const p0 = proj(0, 0), p1 = proj(100, 0), sc = Math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 100;
    const tf = { cx: p0[0], y0: p0[1], x0: 0, s: sc };
    ctx.save(); ctx.globalAlpha = 0.34 * a;
    assembled(t, tf, { led: 0 });
    ctx.restore();
    // the charge climbing into the emitter
    const k = easeIn(s / len), e = proj(60, 0);
    ctx.save(); ctx.globalAlpha = clamp(s / 0.1); ctx.fillStyle = WHITE; ctx.shadowColor = ICE; ctx.shadowBlur = 30 + 60 * k;
    ctx.beginPath(); ctx.arc(e[0], lerp(e[1] + 420, e[1], easeOut(s / 0.3)), 4 + 9 * k, 0, 7); ctx.fill(); ctx.restore();
  }

  // =================================================================================== TITLE (over the 3D)
  function title(t, flick) {
    const s = t - T.title; if (s < 0) return;
    const k = back(s / 0.26, 1.3), a = clamp(s / 0.06);
    const g = ctx.createLinearGradient(0, 960, 0, 1920); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(0.25, 'rgba(0,0,0,0.5)'); g.addColorStop(0.6, 'rgba(0,0,0,0.72)'); g.addColorStop(1, 'rgba(0,0,0,0.8)');
    ctx.save(); ctx.globalAlpha = clamp(s / 0.2); ctx.fillStyle = g; ctx.fillRect(0, 960, W, 960); ctx.restore();
    ctx.save(); ctx.translate(540, 1235); const sc = lerp(1.32, 1, k); ctx.scale(sc, sc); ctx.translate(-540, -1235);
    const sp = lerp(44, 5, easeOut(s / 0.3));
    ctx.font = anton(238); ctx.letterSpacing = '5px'; const FS = Math.floor(238 * 950 / ctx.measureText('DARK SABER').width); ctx.letterSpacing = '0px';
    if (s < 0.1) for (const [dx, col] of [[-10, 'rgba(120,200,255,0.8)'], [10, 'rgba(255,255,255,0.6)']]) text('DARK SABER', 540 + dx * (1 - s / 0.1) + sp / 2, 1235, anton(FS), { align: 'center', spacing: sp, color: col, alpha: a });
    ctx.shadowColor = 'rgba(190,225,255,0.55)'; ctx.shadowBlur = 34 + 16 * flick;
    text('DARK SABER', 540 + sp / 2, 1235, anton(FS), { align: 'center', spacing: sp, alpha: a, color: '#ffffff' });
    ctx.restore();
    const s2 = t - T.sub;
    if (s2 > 0) {
      const a2 = smooth(s2 / 0.3), w = 250 * easeOut(s2 / 0.4);
      ctx.save(); ctx.globalAlpha = a2 * 0.8; ctx.fillStyle = ICE; ctx.fillRect(540 - w, 1283, w * 2, 2); ctx.restore();
      text('UPCOMING PROJECT', 540 + 8, 1347 + (1 - a2) * 16, inter(40, 700), { align: 'center', spacing: 16, alpha: a2, color: '#e8f2ff' });
    }
  }

  function draw(t, { proj, flick = 0, emitPx = null } = {}) {
    ctx.setTransform(scale, 0, 0, scale, 0, 0); ctx.clearRect(0, 0, W, H);
    if (t < T.hook[1]) hook(t);
    else if (t < T.print[1]) print(t);
    else if (t < T.assemble[1]) assemble(t);
    else if (t < T.solder[1]) solder(t);
    else if (t < T.dark[1]) dark(t, proj);
    else {
      const si = t - T.ignite;                       // ignition flash, blooming out of the emitter
      if (si < 0.3 && emitPx) {
        const g = ctx.createRadialGradient(emitPx[0], emitPx[1], 0, emitPx[0], emitPx[1], 500 + 2600 * si);
        const a = 0.7 * Math.exp(-si * 13);
        g.addColorStop(0, `rgba(235,246,255,${a})`); g.addColorStop(0.4, `rgba(170,215,255,${a * 0.35})`); g.addColorStop(1, 'rgba(170,215,255,0)');
        ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
      }
      title(t, flick);
    }
  }
  return { draw };
}
