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
    ("Head", "Smoked acrylic sheet 3 mm, A5 (eye lenses + chest chevron)", 1, 8.00, "typical", "laser-cut or hand-cut"),
    ("Head", "WS2812B 8-LED strip (chest chevron mode light)", 1, 4.00, "typical", "blue walk / orange skate / white crawl"),
    ("Frame", "PETG filament 1 kg, blue (R9 Icon Blue fairings)", 1, 20.00, "typical $18-22/kg",
     "black panels print in the black PLA+, stripes in any grey/white leftover"),
    ("Frame", "6061 aluminium: 1/8 in sheet (bracket/foot/shoulder/frame plates) + 1x1x1/16 in square tube (bones)", 1, 0.00,
     "FRC team stock / scrap (about $25 if bought)", "cut on the team CNC router"),
    ("Sensors", "OV5647 5 MP camera for Pi Zero (in the M-duct)", 1, 10.00, "typical", "replaces the $25 Camera Module 3"),
]
DROP = {("Head", "0.96 in OLED 'eyes' (SSD1306)"), ("Sensors", "Raspberry Pi Camera Module 3 (head eye)")}
SWAP_OLED = ("Head", "0.91 in 128x32 OLED (SSD1306) slit eyes", 2, 4.00, "typical", "behind the slanted eye lenses")
UPGRADE = ("Feetech STS3250 50 kg.cm bus servo (drop-in for ST3215, same case) on hip roll / hip pitch / knee", 6, 44.65,
           "alibaba Feetech store $44.65-47.77 (2026-11); NOT in the $700")


def items():
    rows = [r for r in HP.BOM if (r[0], r[1]) not in DROP]
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
        w.writerow([])
        it, q, u, src = UPGRADE
        w.writerow(["OPTIONAL", it, q, f"{u:.2f}", f"{q * u:.2f}", src, "halves the worst walking load (74% -> 45% of stall)"])
    print(f"subtotal {sub:.2f} margin {margin:.2f} contingency {cont:.2f} total {total:.2f}")
    return sub, margin, cont, total


if __name__ == "__main__":
    main(sys.argv[1])
