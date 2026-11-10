#!/usr/bin/env python3
"""Turn the 12 printable STLs into render-ready geometry for the reel.

Nothing is remodelled.  Every mesh is read from hardware/stl/*.stl, and
hardware/generate_stl.py supplies where it sits: each STL is in print orientation, so
this script undoes the generator's print transform, then checks the result against the
generator's own world-frame mesh (max vertex distance is printed, it must be ~0).

Render-only changes:
  * smooth vertex normals with a crease angle, so curved surfaces lose their facets
  * a 0.9 mm rounded edge on the 8 shell pieces (so edges catch a highlight), cut back
    with the original pin socket and spring counterbore

Output:  reel/assets/ghost.bin (float32 positions + normals [+ tangents]) and ghost.json.
World frame is the generator's: +x right, +y up, +z toward the viewer, millimetres.
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np
import scipy.sparse as sp
import trimesh
from scipy.spatial import ConvexHull, HalfspaceIntersection, cKDTree
from trimesh.creation import icosphere
from trimesh.transformations import translation_matrix

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
STL = os.path.join(REPO, "hardware", "stl")
OUT = os.path.join(HERE, "..", "assets")
sys.path.insert(0, os.path.join(REPO, "hardware"))
import generate_stl as G  # noqa: E402

p = dict(G.P)
BEVEL = 0.9


def load(name):
    m = trimesh.load(os.path.join(STL, name + ".stl"), force="mesh")
    m.merge_vertices()
    return m


def maxdist(a, b):
    """Symmetric max nearest-vertex distance between two meshes."""
    da = cKDTree(b.vertices).query(a.vertices)[0].max()
    db = cKDTree(a.vertices).query(b.vertices)[0].max()
    return max(da, db)


def placed(name, world_from_print, reference):
    """Load an STL, move it to the world frame, verify it against the generator's mesh."""
    m = load(name)
    m.apply_transform(world_from_print)
    err = maxdist(m, reference)
    flag = "ok" if err < 1e-3 else "MISMATCH"
    print(f"  {name:18s} {len(m.faces):6d} tris   placement error {err:.5f} mm  {flag}")
    if err >= 1e-3:
        raise SystemExit(f"{name}: STL does not match generate_stl.py")
    return m


# ---------------------------------------------------------------------------
# normals
# ---------------------------------------------------------------------------
def creased_normals(V, F, crease_deg=38.0, fixed=None):
    """Per-corner normals: average the normals of the faces around each vertex that are
    within `crease_deg` of the corner's own face, weighted by area x corner angle.
    Returns (positions[n*3,3], normals[n*3,3]) as a triangle soup."""
    tri = V[F]
    e0, e1, e2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 1], tri[:, 0] - tri[:, 2]
    fn = np.cross(e0, -e2)
    area = np.linalg.norm(fn, axis=1) / 2.0
    fn = fn / np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-20)

    def ang(a, b):
        a = a / np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-20)
        b = b / np.maximum(np.linalg.norm(b, axis=1, keepdims=True), 1e-20)
        return np.arccos(np.clip((a * b).sum(1), -1, 1))
    cang = np.stack([ang(e0, -e2), ang(e1, -e0), ang(e2, -e1)], axis=1)   # [f,3]

    nf = len(F)
    corner_face = np.repeat(np.arange(nf), 3)
    corner_vert = F.reshape(-1)
    w = (area[:, None] * cang).reshape(-1) + 1e-12
    A = sp.csr_matrix((np.ones(nf * 3), (np.arange(nf * 3), corner_vert)), shape=(nf * 3, len(V)))
    pairs = (A @ A.T).tocoo()
    i, j = pairs.row, pairs.col
    keep = (fn[corner_face[i]] * fn[corner_face[j]]).sum(1) >= math.cos(math.radians(crease_deg))
    i, j = i[keep], j[keep]
    N = np.zeros((nf * 3, 3))
    np.add.at(N, i, fn[corner_face[j]] * w[j][:, None])
    bad = np.linalg.norm(N, axis=1) < 1e-12
    N[bad] = fn[corner_face[bad]]
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    if fixed is not None:
        mask, vals = fixed
        N[mask] = vals[mask]
    return tri.reshape(-1, 3), N


# ---------------------------------------------------------------------------
# shell piece: rounded edges
# ---------------------------------------------------------------------------
def rounded_fin(fin_world, cavity):
    """fin_world: the STL piece in its top-front world position; cavity: the generator's pin
    socket + spring counterbore.  Returns a piece whose convex outer skin has BEVEL mm
    rounded edges, with the same socket cut back in."""
    hull = fin_world.convex_hull
    # inset the convex hull by BEVEL (shift every face plane inward) ...
    nrm, off = hull.face_normals, -(hull.face_normals * hull.triangles[:, 0]).sum(1)
    hs = np.unique(np.round(np.column_stack([nrm, off + BEVEL]), 6), axis=0)
    inner_pts = HalfspaceIntersection(hs, hull.centroid).intersections
    inner = trimesh.Trimesh(*_hull(inner_pts))
    # ... then roll a ball of radius BEVEL around it
    ball = icosphere(subdivisions=3, radius=BEVEL).vertices
    cloud = (inner.vertices[:, None, :] + ball[None, :, :]).reshape(-1, 3)
    skin = trimesh.Trimesh(*_hull(cloud))
    out = skin.difference(cavity)
    out.merge_vertices()
    # exact normals on the skin: direction from the closest point of the inset solid
    cp, dist, _ = trimesh.proximity.closest_point(inner, out.vertices)
    n_skin = out.vertices - cp
    n_skin /= np.maximum(np.linalg.norm(n_skin, axis=1, keepdims=True), 1e-9)
    on_skin = np.abs(dist - BEVEL) < 0.02
    return out, on_skin, n_skin


def _hull(pts):
    h = ConvexHull(pts)
    idx = np.unique(h.simplices)
    remap = -np.ones(len(pts), int); remap[idx] = np.arange(len(idx))
    V, F = pts[idx], remap[h.simplices]
    c = V.mean(0)
    tri = V[F]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    flip = ((tri[:, 0] - c) * n).sum(1) < 0
    F[flip] = F[flip][:, ::-1]
    return V, F


# ---------------------------------------------------------------------------
def main():
    os.makedirs(OUT, exist_ok=True)
    blob, manifest = [], {"parts": {}}

    def emit(name, pos, nrm, tan=None):
        ofs = sum(len(b) for b in blob)
        arrs = [pos, nrm] + ([tan] if tan is not None else [])
        data = np.concatenate([a.astype("<f4").reshape(-1) for a in arrs])
        blob.append(data)
        manifest["parts"][name] = {"offset": int(ofs), "count": int(len(pos)), "tangents": tan is not None}

    def emit_mesh(name, m, crease=38.0):
        pos, nrm = creased_normals(np.asarray(m.vertices), np.asarray(m.faces), crease)
        emit(name, pos, nrm)

    print("Placing STLs with generate_stl.py transforms:")
    R, rot, T = p["core_r"], G.rot, translation_matrix

    # ---- shell piece (top-front), closed ------------------------------------------------
    raw = G.piece_raw(p)
    axis0 = G.piece_axis(raw)
    nrm_bed = raw.face_normals[int(np.argmax(raw.area_faces))]
    Rp = np.linalg.inv(G.align_z_to(-nrm_bed))
    tmp = G.fin(p); tmp.apply_transform(Rp)
    fin_print = T(-tmp.bounds[0]) @ Rp                                # generator: world -> bed
    closed_ofs = G.shell_offset(p, 0.0)
    ref = G.fin(p); ref.apply_translation(axis0 * closed_ofs)
    fin_w = placed("fin_x8", T(axis0 * closed_ofs) @ np.linalg.inv(fin_print), ref)
    r_in, r_out = G.socket_range(p, raw)
    depth = min(p["fin_socket_depth"], (r_out - r_in) - 3.0)
    seat_d = p["spring_seat_depth"]
    cav = G.cyl_along(axis0, p["fin_socket_r"], r_in - 3.0, r_in + seat_d + depth).union(
        G.cyl_along(axis0, p["spring_od"] / 2.0 + 0.3, r_in - 3.0, r_in + seat_d))
    cav.apply_translation(axis0 * closed_ofs)
    rf, on_skin, n_skin = rounded_fin(fin_w, cav)
    chk = fin_w.convex_hull.difference(cav)
    print(f"  {'socket check':18s}               STL vs hull-minus-socket {maxdist(chk, fin_w):.5f} mm")
    V, F = np.asarray(rf.vertices), np.asarray(rf.faces)
    fnrm = rf.face_normals
    skin_face = on_skin[F].all(1) & ((n_skin[F].mean(1) * fnrm).sum(1) > 0.8)
    fixed_mask = np.repeat(skin_face, 3)
    pos, nrm = creased_normals(V, F, 40.0, fixed=(fixed_mask, n_skin[F.reshape(-1)]))
    # brushing direction: along the piece's own axis, projected into the surface
    tan = axis0[None, :] - (nrm @ axis0)[:, None] * nrm
    alt = np.cross(nrm, [1.0, 0, 0])
    weak = np.linalg.norm(tan, axis=1) < 0.15
    tan[weak] = alt[weak]
    tan /= np.linalg.norm(tan, axis=1, keepdims=True)
    emit("fin", pos, nrm, np.column_stack([tan, np.ones(len(tan))]))
    print(f"  {'fin (rounded)':18s} {len(F):6d} tris   {BEVEL} mm edge radius, "
          f"volume {rf.volume/fin_w.volume*100:.1f}% of the STL piece")

    # piece rotations (the generator mirrors the back four; the piece is x-symmetric, so a
    # mirror in z equals a half turn about y and winding stays intact)
    fin_mats, dirs = [], []
    for i in range(8):
        M = rot([0, 0, 1], -90 * (i % 4))
        if i >= 4:
            M = rot([0, 1, 0], 180) @ rot([0, 0, 1], 90 * (i % 4))
        gen = trimesh.transform_points([raw.centroid], G.piece_transform(i))[0]
        mine = trimesh.transform_points([raw.centroid], M)[0]
        assert np.allclose(gen, mine, atol=1e-6), i
        fin_mats.append(M.tolist()); dirs.append(G.unit(mine).tolist())
    gen_fins = G.fins_in_place(p, 0.0)
    worst = 0.0
    for i in range(8):
        m = fin_w.copy(); m.apply_transform(np.array(fin_mats[i]))
        worst = max(worst, maxdist(m, gen_fins[i]))
    print(f"  {'8 pieces in place':18s}               placement error {worst:.5f} mm  ok")

    # ---- core, bezel ---------------------------------------------------------------------
    front, back, front_p, back_p = G.core_halves(p)
    tmp = front.copy(); tmp.apply_transform(rot([1, 0, 0], 180))
    emit_mesh("core_front", placed("core_front", np.linalg.inv(T([0, 0, -tmp.bounds[0][2]]) @ rot([1, 0, 0], 180)), front))
    emit_mesh("core_back", placed("core_back", T([0, 0, back.bounds[0][2]]), back))
    bez_T = T([0, 0, R - 8.5 + 13.0]) @ rot([1, 0, 0], 180)            # as in the generator's collision check
    bez_ref = G.eye_bezel(p); bez_ref.apply_transform(bez_T)
    bez = placed("eye_bezel", bez_T, bez_ref)
    emit_mesh("eye_bezel", bez)

    # ---- slider pin, spider ring (kept in their own z-up frames, placed at run time) -------
    emit_mesh("slider_pin", placed("slider_pin_x8", np.eye(4), G.slider_pin(p)))
    emit_mesh("spider_ring", placed("spider_ring", np.eye(4), G.spider_ring(p)))
    emit_mesh("spool", placed("spool", np.eye(4), G.spool(p)))
    emit_mesh("shell_servo_mount", placed("shell_servo_mount", np.eye(4), G.shell_servo_mount(p)))

    # ---- stand ---------------------------------------------------------------------------
    arm_m, arm_p, y0 = G.arm(p)
    tmp = arm_m.copy(); tmp.apply_transform(rot([0, 1, 0], 90))
    emit_mesh("arm", placed("arm", np.linalg.inv(T(-tmp.bounds[0]) @ rot([0, 1, 0], 90)), arm_m))
    hm, hm_p = G.head_mount(p)
    tmp = hm.copy(); tmp.apply_transform(rot([0, 1, 0], -90))
    emit_mesh("head_mount", placed("head_mount", np.linalg.inv(T(-tmp.bounds[0]) @ rot([0, 1, 0], -90)), hm))
    base_m, lid_m = G.base(p, y0)
    # The generator's preview drops the lid 3 mm into the arm's pan disc.  Seat it properly:
    # lid top flush under the disc, base wall directly under the lid.
    lid_T = T([0, y0 - 6.0, p["base_center_z"]]) @ rot([1, 0, 0], -90)
    base_T = T([0, y0 - 3.0 - p["base_h"], p["base_center_z"]]) @ rot([1, 0, 0], -90)
    ref = base_m.copy(); ref.apply_transform(base_T)
    emit_mesh("base", placed("base", base_T, ref))
    ref = lid_m.copy(); ref.apply_transform(lid_T)
    emit_mesh("base_lid", placed("base_lid", lid_T, ref))

    # ---- mechanism numbers ---------------------------------------------------------------
    z_open, z_closed, L_front, L_back, cap_open, cap_closed = G.ring_travel(p)
    servo_y = -(p["arm_z"] - p["base_center_z"])
    manifest.update(
        fin_matrices=fin_mats, fin_dirs=dirs, fin_axis0=axis0.tolist(),
        fin_bed_matrix=(fin_print @ T(-axis0 * closed_ofs)).tolist(),   # closed world pose -> print bed (z up)
        shell_travel=p["shell_travel"], closed_gap=p["closed_gap"],
        spring_seat_depth=p["spring_seat_depth"], spring_od=12.0,
        core_r=R, core_wall=p["core_wall"],
        pin_cap_closed=cap_closed - p["pin_cap_t"] / 2.0,      # radius of the pin's inner end, closed
        pin_cap_t=p["pin_cap_t"],
        ring_z_open=z_open, ring_z_closed=z_closed, ring_tie_r=p["ring_tie_r"], ring_t=p["ring_t"],
        tendon_front=L_front, tendon_back=L_back,
        bezel_front_z=R - 8.5 + 13.0, bezel_window_r=p["bezel_window_r"], bezel_r=p["bezel_r"],
        bezel_lip_t=p["bezel_lip_t"], led_ring_r=p["led_ring_r"], bezel_len=p["bezel_len"],
        tilt_pivot=[0.0, -4.0, p["tilt_pivot_z"]], pan_axis=[0.0, 0.0, p["arm_z"]],
        arm_y0=y0, lid_top_y=y0, base_bottom_y=y0 - 3.0 - p["base_h"], base_h=p["base_h"],
        base_center_z=p["base_center_z"], base_r=p["base_r"], base_wall=p["base_wall"],
        pan_servo_y=servo_y, servo_body=list(p["servo_body"]), pi_holes=list(p["pi_holes"]),
        spool_r=p["spool_r"], bevel=BEVEL,
        neck_z=-(R + 5.0),
    )
    with open(os.path.join(OUT, "ghost.bin"), "wb") as f:
        f.write(np.concatenate(blob).tobytes())
    with open(os.path.join(OUT, "ghost.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    tris = sum(v["count"] for v in manifest["parts"].values()) // 3
    print(f"wrote assets/ghost.bin + ghost.json  ({tris} triangles, {sum(len(b) for b in blob)*4/1e6:.1f} MB)")
    print(f"mechanism: ring z {z_closed:.1f} (closed) -> {z_open:.1f} (open); tendons {L_front:.1f} / {L_back:.1f} mm; "
          f"pin inner end at r={cap_closed - p['pin_cap_t']/2:.1f} closed, +{p['shell_travel']:.0f} open")


if __name__ == "__main__":
    main()
