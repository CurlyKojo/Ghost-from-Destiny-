// On-screen text, drawn in the DOM over the canvas.  Everything is laid out on a 1080x1920
// stage and kept inside Instagram's safe area (clear of the top bar, the caption block at
// the bottom and the button column on the right).
import { BEAT, BAR, BARS, DROP_BEAT, DURATION } from './timeline.js';

const CSS = `
#stage{position:absolute;left:0;top:0;width:1080px;height:1920px;transform-origin:0 0;pointer-events:none;overflow:hidden;font-family:'Inter Tight',Inter,system-ui,sans-serif;color:#fff}
#stage *{box-sizing:border-box}
.scrim{position:absolute;left:0;width:1080px;pointer-events:none}
#scrimTop{top:0;height:1250px;background:linear-gradient(180deg,rgba(2,4,8,.80) 0%,rgba(2,4,8,.66) 55%,rgba(2,4,8,0) 100%)}
#scrimBottom{bottom:0;height:1000px;background:linear-gradient(0deg,rgba(2,4,8,.86) 0%,rgba(2,4,8,.62) 55%,rgba(2,4,8,0) 100%)}
#hook{position:absolute;left:70px;top:330px;width:980px;white-space:nowrap;font-weight:900;font-size:122px;line-height:1.0;letter-spacing:-3px;text-shadow:0 4px 40px rgba(0,0,0,.6)}
#hook em{font-style:normal;color:#8fdcff;text-shadow:0 0 34px rgba(110,200,255,.55),0 4px 40px rgba(0,0,0,.6)}
#label{position:absolute;left:70px;top:1215px;transform-origin:0 100%}
#label .rule{display:block;width:110px;height:10px;background:#8fdcff;margin-bottom:22px;box-shadow:0 0 24px rgba(110,200,255,.6)}
#label .word{display:block;font-weight:900;font-size:150px;line-height:.95;letter-spacing:-4px;text-shadow:0 6px 44px rgba(0,0,0,.85),0 0 3px rgba(0,0,0,.9)}
.bubble{position:absolute;max-width:800px;padding:26px 38px 30px;border-radius:44px;font-size:52px;line-height:1.12;transform-origin:50% 100%}
.bubble .who{display:block;font:700 22px/1 'JetBrains Mono',monospace;letter-spacing:5px;margin-bottom:12px;opacity:.6}
.bubble.user{right:110px;background:#f4f6fa;color:#0a0d14;font-weight:800;border-bottom-right-radius:10px;box-shadow:0 14px 60px rgba(0,0,0,.55)}
.bubble.ghost{left:70px;max-width:900px;white-space:nowrap;background:rgba(6,14,26,.86);color:#e4f7ff;border:3px solid #86d9ff;font:700 44px/1.15 'JetBrains Mono',monospace;letter-spacing:-1px;border-bottom-left-radius:10px;box-shadow:0 0 46px rgba(90,190,255,.38),inset 0 0 30px rgba(90,190,255,.12)}
.bubble.ghost .who{color:#86d9ff;opacity:.95}
.bubble.ghost .hex{display:inline-block;width:20px;height:22px;margin-right:12px;vertical-align:-3px;background:#86d9ff;clip-path:polygon(50% 0,100% 25%,100% 75%,50% 100%,0 75%,0 25%)}
#hey{position:absolute;right:140px;top:1180px;font-size:84px;font-weight:900;padding:30px 50px 34px}
#end{position:absolute;left:70px;top:1090px;width:900px}
#end .big{font-weight:900;font-size:112px;line-height:.98;letter-spacing:-3px;text-shadow:0 6px 44px rgba(0,0,0,.8)}
#end .big em{font-style:normal;color:#8fdcff}
#end .handle{margin-top:34px;font-weight:800;font-size:60px;color:#8fdcff;letter-spacing:-1px;text-shadow:0 0 30px rgba(110,200,255,.45)}
#end .fine{margin-top:26px;font-weight:600;font-size:31px;color:#aeb9c8}
#beats{position:absolute;left:0;top:1484px;width:1080px;height:150px;font-family:'JetBrains Mono',monospace;display:none}
#beats .bg{position:absolute;inset:0;background:rgba(0,0,0,.72)}
#beats .flash{position:absolute;left:0;top:0;width:1080px;height:12px;background:#fff}
#beats .txt{position:absolute;left:40px;top:30px;font-weight:700;font-size:40px;letter-spacing:1px}
#beats .time{position:absolute;right:40px;top:30px;font-weight:500;font-size:40px;color:#b8c4d4}
#beats .dots{position:absolute;left:430px;top:34px;display:flex;gap:16px}
#beats .dots i{width:40px;height:40px;border-radius:8px;background:#2a3038}
#beats .dots i.on{background:#fff}
#beats .bars{position:absolute;left:40px;top:100px;width:1000px;height:28px}
#beats .bars i{position:absolute;top:0;height:28px;width:2px;background:#5b6675}
#beats .bars i.drop{background:#ff4d5e;width:4px}
#beats .bars b{position:absolute;top:8px;height:12px;left:0;background:#8fdcff}
#beats .bars span{position:absolute;top:-2px;font-size:20px;font-weight:700;color:#ff4d5e;transform:translateX(8px)}
`;

const pop = (s, d = 0.12) => { const x = Math.min(1, Math.max(0, s / d)); const c = 1.9; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); };

export function createOverlay(scale = 1) {
  const style = document.createElement('style'); style.textContent = CSS; document.head.appendChild(style);
  const stage = document.createElement('div'); stage.id = 'stage'; stage.style.transform = `scale(${scale})`;
  stage.innerHTML = `
    <div class="scrim" id="scrimTop"></div><div class="scrim" id="scrimBottom"></div>
    <div id="hook">I\u2019m building<br>an AI companion<br>that <em>talks back.</em></div>
    <div id="label"><span class="rule"></span><span class="word"></span></div>
    <div class="bubble user" id="hey"><span class="who">YOU</span>Hey Ghost</div>
    <div class="bubble user" id="bu"><span class="who">YOU</span><span class="t"></span></div>
    <div class="bubble ghost" id="bg"><span class="who"><span class="hex"></span>GHOST</span><span class="t"></span></div>
    <div id="end"><div class="big">Concept.<br><em>Build to follow.</em></div><div class="handle">@kobethompson23</div><div class="fine">Fan project, not affiliated with Bungie.</div></div>
    <div id="beats"><div class="bg"></div><div class="flash"></div><div class="txt"></div><div class="dots"><i></i><i></i><i></i><i></i></div><div class="time"></div><div class="bars"></div></div>`;
  document.body.appendChild(stage);
  const $ = (id) => stage.querySelector(id);
  const el = { top: $('#scrimTop'), bottom: $('#scrimBottom'), hook: $('#hook'), label: $('#label'), word: $('#label .word'), hey: $('#hey'),
    bu: $('#bu'), but: $('#bu .t'), bg: $('#bg'), bgt: $('#bg .t'), end: $('#end'), beats: $('#beats'), flash: $('#beats .flash'), txt: $('#beats .txt'),
    time: $('#beats .time'), dots: [...stage.querySelectorAll('#beats .dots i')], bars: $('#beats .bars') };
  let barsHtml = '';
  for (let i = 0; i <= BARS; i++) barsHtml += `<i class="${i * 4 === DROP_BEAT ? 'drop' : ''}" style="left:${(i / BARS) * 1000}px"></i>`;
  barsHtml += `<span style="left:${(DROP_BEAT / 4 / BARS) * 1000}px">DROP</span><b></b>`;
  el.bars.innerHTML = barsHtml; el.prog = el.bars.querySelector('b');
  let beatsOn = false, uiOn = true;

  function draw({ t, beat, ov }) {
    el.top.style.opacity = uiOn ? ov.scrimTop : 0; el.bottom.style.opacity = uiOn ? ov.scrimBottom : 0;
    el.hook.style.opacity = uiOn ? ov.hook : 0;
    // part labels: pop in on the cut
    if (ov.label && uiOn) {
      el.label.style.display = 'block'; el.word.textContent = ov.label.text;
      const k = pop(ov.label.s, 0.1); el.label.style.transform = `translateY(${(1 - k) * 40}px) scale(${0.9 + 0.1 * k})`; el.label.style.opacity = Math.min(1, ov.label.s / 0.05);
    } else el.label.style.display = 'none';
    el.hey.style.display = ov.heyGhost > 0 && uiOn ? 'block' : 'none';
    if (ov.heyGhost > 0) { el.hey.style.transform = `scale(${0.6 + 0.4 * ov.heyGhost})`; el.hey.style.opacity = Math.min(1, ov.heyS / 0.05); }
    const user = ov.bubbles.find((b) => b.who === 'user'), ghost = ov.bubbles.find((b) => b.who === 'ghost');
    const place = (node, textNode, b, top) => {
      if (!b || !uiOn) { node.style.display = 'none'; return; }
      node.style.display = 'block'; textNode.textContent = b.text; node.style.top = top + 'px';
      const k = pop(b.s, 0.12); node.style.transform = `translateY(${(1 - k) * 46}px) scale(${0.82 + 0.18 * k})`; node.style.opacity = Math.min(1, b.s / 0.05);
      node.style.fontSize = b.big ? '72px' : '';
    };
    place(el.bu, el.but, user, 1085);
    place(el.bg, el.bgt, ghost, user ? 1320 : 1230);
    el.end.style.opacity = uiOn ? ov.end : 0; el.end.style.transform = `translateY(${(1 - ov.end) * 30}px)`;

    // beat markers (the toggle): bar, beat, time, a flash on every beat, the drop in red
    el.beats.style.display = beatsOn ? 'block' : 'none';
    if (beatsOn) {
      const bi = Math.floor(beat + 1e-6), bar = Math.floor(bi / 4) + 1, inBar = bi % 4, sb = (beat - bi) * BEAT;
      el.txt.textContent = `BAR ${String(bar).padStart(2, '0')} · BEAT ${inBar + 1}`;
      el.txt.style.color = bi >= DROP_BEAT && bi < DROP_BEAT + 4 ? '#ff4d5e' : '#fff';
      el.time.textContent = t.toFixed(2).padStart(5, '0') + 's';
      el.dots.forEach((d, i) => d.classList.toggle('on', i === inBar));
      el.flash.style.opacity = Math.exp(-sb * 14); el.flash.style.background = inBar === 0 ? (bi === DROP_BEAT ? '#ff4d5e' : '#8fdcff') : '#fff';
      el.flash.style.height = inBar === 0 ? '18px' : '10px';
      el.prog.style.width = (t / DURATION) * 1000 + 'px';
    }
  }
  return { draw, stage, setBeats: (v) => { beatsOn = v; }, setUI: (v) => { uiOn = v; }, get beats() { return beatsOn; } };
}
