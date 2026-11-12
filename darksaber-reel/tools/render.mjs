// Render the Darksaber reel to MP4 (1080x1920, 30 fps) with the synthesised sound.
//   node tools/render.mjs [--scale 0.5] [--workers 3]
import { createRequire } from 'node:module';
import { spawn, execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const { chromium } = createRequire(import.meta.url)('playwright');
import { serve } from './server.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const T = JSON.parse(fs.readFileSync(path.join(ROOT, 'timing.json'), 'utf8'));
const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i < 0 ? d : process.argv[i + 1]; };
const scale = +arg('scale', 1), workers = +arg('workers', 3), FPS = T.fps, FRAMES = Math.round(T.duration * FPS);
const W = Math.round(1080 * scale / 2) * 2, H = Math.round(1920 * scale / 2) * 2;
const X264 = ['-c:v', 'libx264', '-preset', 'slow', '-crf', '15', '-pix_fmt', 'yuv420p', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709'];
const done = (p) => new Promise((res, rej) => p.on('close', (c) => (c === 0 ? res() : rej(new Error('exit ' + c)))));
const write = (stream, buf) => new Promise((res) => (stream.write(buf) ? res() : stream.once('drain', res)));

if (process.argv.includes('--segment')) {
  const i0 = process.argv.indexOf('--segment'), a = +process.argv[i0 + 1], b = +process.argv[i0 + 2], file = process.argv[i0 + 3];
  const { srv, url } = await serve();
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-gpu-vsync'] });
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  page.on('pageerror', (e) => console.log('[pageerror]', e.message));
  await page.goto(`${url}/index.html?capture=1&scale=${scale}`);
  await page.waitForFunction('window.__ready === true', null, { timeout: 600000 });
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'png', '-i', '-', ...X264, file], { stdio: ['pipe', 'inherit', 'inherit'] });
  const t0 = Date.now();
  for (let i = a; i < b; i++) {
    await page.evaluate((n) => window.renderFrame(n), i);
    await write(ff.stdin, await page.screenshot({ type: 'png' }));
    if ((i - a) % 20 === 19 || i === b - 1) console.log(`[${a}-${b}] ${i - a + 1}/${b - a}  ${((Date.now() - t0) / (i - a + 1) / 1000).toFixed(2)} s/frame`);
  }
  ff.stdin.end(); await done(ff); await browser.close(); srv.close();
  process.exit(0);
}

const out = path.join(ROOT, 'out'); fs.mkdirSync(out, { recursive: true });
const tag = scale === 1 ? '' : `_${H}p`, t0 = Date.now(), segs = [], jobs = [];
// the 2D half renders fast and the 3D half slowly, so give the 3D frames to more workers
const cut = Math.round(T.dark[0] * FPS), bounds = [0, cut];
for (let w = 1; w < workers; w++) bounds.push(cut + Math.round(((FRAMES - cut) * w) / (workers - 1)));
for (let w = 0; w < bounds.length - 1; w++) {
  const file = path.join(out, `seg${w}${tag}.mp4`); segs.push(file);
  jobs.push(done(spawn(process.execPath, [fileURLToPath(import.meta.url), '--segment', bounds[w], bounds[w + 1], file, '--scale', scale], { stdio: 'inherit', env: process.env })));
}
await Promise.all(jobs);
const list = path.join(out, `segs${tag}.txt`); fs.writeFileSync(list, segs.map((s) => `file '${s}'`).join('\n'));
const final = path.join(out, `darksaber_reel${tag}.mp4`);
execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', list, '-i', path.join(ROOT, 'assets', 'sfx.wav'), '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-shortest', '-movflags', '+faststart', final], { stdio: 'inherit' });
for (const s of segs) fs.rmSync(s, { force: true }); fs.rmSync(list, { force: true });
console.log(`done in ${((Date.now() - t0) / 60000).toFixed(1)} min -> ${final}`);
