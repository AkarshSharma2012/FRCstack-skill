"""ollie_bom.py -- OLLIE parts list (CSV + markdown table) built on the checked $700 humanoid BOM.

Usage: python ollie_bom.py OUT_DIR
Adds the heel-wheel drive, visor face and mode light; keeps the total at or under $700 by sizing the
contingency line.  Prices are list/typical prices seen 2026-11; recheck before ordering."""
import csv
import sys
from pathlib import Path

import humanoid_plan as HP

BUDGET = 700.0
ADD = [
    ("Wheels", "N20 micro metal gearmotor 6 V 150:1 with magnetic encoder (generic, Pololu #5192 class)", 2, 10.00,
     "typical marketplace price; Pololu #5192 is the reference spec (220 rpm, 2.0 kg.cm @ 6 V)",
     "one per heel wheel, skate mode"),
    ("Wheels", "DRV8833 dual H-bridge motor driver breakout", 1, 4.00, "typical", "drives both heel motors from the ESP32"),
    ("Wheels", "MR63ZZ bearing 3x6x2.5 mm, 10-pack", 1, 6.00, "typical", "outer support for each heel wheel"),
    ("Head", "Smoked acrylic sheet 3 mm, A5 (visor)", 1, 8.00, "typical", "laser-cut or hand-cut visor"),
    ("Head", "WS2812B 8-LED stick (chest mode light)", 1, 4.00, "typical", "blue walk / orange skate / white crawl"),
]
DROP = {"Head": "0.96 in OLED 'eyes' (SSD1306)"}
SWAP_OLED = ("Head", "0.91 in 128x32 OLED (SSD1306) slit eyes", 2, 4.00, "typical", "behind the visor")


def items():
    rows = [r for r in HP.BOM if not (r[0] in DROP and r[1] == DROP[r[0]])]
    return rows + [SWAP_OLED] + ADD


def main(out):
    out = Path(out)
    rows = items()
    sub = sum(q * u for _, _, q, u, _, _ in rows)
    margin = round(sub * HP.SHIP_TAX_RATE, 2)
    cont = round(max(0.0, min(25.0, BUDGET - sub - margin)), 2)
    total = round(sub + margin + cont, 2)
    if total > BUDGET + 1e-9:
        raise SystemExit(f"over budget {total}")
    with (out / "ollie-bom.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["category", "item", "qty", "unit_usd", "line_usd", "source", "note"])
        for c, it, q, u, src, note in rows:
            w.writerow([c, it, q, f"{u:.2f}", f"{q * u:.2f}", src, note])
        w.writerow(["", "Parts subtotal", "", "", f"{sub:.2f}", "", ""])
        w.writerow(["", "Shipping + tax margin 10%", "", "", f"{margin:.2f}", "", ""])
        w.writerow(["", "Contingency", "", "", f"{cont:.2f}", "", "sized to stay under the cap"])
        w.writerow(["", "TOTAL", "", "", f"{total:.2f}", "", "cap 700.00"])
    print(f"subtotal {sub:.2f} margin {margin:.2f} contingency {cont:.2f} total {total:.2f}")
    return sub, margin, cont, total


if __name__ == "__main__":
    main(sys.argv[1])
