#!/usr/bin/env python3
"""
Parametric Destiny Ghost shell generator.

Produces every printable part as an STL in hardware/stl/ plus a preview render.
Everything is built in the "world" frame:  +x right, +y up, +z toward the viewer
(the eye faces +z).  Units are millimetres.

    python3 hardware/generate_stl.py            # writes hardware/stl/*.stl + preview.png
    python3 hardware/generate_stl.py --scale 0.8  # smaller Ghost

Requires:  pip install trimesh manifold3d numpy scipy shapely matplotlib
"""
from __future__ import annotations

import argparse
import math
import os
import sys

import numpy as np
import trimesh
from trimesh.creation import box, cylinder, icosphere
from trimesh.transformations import rotation_matrix, translation_matrix

# ---------------------------------------------------------------------------
# Parameters (mm).  Tweak these, re-run, re-slice.
# ---------------------------------------------------------------------------
P = dict(
    # Shell (the 8 silver pieces) -----------------------------------------
    half_w=90.0,          # half of the front-view diamond width/height (tip to tip = 180)
    half_d=75.0,          # the piece axes aim at (0, half_w, half_d): depth ~0.85 x width
    tip_w=40.0,           # length of the blunt tip edge (the arm width in the side view)
    wing_frac=0.5,        # wings sit this far along the diamond edge (0.5 = edge midpoint)
    inner_diag=(25.0, 26.0),   # (d, z): inner corners at (+-d, d, z) on the diagonals, at the eye ring
    inner_front=(26.0, 28.0),  # (y, z) of the inner-front corner on the ridge, beside the bezel
    inner_back=44.0,      # distance of the inner-back corner (on the seam plane)
    piece_gap=0.975,      # each piece scaled about its centroid -> ~2 mm seams
    # Spreading shell mechanism ---------------------------------------------
    # Each piece is glued onto a slider pin that runs in a guide tube in the core.  A
    # compression spring on the pin pushes the piece OUT; a fishing-line tendon from the
    # pin's inner cap to a spool on a servo in the core pulls it back IN.
    # The eight tendons tie to a small SPIDER RING on the eye axis inside the core.  A
    # Bowden cable (PTFE sheath + wire) runs from the ring out through the hollow neck,
    # down the arm, to a spool on a servo in the base.  Pulling the ring backward closes
    # all eight pieces at once; the generator prints the ring travel and tendon lengths.
    closed_gap=3.0,       # piece-to-core gap when closed: the reference's tight seams
    spring_seat_depth=6.0,  # counterbore inside the piece that swallows the compressed spring
    shell_travel=12.0,    # how far each piece slides out when the shell opens
    pin_r=4.8,            # slider pin
    pin_cap_r=6.0,        # cap on the pin's inner end: stop against the guide tube + tendon anchor
    pin_cap_t=3.0,
    sleeve_r=5.15,        # guide bore for the pin (0.35 mm clearance)
    sleeve_or=7.5,        # guide tube outer radius (inside the core)
    sleeve_len=6.0,       # guide tube length inward from the inner wall
    fin_socket_r=5.0,     # socket in the piece for the pin (glue fit)
    fin_socket_depth=12.0,
    spring_od=12.5,       # spring counterbore in the piece (12 mm OD spring)
    ring_r=7.0,           # spider ring
    ring_t=3.0,
    ring_tie_r=5.3,       # tendon holes on the ring
    bowden_r=2.2,         # bore for the 4 mm PTFE sheath's inner wire / sheath seat
    sheath_r=2.15,        # 4 mm OD PTFE tube (slight clearance)
    spool_r=8.0,
    spool_t=6.0,
    # Core (black sphere) ---------------------------------------------------
    core_r=35.0,
    core_wall=3.0,
    eye_bore_r=23.6,      # bore for the eye bezel tube
    lip_h=5.0,            # joining lip on the back half
    # Eye bezel -------------------------------------------------------------
    bezel_r=23.4,         # tube outer radius (0.2 mm clearance in the bore)
    bezel_len=9.0,        # tube length; the PCB backplate adds 4 mm behind it
    bezel_window_r=16.6,  # lens window (GC9A01 active area is 32.4 mm dia)
    bezel_lip_t=2.0,
    led_ring_r=22.5,      # 16-LED NeoPixel ring is 44.5 mm OD -> pocket radius
    led_ring_t=4.0,
    # Stand -----------------------------------------------------------------
    base_r=90.0,
    base_h=32.0,
    base_wall=2.5,
    base_center_z=-58.0,  # base puck centre sits this far behind the core centre
    arm_z=-122.0,         # lower arm centreline: clears the bottom-back piece, shell open, at 15 deg
    arm_w=16.0,           # arm cross-section (x)
    arm_d=24.0,           # arm cross-section (z)
    tilt_pivot_z=-70.0,   # tilt axis (parallel to x) sits here behind the core
    # Servo (MG90S / SG90 footprint) ----------------------------------------
    servo_body=(23.2, 12.6),   # slot for the body (L x W) with clearance
    servo_body_h=24.0,
    servo_hole_spacing=28.0,
    servo_hole_r=1.1,
    # Raspberry Pi 4 mounting pattern
    pi_holes=(58.0, 49.0),
    pi_hole_r=1.4,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


def rot(axis, deg, point=None):
    return rotation_matrix(math.radians(deg), axis, point)


def align_z_to(direction):
    """Transform that rotates +z onto `direction`."""
    d = unit(direction)
    z = np.array([0.0, 0.0, 1.0])
    c = float(np.dot(z, d))
    if c > 0.999999:
        return np.eye(4)
    if c < -0.999999:
        return rot([1, 0, 0], 180)
    axis = np.cross(z, d)
    return rotation_matrix(math.acos(c), axis)


def cyl_along(direction, r, start, end, sections=48):
    """Cylinder of radius r along `direction` from distance `start` to `end` from origin."""
    d = unit(direction)
    length = end - start
    c = cylinder(radius=r, height=length, sections=sections)
    c.apply_translation([0, 0, start + length / 2.0])
    c.apply_transform(align_z_to(d))
    return c


def union(meshes):
    meshes = [m for m in meshes if m is not None]
    out = meshes[0]
    for m in meshes[1:]:
        out = out.union(m)
    return out


def difference(a, subtract):
    out = a
    for m in subtract:
        out = out.difference(m)
    return out


def check(mesh, name):
    if not mesh.is_watertight:
        print(f"  ! {name}: mesh is not watertight (slicers usually repair this)")
    ext = mesh.extents
    print(f"  {name:18s} {ext[0]:6.1f} x {ext[1]:6.1f} x {ext[2]:6.1f} mm   "
          f"{mesh.volume/1000:6.1f} cm3   {len(mesh.faces)} tris")
    return mesh


from trimesh.transformations import scale_matrix


def piece_points(p):
    """Corner points of the TOP-FRONT shell piece in the world frame (x right, y up, z front).

    Read straight off the reference sheet:
      A1, A2  the blunt tip edge (a point from the front, a short flat end from the side)
      W+, W-  the wings: on the diamond's edge midpoints, on the mid-plane z=0, where four
              pieces meet - they give the solid diamond outline from the front and the
              central-diamond / notch pattern from the top and side
      D+, D-  inner corners on the diagonals at the eye ring: adjacent pieces share the
              W-D edge, so the front shows thin diagonal seams from the eye to the edge midpoints
      Cf      inner-front corner on the ridge, beside the eye bezel
      Cb      inner-back corner on the seam plane
    The ridge A1-A2-Cf is the crease you see down the middle of each piece.
    """
    b, c, w = p["half_w"], p["half_d"], p["tip_w"]
    n = math.hypot(b, c)
    axis = np.array([0.0, b / n, c / n])
    perp = np.array([0.0, -c / n, b / n])          # down-front, perpendicular to the axis
    L = (b * n - w * c / 2.0) / b                   # so the upper tip corner sits at y = b
    A1 = axis * L - perp * (w / 2.0)
    A2 = axis * L + perp * (w / 2.0)
    f = p["wing_frac"]
    Wp = np.array([b * f, b * (1 - f), 0.0])
    Wm = np.array([-b * f, b * (1 - f), 0.0])
    d, zd = p["inner_diag"]
    Dp = np.array([d, d, zd])
    Dm = np.array([-d, d, zd])
    Cf = np.array([0.0, p["inner_front"][0], p["inner_front"][1]])
    Cb = np.array([0.0, p["inner_back"], 0.0])
    return np.array([A1, A2, Wp, Wm, Dp, Dm, Cf, Cb])


def piece_transform(index):
    """Transform taking the top-front piece to piece `index` (0..7).
    0 top-front, 1 right-front, 2 bottom-front, 3 left-front, 4..7 the same at the back."""
    T = rot([0, 0, 1], -90 * (index % 4))
    if index >= 4:
        T = np.diag([1.0, 1.0, -1.0, 1.0]) @ T
    return T


def piece_raw(p):
    """Top-front piece: convex hull of the six corner points, shrunk a hair for the seams."""
    pts = piece_points(p)
    m = trimesh.points.PointCloud(pts).convex_hull
    m.apply_transform(scale_matrix(p["piece_gap"], m.centroid))
    return m


def _inside_hull(m, pts):
    """Point-in-convex-mesh test without extra dependencies."""
    origins = m.triangles[:, 0, :]
    normals = m.face_normals
    d = (pts[:, None, :] - origins[None, :, :]) @ normals.T  # wrong shape guard below
    d = np.einsum("pfk,fk->pf", pts[:, None, :] - origins[None, :, :], normals)
    return np.all(d <= 1e-6, axis=1)


def piece_axis(m):
    return unit(m.centroid)


def socket_range(p, m):
    """Where along the centroid ray the peg socket can live: (entry radius, end radius)."""
    ax = piece_axis(m)
    rs = np.arange(20.0, 120.0, 0.25)
    inside = _inside_hull(m, rs[:, None] * ax[None, :])
    if not inside.any():
        raise RuntimeError("centroid ray misses the piece")
    r_in = float(rs[inside][0])
    r_out = float(rs[inside][-1])
    return r_in, r_out


def fin(p):
    """One shell piece (top-front orientation) with the pin socket and spring counterbore
    bored along the centroid ray."""
    m = piece_raw(p)
    r_in, r_out = socket_range(p, m)
    depth = min(p["fin_socket_depth"], (r_out - r_in) - 3.0)
    ax = piece_axis(m)
    seat_d = p["spring_seat_depth"]
    sock = cyl_along(ax, p["fin_socket_r"], r_in - 1.0, r_in + seat_d + depth)
    seat = cyl_along(ax, p["spring_od"] / 2.0 + 0.3, r_in - 1.0, r_in + seat_d)
    return difference(m, [sock, seat])


def shell_offset(p, open_frac: float) -> float:
    """How far (mm) each piece sits out along its ray from the modelled position:
    closed_gap minus the built-in ~3 mm, plus travel * open_frac."""
    m = piece_raw(p)
    r_in, _ = socket_range(p, m)
    base_gap = r_in - p["core_r"]
    return (p["closed_gap"] - base_gap) + p["shell_travel"] * open_frac


def fin_printable(p):
    """The piece for printing: its largest flat face on the bed."""
    m = fin(p)
    raw = piece_raw(p)
    i = int(np.argmax(raw.area_faces))
    nrm = raw.face_normals[i]
    m.apply_transform(np.linalg.inv(align_z_to(-nrm)))   # face normal -> -z (face down)
    m.apply_translation(-m.bounds[0])
    return m


def fins_in_place(p, open_frac: float = 0.0):
    """All 8 pieces placed on the assembled Ghost (world frame), shell closed (0) .. open (1)."""
    base = fin(p)
    base.apply_translation(piece_axis(piece_raw(p)) * shell_offset(p, open_frac))
    out = []
    for i in range(8):
        m = base.copy()
        m.apply_transform(piece_transform(i))
        out.append(m)
    return out


def slider_pin(p):
    """Pin that carries a shell piece through the core's guide tube.  Print 8, vertical."""
    m = piece_raw(p)
    r_in, _ = socket_range(p, m)
    cap_r0 = p["core_r"] - p["core_wall"] - p["sleeve_len"] - p["shell_travel"] - 2.0  # cap radius (closed)
    tip_r = p["core_r"] + p["closed_gap"] + p["spring_seat_depth"] + p["fin_socket_depth"] - 1.0  # socket bottom (closed)
    length = tip_r - cap_r0
    pin = cylinder(radius=p["pin_r"], height=length, sections=48)
    pin.apply_translation([0, 0, length / 2.0])
    cap = cylinder(radius=p["pin_cap_r"], height=p["pin_cap_t"], sections=48)
    cap.apply_translation([0, 0, -p["pin_cap_t"] / 2.0])
    hole = cyl_along([1, 0, 0], 0.8, -10, 10)           # tendon hole through the cap
    hole.apply_translation([0, 0, -p["pin_cap_t"] / 2.0])
    m = pin.union(cap).difference(hole)
    m.apply_translation([0, 0, p["pin_cap_t"]])
    return m


def spider_ring(p):
    """The eight tendons tie to this ring; the Bowden wire pulls it backward along the eye axis."""
    m = cylinder(radius=p["ring_r"], height=p["ring_t"], sections=64)
    m.apply_translation([0, 0, p["ring_t"] / 2.0])
    holes = [cylinder(radius=1.3, height=10, sections=16)]           # wire knot / crimp
    for i in range(8):
        a = i * math.pi / 4 + math.pi / 8
        h = cylinder(radius=0.9, height=10, sections=12)
        h.apply_translation([p["ring_tie_r"] * math.cos(a), p["ring_tie_r"] * math.sin(a), 0])
        holes.append(h)
    return difference(m, holes)


def shell_servo_mount(p):
    """Bracket for the shell servo in the base: MG90S lies on its side (shaft along +x), the
    spool sits on the shaft, and a post 22 mm out holds the end of the Bowden sheath in line
    with the spool rim so the wire runs straight."""
    sb = p["servo_body"]
    blk = box(extents=[16.0, sb[0] + 6.0, sb[1] + 8.0])
    blk.apply_translation([-8.0, 0, (sb[1] + 8.0) / 2.0])
    pocket = box(extents=[sb[1] + 0.4, sb[0], 40.0])              # body slides in from the top
    pocket.apply_transform(rot([0, 1, 0], 90))
    pocket.apply_translation([-8.0 + 0.0, 0, (sb[1] + 8.0) / 2.0 + 4.0 + 20.0 - 4.0])
    # simpler: an open-top cradle: cut a channel the width of the body through the block
    chan = box(extents=[sb[1] + 0.4, sb[0] + 0.4, 40.0])
    chan.apply_translation([-8.0, 0, 4.0 + 20.0])
    tabs = []
    for sy in (1, -1):
        t = cylinder(radius=p["servo_hole_r"], height=30, sections=16)
        t.apply_transform(rot([0, 1, 0], 90))
        t.apply_translation([-8.0, sy * p["servo_hole_spacing"] / 2.0, 4.0 + sb[1] / 2.0])
        tabs.append(t)
    foot = box(extents=[52.0, sb[0] + 6.0, 3.0]); foot.apply_translation([10.0, 0, 1.5])
    post = box(extents=[8.0, 10.0, 4.0 + sb[1] / 2.0 + p["spool_r"] + 3.0])
    post.apply_translation([32.0, 0, post.extents[2] / 2.0])
    sheath = cylinder(radius=p["sheath_r"], height=6.0, sections=24)
    sheath.apply_transform(rot([0, 1, 0], 90))
    sheath.apply_translation([32.0 + 1.0, 0, 4.0 + sb[1] / 2.0 + p["spool_r"]])
    wire = cylinder(radius=1.2, height=20.0, sections=16)
    wire.apply_transform(rot([0, 1, 0], 90))
    wire.apply_translation([32.0 - 4.0, 0, 4.0 + sb[1] / 2.0 + p["spool_r"]])
    screws = []
    for sx in (-8.0, 28.0):
        for sy in (1, -1):
            s = cylinder(radius=1.7, height=10, sections=16)
            s.apply_translation([sx + 12.0, sy * (sb[0] / 2.0 + 1.0), 1.5]); screws.append(s)
    m = union([blk, foot, post])
    return difference(m, [chan, sheath, wire] + tabs + screws)


def ring_travel(p):
    """Solve for the ring's open/closed positions on the eye axis such that fixed-length
    tendons are taut in both states for the front group and the back group.
    Returns (z_open, z_closed, L_front, L_back)."""
    from scipy.optimize import fsolve
    R, wall = p["core_r"], p["core_wall"]
    cap_open = R - wall - p["sleeve_len"] - p["pin_cap_t"] / 2.0
    cap_closed = cap_open - p["shell_travel"]
    d = unit(piece_raw(p).centroid)                 # top-front ray
    tie = np.array([0.0, p["ring_tie_r"], 0.0])     # tie point on the ring, same azimuth
    def L(cap_r, z, back):
        c = d * cap_r
        if back: c = c * np.array([1, 1, -1])
        return np.linalg.norm(c - (tie + [0, 0, z]))
    def eqs(v):
        z0, z1 = v
        return [L(cap_open, z0, False) - L(cap_closed, z1, False),
                L(cap_open, z0, True) - L(cap_closed, z1, True)]
    z0, z1 = fsolve(eqs, [-10.0, -20.0])
    return float(z0), float(z1), float(L(cap_open, z0, False)), float(L(cap_open, z0, True)), cap_open, cap_closed


def spool(p):
    """Tendon spool for the shell servo: sits on a stock 20 mm round horn."""
    base_h = 3.0
    base_d = cylinder(radius=p["spool_r"] + 4.0, height=base_h, sections=64)   # sits on the horn
    base_d.apply_translation([0, 0, base_h / 2.0])
    horn = cylinder(radius=10.3, height=1.8, sections=64)      # pocket for the round horn
    horn.apply_translation([0, 0, 0.9])
    body = cylinder(radius=p["spool_r"], height=p["spool_t"], sections=64)
    body.apply_translation([0, 0, base_h + p["spool_t"] / 2.0])
    top = cylinder(radius=p["spool_r"] + 3.0, height=1.5, sections=64)
    top.apply_translation([0, 0, base_h + p["spool_t"] - 0.75])
    m = union([base_d, body, top])
    holes = [cylinder(radius=2.2, height=20, sections=24)]      # horn screw
    for i in range(8):
        h = cylinder(radius=0.9, height=20, sections=16)
        h.apply_translation([(p["spool_r"] - 1.8) * math.cos(i * math.pi / 4),
                             (p["spool_r"] - 1.8) * math.sin(i * math.pi / 4), 0])
        holes.append(h)
    return difference(m, [horn] + holes)


def peg_dirs(p):
    """Centroid rays of the 8 pieces - the core pegs point along these."""
    m = piece_raw(p)
    return [unit(trimesh.transform_points([m.centroid], piece_transform(i))[0]) for i in range(8)]


def core_halves(p):
    """Front and back hemispheres of the core, with pegs, eye bore, lip."""
    R, wall = p["core_r"], p["core_wall"]
    sphere = icosphere(subdivisions=4, radius=R)
    cavity = icosphere(subdivisions=4, radius=R - wall)
    def pegs(front: bool):
        """Guide tubes for the slider pins: from inside the cavity out to the surface."""
        dirs = [d for d in peg_dirs(p) if (d[2] > 0) == front]
        return [cyl_along(d, p["sleeve_or"], R - wall - p["sleeve_len"], R - 0.5) for d in dirs]

    def bores(front: bool):
        dirs = [d for d in peg_dirs(p) if (d[2] > 0) == front]
        return [cyl_along(d, p["sleeve_r"], R - wall - p["sleeve_len"] - 1.0, R + 2.0) for d in dirs]

    big = box(extents=[4 * R, 4 * R, 2 * R])
    front_keep = big.copy(); front_keep.apply_translation([0, 0, R])
    back_keep = big.copy(); back_keep.apply_translation([0, 0, -R])

    # ---- front half
    front = union([sphere] + pegs(True))
    front = front.intersection(front_keep)
    bore = cylinder(radius=p["eye_bore_r"], height=R, sections=96)
    bore.apply_translation([0, 0, R])
    screw_holes = []
    for a in (90, 210, 330):
        sh = cyl_along([math.cos(math.radians(a)), math.sin(math.radians(a)), 0],
                       1.1, R - wall - p["lip_h"], R + 1)
        sh.apply_translation([0, 0, p["lip_h"] / 2.0])
        screw_holes.append(sh)
    front = difference(front, [cavity, bore] + screw_holes + bores(True))

    # ---- back half
    back = union([sphere] + pegs(False))
    back = back.intersection(back_keep)
    back = back.difference(cavity)
    # Bowden wire passes from the neck socket straight into the cavity along the eye axis
    bowden = cylinder(radius=p["bowden_r"], height=30.0, sections=32)
    bowden.apply_translation([0, 0, -(R - wall) - 8.0])
    lip_o = cylinder(radius=R - wall - 0.3, height=p["lip_h"], sections=96)
    lip_o.apply_translation([0, 0, p["lip_h"] / 2.0])
    foot = cylinder(radius=R - 1.0, height=3.0, sections=96)      # overlaps the wall
    foot.apply_translation([0, 0, -1.5])
    lip_i = cylinder(radius=R - wall - 2.5, height=p["lip_h"] + 8, sections=96)
    lip = lip_o.union(foot).difference(lip_i)
    back = back.union(lip)
    # pilot holes in the lip for the 3 screws
    pilots = []
    for a in (90, 210, 330):
        ph = cyl_along([math.cos(math.radians(a)), math.sin(math.radians(a)), 0],
                       0.8, R - wall - 3.0, R)
        ph.apply_translation([0, 0, p["lip_h"] / 2.0])
        pilots.append(ph)
    # neck mount pad: a flat boss on the back pole with a socket for the head-mount stub
    pad = cylinder(radius=14.0, height=8.0, sections=64)        # face at z = -(R+5)
    pad.apply_translation([0, 0, -(R + 5.0) + 4.0])
    back = back.union(pad)
    stub_sock = cylinder(radius=6.3, height=8.0, sections=48)   # 8 mm deep socket
    stub_sock.apply_translation([0, 0, -(R + 5.0) + 4.0])
    # cable exit right next to the neck
    cable = cyl_along([0, -0.35, -1], 4.5, R - wall - 8, R + 8)
    back = difference(back, pilots + [stub_sock, cable, bowden] + bores(False))
    # 4 mic/vent holes on top of the back half
    vents = [cyl_along([0.15 * i, 0.75, -0.6], 1.3, R - wall - 2, R + 2) for i in (-2, -1, 1, 2)]
    back = difference(back, vents)

    # print orientation: flat faces on the bed
    front_p = front.copy()
    front_p.apply_transform(rot([1, 0, 0], 180))   # cut face down, eye up
    front_p.apply_translation([0, 0, -front_p.bounds[0][2]])
    back_p = back.copy()
    back_p.apply_translation([0, 0, -back_p.bounds[0][2]])  # lip up
    return front, back, front_p, back_p


def eye_bezel(p):
    """Tube that press-fits into the core bore.  Front to back: 2 mm lens lip (print it in
    white/clear so the ring glows through the slots), LED-ring pocket, the display glass,
    then a backplate with a square pocket that locates the 36.5 mm display PCB."""
    L = p["bezel_len"]
    tube = cylinder(radius=p["bezel_r"], height=L, sections=96)
    tube.apply_translation([0, 0, L / 2.0])
    window = cylinder(radius=p["bezel_window_r"], height=L + 20, sections=96)
    window.apply_translation([0, 0, L / 2.0])
    pocket = cylinder(radius=p["led_ring_r"], height=L, sections=96)
    pocket.apply_translation([0, 0, p["bezel_lip_t"] + L / 2.0])
    slots = []
    for i in range(8):
        s = box(extents=[3.0, 4.0, p["bezel_lip_t"] + 2])
        s.apply_translation([0, (p["bezel_window_r"] + p["led_ring_r"]) / 2.0, p["bezel_lip_t"] / 2.0])
        s.apply_transform(rot([0, 0, 1], i * 45 + 22.5))
        slots.append(s)
    # backplate: square-ish plate with corners trimmed to fit the sphere cavity
    plate = box(extents=[44, 44, 4]); plate.apply_translation([0, 0, L + 2])
    trim = cylinder(radius=28.5, height=6, sections=96); trim.apply_translation([0, 0, L + 2])
    plate = plate.intersection(trim)
    pcb = box(extents=[36.8, 36.8, 2.6]); pcb.apply_translation([0, 0, L + 1.3])
    through = cylinder(radius=15, height=10, sections=64); through.apply_translation([0, 0, L + 2])
    fpc = box(extents=[16, 8, 10]); fpc.apply_translation([0, -21, L + 2])
    m = union([tube.difference(window).difference(pocket), plate])
    m = difference(m, slots + [pcb, through, fpc, window])
    m.apply_translation([0, 0, -m.bounds[0][2]])
    return m


def arm(p):
    """Curved arm: pan-horn disc at the bottom, tilt-servo pocket at the top."""
    # centreline path in the y/z plane (x = 0)
    y0 = -p["half_w"] - 25.0                                        # under the low tips
    top_y = 0.0
    zc = p["arm_z"]
    ztop = p["tilt_pivot_z"] - 5.5          # centre of the tilt-servo block
    pts = []
    for y in np.linspace(y0, top_y - 4, 40):
        # vertical from the base, then an S-bend forward between y=-45 and y=-12 so the
        # lower-back fin can swing past when the head tilts nose-down
        s = min(max((y + 52.0) / 38.0, 0.0), 1.0)
        s = s * s * (3 - 2 * s)
        pts.append([0, y, zc + (ztop - zc) * s])
    pts = np.array(pts)
    seg = []
    for a, b in zip(pts[:-1], pts[1:]):
        d = b - a
        L = np.linalg.norm(d) + 0.6
        s = box(extents=[p["arm_w"], L, p["arm_d"]])
        s.apply_transform(align_z_to(d) @ rot([1, 0, 0], -90))
        s.apply_translation((a + b) / 2.0)
        seg.append(s)
    body = union(seg)
    # pan horn disc
    disc = cylinder(radius=18, height=6, sections=64)
    disc.apply_transform(rot([1, 0, 0], 90))
    disc.apply_translation([0, y0 + 3, zc])
    holes = [cyl_along([0, 1, 0], 3.0, y0 - 1, y0 + 8)]
    for a in range(0, 360, 90):
        hh = cyl_along([0, 1, 0], 1.1, y0 - 1, y0 + 8)
        hh.apply_translation([7 * math.cos(math.radians(a)), 0, 7 * math.sin(math.radians(a))])
        holes.append(hh)
    for hh in holes:
        hh.apply_translation([0, 0, zc])
    # tilt servo block at the top.  Servo shaft points +x (horn on the +x face),
    # body runs along z with the shaft 5.5 mm toward +z of the body centre,
    # mounting screws go in along x through the tabs.
    bz = p["tilt_pivot_z"] - 5.5
    blk = box(extents=[26, 30, 42])
    blk.apply_translation([0, top_y - 4, bz])
    slot = box(extents=[40, p["servo_body"][1], p["servo_body"][0]])
    slot.apply_translation([0, top_y - 4, bz])
    sholes = []
    for sz in (1, -1):
        sh = cyl_along([1, 0, 0], p["servo_hole_r"], -20, 20)
        sh.apply_translation([0, top_y - 4, bz + sz * p["servo_hole_spacing"] / 2.0])
        sholes.append(sh)
    m = union([body, disc, blk])
    m = difference(m, holes + [slot] + sholes)
    # cable channel down the back of the arm
    chan = box(extents=[8, abs(y0) + 40, 6])
    chan.apply_translation([0, (y0 + top_y) / 2.0, zc - p["arm_d"] / 2.0 + 2])
    m = m.difference(chan)
    # print orientation: lay on its side (x down) for strength along the arm
    m_p = m.copy()
    m_p.apply_transform(rot([0, 1, 0], 90))
    m_p.apply_translation(-m_p.bounds[0])
    return m, m_p, y0


def head_mount(p):
    """Bracket: horn plate on the +x face of the tilt servo, beam across the front of the
    servo block, and a round stub that plugs into the socket on the core's back pole."""
    pz = p["tilt_pivot_z"]
    y = -4.0                                    # servo block centre height
    plate = box(extents=[3, 24, 38])                # 2 mm horn gap off the block's +x face
    plate.apply_translation([16.5, y, pz + 7])
    horn_holes = []
    for dy, dz in ((0, 0), (0, 7), (0, -7), (7, 0), (-7, 0)):
        hh = cyl_along([1, 0, 0], 1.1, 12, 17)
        hh.apply_translation([0, y + dy, pz + dz])
        horn_holes.append(hh)
    beam_z = (pz - 5.5) + 21 + 4.0 + 3.5       # 4 mm in front of the servo block face
    beam = box(extents=[26, 8, 7])
    beam.apply_translation([5, y, beam_z])
    stub_far = -(p["core_r"] + 5.0) + 8.0 - 1.0    # bottom of the socket, minus clearance
    stub = cylinder(radius=6.0, height=stub_far - (beam_z - 3.5), sections=48)
    stub.apply_translation([0, y, (beam_z - 3.5 + stub_far) / 2.0])
    riser = box(extents=[12, 8 + abs(y), 7])   # brings the stub up to y=0 (core pole)
    riser.apply_translation([0, y / 2.0, beam_z])
    stub.apply_translation([0, -y, 0])          # stub is centred on the core pole (y=0)
    m = union([plate, beam, riser, stub])
    sheath = cylinder(radius=p["sheath_r"], height=80.0, sections=32)   # PTFE tube runs right through
    sheath.apply_translation([0, 0, beam_z - 20.0])
    m = difference(m, horn_holes + [sheath])
    m_p = m.copy()
    m_p.apply_transform(rot([0, 1, 0], -90))
    m_p.apply_translation(-m_p.bounds[0])
    return m, m_p


def base(p, arm_y0):
    """Hollow puck: Pi 4 standoffs, speaker grille, pan-servo pocket on the lid.

    Base frame: +z up, +y toward the BACK of the Ghost (world -z), x right.
    """
    R, H, w = p["base_r"], p["base_h"], p["base_wall"]
    servo_y = -(p["arm_z"] - p["base_center_z"])   # pan servo position on the lid
    shell = cylinder(radius=R, height=H, sections=128)
    shell.apply_translation([0, 0, H / 2.0])
    inner = cylinder(radius=R - w, height=H, sections=128)
    inner.apply_translation([0, 0, H / 2.0 + w])
    body = shell.difference(inner)
    # Pi 4 standoffs, board centred a little forward, 6 mm tall, M2.5 pilot holes
    px, py = p["pi_holes"]
    posts, pholes = [], []
    for sx in (-0.5, 0.5):
        for sy in (-0.5, 0.5):
            x, yy = sx * px, -8 + sy * py
            c = cylinder(radius=3.2, height=6, sections=32); c.apply_translation([x, yy, w + 3])
            hcyl = cylinder(radius=p["pi_hole_r"], height=12, sections=24); hcyl.apply_translation([x, yy, w + 3])
            posts.append(c); pholes.append(hcyl)
    body = union([body] + posts)
    # rear wall cutouts: power jack (8 mm) and a slot for a USB/HDMI pigtail
    jack = cyl_along([0, 1, 0], 4.2, R - 6, R + 6); jack.apply_translation([-28, 0, H / 2.0])
    usb = box(extents=[18, 12, 9]); usb.apply_translation([28, R, H / 2.0])
    # lid screw posts
    lposts, lholes = [], []
    for a in (45, 135, 225, 315):
        x, yy = (R - 7) * math.cos(math.radians(a)), (R - 7) * math.sin(math.radians(a))
        c = cylinder(radius=4.0, height=H - w, sections=32); c.apply_translation([x, yy, w + (H - w) / 2.0])
        hc = cylinder(radius=1.3, height=14, sections=24); hc.apply_translation([x, yy, H - 6])
        lposts.append(c); lholes.append(hc)
    body = union([body] + lposts)
    # vent slots in the floor under the Pi
    vents = []
    for i in range(-3, 4):
        v = box(extents=[40, 3, w + 2]); v.apply_translation([0, -8 + i * 6, w / 2.0]); vents.append(v)
    body = difference(body, pholes + [jack, usb] + vents + lholes)

    # ---- lid: 3 mm disc + hanging locating ring
    lid = cylinder(radius=R, height=3.0, sections=128)
    lid.apply_translation([0, 0, 1.5])
    ring_o = cylinder(radius=R - w - 0.3, height=3.0, sections=128); ring_o.apply_translation([0, 0, -1.5])
    ring_i = cylinder(radius=R - w - 2.3, height=5.0, sections=128); ring_i.apply_translation([0, 0, -1.5])
    lid = lid.union(ring_o.difference(ring_i))
    # pan servo pocket (shaft up, body long axis along y, screws along z)
    pocket = box(extents=[p["servo_body"][1], p["servo_body"][0], 20])
    pocket.apply_translation([0, servo_y, 0])
    shol = []
    for sy in (1, -1):
        sh = cylinder(radius=p["servo_hole_r"], height=20, sections=24)
        sh.apply_translation([0, servo_y + sy * p["servo_hole_spacing"] / 2.0, 0])
        shol.append(sh)
    # speaker grille (hex pattern) for a 40 mm speaker at the front-left
    gx0, gy0 = -34.0, -34.0
    grille = []
    for gy in range(-4, 5):
        for gx in range(-4, 5):
            x = gx0 + gx * 5.0 + (gy % 2) * 2.5
            yy = gy0 + gy * 4.4
            if (x - gx0) ** 2 + (yy - gy0) ** 2 <= 17 ** 2:
                g = cylinder(radius=1.5, height=20, sections=12); g.apply_translation([x, yy, 0]); grille.append(g)
    # cable slot beside the servo + lid screw holes + mic hole
    cslot = box(extents=[10, 8, 20]); cslot.apply_translation([16, servo_y, 0])
    lidholes = []
    for a in (45, 135, 225, 315):
        x, yy = (R - 7) * math.cos(math.radians(a)), (R - 7) * math.sin(math.radians(a))
        c = cylinder(radius=1.7, height=20, sections=24); c.apply_translation([x, yy, 0]); lidholes.append(c)
    lid = difference(lid, [pocket, cslot] + shol + grille + lidholes)
    lid.apply_translation([0, 0, -lid.bounds[0][2]])
    return body, lid


# ---------------------------------------------------------------------------
# Assembly preview
# ---------------------------------------------------------------------------
def preview(parts, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = plt.figure(figsize=(18, 6), facecolor="#0b0d12")
    views = [(18, -50, "3/4 view"), (0, -90, "front"), (0, 0, "side"), (90, -90, "top")]
    for i, (elev, azim, title) in enumerate(views):
        ax = fig.add_subplot(1, 4, i + 1, projection="3d", facecolor="#0b0d12")
        allpts = []
        for mesh, color in parts:
            tri = mesh.vertices[mesh.faces]
            # matplotlib is z-up; our world is y-up, z-front -> remap (x, -z, y)
            tri = np.stack([tri[..., 0], -tri[..., 2], tri[..., 1]], axis=-1)
            allpts.append(tri.reshape(-1, 3))
            pc = Poly3DCollection(tri, facecolors=color, edgecolors="none", linewidths=0)
            pc.set_alpha(1.0)
            ax.add_collection3d(pc)
        allpts = np.vstack(allpts)
        lo, hi = allpts.min(0), allpts.max(0)
        c = (lo + hi) / 2
        r = (hi - lo).max() / 2
        ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
        ax.set_box_aspect([1, 1, 1])
        ax.view_init(elev=elev, azim=azim)
        ax.set_axis_off()
        ax.set_title(title, color="#9fb3c8")
    plt.tight_layout()
    plt.savefig(path, dpi=110, facecolor=fig.get_facecolor())
    print(f"  preview -> {path}")


def parts_preview(parts, path):
    """One shaded thumbnail per STL, in print orientation."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = plt.figure(figsize=(16, 12), facecolor="#0b0d12")
    light = unit([0.3, -0.5, 0.8])
    for i, (n, m) in enumerate(parts.items()):
        ax = fig.add_subplot(3, 4, i + 1, projection="3d", facecolor="#0b0d12")
        shade = 0.35 + 0.65 * np.clip(m.face_normals @ light, 0, 1)
        cols = np.stack([shade * 0.8, shade * 0.82, shade * 0.9, np.ones_like(shade)], axis=1)
        ax.add_collection3d(Poly3DCollection(m.vertices[m.faces], facecolors=cols, edgecolors="none"))
        lo, hi = m.bounds
        c, r = (lo + hi) / 2, (hi - lo).max() / 2
        ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
        ax.set_box_aspect([1, 1, 1]); ax.view_init(elev=30, azim=-50); ax.set_axis_off()
        e = m.extents
        ax.set_title(f"{n}.stl   {e[0]:.0f} x {e[1]:.0f} x {e[2]:.0f} mm", color="#9fb3c8", fontsize=10)
    plt.tight_layout()
    plt.savefig(path, dpi=100, facecolor=fig.get_facecolor())
    print(f"  parts   -> {path}")


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "stl"))
    ap.add_argument("--scale", type=float, default=1.0, help="uniform scale (fins/core only)")
    ap.add_argument("--no-preview", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    p = dict(P)
    if args.scale != 1.0:
        for k in ("half_w", "half_d", "tip_w", "inner_back", "core_r"):
            p[k] *= args.scale
        p["inner_front"] = tuple(v * args.scale for v in p["inner_front"])
        p["inner_diag"] = tuple(v * args.scale for v in p["inner_diag"])

    print("Generating parts...")
    parts = {}
    parts["fin_x8"] = check(fin_printable(p), "fin_x8")
    front, back, front_p, back_p = core_halves(p)
    parts["core_front"] = check(front_p, "core_front")
    parts["core_back"] = check(back_p, "core_back")
    parts["eye_bezel"] = check(eye_bezel(p), "eye_bezel")
    parts["slider_pin_x8"] = check(slider_pin(p), "slider_pin_x8")
    parts["spider_ring"] = check(spider_ring(p), "spider_ring")
    parts["spool"] = check(spool(p), "spool")
    parts["shell_servo_mount"] = check(shell_servo_mount(p), "shell_servo_mount")
    arm_m, arm_p, y0 = arm(p)
    parts["arm"] = check(arm_p, "arm")
    hm, hm_p = head_mount(p)
    parts["head_mount"] = check(hm_p, "head_mount")
    base_m, lid_m = base(p, y0)
    parts["base"] = check(base_m, "base")
    parts["base_lid"] = check(lid_m, "base_lid")

    # collision check between neighbouring fins and fin/core
    core_plus_bezel = front.union(back)
    bez = eye_bezel(p).copy()
    bez.apply_transform(rot([1, 0, 0], 180)); bez.apply_translation([0, 0, p["core_r"] - 8.5 + 13.0])
    fins_open = fins_in_place(p, 1.0)
    fins = fins_in_place(p, 0.0)
    for label, fs in (("closed", fins), ("open", fins_open)):
        worst_ff = 0.0
        for i in range(8):
            for j in range(i + 1, 8):
                inter = fs[i].intersection(fs[j])
                worst_ff = max(worst_ff, 0.0 if inter.is_empty else inter.volume)
        worst_fc = 0.0
        for f in fs:
            for other in (core_plus_bezel, bez):
                inter = f.intersection(other)
                worst_fc = max(worst_fc, 0.0 if inter.is_empty else inter.volume)
        print(f"  shell {label:6s}: piece/piece overlap {worst_ff:.2f} mm3, piece/core+bezel overlap {worst_fc:.2f} mm3 (both should be 0)")
    print(f"  shell travel {p['shell_travel']:.0f} mm; closed gap {p['closed_gap']:.0f} mm, open gap {p['closed_gap'] + p['shell_travel']:.0f} mm")
    z0, z1, Lf, Lb, cap_o, cap_c = ring_travel(p)
    print(f"  spider ring: open at z={z0:.1f}, closed at z={z1:.1f} (wire pull {z0 - z1:.1f} mm); "
          f"tendons: front 4 = {Lf:.1f} mm, back 4 = {Lb:.1f} mm (cap centre to ring hole)")
    # ring vs closed back caps clearance
    ring = cylinder(radius=p["ring_r"], height=p["ring_t"], sections=48); ring.apply_translation([0, 0, z1])
    clash = 0.0
    for dd in peg_dirs(p):
        cap = cylinder(radius=p["pin_cap_r"], height=p["pin_cap_t"], sections=32)
        cap.apply_transform(align_z_to(dd)); cap.apply_translation(dd * cap_c)
        i = cap.intersection(ring); clash = max(clash, 0.0 if i.is_empty else i.volume)
        for other in (front, back):
            i = cap.intersection(other); clash = max(clash, 0.0 if i.is_empty else i.volume)
    print(f"  ring/cap/core clash at closed: {clash:.1f} mm3 (should be 0); cavity floor at z={-(p['core_r'] - p['core_wall']):.0f}")
    # tilt sweep: head + mount rotate about the tilt pivot; nothing may hit the arm
    sweep = {}
    for deg in (-20, -15, 15, 20):
        Rm = rotation_matrix(math.radians(deg), [1, 0, 0], [0, -4, p["tilt_pivot_z"]])
        worst = 0.0
        for m in fins + fins_open + [hm]:
            mm = m.copy(); mm.apply_transform(Rm)
            i = mm.intersection(arm_m)
            worst = max(worst, 0.0 if i.is_empty else i.volume)
        sweep[deg] = worst
    print("  tilt sweep, overlap with the arm (mm3): " +
          "  ".join(f"{d:+d}deg={v:.1f}" for d, v in sweep.items()) + "   (software clamps to +-15)")
    for label, fs in (("closed", fins), ("open", fins_open)):
        span = np.ptp(np.vstack([f.vertices for f in fs]), axis=0)
        print(f"  assembled Ghost {label}: {span[0]:.0f} wide x {span[1]:.0f} tall x {span[2]:.0f} deep")

    for name, m in parts.items():
        path = os.path.join(args.out, f"{name}.stl")
        m.export(path)
    print(f"  wrote {len(parts)} STL files to {args.out}")

    if not args.no_preview:
        silver, dark, blue, stand = "#c9ced6", "#22252b", "#4fc3ff", "#3a3f48"
        eye = cylinder(radius=p["bezel_window_r"], height=4, sections=64)
        eye.apply_translation([0, 0, p["core_r"] - 4])
        # stand in world coords: base puck lies in the x/z plane under the ghost
        base_w = base_m.copy()
        base_w.apply_transform(rot([1, 0, 0], -90))
        base_w.apply_translation([0, y0 - p["base_h"], p["base_center_z"]])
        lid_w = lid_m.copy()
        lid_w.apply_transform(rot([1, 0, 0], -90))
        lid_w.apply_translation([0, y0 - 3, p["base_center_z"]])
        scene = [(f, silver) for f in fins] + [(front, dark), (back, dark), (eye, blue),
                                               (arm_m, stand), (hm, stand), (base_w, stand), (lid_w, stand)]
        preview(scene, os.path.join(os.path.dirname(args.out), "preview.png"))
        scene_open = [(f, silver) for f in fins_open] + [(front, dark), (back, dark), (eye, blue),
                                                         (arm_m, stand), (hm, stand), (base_w, stand), (lid_w, stand)]
        preview(scene_open, os.path.join(os.path.dirname(args.out), "preview_open.png"))
        parts_preview(parts, os.path.join(os.path.dirname(args.out), "parts.png"))


if __name__ == "__main__":
    sys.exit(main())
