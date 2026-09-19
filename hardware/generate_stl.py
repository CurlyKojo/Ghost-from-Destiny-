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
    # Shell (the 8 silver fins) -------------------------------------------
    cube_edge=110.0,      # the 8 fin tips sit on the corners of this cube
    fin_leg=48.0,         # how far each fin's front plate runs along the cube edges
    fin_plate_t=7.0,      # thickness of the flat front plate
    fin_edge_bevel=2.0,   # bevel on the plate's back edges
    fin_tail_end=43.0,    # distance from centre where the fin's inner (tail) face sits
    fin_tail_radius=20.0, # circumradius of the tail-end triangle (controls the taper)
    fin_socket_r=5.4,     # socket hole in the tail for the core peg
    fin_socket_depth=8.0,
    # Core (black sphere) ---------------------------------------------------
    core_r=37.0,
    core_wall=3.0,
    peg_r=5.0,
    peg_reach=6.0,        # how far the peg goes into the fin socket
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
    base_h=32.0,
    base_wall=2.5,
    base_r=80.0,
    base_center_z=-30.0,  # base puck centre sits this far behind the core centre
    arm_z=-92.0,          # lower arm centreline sits this far behind the core centre
    arm_w=16.0,           # arm cross-section (x)
    arm_d=24.0,           # arm cross-section (z)
    tilt_pivot_z=-66.0,   # tilt axis (parallel to x) sits here behind the core
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


# The 8 fin axes in the world frame: tips point up/down/left/right, front & back.
FIN_DIRS = [unit(v) for v in (
    (0, math.sqrt(2), 1), (0, -math.sqrt(2), 1), (math.sqrt(2), 0, 1), (-math.sqrt(2), 0, 1),
    (0, math.sqrt(2), -1), (0, -math.sqrt(2), -1), (math.sqrt(2), 0, -1), (-math.sqrt(2), 0, -1),
)]
# Rotation taking the cube frame (corners at +-1,+-1,+-1) to the world frame.
CUBE_TO_WORLD = rot([0, 0, 1], 45)


# ---------------------------------------------------------------------------
# Parts
# ---------------------------------------------------------------------------
def fin(p):
    """One shell fin, built on the (+,+,+) cube corner (cube frame, before the 45 deg spin).

    Shape: a flat right-triangle FRONT PLATE lying in the cube's front face (this is what
    tiles the diamond you see from the front), `fin_plate_t` thick, tapering back to a small
    triangular tail that plugs onto the core.  From the side and top the fins read as an X,
    like the reference sheet.
    """
    h = p["cube_edge"] / 2.0
    d = p["fin_leg"]
    t = p["fin_plate_t"]
    front = np.array([[h, h, h], [h - d, h, h], [h, h - d, h]])
    c2 = front.mean(axis=0)
    back = np.array([c2 + (v - c2) * (1 - p["fin_edge_bevel"] / d) for v in front])
    back[:, 2] = h - t
    axis = unit([1, 1, 1])
    tail_c = axis * p["fin_tail_end"]
    # tail triangle: two vertices under the plate's outer corners (120 deg apart around
    # the axis) and the third pointing back into the cube.  The apex itself sits ON the
    # axis, so it cannot be used to derive a direction.
    u1 = unit([-2, 1, 1]); u2 = unit([1, -2, 1]); u3 = unit([1, 1, -2])
    tail = np.array([tail_c + u * p["fin_tail_radius"] for u in (u1, u2, u3)])
    pts = np.vstack([front, back, tail])
    m = trimesh.points.PointCloud(pts).convex_hull

    # socket for the core peg, bored in from the tail face
    sock = cyl_along(axis, p["fin_socket_r"],
                     p["fin_tail_end"] - 1.0,
                     p["fin_tail_end"] + p["fin_socket_depth"])
    return m.difference(sock)          # still sitting on the +++ cube corner


def fin_printable(p):
    """The fin for printing: flat front plate on the bed, tail pointing up."""
    m = fin(p)
    m.apply_transform(rot([1, 0, 0], 180))                     # front face (z=h) -> down
    m.apply_translation(-m.bounds[0])
    return m


def fins_in_place(p):
    """All 8 fins exactly placed on the assembled Ghost (world frame)."""
    out = []
    for sx in (1, -1):
        for sy in (1, -1):
            for sz in (1, -1):
                m = fin(p)
                # mirror the +++ fin onto the other corners; trimesh fixes the winding
                m.apply_transform(np.diag([sx, sy, sz, 1.0]))
                m.apply_transform(CUBE_TO_WORLD)
                out.append(m)
    return out


def core_halves(p):
    """Front and back hemispheres of the core, with pegs, eye bore, lip."""
    R, wall = p["core_r"], p["core_wall"]
    sphere = icosphere(subdivisions=4, radius=R)
    cavity = icosphere(subdivisions=4, radius=R - wall)
    peg_end = p["fin_tail_end"] + p["peg_reach"]

    def pegs(front: bool):
        dirs = [d for d in FIN_DIRS if (d[2] > 0) == front]
        return [cyl_along(d, p["peg_r"], R - wall - 1.0, peg_end) for d in dirs]

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
    front = difference(front, [cavity, bore] + screw_holes)

    # ---- back half
    back = union([sphere] + pegs(False))
    back = back.intersection(back_keep)
    back = back.difference(cavity)
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
    pad = cylinder(radius=14.0, height=6.0, sections=64)        # face at z = -(R+2)
    pad.apply_translation([0, 0, -(R + 2.0) + 3.0])
    back = back.union(pad)
    stub_sock = cylinder(radius=6.3, height=12.0, sections=48)  # 12 mm deep socket
    stub_sock.apply_translation([0, 0, -(R + 2.0) + 6.0])
    # cable exit right next to the neck
    cable = cyl_along([0, -0.35, -1], 4.5, R - wall - 8, R + 8)
    back = difference(back, pilots + [stub_sock, cable])
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
    y0 = -(p["cube_edge"] / 2.0 * math.sqrt(3) * math.sqrt(2.0 / 3.0)) - 25.0  # under the low tips
    top_y = 0.0
    zc = p["arm_z"]
    ztop = p["tilt_pivot_z"] - 5.5          # centre of the tilt-servo block
    pts = []
    for y in np.linspace(y0, top_y - 4, 40):
        # vertical from the base, then an S-bend forward between y=-45 and y=-12 so the
        # lower-back fin can swing past when the head tilts nose-down
        s = min(max((y + 45.0) / 33.0, 0.0), 1.0)
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
    stub_far = -(p["core_r"] + 2.0) + 12.0 - 1.0   # bottom of the socket, minus clearance
    stub = cylinder(radius=6.0, height=stub_far - (beam_z - 3.5), sections=48)
    stub.apply_translation([0, y, (beam_z - 3.5 + stub_far) / 2.0])
    riser = box(extents=[12, 8 + abs(y), 7])   # brings the stub up to y=0 (core pole)
    riser.apply_translation([0, y / 2.0, beam_z])
    stub.apply_translation([0, -y, 0])          # stub is centred on the core pole (y=0)
    m = union([plate, beam, riser, stub])
    m = difference(m, horn_holes)
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

    fig = plt.figure(figsize=(16, 8), facecolor="#0b0d12")
    light = unit([0.3, -0.5, 0.8])
    for i, (n, m) in enumerate(parts.items()):
        ax = fig.add_subplot(2, 4, i + 1, projection="3d", facecolor="#0b0d12")
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
        for k in ("cube_edge", "fin_leg", "fin_tail_end", "fin_tail_radius", "core_r"):
            p[k] *= args.scale

    print("Generating parts...")
    parts = {}
    parts["fin_x8"] = check(fin_printable(p), "fin_x8")
    front, back, front_p, back_p = core_halves(p)
    parts["core_front"] = check(front_p, "core_front")
    parts["core_back"] = check(back_p, "core_back")
    parts["eye_bezel"] = check(eye_bezel(p), "eye_bezel")
    arm_m, arm_p, y0 = arm(p)
    parts["arm"] = check(arm_p, "arm")
    hm, hm_p = head_mount(p)
    parts["head_mount"] = check(hm_p, "head_mount")
    base_m, lid_m = base(p, y0)
    parts["base"] = check(base_m, "base")
    parts["base_lid"] = check(lid_m, "base_lid")

    # collision check between neighbouring fins and fin/core
    fins = fins_in_place(p)
    inter = fins[0].intersection(fins[1])
    core_sphere = icosphere(subdivisions=3, radius=p["core_r"])
    inter2 = fins[0].intersection(core_sphere)
    print(f"  fin/fin overlap volume: {inter.volume if not inter.is_empty else 0:.2f} mm3 "
          f"(should be 0)   fin/core overlap: {inter2.volume if not inter2.is_empty else 0:.2f} mm3")
    # tilt sweep: head + mount rotate about the tilt pivot; nothing may hit the arm
    worst = 0.0
    for deg in (-20, -15, 15, 20):
        Rm = rotation_matrix(math.radians(deg), [1, 0, 0], [0, -4, p["tilt_pivot_z"]])
        for m in fins + [hm]:
            mm = m.copy(); mm.apply_transform(Rm)
            i = mm.intersection(arm_m)
            worst = max(worst, 0.0 if i.is_empty else i.volume)
    print(f"  tilt sweep +-20 deg: worst overlap with the arm {worst:.1f} mm3 (should be 0)")
    tips = np.array([f.vertices[np.argmax(np.linalg.norm(f.vertices, axis=1))] for f in fins])
    span = np.ptp(tips, axis=0)
    print(f"  assembled Ghost: {span[0]:.0f} wide x {span[1]:.0f} tall x {span[2]:.0f} deep (tip to tip)")

    for name, m in parts.items():
        path = os.path.join(args.out, f"{name}.stl")
        m.export(path)
    print(f"  wrote {len(parts)} STL files to {args.out}")

    if not args.no_preview:
        silver, dark, blue, stand = "#c9ced6", "#22252b", "#4fc3ff", "#3a3f48"
        eye = cylinder(radius=p["bezel_window_r"], height=4, sections=64)
        eye.apply_translation([0, 0, p["core_r"] - 6])
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
        parts_preview(parts, os.path.join(os.path.dirname(args.out), "parts.png"))


if __name__ == "__main__":
    sys.exit(main())
