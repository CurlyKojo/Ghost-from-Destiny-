# Ghost teaser reel

Render pipeline for the 30-second Instagram reel (1080x1920).

- `prep/build_assets.py` reads the 12 STLs in `hardware/stl/`, places each one with the
  transforms from `hardware/generate_stl.py` (and checks the result against the generator),
  smooths the normals and writes `assets/ghost.bin` + `assets/ghost.json`.
- `src/ghost.js` builds the rig: shell on its slider pins and springs, core, bezel, screen,
  LED ring, stand. `src/eye.js` is `software/ghost/eye.py` ported to a shader, with the mood
  colours from `eye.py` and the LED colours from `lights.py`.
- `src/studio.js` is the lighting, floor, haze and post chain.
- `tools/render_still.mjs` renders a still through headless Chromium.

```bash
pip install trimesh manifold3d numpy scipy rtree
npm install
python3 prep/build_assets.py
NODE_PATH=$(npm root -g) node tools/render_still.mjs closed out/closed.png
tools/pair.sh look            # closed + open, side by side, in out/
```

`stills/` holds the look-approval frames.
