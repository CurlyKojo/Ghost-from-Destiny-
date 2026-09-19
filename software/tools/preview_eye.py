#!/usr/bin/env python3
"""Render the eye in every mood to a contact sheet (no hardware needed).

    python tools/preview_eye.py            -> docs/eye_moods.png
    python tools/preview_eye.py --live     -> opens a window and animates (needs tkinter)
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("GHOST_DISPLAY", "none")

from PIL import Image, ImageDraw  # noqa: E402

from ghost.eye import MOODS, EyeRenderer, EyeState  # noqa: E402


def sheet(path):
    moods = list(MOODS)
    cols, size, pad = 7, 240, 12
    rows = (len(moods) + cols - 1) // cols
    out = Image.new("RGB", (cols * (size + pad) + pad, rows * (size + pad + 20) + pad), (11, 13, 18))
    d = ImageDraw.Draw(out)
    for i, m in enumerate(moods):
        r = EyeRenderer()
        st = EyeState(mood=m, level=0.5 if m == "speaking" else 0.0, listening_level=0.6 if m == "listening" else 0.0)
        r._t0 -= 0.7
        for _ in range(30):                     # let the easing settle
            img = r.frame(st)
        x, y = pad + (i % cols) * (size + pad), pad + (i // cols) * (size + pad + 20)
        # round mask, like the real display
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
        out.paste(img, (x, y), mask)
        d.text((x + 8, y + size + 4), m, fill=(160, 180, 200))
    out.save(path)
    print("wrote", path)


def live():
    import tkinter as tk
    from PIL import ImageTk
    r = EyeRenderer(); st = EyeState()
    root = tk.Tk(); root.title("Ghost eye")
    lbl = tk.Label(root); lbl.pack()
    moods = list(MOODS); idx = [0]
    def key(e):
        idx[0] = (idx[0] + 1) % len(moods); st.mood = moods[idx[0]]; root.title(f"Ghost eye - {st.mood}")
    root.bind("<space>", key)
    def tick():
        st.level = abs(__import__("math").sin(time.time() * 9)) if st.mood == "speaking" else 0
        im = ImageTk.PhotoImage(r.frame(st)); lbl.configure(image=im); lbl.image = im
        root.after(40, tick)
    tick(); print("space = next mood"); root.mainloop()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--live", action="store_true")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "..", "docs", "eye_moods.png"))
    a = ap.parse_args()
    live() if a.live else sheet(a.out)
