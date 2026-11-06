"""make_ollie_folder.py -- collect every OLLIE version, the prices and the plan into one folder.

Usage: python make_ollie_folder.py DEST            (e.g. %USERPROFILE%\\Desktop\\OLLIE)
Sources: the repo's .frcstack/out (current build) and the packages already in ~/Downloads (older
versions).  Re-run after any change; it overwrites files in DEST but never deletes anything else.
Writes an editable OLLIE-prices.xlsx (line totals and the total are live formulas)."""
import shutil
import sys
from pathlib import Path

import ollie_bom as B

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / ".frcstack" / "out"
DL = Path.home() / "Downloads"
FUSION = REPO / "skills" / "frcstack" / "fusion" / "OLLIE_joints"

VERSIONS = [
    # folder, date, parts, mass kg, total $, what changed
    ("v0-humanoid-700", "2026-11-01", 75, 2.8, 672.70,
     "Starting point: plain 20-servo biped, all PLA brackets, $700 cap."),
    ("v1-OLLIE-700", "2026-11-03", 95, 3.2, 700.00,
     "OLLIE look from the sketch; walk + heel-wheel skate + crawl; Fusion joint script."),
    ("v2-OLLIE-700", "2026-11-05", 166, 4.0, 700.00,
     "Human proportions, CNC 6061 plates (3 mm horn / 4 mm idler) + box-tube bones, R9-style fairings, "
     "3-finger hands, MuJoCo sim + renders.  Aluminium was assumed to be team stock ($0)."),
    ("v2.1-OLLIE-1000 (CURRENT)", "2026-11-06", 180, 4.0, None,
     "$1,000 cap, every part bought (team tools only); 6 STS3250 on hip roll/pitch + knee; "
     "break-detection sensor pack; all plates 1/8 in from one 12 x 24 in sheet (+14 printed spacer rings)."),
]
ALTERNATIVES = [
    # motor, unit $, source, torque, verdict
    ("Waveshare ST3215 (baseline)", 16.99, "waveshare.com", "30 kg.cm @ 12 V", "Used on 10 lower-load joints"),
    ("Feetech STS3250", 44.65, "alibaba.com Feetech store ($44.65-47.77)", "50 kg.cm @ 12 V, same case",
     "CHOSEN for hip roll, hip pitch, knee (6)"),
    ("Waveshare ST3025", 77.95, "waveshare.com ($79.99, $77.95 at 4+)", "40 kg.cm @ 12 V",
     "over the cap (see whole-robot totals below)"),
    ("ROBOTIS DYNAMIXEL XM540-W270-T", 482.89, "robotis.us", "industrial smart servo",
     "12 legs = $5,794.68: only as a sponsorship test"),
]
def scenarios():
    """Whole-robot totals (incl. 10 % ship/tax) if the leg motor choice changes, from the live BOM."""
    sub = B.totals()[0]
    st, sts, st25 = 16.99, 44.65, 77.95
    rows = [("Chosen plan: 6 STS3250 + 10 ST3215", sub),
            ("All ST3215 (no upgrade)", sub - 6 * (sts - st)),
            ("STS3250 on all 12 leg joints", sub + 6 * (sts - st)),
            ("6 ST3025 instead of the 6 STS3250", sub + 6 * (st25 - sts))]
    return [(n, round(s * (1 + B.SHIP_TAX), 2)) for n, s in rows]


def cp(src, dst):
    src, dst = Path(src), Path(dst)
    if not src.exists():
        print("  missing (skipped):", src)
        return 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)
    return 1


def copy_versions(V):
    d = V / "v0-humanoid-700"
    for f in ("humanoid-700-plan.md", "humanoid-700-bom.csv", "humanoid-700-print-list.csv",
              "humanoid-700-report.json", "humanoid-700-stand.step", "humanoid-700-single-support-left.step"):
        cp(OUT / "humanoid" / f, d / f)
    cp(OUT / "humanoid" / "preview.png", d / "humanoid-700-preview.png")

    d = V / "v1-OLLIE-700"
    cp(DL / "OLLIE", d)
    cp(DL / "ollie-concept-sketch-v1.png", d / "ollie-concept-sketch-v1.png")

    d = V / "v2-OLLIE-700"
    for f in ("ollie-v2-stand.step", "ollie-v2-skate.step", "ollie-v2-crawl.step", "ollie-v2-bom.csv",
              "ollie-v2-print-list.csv", "ollie-v2-report.json", "ollie-v2-joints.json", "ollie-v2-preview.png"):
        cp(DL / "OLLIE-v2" / f, d / f)

    d = V / "v2.1-OLLIE-1000 (CURRENT)"
    src = OUT / "ollie-v2"
    for f in ("ollie-stand.step", "ollie-skate.step", "ollie-crawl.step", "ollie-print-list.csv",
              "ollie-report.json", "ollie-joints.json"):
        cp(src / f, d / f.replace("ollie-", "ollie-v2.1-"))
    cp(FUSION, d / "OLLIE_joints")
    cp(src / "ollie-joints.json", d / "OLLIE_joints" / "ollie-joints.json")


def copy_media(M):
    for f in ("hero", "front", "side", "back", "skate", "crawl", "xray", "callouts"):
        cp(DL / "OLLIE-v2" / f"ollie-v2-{f}.png", M / "renders" / f"ollie-{f}.png")
    cp(DL / "OLLIE-v2" / "ollie-v2-turntable.mp4", M / "videos" / "ollie-turntable.mp4")
    for f in ("demo", "walk", "skate", "crawl"):
        cp(DL / "OLLIE-v2" / f"ollie-v2-sim-{f}.mp4", M / "videos" / f"ollie-sim-{f}.mp4")
    cp(DL / "OLLIE-v2" / "OLLIE-5min-video-script.md", M / "OLLIE-5min-video-script.md")
    cp(DL / "ollie-concept-sketch-v1.png", M / "renders" / "ollie-concept-sketch-v1.png")


def prices_xlsx(path, total):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    head = Font(bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="1F3A8A")

    def header(ws, cols, widths):
        ws.append(cols)
        for i, w in enumerate(widths, 1):
            ws.cell(1, i).font, ws.cell(1, i).fill = head, fill
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A2"

    ws = wb.active
    ws.title = "BOM $1000"
    header(ws, ["Group", "Item", "Qty", "Unit $", "Line $", "Source", "Use"], [15, 60, 6, 9, 10, 38, 50])
    for c, it, q, u, src, note in B.BOM:
        r = ws.max_row + 1
        ws.append([c, it, q, u, f"=C{r}*D{r}", src, note])
    last = ws.max_row
    rs = last + 2                                   # one blank row, then the subtotal
    for i, row in enumerate([["", "Parts subtotal", "", "", f"=SUM(E2:E{last})"],
                             ["", "Shipping + tax", "", B.SHIP_TAX, f"=E{rs}*D{rs + 1}"],
                             ["", "TOTAL", "", "", f"=E{rs}+E{rs + 1}"],
                             ["", "Cap", "", "", B.BUDGET],
                             ["", "Left under cap", "", "", f"=E{rs + 3}-E{rs + 2}"]]):
        for j, v in enumerate(row, 1):
            ws.cell(rs + i, j, v)
    for r in range(2, ws.max_row + 1):
        for col in (4, 5):
            ws.cell(r, col).number_format = "$#,##0.00"
        ws.cell(r, 7).alignment = Alignment(wrap_text=True)
    ws.cell(rs + 1, 4).number_format = "0%"
    for r in (rs, rs + 2, rs + 4):
        ws.cell(r, 2).font = ws.cell(r, 5).font = Font(bold=True)

    ws = wb.create_sheet("By group")
    header(ws, ["Group", "$", "Share"], [18, 12, 10])
    sub = sum(q * u for _, _, q, u, _, _ in B.BOM)
    for g, v in sorted(B.by_cat().items(), key=lambda kv: -kv[1]):
        ws.append([g, round(v, 2), v / sub])
    for r in range(2, ws.max_row + 1):
        ws.cell(r, 2).number_format, ws.cell(r, 3).number_format = "$#,##0.00", "0%"

    ws = wb.create_sheet("Versions")
    header(ws, ["Version", "Date", "Parts", "Mass kg", "Total $", "What changed"], [26, 12, 7, 9, 10, 100])
    for v, dt, n, m, t, what in VERSIONS:
        ws.append([v, dt, n, m, total if t is None else t, what])
        ws.cell(ws.max_row, 5).number_format = "$#,##0.00"
        ws.cell(ws.max_row, 6).alignment = Alignment(wrap_text=True)

    ws = wb.create_sheet("Motor options")
    header(ws, ["Motor", "Unit $", "Source", "Torque", "Verdict"], [34, 10, 40, 28, 48])
    for row in ALTERNATIVES:
        ws.append(list(row))
        ws.cell(ws.max_row, 2).number_format = "$#,##0.00"
    ws.append([])
    ws.append(["Whole-robot total with...", "Total $"])
    ws.cell(ws.max_row, 1).font = ws.cell(ws.max_row, 2).font = Font(bold=True)
    for name, t in scenarios():
        ws.append([name, t])
        ws.cell(ws.max_row, 2).number_format = "$#,##0.00"
        ws.cell(ws.max_row, 3).value = "under cap" if t <= B.BUDGET else "OVER cap"

    ws = wb.create_sheet("If prices rise")
    header(ws, ["Cut", "Saves $ (incl. tax)", "Cost of cutting it"], [40, 18, 70])
    for c, v, why in B.FIRST_CUTS:
        ws.append([c, round(v * (1 + B.SHIP_TAX), 2), why])
        ws.cell(ws.max_row, 2).number_format = "$#,##0.00"
    ws.append([])
    ws.append(["Not counted in the $1,000:"])
    for n in B.NOT_COUNTED:
        ws.append([n])
    wb.save(path)


def readme(total, left):
    vrows = "\n".join(f"| {v} | {dt} | {n} | {m} | ${total if t is None else t:,.2f} | {what} |"
                      for v, dt, n, m, t, what in VERSIONS)
    return f"""# OLLIE: walk / skate / crawl humanoid

**Current version: v2.1, ${total:,.2f} total (${left:,.2f} under the $1,000 cap).**  Every part is bought;
the team's CNC router, printers and tools are used, nothing is taken from team stock.  Proposed design:
not built or tested yet.

## Folders
| Folder | What is in it |
|---|---|
| `01-Plan` | **Start here.** `OLLIE-1000-plan.md`: costs, motors, mode switching, break-detection sensors, CNC stock, build order, risks |
| `02-Prices` | `OLLIE-prices.xlsx` (editable: change a price or qty and the total updates), the same BOM as CSV, motor options compared, version cost history, what to cut if prices rise |
| `03-Versions` | Every design version with its CAD (STEP), parts list, checks report.  `v2.1-OLLIE-1000 (CURRENT)` is the one to build |
| `04-Media` | Renders, turntable, simulation videos, concept sketch, 5-minute video script |
| `05-Simulation` | `OLLIE-live-sim.bat`: live MuJoCo sim (1 walk, 2 skate, 3 crawl).  Runs from the FRCstack repo on this PC |

## Versions
| Version | Date | Parts | Mass kg | Total | What changed |
|---|---|---|---|---|---|
{vrows}

`03-Versions/VERSIONS.md` has the same history.

## Open the current CAD in Fusion
1. Open `03-Versions/v2.1-OLLIE-1000 (CURRENT)/ollie-v2.1-stand.step`.
2. Utilities > Add-Ins > Scripts > green **+** > pick the `OLLIE_joints` folder next to it > Run.  It adds the 22 motor joints.

## Notes
- Renders and videos were made from v2.  v2.1 only changes the idler plates (4 mm to 1/8 in, with a 1 mm
  printed spacer), so they look the same.
- Prices were checked 2026-11; lines marked "est." are estimates.  Recheck before ordering, and confirm the
  STS3250 price and shipping first.
- v2.1 CAD checks: 180 parts, 0 collisions and 0 floor hits in 11 poses; all 34 plates use about half the
  12 x 24 in sheet; the 4 bones fit in 2 ft of tube.
"""


def main(dest):
    D = Path(dest)
    D.mkdir(parents=True, exist_ok=True)
    B.check_bom()
    sub, tax, total = B.totals()
    fit = B.metal_fit(OUT / "ollie-v2" / "ollie-print-list.csv")
    plan = D / "01-Plan"
    plan.mkdir(exist_ok=True)
    (plan / "OLLIE-1000-plan.md").write_text(B.plan_md(sub, tax, total, fit), encoding="utf-8")
    pr = D / "02-Prices"
    pr.mkdir(exist_ok=True)
    B.write_csv(pr / "OLLIE-1000-bom.csv", sub, tax, total)
    prices_xlsx(pr / "OLLIE-prices.xlsx", total)
    for v, src in (("v0-humanoid-700", OUT / "humanoid" / "humanoid-700-bom.csv"),
                   ("v1-OLLIE-700", DL / "OLLIE" / "ollie-bom.csv"),
                   ("v2-OLLIE-700", DL / "OLLIE-v2" / "ollie-v2-bom.csv")):
        cp(src, pr / "older-versions" / f"{v}-bom.csv")
    V = D / "03-Versions"
    copy_versions(V)
    (V / "VERSIONS.md").write_text("# OLLIE versions\n\n| Version | Date | Parts | Mass kg | Total | What changed |\n"
                                   "|---|---|---|---|---|---|\n" + "\n".join(
                                       f"| {v} | {dt} | {n} | {m} | ${total if t is None else t:,.2f} | {w} |"
                                       for v, dt, n, m, t, w in VERSIONS) + "\n", encoding="utf-8")
    copy_media(D / "04-Media")
    cp(DL / "OLLIE-live-sim.bat", D / "05-Simulation" / "OLLIE-live-sim.bat")
    (D / "README.md").write_text(readme(total, B.BUDGET - total), encoding="utf-8")
    files = [p for p in D.rglob("*") if p.is_file()]
    print(f"{D}: {len(files)} files, {sum(p.stat().st_size for p in files) / 1e6:.0f} MB, total ${total:.2f}")


if __name__ == "__main__":
    main(sys.argv[1])
