#!/usr/bin/env python3
"""Darksaber reel: turn the project's 12 print-ready STLs into render assets.

    python3 -I prep/build_assets.py /path/to/darksaber-led-blade

The STLs are in print orientation.  This puts each one back in the assembled pose using
the constants in the project's scripts/build.py (emitter frame S, Y, H; blade centre;
segment and core cut positions), then writes:

  assets/saber.bin + saber.json   meshes for the 3D shots (positions + smoothed normals)
  assets/outlines.json            2D side-view outlines for the line-art shots, taken from
                                  the same geometry (so the drawings are the real parts)

Saber frame used by the reel: x = along the blade toward the tip (mm from the emitter's
rear face), y = up, z = toward the viewer, with the blade's centre line on y = 0.
"""
import json
import math
import os
import sys

import numpy as np
import scipy.sparse as sp
import trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union

SRC = sys.argv[1]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
os.makedirs(OUT, exist_ok=True)
load = lambda n: trimesh.load(os.path.join(SRC, "out", "stl", n + ".stl"), force="mesh")

# ---- constants from scripts/build.py and scripts/hero.py -----------------------------------
C = -28.68                      # blade centre height in the emitter frame
W, TH = 30.0, 8.0               # blade section 8 x 30 mm
SPLUG, STIP = 76.0, 700.0
SEGS = [(SPLUG, 300.0), (300.0, 520.0), (520.0, STIP + 1)]
CW, CT, CS0 = 16.0, 5.8, 80.0
A_CUTS = [CS0, CS0 + 200, CS0 + 400]
B_CUTS = [CS0, CS0 + 100, CS0 + 300, CS0 + 500]

# frame (S, Y, H) -> saber frame (x, y, z) = (S, H - C, -Y)
F = np.array([[1, 0, 0, 0], [0, 0, 1, -C], [0, -1, 0, 0], [0, 0, 0, 1.0]])


def creased_normals(V, Fc, crease_deg=38.0):
    tri = V[Fc]
    e0, e1, e2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 1], tri[:, 0] - tri[:, 2]
    fn = np.cross(e0, -e2)
    area = np.linalg.norm(fn, axis=1) / 2.0
    fn = fn / np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-20)

    def ang(a, b):
        a = a / np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-20)
        b = b / np.maximum(np.linalg.norm(b, axis=1, keepdims=True), 1e-20)
        return np.arccos(np.clip((a * b).sum(1), -1, 1))
    cang = np.stack([ang(e0, -e2), ang(e1, -e0), ang(e2, -e1)], axis=1)
    nf = len(Fc)
    cf = np.repeat(np.arange(nf), 3)
    w = (area[:, None] * cang).reshape(-1) + 1e-12
    A = sp.csr_matrix((np.ones(nf * 3), (np.arange(nf * 3), Fc.reshape(-1))), shape=(nf * 3, len(V)))
    pairs = (A @ A.T).tocoo()
    i, j = pairs.row, pairs.col
    keep = (fn[cf[i]] * fn[cf[j]]).sum(1) >= math.cos(math.radians(crease_deg))
    i, j = i[keep], j[keep]
    N = np.zeros((nf * 3, 3))
    np.add.at(N, i, fn[cf[j]] * w[j][:, None])
    bad = np.linalg.norm(N, axis=1) < 1e-12
    N[bad] = fn[cf[bad]]
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    return tri.reshape(-1, 3), N


blob, manifest = [], {"parts": {}}


def emit(name, m):
    m = m.copy(); m.merge_vertices(); m.apply_transform(F)
    pos, nrm = creased_normals(np.asarray(m.vertices), np.asarray(m.faces))
    ofs = sum(len(b) for b in blob)
    blob.append(np.concatenate([pos.astype("<f4").reshape(-1), nrm.astype("<f4").reshape(-1)]))
    manifest["parts"][name] = {"offset": int(ofs), "count": int(len(pos))}
    b = m.bounds
    print(f"  {name:12s} {len(m.faces):6d} tris   x {b[0][0]:7.1f}..{b[1][0]:7.1f}   y {b[0][1]:6.1f}..{b[1][1]:6.1f}   z {b[0][2]:6.1f}..{b[1][2]:6.1f}")
    return m


def T(mat3, t):
    M = np.eye(4); M[:3, :3] = mat3; M[:3, 3] = t; return M


print("Assembling from print pose (emitter frame -> saber frame):")
# ---- emitter: same frame detection as build.py, run on the modified part -----------------
E = load("Emitter_Lower_LED")
n, ar = E.face_normals, E.area_faces
sel = (n @ np.array([0.85, 0, 0.53])) > 0.9995
p = (n[sel] * ar[sel, None]).sum(0); p[1] = 0; p /= np.linalg.norm(p)
R = np.vstack([[p[2], 0, -p[0]], [0, 1.0, 0], p])
Vv = E.vertices @ R.T
S0, H0 = Vv[:, 0].min(), Vv[:, 2].max()
mid = (Vv[:, 0] > S0 + 40) & (Vv[:, 0] < S0 + 90)
yc = (Vv[mid, 1].min() + Vv[mid, 1].max()) / 2
E.apply_transform(T(R, -np.array([S0, yc, H0])))
assert abs(E.extents[0] - 115.7) < 0.2 and abs(E.extents[2] - 51.2) < 0.2, E.extents
emitter = emit("emitter", E)

# ---- plug: stand() put S on z; its blade slot is centred on (Y, H) = (0, C) --------------
Pl = load("Emitter_Plug")
slot = min(Pl.section(plane_origin=[0, 0, 8], plane_normal=[0, 0, 1]).discrete, key=len)[:, :2]
sx, sy = (slot[:, 0].min() + slot[:, 0].max()) / 2, (slot[:, 1].min() + slot[:, 1].max()) / 2
Pl.apply_transform(T([[0, 0, 1], [1, 0, 0], [0, 1, 0]], [SPLUG + 0.2, -sx, C - sy]))
plug = emit("plug", Pl)

# ---- blade shells: x = Y + 4, y = H - (C - 15), z = S - s0 --------------------------------
shells = []
for i, (s0, s1) in enumerate(SEGS):
    m = load(f"Blade_Shell_{i + 1}" + ("_tip" if i == 2 else ""))
    m.apply_transform(T([[0, 0, 1], [1, 0, 0], [0, 1, 0]], [s0, -TH / 2, C - W / 2]))
    shells.append(emit(f"shell{i + 1}", m))

# ---- core strips: x = S - s0, y = H - (C - 8), z = thickness; layer A behind, B in front ----
cores = []
for tag, cuts, y0 in (("A", A_CUTS, -CT / 2), ("B", B_CUTS, 0.0)):
    for j, s0 in enumerate(cuts):
        m = load(f"Core_{tag}{j + 1}")
        m.apply_transform(T([[1, 0, 0], [0, 0, 1], [0, 1, 0]], [s0, y0, C - CW / 2]))
        cores.append((f"core{tag}{j + 1}", emit(f"core{tag}{j + 1}", m)))

with open(os.path.join(OUT, "saber.bin"), "wb") as f:
    f.write(np.concatenate(blob).tobytes())

# ---- 2D outlines (side view: x along the blade, y up) -----------------------------------------
def silhouette(m, tol=0.06):
    tri = m.vertices[m.faces][:, :, :2]
    d1, d2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    area = np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / 2
    polys = [Polygon(t) for t in tri[area > 1e-4]]
    u = unary_union([q.buffer(0.01) for q in polys]).buffer(-0.01)
    u = max(u.geoms, key=lambda g: g.area) if u.geom_type != "Polygon" else u
    return u.simplify(tol)


def section(m, z, tol=0.05):
    sc = m.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    loops = [Polygon(e[:, :2]).buffer(0) for e in sc.discrete if len(e) > 3]
    loops.sort(key=lambda q: -q.area)
    out = loops[0]
    for q in loops[1:]:
        out = out.difference(q) if out.contains(q.representative_point()) else out.union(q)
    return out.simplify(tol)


ring = lambda r: [[round(float(x), 2), round(float(y), 2)] for x, y in list(r.coords)[:-1]]
poly = lambda q: {"outer": ring(q.exterior), "holes": [ring(h) for h in q.interiors]}
biggest = lambda g: max(g.geoms, key=lambda q: q.area) if g.geom_type != "Polygon" else g

em_sil = silhouette(emitter)
em_cut = biggest(section(emitter, -6.0))            # the project's own figure cuts 6 mm off centre
plug_cut = biggest(section(plug, -6.0))
core_polys = [(n, silhouette(m, 0.02)) for n, m in cores]
core_all = unary_union([q.buffer(0.02) for n, q in core_polys if n.startswith("coreA")]).buffer(-0.02)
core_all = biggest(core_all).simplify(0.02)
# LED strip: runs round the core's edge, open at the emitter end
pts = np.array(core_all.exterior.coords[:-1])
start = int(np.argmin(np.abs(pts[:, 0] - pts[:, 0].min()) + (pts[:, 1] < 0) * 1e3))     # rear corner, top edge
pts = np.roll(pts, -start, axis=0)
if pts[1, 0] < pts[0, 0] + 1 and abs(pts[1, 1] - pts[0, 1]) > 1:                          # first step runs down the rear edge: flip
    pts = np.roll(pts[::-1], 1, axis=0)
led = [[round(float(x), 2), round(float(y), 2)] for x, y in pts]
led_len = float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())

outlines = {
    "emitter": poly(em_sil), "emitterCut": poly(em_cut), "plugCut": poly(plug_cut),
    "shells": [poly(silhouette(m, 0.02)) for m in shells],
    "cores": {n: poly(q) for n, q in core_polys}, "core": poly(core_all),
    "led": led, "ledLength": round(led_len, 1),
    "blade": {"x0": SPLUG, "tip": STIP, "half": W / 2, "thick": TH},
    "segments": [[a, min(b, STIP)] for a, b in SEGS], "aJoints": A_CUTS[1:], "bJoints": B_CUTS[1:],
    "bay": {"x0": 34.0, "x1": 76.0},
}
manifest.update(blade={"x0": SPLUG, "tip": STIP, "half": W / 2, "thick": TH}, core={"x0": CS0, "x1": float(core_all.bounds[2]), "half": CW / 2, "thick": CT},
                emitter={"x0": 0.0, "x1": float(emitter.bounds[1][0]), "top": float(emitter.bounds[1][1]), "bottom": float(emitter.bounds[0][1]), "halfZ": float(emitter.bounds[1][2])},
                led=led)
json.dump(manifest, open(os.path.join(OUT, "saber.json"), "w"))
json.dump(outlines, open(os.path.join(OUT, "outlines.json"), "w"))
print(f"wrote assets: {sum(v['count'] for v in manifest['parts'].values()) // 3} triangles; "
      f"emitter outline {len(outlines['emitter']['outer'])} pts, cut {len(outlines['emitterCut']['outer'])} pts + {len(outlines['emitterCut']['holes'])} holes; "
      f"LED path {led_len:.0f} mm round the core edge")
