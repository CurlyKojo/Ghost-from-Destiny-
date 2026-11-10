// Contact sheet of frames at given times, for checking shots quickly.
//   node tools/sheet.mjs out/sheet.png 0.5 [beats] t1 t2 t3 ...      (times in seconds, or "b12.5" for a beat)
import { createRequire } from 'node:module';
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
const { chromium } = createRequire(import.meta.url)('playwright');
import { serve } from './server.mjs';

let [out, scaleArg, ...rest] = process.argv.slice(2);
const scale = +scaleArg;
const beats = rest[0] === 'beats'; if (beats) rest.shift();
const BEAT = 60 / 110;
const times = rest.map((x) => (x.startsWith('b') ? +x.slice(1) * BEAT : +x));
const W = Math.round(1080 * scale), H = Math.round(1920 * scale);
const { srv, url } = await serve();
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log('[page]', m.text().slice(0, 400)); });
page.on('pageerror', (e) => console.log('[pageerror]', e.message));
await page.goto(`${url}/reel.html?capture=1&scale=${scale}${beats ? '&beats=1' : ''}`);
await page.waitForFunction('window.__ready === true', null, { timeout: 600000 });
const dir = out.replace(/\.png$/, '_frames'); fs.mkdirSync(dir, { recursive: true });
const files = [];
for (const [i, t] of times.entries()) {
  const t0 = Date.now();
  const shot = await page.evaluate((tt) => window.renderTime(tt), t);
  const f = `${dir}/${String(i).padStart(3, '0')}.png`;
  await page.screenshot({ path: f }); files.push(f);
  console.log(`${t.toFixed(2)}s  beat ${(t / BEAT).toFixed(2)}  ${shot}  ${Date.now() - t0} ms`);
}
await browser.close(); srv.close();
const cols = Math.min(files.length, +(process.env.COLS || 6));
execFileSync('python3', ['-c', `
import sys
from PIL import Image
fs=sys.argv[2:]; cols=int(sys.argv[1]); ims=[Image.open(f).convert('RGB') for f in fs]
w,h=ims[0].size; rows=(len(ims)+cols-1)//cols
s=Image.new('RGB',(w*cols,h*rows))
for i,im in enumerate(ims): s.paste(im,((i%cols)*w,(i//cols)*h))
s.save('${out}')`, String(cols), ...files]);
console.log('wrote', out);
