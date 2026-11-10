// Render stills of the assembled Ghost with headless Chromium.
//   node tools/render_still.mjs closed out/still_closed.png ["extra=query&params"]
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('playwright');
import { serve } from './server.mjs';

const [state = 'closed', out = `out/still_${state}.png`, extra = ''] = process.argv.slice(2);
const W = +(new URLSearchParams(extra).get('w') || 1080), H = +(new URLSearchParams(extra).get('h') || 1920);
const { srv, url } = await serve();
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-gpu-vsync'] });
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log('[page]', m.text()); });
page.on('pageerror', (e) => console.log('[pageerror]', e.message));
const t0 = Date.now();
await page.goto(`${url}/still.html?state=${state}&${extra}`);
await page.waitForFunction('window.__ready === true', null, { timeout: 600000 });
const ms = await page.evaluate('window.__ms');
await page.screenshot({ path: out });
console.log(`${out}  (${ms.toFixed(0)} ms/frame, ${((Date.now() - t0) / 1000).toFixed(1)} s total)`);
await browser.close(); srv.close();
