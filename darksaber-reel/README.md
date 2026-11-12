# Darksaber teaser reel

An 11.5-second Instagram reel (1080x1920, 30 fps) for the Darksaber LED blade project:
line-art build (print, assemble, solder), lights out, the blade ignites standing up, swings
level as the camera drops in, title.

- `video/darksaber_reel.mp4` is the cut, with its own synthesised sound.
- The drawings and the 3D blade, core, emitter and plug come from the project's 12 STLs.
  The handle and guard are stand-ins: the original hilt files are not in the project folder.

## How it is made

- `timing.json` is the edit. Picture and sound both read it.
- `prep/build_assets.py <project folder>` puts the print-pose STLs back in the assembled
  pose (constants from the project's `scripts/build.py`) and writes meshes for the 3D shots
  plus 2D outlines for the line-art shots.
- `prep/make_audio.py` synthesises every sound from scratch: printer, snaps, solder, switch,
  ignition, hum, swing, title hit. No samples and no film audio.
- `src/scene2d.js` draws the 2D half on a canvas. `src/saber.js` is the 3D saber,
  `src/studio.js` the lighting and post chain, `index.html` the 3D shots and the page.

```bash
pip install trimesh shapely scipy numpy networkx
npm install
python3 -I prep/build_assets.py /path/to/darksaber-led-blade
python3 prep/make_audio.py
export NODE_PATH=$(npm root -g)          # for the pre-installed Playwright
node tools/render.mjs                    # -> out/darksaber_reel.mp4
node tools/render.mjs --scale 0.5        # quick preview
```

Live preview: `node tools/server.mjs`, open `http://127.0.0.1:8123/index.html`, space to play.
