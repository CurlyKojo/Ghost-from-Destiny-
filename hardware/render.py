#!/usr/bin/env python3
"""
Shaded renders of the assembled Ghost, no GPU needed.

    python3 hardware/render.py            -> docs/renders/hero.png, hero_open.png, turnaround.png

A small numpy z-buffer rasterizer: perspective camera, smooth normals, three lights with
Blinn-Phong highlights, metallic silver pieces with the gold tips from the reference sheet,
an emissive eye with bloom, and a soft floor shadow.  It takes ~1 minute per image.
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(__file__))
import generate_stl as g  # noqa: E402
from generate_stl import cylinder, rot  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "renders")


# ---------------------------------------------------------------------------
# materials: (albedo rgb 0..1, specular 0..1, shininess, emissive rgb)
# ---------------------------------------------------------------------------
SILVER = (np.array([0.80, 0.82, 0.86]), 0.9, 60.0, None)
GOLD = (np.array([0.78, 0.58, 0.25]), 0.9, 40.0, None)
DARK = (np.array([0.10, 0.11, 0.13]), 0.5, 30.0, None)
BEZEL = (np.array([0.16, 0.18, 0.22]), 0.6, 40.0, None)
STAND = (np.array([0.20, 0.22, 0.25]), 0.25, 12.0, None)
EYE = (np.array([0.35, 0.75, 1.00]), 0.0, 1.0, np.array([0.45, 0.85, 1.20]))
EYE_CORE = (np.array([1.0, 1.0, 1.0]), 0.0, 1.0, np.array([1.2, 1.3, 1.4]))
RING = (np.array([0.3, 0.6, 1.0]), 0.0, 1.0, np.array([0.25, 0.55, 0.95]))


def look_at(eye, target, up=(0, 1, 0)):
    eye, target, up = map(lambda v: np.asarray(v, float), (eye, target, up))
    f = target - eye; f /= np.linalg.norm(f)
    r = np.cross(f, up); r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return eye, r, u, f


class Raster:
    def __init__(self, w, h, fov_deg=28.0, ss=2):
        self.w, self.h, self.ss = w * ss, h * ss, ss
        self.f = 0.5 * self.h / math.tan(math.radians(fov_deg) / 2)
        self.color = np.zeros((self.h, self.w, 3), np.float32)
        self.emis = np.zeros((self.h, self.w, 3), np.float32)
        self.depth = np.full((self.h, self.w), np.inf, np.float32)
        self.lights = []           # (direction toward light, colour, intensity)

    def set_camera(self, eye, target):
        self.eye, self.r, self.u, self.fwd = look_at(eye, target)

    def project(self, pts):
        d = pts - self.eye
        x, y, z = d @ self.r, d @ self.u, d @ self.fwd
        sx = self.w / 2 + self.f * x / z
        sy = self.h / 2 - self.f * y / z
        return sx, sy, z

    def draw(self, mesh, material, vertex_colors=None, smooth=True, tip_gold=None):
        """tip_gold=(tip_radius, cap_length): paint pixels within cap_length of the tip gold."""
        albedo, spec, shin, emis = material
        V = np.asarray(mesh.vertices, float)
        F = np.asarray(mesh.faces)
        N = np.asarray(mesh.vertex_normals if smooth else mesh.face_normals, float)
        sx, sy, z = self.project(V)
        cols = vertex_colors if vertex_colors is not None else np.tile(albedo, (len(V), 1))
        # back-face + off-screen culling
        fn = np.asarray(mesh.face_normals)
        fc = V[F].mean(axis=1)
        view = self.eye - fc
        front = np.einsum("ij,ij->i", fn, view) > 0
        for fi in np.nonzero(front)[0]:
            i0, i1, i2 = F[fi]
            X = np.array([sx[i0], sx[i1], sx[i2]]); Y = np.array([sy[i0], sy[i1], sy[i2]])
            Z = np.array([z[i0], z[i1], z[i2]])
            if Z.min() <= 0.1:
                continue
            x0, x1 = int(max(0, X.min())), int(min(self.w - 1, X.max()) + 1)
            y0, y1 = int(max(0, Y.min())), int(min(self.h - 1, Y.max()) + 1)
            if x1 <= x0 or y1 <= y0:
                continue
            px, py = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
            det = (X[1] - X[0]) * (Y[2] - Y[0]) - (X[2] - X[0]) * (Y[1] - Y[0])
            if abs(det) < 1e-9:
                continue
            l1 = ((X[1] - X[0]) * (py - Y[0]) - (px - X[0]) * (Y[1] - Y[0])) / det  # weight of v2
            l2 = ((px - X[0]) * (Y[2] - Y[0]) - (X[2] - X[0]) * (py - Y[0])) / det  # weight of v1
            l0 = 1 - l1 - l2
            inside = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
            if not inside.any():
                continue
            # perspective-correct interpolation of depth
            invz = l0 / Z[0] + l2 / Z[1] + l1 / Z[2]
            zz = 1.0 / np.where(invz == 0, 1e-9, invz)
            sub = self.depth[y0:y1, x0:x1]
            upd = inside & (zz < sub)
            if not upd.any():
                continue
            w0, w1, w2 = (l0 / Z[0]) * zz, (l2 / Z[1]) * zz, (l1 / Z[2]) * zz
            if smooth:
                n = w0[..., None] * N[i0] + w1[..., None] * N[i1] + w2[..., None] * N[i2]
            else:
                n = np.broadcast_to(fn[fi], w0.shape + (3,))
            n = n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-9)
            c = w0[..., None] * cols[i0] + w1[..., None] * cols[i1] + w2[..., None] * cols[i2]
            # world position for the view vector (and the gold caps)
            P = w0[..., None] * V[i0] + w1[..., None] * V[i1] + w2[..., None] * V[i2]
            if tip_gold is not None:
                k = np.clip((np.linalg.norm(P, axis=-1) - (tip_gold[0] - tip_gold[1])) / 2.0, 0, 1)[..., None]
                c = c * (1 - k) + GOLD[0] * k
            v = self.eye - P; v /= np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)
            shade = 0.10 * c                                        # ambient
            for ldir, lcol, lint in self.lights:
                ndl = np.clip(np.einsum("...k,k->...", n, ldir), 0, 1)
                hv = v + ldir; hv /= np.maximum(np.linalg.norm(hv, axis=-1, keepdims=True), 1e-9)
                ndh = np.clip(np.einsum("...k,...k->...", n, hv), 0, 1)
                shade = shade + c * (ndl * lint)[..., None] * lcol + spec * (ndh ** shin * lint)[..., None] * lcol
            # fresnel-ish rim for the metal
            rim = (1 - np.clip(np.einsum("...k,...k->...", n, v), 0, 1)) ** 3
            shade = shade + (0.35 * spec * rim)[..., None] * np.array([0.6, 0.7, 0.9])
            self.color[y0:y1, x0:x1][upd] = shade[upd]
            self.depth[y0:y1, x0:x1][upd] = zz[upd]
            self.emis[y0:y1, x0:x1][upd] = emis if emis is not None else 0.0

    def finish(self, bg_top=(0.10, 0.11, 0.14), bg_bot=(0.02, 0.02, 0.03), floor_y=None, floor_shadow=None):
        h, w = self.h, self.w
        t = np.linspace(0, 1, h)[:, None, None]
        bg = np.array(bg_top) * (1 - t) + np.array(bg_bot) * t
        bg = np.broadcast_to(bg, (h, w, 3)).copy()
        # soft shadow ellipse on the floor
        if floor_shadow is not None:
            cx, cy, rx, ry, k = floor_shadow
            yy, xx = np.mgrid[0:h, 0:w]
            d = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
            bg *= (1 - k * np.exp(-d * 2.2))[..., None]
        img = np.where(np.isinf(self.depth)[..., None], bg, self.color)
        # bloom from emissive surfaces
        e = Image.fromarray((np.clip(self.emis, 0, 1) * 255).astype(np.uint8))
        e = e.filter(ImageFilter.GaussianBlur(self.ss * 18))
        img = img + np.asarray(e).astype(np.float32) / 255.0 * 0.9 + self.emis * 0.6
        # tone map + gamma
        img = img / (1 + img * 0.35)
        img = np.clip(img, 0, 1) ** (1 / 2.05)
        out = Image.fromarray((img * 255).astype(np.uint8))
        return out.resize((w // self.ss, h // self.ss), Image.LANCZOS)


# ---------------------------------------------------------------------------
def scene_parts(p, open_frac):
    """(mesh, material, vertex_colors) for everything in the assembled Ghost."""
    fins = g.fins_in_place(p, open_frac)
    front, back, _, _ = g.core_halves(p)
    bez = g.eye_bezel(p); bez.apply_transform(rot([1, 0, 0], 180)); bez.apply_translation([0, 0, p["core_r"] - 8.5 + 13.0])
    eye = cylinder(radius=p["bezel_window_r"] - 0.5, height=2, sections=96); eye.apply_translation([0, 0, p["core_r"] + 1.5])
    eye_core = cylinder(radius=6.0, height=2.2, sections=48); eye_core.apply_translation([0, 0, p["core_r"] + 1.6])
    ring = cylinder(radius=p["bezel_window_r"] + 3.2, height=1.4, sections=96).difference(
        cylinder(radius=p["bezel_window_r"] + 0.8, height=3, sections=96))
    ring.apply_translation([0, 0, p["core_r"] + 2.6])
    arm_m, _, y0 = g.arm(p); hm, _ = g.head_mount(p)
    base_m, lid_m = g.base(p, y0)
    base_w = base_m.copy(); base_w.apply_transform(rot([1, 0, 0], -90)); base_w.apply_translation([0, y0 - p["base_h"], p["base_center_z"]])
    lid_w = lid_m.copy(); lid_w.apply_transform(rot([1, 0, 0], -90)); lid_w.apply_translation([0, y0 - 3, p["base_center_z"]])

    parts = []
    for f in fins:
        # small gold caps on the tips, like the sheet (painted per pixel by distance from the tip)
        tip_r = np.linalg.norm(f.vertices, axis=1).max()
        parts.append((f, SILVER, None, False, (tip_r, 11.0)))
    parts += [(front, DARK, None, True, None), (back, DARK, None, True, None), (bez, BEZEL, None, False, None),
              (eye, EYE, None, False, None), (eye_core, EYE_CORE, None, False, None), (ring, RING, None, False, None),
              (arm_m, STAND, None, False, None), (hm, STAND, None, False, None),
              (base_w, STAND, None, True, None), (lid_w, STAND, None, False, None)]
    floor_y = y0 - p["base_h"]
    return parts, floor_y


def render_view(p, open_frac, eye_pos, target, w=1400, h=1050, fov=26.0, shadow=True):
    r = Raster(w, h, fov)
    r.set_camera(eye_pos, target)
    r.lights = [
        (g.unit([-0.5, 0.8, 0.6]), np.array([1.0, 0.98, 0.95]), 1.15),   # key: upper left front
        (g.unit([0.8, 0.3, 0.4]), np.array([0.7, 0.8, 1.0]), 0.45),      # fill: right, cool
        (g.unit([0.2, 0.4, -1.0]), np.array([0.8, 0.9, 1.0]), 0.6),      # rim: from behind
    ]
    parts, floor_y = scene_parts(p, open_frac)
    for mesh, mat, vc, smooth, gold in parts:
        r.draw(mesh, mat, vc, smooth=smooth, tip_gold=gold)
    fs = None
    if shadow:
        sx, sy, _ = r.project(np.array([[0.0, floor_y, p["base_center_z"]]]))
        fs = (float(sx[0]), float(sy[0]) + r.h * 0.03, r.w * 0.30, r.h * 0.055, 0.7)
    return r.finish(floor_shadow=fs)


def main():
    os.makedirs(OUT, exist_ok=True)
    p = dict(g.P)
    target = (0, -20, -10)
    hero_cam = (330, 150, 420)
    print("hero (closed)..."); render_view(p, 0.0, hero_cam, target).save(os.path.join(OUT, "hero.png"))
    print("hero (open)...");   render_view(p, 1.0, hero_cam, target).save(os.path.join(OUT, "hero_open.png"))
    print("turnaround...")
    views = [("front", (0, 40, 560)), ("three-quarter", (400, 120, 400)),
             ("side", (560, 40, 0)), ("back three-quarter", (-380, 160, -420))]
    tiles = []
    for name, cam in views:
        tiles.append((name, render_view(p, 0.0, cam, (0, -15, -10), w=700, h=560, fov=24.0)))
    W, H = 700, 560
    sheet = Image.new("RGB", (2 * W, 2 * H))
    from PIL import ImageDraw
    d = ImageDraw.Draw(sheet)
    for i, (name, im) in enumerate(tiles):
        x, y = (i % 2) * W, (i // 2) * H
        sheet.paste(im, (x, y)); d.text((x + 16, y + 12), name, fill=(170, 185, 200))
    sheet.save(os.path.join(OUT, "turnaround.png"))
    print("done ->", OUT)


if __name__ == "__main__":
    main()
