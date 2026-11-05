"""Grab a contact sheet of frames from an MP4 for a visual check."""
import sys

import imageio.v2 as imageio
import numpy as np
from PIL import Image


def main(mp4, out_png, times=(1.5, 6, 10, 14, 19, 24, 29, 34)):
    r = imageio.get_reader(mp4)
    fps = r.get_meta_data()["fps"]
    want = {int(t * fps) for t in times}
    tiles = []
    for i, fr in enumerate(r):
        if i in want:
            tiles.append(Image.fromarray(fr).resize((640, 360)))
    r.close()
    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 640, rows * 360), (255, 255, 255))
    for k, t in enumerate(tiles):
        sheet.paste(t, ((k % cols) * 640, (k // cols) * 360))
    sheet.save(out_png)
    print("wrote", out_png, len(tiles), "tiles")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
