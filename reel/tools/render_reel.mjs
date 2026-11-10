// Render the reel to MP4.
//   node tools/render_reel.mjs                  full 1080x1920 render: out/ghost_reel.mp4 + out/ghost_reel_beats.mp4
//   node tools/render_reel.mjs --scale 0.5      quick half-size preview
//   node tools/render_reel.mjs --workers 3      parallel browser instances (default 3)
// Internal: --segment a b file   renders frames [a, b) to one video-only segment.
import { createRequire } from 'node:module';
import { spawn, execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const { chromium } = createRequire(import.meta.url)('playwright');
import { serve } from './server.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i < 0 ? d : process.argv[i + 1]; };
const scale = +arg('scale', 1), workers = +arg('workers', 3), FPS = 30, FRAMES = Math.round(14 * 4 * (60 / 110) * FPS);
const W = Math.round(1080 * scale / 2) * 2, H = Math.round(1920 * scale / 2) * 2;
const GL = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-gpu-vsync'];
const X264 = ['-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-pix_fmt', 'yuv420p', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-movflags', '+faststart'];

async function open(query) {
  const { srv, url } = await serve();
  const browser = await chromium.launch({ args: GL });
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  page.on('pageerror', (e) => console.log('[pageerror]', e.message));
  await page.goto(`${url}/reel.html?scale=${scale}&${query}`);
  await page.waitForFunction('window.__ready === true', null, { timeout: 600000 });
  return { page, close: async () => { await browser.close(); srv.close(); } };
}
const done = (p) => new Promise((res, rej) => p.on('close', (c) => (c === 0 ? res() : rej(new Error('exit ' + c)))));
const write = (stream, buf) => new Promise((res) => (stream.write(buf) ? res() : stream.once('drain', res)));

if (process.argv.includes('--segment')) {
  const i0 = process.argv.indexOf('--segment'), a = +process.argv[i0 + 1], b = +process.argv[i0 + 2], file = process.argv[i0 + 3];
  const { page, close } = await open('capture=1');
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-', ...X264, file], { stdio: ['pipe', 'inherit', 'inherit'] });
  const t0 = Date.now();
  for (let i = a; i < b; i++) {
    await page.evaluate((n) => window.renderFrame(n), i);
    await write(ff.stdin, await page.screenshot({ type: 'jpeg', quality: 98 }));
    if ((i - a) % 20 === 19 || i === b - 1) console.log(`[${a}-${b}] ${i - a + 1}/${b - a}  ${((Date.now() - t0) / (i - a + 1) / 1000).toFixed(2)} s/frame`);
  }
  ff.stdin.end(); await done(ff); await close();
  process.exit(0);
}

const out = path.join(ROOT, 'out'); fs.mkdirSync(out, { recursive: true });
const tag = scale === 1 ? '' : `_${H}p`;
const t0 = Date.now();
// 1. picture, in parallel segments (every frame is a pure function of its time)
const segs = [], jobs = [];
for (let w = 0; w < workers; w++) {
  const a = Math.round((FRAMES * w) / workers), b = Math.round((FRAMES * (w + 1)) / workers), file = path.join(out, `seg${w}${tag}.mp4`);
  segs.push(file);
  jobs.push(done(spawn(process.execPath, [fileURLToPath(import.meta.url), '--segment', a, b, file, '--scale', scale], { stdio: 'inherit', env: process.env })));
}
await Promise.all(jobs);
const list = path.join(out, `segs${tag}.txt`); fs.writeFileSync(list, segs.map((s) => `file '${s}'`).join('\n'));
const clean = path.join(out, `ghost_reel${tag}.mp4`), beats = path.join(out, `ghost_reel_beats${tag}.mp4`), voice = path.join(ROOT, 'assets', 'voice.wav');
// 2. join, add the Ghost's voice
execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', list, '-i', voice, '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', clean], { stdio: 'inherit' });
console.log(`clean render done in ${((Date.now() - t0) / 60000).toFixed(1)} min -> ${clean}`);
// 3. same picture with the beat-marker strip composited on top
const y = Math.round(1484 * scale), h = Math.round(150 * scale);
const { page, close } = await open('beatsonly=1');
const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-i', clean, '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'png', '-i', '-',
  '-filter_complex', `[0:v][1:v]overlay=0:${y}:shortest=1[v]`, '-map', '[v]', '-map', '0:a', ...X264, '-c:a', 'copy', beats], { stdio: ['pipe', 'inherit', 'inherit'] });
for (let i = 0; i < FRAMES; i++) {
  await page.evaluate((n) => window.renderFrame(n), i);
  await write(ff.stdin, await page.screenshot({ type: 'png', omitBackground: true, clip: { x: 0, y, width: W, height: h } }));
}
ff.stdin.end(); await done(ff); await close();
for (const s of segs) fs.rmSync(s, { force: true }); fs.rmSync(list, { force: true });
console.log(`all done in ${((Date.now() - t0) / 60000).toFixed(1)} min\n  ${clean}\n  ${beats}`);
