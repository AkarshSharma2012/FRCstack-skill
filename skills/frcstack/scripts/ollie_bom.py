"""ollie_bom.py -- OLLIE v2 priced build plan: $1,000 cap, every part bought (team tools only).

Usage: python ollie_bom.py OUT_DIR
Writes OUT_DIR/ollie-bom.csv and OUT_DIR/ollie-plan.md and checks:
  * total (parts + 10 % shipping/tax) <= $1,000, no $0 (borrowed) lines
  * motor count matches the CAD joints (12 leg, 4 arm, 2 gripper, 2 head, 2 wheel)
  * if OUT_DIR/ollie-print-list.csv exists, the CNC plates fit the bought sheet and the bones fit the
    bought tube (area / length check with a router-spacing allowance, not a real nest)
Prices are list/typical prices seen 2026-11; "est." lines are estimates.  Recheck before ordering."""
import csv
import sys
from pathlib import Path

BUDGET = 1000.00
SHIP_TAX = 0.10
SHEET_MM = (305.0, 610.0)          # 12 x 24 in
SHEET_T = 3.2                      # 1/8 in
TUBE_MM = 610.0                    # 2 ft
GAP_MM = 8.0                       # router bit + tabs around every part

# (category, item, qty, unit_usd, source, note)
BOM = [
    # ---- motors (22)
    ("Motors", "Feetech STS3250 50 kg.cm bus servo (ST-3250-C001, same case as ST3215)", 6, 44.65,
     "alibaba.com Feetech store, $44.65-47.77 (2026-11)", "hip roll, hip pitch, knee on both legs (the high-load joints)"),
    ("Motors", "Waveshare ST3215 30 kg.cm bus servo, 12 V, 360 deg magnetic encoder", 10, 16.99,
     "waveshare.com ($16.99-21.99)", "hip yaw + ankle pitch + ankle roll (6), shoulder + elbow (4)"),
    ("Motors", "Waveshare SC09 2.3 kg.cm bus servo", 4, 11.50, "robotshop.com RB-Wav-707", "2 grippers, head pan, head tilt"),
    ("Motors", "N20 6 V 150:1 gearmotor with magnetic encoder (Pololu #5192 class)", 2, 10.00, "est. marketplace",
     "heel wheels (skate mode)"),
    # ---- brain + movement control
    ("Control", "Waveshare Serial Bus Servo Driver HAT (A), ESP32, XT60", 1, 18.99, "waveshare.com",
     "fast loop: servo bus, IMU balance, wheel PWM"),
    ("Control", "Raspberry Pi Zero 2 W", 1, 15.00, "raspberrypi.com list",
     "mode switching, gait planner, camera, break-prediction software"),
    ("Control", "microSD card 32 GB (A1)", 1, 8.00, "est.", "Pi OS + sensor logs for break prediction"),
    ("Control", "DRV8833 dual H-bridge breakout", 1, 4.00, "est.", "drives both heel motors"),
    ("Sensors", "MPU-6050 6-axis IMU (chest)", 1, 6.00, "est.", "balance + fall detection"),
    ("Sensors", "OV5647 5 MP camera for Pi Zero", 1, 10.00, "est.", "head M-duct"),
    ("Head", "0.91 in 128x32 OLED (SSD1306) eyes", 2, 4.00, "est.", ""),
    ("Head", "WS2812B 8-LED strip (chest mode light)", 1, 4.00, "est.", "blue walk / orange skate / white crawl"),
    # ---- break-prediction sensor pack (the team writes the software)
    ("Health sensors", "INA226 current/voltage monitor breakout", 1, 5.00, "est.", "total pack current + battery sag"),
    ("Health sensors", "FSR402 force sensor (4 per foot)", 8, 2.50, "est.",
     "foot contact for mode switching + hard-landing counts"),
    ("Health sensors", "ADS1115 16-bit ADC breakout", 2, 5.00, "est.", "one per leg, reads that foot's 4 FSRs"),
    ("Health sensors", "2x MPU-6050 (shins) + TCA9548A I2C mux", 1, 9.00, "est.",
     "leg vibration/impact; mux gives each leg its own I2C channel"),
    # ---- power
    ("Power", "Ovonic 3S 11.1 V 5000 mAh 50C LiPo, XT60", 1, 32.99, "ovonicshop.com", ""),
    ("Power", "LiPo balance charger (2-3S, AC)", 1, 30.00, "est. (ISDT/HTRC class)", ""),
    ("Power", "6 V 3 A UBEC for the SC09 chain", 1, 8.00, "est.", "SC09 is 4-6 V only"),
    ("Power", "XT60 pigtails, 30 A fuse + holder, main switch, LiPo bag", 1, 18.00, "est.", "safety"),
    # ---- structure
    ("Metal", "6061-T6 sheet 1/8 in, 12 x 24 in", 1, 39.85, "speedymetals.com 61p.125 ($39.85)",
     "all 34 CNC plates (bracket, idler, foot, shoulder, side frame)"),
    ("Metal", "6061-T6 square tube 1 x 1 x 1/16 in, 2 ft", 1, 12.00, "est. (online metals / local)",
     "thigh + shin bones"),
    ("Print", "PLA+ filament 1 kg", 2, 18.00, "est.", "skeleton blocks, cradles, spacer rings"),
    ("Print", "PETG filament 1 kg, blue", 1, 20.00, "est.", "R9-style fairings"),
    ("Print", "TPU 95A filament 0.5 kg", 1, 16.00, "est.", "soles, pads, tyres"),
    ("Hardware", "M2/M3 screws, nuts, M3 heat-set inserts kit", 1, 22.00, "est.", ""),
    ("Hardware", "MR63ZZ bearings 3x6x2.5, 10-pack", 1, 6.00, "est.", "heel wheel outer support"),
    ("Hardware", "Smoked acrylic 3 mm, A5", 1, 8.00, "est.", "eye lenses + chest chevron"),
    # ---- wiring
    ("Wiring", "SC servo bus cable (separate 6 V SC09 chain)", 1, 6.00, "est.", ""),
    ("Wiring", "3-pin servo bus extensions, assorted", 1, 14.00, "est.", ""),
    ("Wiring", "Silicone wire 18/22 AWG, heat-shrink, JST/Dupont kit, 10 k resistors", 1, 15.00, "est.",
     "FSR dividers + sensor leads"),
]
MOTORS_EXPECTED = 22
FIRST_CUTS = [("2x shin IMUs + I2C mux", 9.00, "servo current/temp/lag + foot FSRs still feed break prediction"),
              ("STS3250 -> ST3215 on hip roll only (2)", 2 * (44.65 - 16.99), "hip roll is the lowest of the 3 upgraded loads")]
NOT_COUNTED = ["CNC router, end mills, 3D printers, soldering station, hand tools (team tools, used not taken)",
               "Broken end mills or other team consumables we wear out (replace from the failures budget)",
               "Repairs, spare servos and later upgrades (separate failures budget, reported separately)"]


def totals():
    sub = round(sum(q * u for _, _, q, u, _, _ in BOM), 2)
    tax = round(sub * SHIP_TAX, 2)
    return sub, tax, round(sub + tax, 2)


def by_cat():
    out = {}
    for c, _, q, u, _, _ in BOM:
        out[c] = out.get(c, 0.0) + q * u
    return out


def check_bom():
    zero = [it for _, it, q, u, _, _ in BOM if u <= 0 or q <= 0]
    if zero:
        raise SystemExit(f"borrowed / zero-cost lines not allowed: {zero}")
    motors = sum(q for c, _, q, _, _, _ in BOM if c == "Motors")
    if motors != MOTORS_EXPECTED:
        raise SystemExit(f"motor count {motors} != {MOTORS_EXPECTED}")
    total = totals()[2]
    if total > BUDGET:
        raise SystemExit(f"over budget: {total:.2f}")


def metal_fit(print_list: Path):
    """Area/length sanity check of the CNC aluminium against the bought stock."""
    if not print_list.exists():
        return None
    plates, tubes, thick = [], [], []
    with print_list.open(newline="") as fh:
        for r in csv.DictReader(fh):
            if not r["material"].startswith("6061"):
                continue
            d = sorted(float(v) for v in r["bbox_mm"].split(" x "))
            if "tube" in r["part"]:
                tubes.append((r["part"], d[2]))
            else:
                plates.append((r["part"], d[1], d[2]))
                if d[0] > SHEET_T + 0.3:
                    thick.append((r["part"], d[0]))
    area = sum((a + GAP_MM) * (b + GAP_MM) for _, a, b in plates)
    sheet = SHEET_MM[0] * SHEET_MM[1]
    longest = max((b for _, _, b in plates), default=0.0)
    tube_len = sum(L + GAP_MM for _, L in tubes)
    res = {"plates": len(plates), "plate_area_mm2": round(area), "sheet_area_mm2": round(sheet),
           "sheet_use": round(area / sheet, 2), "longest_plate_mm": longest, "tubes": len(tubes),
           "tube_mm": round(tube_len), "tube_stock_mm": TUBE_MM, "too_thick": thick}
    ok = area <= 0.75 * sheet and longest <= SHEET_MM[1] - 20 and tube_len <= TUBE_MM - 20 and not thick
    res["ok"] = ok
    if not ok:
        raise SystemExit(f"metal stock check failed: {res}")
    return res


def write_csv(path, sub, tax, total):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["category", "item", "qty", "unit_usd", "line_usd", "source", "note"])
        for c, it, q, u, src, note in BOM:
            w.writerow([c, it, q, f"{u:.2f}", f"{q * u:.2f}", src, note])
        w.writerow(["", "Parts subtotal", "", "", f"{sub:.2f}", "", ""])
        w.writerow(["", "Shipping + tax 10%", "", "", f"{tax:.2f}", "", ""])
        w.writerow(["", "TOTAL", "", "", f"{total:.2f}", "", f"cap {BUDGET:.2f}, left {BUDGET - total:.2f}"])


def plan_md(sub, tax, total, fit):
    cats = by_cat()
    L = []
    a = L.append
    a("# OLLIE v2 - $1,000 Priced Build Plan")
    a("")
    a(f"**Total: ${total:,.2f}** (parts ${sub:,.2f} + 10 % shipping/tax ${tax:,.2f}), "
      f"**${BUDGET - total:,.2f} under the $1,000 cap.**  Every part is bought; the team's CNC router, "
      "printers and tools are used but nothing is taken from team stock.  Repairs and upgrades come from a "
      "separate failures budget.  *Proposed design: not built or tested.  Prices seen 2026-11; lines marked "
      "est. are estimates.*")
    a("")
    a("## 1. Where the money goes")
    a("| Group | $ | Share |")
    a("|---|---:|---:|")
    for c, v in sorted(cats.items(), key=lambda kv: -kv[1]):
        a(f"| {c} | {v:,.2f} | {100 * v / sub:.0f} % |")
    a(f"| **Parts subtotal** | **{sub:,.2f}** | |")
    a(f"| Shipping + tax (10 %) | {tax:,.2f} | |")
    a(f"| **Total** | **{total:,.2f}** | cap $1,000 |")
    a("")
    a("## 2. Full parts list")
    a("| # | Group | Item | Qty | Unit $ | Line $ | Source | Use |")
    a("|---|---|---|---:|---:|---:|---|---|")
    for i, (c, it, q, u, src, note) in enumerate(BOM, 1):
        a(f"| {i} | {c} | {it} | {q} | {u:.2f} | {q * u:.2f} | {src} | {note} |")
    a("")
    a("## 3. Motors (22)")
    a("| Joint | Motor | Why |")
    a("|---|---|---|")
    a("| Hip roll, hip pitch, knee (x2 legs) | STS3250, 50 kg.cm | highest walking loads: worst case drops from "
      "74 % to 45 % of stall in the CAD statics |")
    a("| Hip yaw, ankle pitch, ankle roll (x2) | ST3215, 30 kg.cm | lower loads |")
    a("| Shoulder, elbow (x2 arms) | ST3215 | |")
    a("| Grippers (2), head pan + tilt | SC09 on its own 6 V chain | |")
    a("| Heel wheels (2) | N20 150:1 encoder gearmotor + DRV8833 | skate mode |")
    a("")
    a("STS3250 and ST3215 share the case size and bus protocol, so the CAD brackets fit both.  The STS3250 "
      "stalls at about 4.2 A vs 2.7 A, so keep firmware torque limits on and split the 12 V servos over "
      "4 chains.")
    a("")
    a("## 4. Movement control and mode switching")
    a("```")
    a("3S LiPo -- 30 A fuse -- switch --+-- Servo Driver HAT (A) (ESP32) -- 4 TTL chains: L leg, R leg, arms")
    a("                                 |        |-- DRV8833 -- 2x N20 heel wheels")
    a("                                 |        |-- UART -- Pi Zero 2 W -- camera, OLED eyes, LED strip")
    a("                                 +-- 6 V UBEC -- SC09 chain (grippers, head)")
    a("I2C: chest IMU + INA226 on the main bus; TCA9548A mux -> one channel per leg (shin IMU + ADS1115 + 4 FSRs)")
    a("```")
    a("- **ESP32 (fast loop, 100-200 Hz):** reads every servo, the IMU and the wheel encoders; runs balance "
      "and the wheel motors; stops everything if the robot tips or the pack sags.")
    a("- **Pi Zero 2 W (slow loop):** picks the mode and plans motion.  Walk -> skate when both feet are flat "
      "and the floor is smooth; skate/walk -> crawl when the IMU tilt or a low-battery limit says so; the "
      "foot FSRs confirm each transition finished before the next starts.")
    a("- Mode switching needs no extra boards: it is software on the two controllers above.")
    a("")
    a("## 5. Break-prediction hardware (your own system)")
    a("You are writing the prediction software.  This plan only makes sure it has data:")
    a("")
    a("| Signal | From | Early warning of |")
    a("|---|---|---|")
    a("| Position vs. command (lag), load, current, temperature, voltage per joint | every bus servo | "
      "stripped / worn gears, binding, overheating motors |")
    a("| Foot force, 4 per foot | FSRs + ADS1115 | hard landings, uneven loading, loose sole |")
    a("| Shin + chest vibration and shocks | 3x MPU-6050 | loose brackets, cracked parts, falls |")
    a("| Pack current and voltage | INA226 | battery ageing, a servo drawing too much |")
    a("")
    a("Log to the microSD on the Pi and train on a laptop; the Pi Zero only runs the trained model.  "
      "Confirm that the servos you buy actually report current before relying on it (some listings only "
      "promise position, load, speed and voltage).")
    a("")
    a("## 6. CNC aluminium (bought stock, team router)")
    if fit:
        a(f"- **{fit['plates']} plates** from one 12 x 24 in sheet of 1/8 in 6061-T6: they use about "
          f"**{100 * fit['sheet_use']:.0f} %** of the sheet including {GAP_MM:.0f} mm router spacing, which leaves room "
          f"to recut a bad part.  Longest plate {fit['longest_plate_mm']:.0f} mm.")
        a(f"- **{fit['tubes']} bones** need about {fit['tube_mm']} mm of 1 x 1 x 1/16 in tube: 2 ft (610 mm) covers it.")
    a("- All bracket idler plates are now 1/8 in (were 4 mm, which needed a second $52 sheet).  A 1 mm "
      "printed spacer ring keeps the same idler gap.  The thinner idler is about 20 % less stiff: check for "
      "flex on the first leg before cutting the rest.")
    a("- Cutting bits and machine time are team tools.  Anything we break gets replaced from the failures budget.")
    a("")
    a("## 7. Not counted in the $1,000")
    for n in NOT_COUNTED:
        a(f"- {n}")
    a("")
    a("## 8. If prices come in high")
    a(f"The plan has only ${BUDGET - total:,.2f} left, so if shipping or a price moves, cut in this order:")
    a("")
    a("| Cut | Saves | Cost of cutting it |")
    a("|---|---:|---|")
    for c, v, why in FIRST_CUTS:
        a(f"| {c} | ${v * (1 + SHIP_TAX):,.2f} incl. tax | {why} |")
    a("")
    a("## 9. Order and build sequence")
    for i, s in enumerate([
            "Confirm the STS3250 price + shipping (Alibaba/AliExpress) and the HAT's current rating; order servos "
            "first (1-3 weeks from China).",
            "Order metal (sheet + tube) and electronics; print skeleton blocks and fairings while waiting.",
            "CNC one leg's plates first, build one leg, and test it hanging before cutting the rest.",
            "Servo setup one at a time: ID, middle position, torque limit about 80 %.",
            "Both legs + pelvis, then torso electronics, arms, head.",
            "Firmware: ESP32 servo/IMU loop and e-stop, then standing balance, then walk / skate / crawl modes.",
            "Start logging every sensor from day 1: the break-prediction system needs healthy and failing data.",
            ], 1):
        a(f"{i}. {s}")
    a("")
    a("## 10. Risks")
    a("- Shipping from China can exceed 10 %; the margin is thin.  Use the cut list above if it does.")
    a("- Not built, not FEA'd: torques come from a quasi-static CAD model.  Walking will be slow (2-4 s per step).")
    a("- Prices drift: recheck every line before ordering.")
    return "\n".join(L) + "\n"


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    check_bom()
    fit = metal_fit(out / "ollie-print-list.csv")
    sub, tax, total = totals()
    write_csv(out / "ollie-bom.csv", sub, tax, total)
    (out / "ollie-plan.md").write_text(plan_md(sub, tax, total, fit), encoding="utf-8")
    print(f"subtotal {sub:.2f} ship/tax {tax:.2f} total {total:.2f} left {BUDGET - total:.2f}")
    if fit:
        print("metal", fit)
    return sub, tax, total


if __name__ == "__main__":
    main(sys.argv[1])
