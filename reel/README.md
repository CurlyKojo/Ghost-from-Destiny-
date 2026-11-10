# Ghost teaser reel

A 30-second concept reel for Instagram: 1080x1920, 30 fps, 14 bars at 110 BPM, the drop on
bar 9 (17.45 s).

- `video/ghost_reel.mp4` is the clean cut. `video/ghost_reel_beats.mp4` is the same cut with
  a beat-marker strip (bar, beat, time, a flash on every beat, the drop in red) for lining up
  the song. The audio track holds only the Ghost's four lines; add the music in Instagram and
  keep the original audio on.
- `stills/` holds the approved look frames.

## How it is made

- `prep/build_assets.py` reads the 12 STLs in `hardware/stl/`, places each one with the
  transforms from `hardware/generate_stl.py` (and checks the result against the generator),
  smooths the normals and writes `assets/ghost.bin` + `assets/ghost.json`.
- `prep/make_voice.py` speaks the lines with the project's own voice: Piper
  `en_US-ryan-medium` through `ghost_fx()` from `software/ghost/tts.py`.
- `src/ghost.js` is the rig: shell on its slider pins and springs, core, bezel, screen, LED
  ring, stand. `src/eye.js` is `software/ghost/eye.py` ported to a shader, with the mood
  colours from `eye.py` and the LED colours from `lights.py`.
- `src/props.js` holds everything that is not an STL: the bought-in electronics for the build
  shots, the tendons, the Bowden cable and the printer.
- `src/studio.js` is the lighting, floor, haze and post chain.
- `src/timeline.js` is the edit: the shot list, every move, every cut on a beat.
- `src/overlay.js` is the on-screen text and the beat markers.

```bash
pip install trimesh manifold3d numpy scipy rtree piper-tts
npm install
python3 prep/build_assets.py
python3 prep/make_voice.py
export NODE_PATH=$(npm root -g)                 # for the pre-installed Playwright
node tools/render_reel.mjs                      # about 40 min on 4 CPU cores -> out/
node tools/render_reel.mjs --scale 0.5          # quick half-size preview
node tools/sheet.mjs out/sheet.png 0.33 b8.5 b32.2 b45    # contact sheet at given beats
```

Live preview: `node tools/server.mjs` and open `http://127.0.0.1:8123/reel.html`.
Space plays, **B** toggles the beat markers, T the text, the arrow keys step one beat.

## Things that differ from the printed parts

- The shell pieces get a 0.9 mm rounded edge and painted orange tips. Render only.
- The lid sits flush under the arm's pan disc (the generator's preview sinks it 3 mm).
- The eye bezel goes on last in the build shots, as a cap over the LED ring and the screen.
