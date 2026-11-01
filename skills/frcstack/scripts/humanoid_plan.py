"""Generate the $700 humanoid robot plan (markdown + CSV BOM) and check the total.

Usage: python humanoid_plan.py OUT_DIR
Prices are list/retail prices seen 2026-11-01 (sources in the CSV); they move, so
the plan keeps a contingency line inside the $700 cap."""
import csv
import sys
from pathlib import Path

BUDGET = 700.00

# (category, item, qty, unit_usd, source, note)
BOM = [
    ("Actuators", "Waveshare ST3215 serial bus servo, 30 kg.cm @ 12 V, 360 deg magnetic encoder", 16, 16.99,
     "waveshare.com/st3215-servo.htm (listed $16.99-$21.99; 12 V version)", "legs 12 (6 per leg), shoulder pitch + elbow 4"),
    ("Actuators", "Waveshare SC09 serial bus servo, 2.3 kg.cm", 4, 11.50,
     "robotshop.com RB-Wav-707 ($11.50)", "2 grippers, head pan, head tilt"),
    ("Control", "Waveshare Serial Bus Servo Driver HAT (A), ESP32-WROOM-32, XT60, 9-25 V", 1, 18.99,
     "waveshare.com/bus-servo-driver-hat-a.htm ($18.99)", "drives all 20 servos on one TTL bus; Wi-Fi"),
    ("Control", "Raspberry Pi Zero 2 W", 1, 15.00, "raspberrypi.com ($15 list)", "high-level brain, camera, gait planner"),
    ("Sensors", "Raspberry Pi Camera Module 3 (head eye)", 1, 25.00, "raspberrypi.com (from $25)", "face/ball tracking"),
    ("Sensors", "6-axis IMU breakout (MPU-6050 class) for balance", 1, 6.00, "typical hobby price", "on chest, I2C to ESP32"),
    ("Power", "Ovonic 3S 11.1 V 5000 mAh 50C LiPo, XT60", 1, 32.99, "ovonicshop.com ($32.99)", "~20-40 min mixed use"),
    ("Power", "LiPo balance charger (2-3S, AC input)", 1, 30.00, "typical (ISDT/HTRC class)", "required to charge safely"),
    ("Power", "5 V 3 A buck/UBEC for Pi + camera", 1, 8.00, "typical hobby price", "from the 3S bus"),
    ("Power", "XT60 pigtails, 30 A blade fuse + holder, main switch, LiPo-safe bag", 1, 18.00, "typical", "safety"),
    ("Frame", "PLA+ filament 1 kg (structure)", 2, 18.00, "typical $16-20/kg", "~1.8 kg printed parts incl. supports"),
    ("Frame", "TPU 95A filament 0.5 kg (feet soles, gripper pads, bumpers)", 1, 16.00, "typical", "grip + impact"),
    ("Frame", "M2/M3 screw + nut + heat-set insert kit", 1, 22.00, "typical assortment", "servo horns use supplied screws"),
    ("Frame", "6 mm carbon tube 1 m (leg spars)", 1, 9.00, "typical", "stiffens thigh/shin"),
    ("Frame", "MR85 flanged bearings, 10-pack", 2, 6.00, "typical", "idler side of every leg joint"),
    ("Wiring", "Servo bus cable extensions, 3-pin, assorted", 1, 14.00, "typical", "daisy-chain"),
    ("Wiring", "Silicone wire 18/22 AWG, heat-shrink, JST/Dupont kit", 1, 15.00, "typical", ""),
    ("Head", "0.96 in OLED 'eyes' (SSD1306)", 2, 4.00, "typical", "expressions"),
]
OPTIONAL = [
    ("Sensors", "4x FSR402 foot force sensors", 4, 6.50, "better balance feedback"),
    ("Head", "I2S speaker amp + mic", 1, 12.00, "voice"),
    ("Actuators", "2 more ST3215 for shoulder roll (arm out to the side)", 2, 16.99, "5-DOF arms"),
    ("Actuators", "1-2 spare ST3215", 1, 16.99, "spares"),
]
SHIP_TAX_RATE = 0.10           # shipping + tax margin on parts
CONTINGENCY = 25.00            # price drift / broken parts


def totals():
    sub = sum(q * u for _, _, q, u, _, _ in BOM)
    margin = round(sub * SHIP_TAX_RATE, 2)
    return sub, margin, sub + margin + CONTINGENCY


DOF = [
    ("Leg (x2)", "hip yaw, hip roll, hip pitch, knee pitch, ankle pitch, ankle roll", "6 x ST3215", 12),
    ("Arm (x2)", "shoulder pitch, elbow pitch", "2 x ST3215", 4),
    ("Gripper (x2)", "1-DOF two-finger gripper (fin-ray TPU pads)", "1 x SC09", 2),
    ("Head", "pan, tilt", "2 x SC09", 2),
]


def plan_md(sub, margin, total):
    lines = []
    a = lines.append
    a("# $700 Humanoid Robot - Full Build Plan")
    a("")
    a("*Generated 2026-11-01.  Prices are current list/retail prices with a 10 % shipping/tax margin and a "
      f"${CONTINGENCY:.0f} contingency.  Total: **${total:,.2f}** (cap $700).*")
    a("")
    a("## 1. Concept")
    a("A ~70 cm tall bipedal humanoid built from 20 smart serial-bus servos on a 3D-printed skeleton. "
      "It does not try to look human - it is a boxy, sturdy robot with two 6-DOF legs, two 2-DOF arms with "
      "grippers, a chest/torso that houses the battery and electronics, and a pan/tilt head with a camera "
      "and OLED 'eyes'.  Every joint reports position, load, speed and voltage, so balance and gait code can "
      "close the loop.")
    a("")
    a("| Spec | Value |")
    a("|---|---|")
    a("| Height / mass target | ~70 cm, ~2.8 kg |")
    a("| Degrees of freedom | 20 (legs 12, arms 4, grippers 2, head 2) |")
    a("| Main servo | Waveshare ST3215, 30 kg.cm stall @ 12 V, 12-bit magnetic encoder, 45 rpm |")
    a("| Bus / controller | 1 Mbps TTL serial bus, ESP32 driver HAT + Raspberry Pi Zero 2 W |")
    a("| Power | 3S 11.1 V 5000 mAh LiPo (servos run directly from the pack, 6-12.6 V rated) |")
    a("| Sensors | camera, 6-axis IMU, servo position/load/voltage feedback |")
    a("")
    a("## 2. Degrees of freedom")
    a("| Group | Joints | Actuators | Count |")
    a("|---|---|---|---|")
    for g, j, act, n in DOF:
        a(f"| {g} | {j} | {act} | {n} |")
    a(f"| **Total** | | | **{sum(d[3] for d in DOF)}** |")
    a("")
    a("**Why ST3215 for legs:** a 70 cm, 2.8 kg robot shifting its weight onto one leg puts roughly "
      "2.8 kg x 9.81 x ~0.06 m = 1.6 N.m on the support-leg hip/ankle roll.  ST3215 stall is ~2.9 N.m, so peak "
      "load is ~57 % of stall: workable for slow, statically-stable walking, but **not** for running or jumping. "
      "Keep legs short (thigh 130 mm, shin 130 mm) and mass low; that ratio is the single most important "
      "design rule for this budget.")
    a("")
    a("## 3. Parts list")
    a("| # | Category | Item | Qty | Unit $ | Line $ | Source / note |")
    a("|---|---|---|---|---|---|---|")
    for i, (c, item, q, u, src, note) in enumerate(BOM, 1):
        a(f"| {i} | {c} | {item} | {q} | {u:.2f} | {q * u:.2f} | {src}{'; ' + note if note else ''} |")
    a(f"| | | **Parts subtotal** | | | **{sub:.2f}** | |")
    a(f"| | | Shipping + tax margin (10 %) | | | {margin:.2f} | |")
    a(f"| | | Contingency | | | {CONTINGENCY:.2f} | price drift / spares |")
    a(f"| | | **TOTAL** | | | **{total:.2f}** | under the $700 cap by ${BUDGET - total:.2f} |")
    a("")
    a("*Assumes you already own a 3D printer, soldering iron, screwdrivers and a computer.  If not, the "
      "budget will not cover them.*")
    a("")
    a("**Optional upgrades (NOT in the $700 total):**")
    a("")
    a("| Item | Qty | Unit $ | Why |")
    a("|---|---|---|---|")
    for c, item, q, u, why in OPTIONAL:
        a(f"| {item} | {q} | {u:.2f} | {why} |")
    a("")
    a("## 4. Electronics and power")
    a("```")
    a("3S LiPo 11.1 V ──XT60── 30 A fuse ── main switch ──┬── Bus Servo Driver HAT (A) (ESP32)")
    a("                                                   │       └─ TTL bus ─ 20 servos (4 daisy chains:")
    a("                                                   │          L-leg 6, R-leg 6, arms+grippers 6, head 2)")
    a("                                                   └── 5 V 3 A buck ── Pi Zero 2 W ── Camera Module 3")
    a("ESP32 <─UART 1 Mbps─> Pi Zero 2 W        IMU (I2C) -> ESP32")
    a("Pi: 2x OLED eyes (I2C)")
    a("```")
    a("- **Servo supply runs straight from the pack** (ST3215 accepts 6-12.6 V), so there is no big regulator.")
    a("- Split the bus into 4 chains so no single 3-pin lead carries more than ~6 servos of current.")
    a("- Peak draw: up to ~2.7 A stall per ST3215; with sensible torque limits set in firmware the realistic "
      "peak is ~10-15 A, which the 5000 mAh pack (50C-class) and XT60 handle easily.")
    a("- **Low-voltage cutoff:** the ESP32 reads pack voltage from servo feedback; stop all motion below "
      "10.5 V (3.5 V/cell).  Always charge in a LiPo bag.")
    a("")
    a("## 5. Printed parts")
    a("| Part | Qty | Material | Notes |")
    a("|---|---|---|---|")
    for p in [("Foot plate with TPU sole", 2, "PLA+ / TPU", "120 x 70 mm, wide stance"),
              ("Ankle bracket (pitch-roll cross)", 2, "PLA+", "bearing on the idle side"),
              ("Shin (two side plates + 6 mm spar)", 2, "PLA+", "130 mm"),
              ("Knee bracket", 2, "PLA+", ""),
              ("Thigh (two side plates + spar)", 2, "PLA+", "130 mm"),
              ("Hip block (yaw-roll-pitch stack)", 2, "PLA+", "keep the three axes intersecting"),
              ("Pelvis plate", 1, "PLA+", "hip yaw servos mount here"),
              ("Torso box (front, back, two sides, lid)", 1, "PLA+", "battery tray low, electronics high"),
              ("Shoulder bracket", 2, "PLA+", ""),
              ("Upper arm / forearm", 4, "PLA+", "100 mm each"),
              ("Gripper (2 fingers + SC09 mount)", 2, "PLA+ / TPU", "fin-ray TPU pads"),
              ("Neck pan/tilt + head shell", 1, "PLA+", "camera + OLED eyes"),
              ("Bumpers / feet edges", 4, "TPU", "fall protection")]:
        a(f"| {p[0]} | {p[1]} | {p[2]} | {p[3]} |")
    a("")
    a("Print settings: 0.2 mm layers, 4 walls, 30-40 % gyroid infill, heat-set inserts for every screw "
      "that goes into plastic.  Total print time roughly 60-80 h.")
    a("")
    a("## 6. Build steps")
    steps = [
        "**Order parts** (servos ship from China: allow 1-3 weeks).  Print while waiting.",
        "**Set up servos one at a time:** plug each servo alone into the driver HAT, give it a unique ID "
        "(1-20, map in Section 2), set the middle position, and set a torque/current limit (~80 %).  Label each.",
        "**Print the legs first** (feet, ankles, shins, knees, thighs, hips, pelvis).  Press bearings and "
        "heat-set inserts.",
        "**Assemble one leg** with servos at their middle position so the leg is straight; check every joint "
        "moves without binding by hand-turning before powering.",
        "**Mirror for the second leg**, mount both on the pelvis, and bench-test each joint over its range on a "
        "stand with the robot hanging (feet off the table).",
        "**Torso:** fit the battery tray, fuse, switch, driver HAT, buck converter and Pi Zero.  Route the four "
        "servo chains through the pelvis.",
        "**Arms and grippers**, then the **head** (pan/tilt, camera, OLED eyes).",
        "**Wiring check:** with no battery, check for shorts; then power from a bench supply at 11 V with a "
        "2 A current limit; confirm all 20 IDs respond.",
        "**Firmware v1 (ESP32):** read all servo states at 100 Hz plus the IMU, and serve a Wi-Fi web panel "
        "with sliders per joint plus an emergency stop.",
        "**Calibration:** record joint offsets so the robot stands straight; write a zero-pose file.",
        "**Balance:** standing with ankle/hip feedback from the IMU (PD on pitch/roll), then a squat test.",
        "**Gait:** start with a slow statically-stable shuffle (shift weight over one foot using hip/ankle "
        "roll, then step); tune on a tether.  Then add a ZMP-style preview gait on the Pi.",
        "**Vision + behaviour on the Pi:** OpenCV colour/face tracking with the head.",
        "**Safety rules:** always test walking on a tether or harness first, keep firmware torque limits on, "
        "and never leave a LiPo charging unattended.",
    ]
    for i, s in enumerate(steps, 1):
        a(f"{i}. {s}")
    a("")
    a("## 7. Schedule (part-time)")
    a("| Week | Work |")
    a("|---|---|")
    for w, t in [("1", "Order parts, start printing legs"), ("2", "Servo IDs, assemble legs + pelvis"),
                 ("3", "Torso electronics, arms, head"), ("4", "Firmware v1, calibration, standing balance"),
                 ("5-6", "Tethered walking, gait tuning"), ("7+", "Vision, voice, behaviours")]:
        a(f"| {w} | {t} |")
    a("")
    a("## 8. Risks and honest limits")
    a("- Hobby bus servos are the weak point for walking: expect slow steps (~2-4 s per step), "
      "overheating on long sessions and occasional stripped horns.  The contingency covers ~1 spare ST3215.")
    a("- Prices drift; recheck before ordering.  The 10 % margin may not cover overseas shipping in all regions.")
    a("- This plan has not been built or tested; joint torques are hand estimates, not a simulation.")
    a("- Upgrade path if walking is too weak: ST3025 (40 kg.cm) or RSBL45-24 servos on the hips/knees only.")
    return "\n".join(lines) + "\n"


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    sub, margin, total = totals()
    if total > BUDGET:
        raise SystemExit(f"over budget: {total:.2f}")
    (out / "humanoid-700-plan.md").write_text(plan_md(sub, margin, total), encoding="utf-8")
    with open(out / "humanoid-700-bom.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["category", "item", "qty", "unit_usd", "line_usd", "source", "note"])
        for c, item, q, u, src, note in BOM:
            w.writerow([c, item, q, f"{u:.2f}", f"{q * u:.2f}", src, note])
        w.writerow(["", "Parts subtotal", "", "", f"{sub:.2f}", "", ""])
        w.writerow(["", "Shipping + tax margin 10%", "", "", f"{margin:.2f}", "", ""])
        w.writerow(["", "Contingency", "", "", f"{CONTINGENCY:.2f}", "", ""])
        w.writerow(["", "TOTAL", "", "", f"{total:.2f}", "", "cap 700.00"])
    print(f"subtotal {sub:.2f}  margin {margin:.2f}  total {total:.2f}")


if __name__ == "__main__":
    main(sys.argv[1])
