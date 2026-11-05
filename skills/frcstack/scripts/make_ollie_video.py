"""
make_ollie_video.py -- assemble the OLLIE simulation demo MP4 from the per-mode frame dumps.

Usage:  python make_ollie_video.py SIM_DIR OUT_MP4

Reads SIM_DIR/frames_{walk,skate,crawl}.npy + sim-log.json, adds a title card, a card before each
mode with the measured numbers, a caption bar on every frame, and an honest end card.
"""
import json
import sys
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FPS = 30
W, H = 1280, 720
BG = (250, 249, 246)
INK = (42, 45, 51)
ORANGE = (255, 107, 44)
GRAY = (138, 143, 152)


def font(size, bold=False):
    for name in (("segoeuib.ttf" if bold else "segoeui.ttf"), ("arialbd.ttf" if bold else "arial.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def card(lines, seconds=2.5):
    """lines: [(text, size, color, bold)]"""
    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)
    total = sum(s + 18 for _, s, _, _ in lines)
    y = (H - total) // 2
    for text, size, col, bold in lines:
        f = font(size, bold)
        w = dr.textlength(text, font=f)
        dr.text(((W - w) / 2, y), text, font=f, fill=col)
        y += size + 18
    dr.rectangle([W / 2 - 60, y + 10, W / 2 + 60, y + 16], fill=ORANGE)
    frame = np.asarray(img)
    return [frame] * int(seconds * FPS)


def caption(frames, title, sub):
    out = []
    ft, fs = font(30, True), font(20)
    for fr in frames:
        img = Image.fromarray(fr)
        dr = ImageDraw.Draw(img, "RGBA")
        dr.rectangle([0, H - 78, W, H], fill=(20, 22, 27, 190))
        dr.rectangle([0, H - 78, 10, H], fill=ORANGE)
        dr.text((28, H - 72), title, font=ft, fill=(255, 255, 255))
        dr.text((28, H - 36), sub, font=fs, fill=(210, 214, 220))
        dr.text((W - 330, 18), "MuJoCo physics simulation", font=fs, fill=(90, 94, 102))
        out.append(np.asarray(img))
    return out


def main(sim_dir, out_mp4):
    sim_dir = Path(sim_dir)
    log = json.loads((sim_dir / "sim-log.json").read_text())
    w, s, c = log["walk"], log["skate"], log["crawl"]
    frames = []
    frames += card([("OLLIE", 96, INK, True), ("walks  \u00b7  skates  \u00b7  crawls", 34, GRAY, False),
                    ("a $700 humanoid, simulated from its CAD", 26, ORANGE, False)], 3.0)
    segs = [
        ("walk", "1  WALK", "steps, cables, door sills", 2,
         f"{w['steps']} steps, {w['distance_m']:.2f} m, no fall  \u00b7  weight moves over each foot before it lifts  \u00b7  2x speed"),
        ("skate", "2  SKATE", "toes up, balancing on the heel wheels", 1,
         f"{s['distance_m']:.2f} m in {s['duration_s']:.0f} s  \u00b7  up to {s['peak_speed_mps']:.2f} m/s  \u00b7  max lean "
         f"{s['max_lean_deg']:.1f}\u00b0  \u00b7  toes never touch  \u00b7  real time"),
        ("crawl", "3  CRAWL", "hands and knees, under furniture", 2,
         f"{c['distance_m']:.2f} m crawled  \u00b7  body stays under {c['max_body_height_m'] * 100:.0f} cm  \u00b7  "
         f"{'passed under the table without touching it' if c['passed_under_table'] else 'heading under the table'}"
         f"  \u00b7  2x speed"),
    ]
    writer = imageio.get_writer(out_mp4, fps=FPS, quality=8, macro_block_size=8)
    n = 0

    def put(fr):
        nonlocal n
        writer.append_data(fr)
        n += 1
    for fr in frames:
        put(fr)
    ft, fs = font(30, True), font(20)
    for key, title, tag, speed, sub in segs:
        for fr in card([(title, 72, INK, True), (tag, 32, GRAY, False)], 1.6):
            put(fr)
        reader = imageio.get_reader(str(sim_dir / f"clip_{key}.mp4"))
        for i, fr in enumerate(reader):
            if i % speed:
                continue
            put(caption_one(fr, title, sub, ft, fs))
        reader.close()
    for fr in card([("Real physics from the CAD: masses, joint limits, motor torque limits", 28, INK, True),
                    ("Model-based controllers, not trained yet. Next: one RL policy that picks the mode.", 24, GRAY, False),
                    ("Not built yet. Looking for sponsors.", 30, ORANGE, True)], 3.5):
        put(fr)
    writer.close()
    print("wrote", out_mp4, n, "frames", round(n / FPS, 1), "s")


def caption_one(fr, title, sub, ft, fs):
    img = Image.fromarray(fr)
    dr = ImageDraw.Draw(img, "RGBA")
    dr.rectangle([0, H - 78, W, H], fill=(20, 22, 27, 190))
    dr.rectangle([0, H - 78, 10, H], fill=ORANGE)
    dr.text((28, H - 72), title, font=ft, fill=(255, 255, 255))
    dr.text((28, H - 36), sub, font=fs, fill=(210, 214, 220))
    dr.text((W - 330, 18), "MuJoCo physics simulation", font=fs, fill=(90, 94, 102))
    return np.asarray(img)


def _old_main_tail():
    frames = []


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
