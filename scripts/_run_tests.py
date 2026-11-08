"""
Standalone test runner for drivetrain tests - no pytest required.
"""
import json
import os
import sys
import traceback

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO_ROOT, '.frcstack', 'drivetrain-10min-20261108')
RESULT_PATH = os.path.join(OUT_DIR, 'result.json')
VALIDATION_PATH = os.path.join(OUT_DIR, 'validation.json')
BOM_PATH = os.path.join(OUT_DIR, 'bom.json')
STEP_PATH = os.path.join(OUT_DIR, 'am14u6_2026_drivetrain.step')
SOURCE_REF = os.path.join(REPO_ROOT, '.frcstack', 'source-cache', 'KB-2026-rev.step')
SCRIPT_PATH = os.path.join(REPO_ROOT, 'scripts', 'drivetrain_2026.py')

passed = []
failed = []
skipped = []

def check(name, fn):
    try:
        result = fn()
        if result == 'SKIP':
            skipped.append(name)
            print(f"  SKIP  {name}")
        else:
            passed.append(name)
            print(f"  PASS  {name}")
    except Exception as e:
        failed.append((name, str(e)))
        print(f"  FAIL  {name}: {e}")

print("=== Drivetrain Readiness Tests ===\n")

# -- Artifact existence --
check("step_exists", lambda: (
    None if os.path.exists(STEP_PATH) and os.path.getsize(STEP_PATH) > 50000
    else (_ for _ in ()).throw(AssertionError(f"STEP missing or too small"))
))

def _step_exists():
    assert os.path.exists(STEP_PATH), f"STEP not found: {STEP_PATH}"
    assert os.path.getsize(STEP_PATH) > 50_000
check("step_exists", _step_exists)

def _result_exists():
    assert os.path.exists(RESULT_PATH)
check("result_json_exists", _result_exists)

def _val_exists():
    assert os.path.exists(VALIDATION_PATH)
check("validation_json_exists", _val_exists)

def _bom_exists():
    assert os.path.exists(BOM_PATH)
check("bom_json_exists", _bom_exists)

def _script_exists():
    assert os.path.exists(SCRIPT_PATH)
check("source_script_exists", _script_exists)

# -- Generated vs sourced --
def _not_copy():
    if not os.path.exists(SOURCE_REF):
        return 'SKIP'
    gen_size = os.path.getsize(STEP_PATH)
    src_size = os.path.getsize(SOURCE_REF)
    assert gen_size != src_size, "Same size as source reference"
    assert src_size > 10_000_000
    assert gen_size < src_size, f"gen={gen_size} src={src_size}"
check("step_not_copy_of_source", _not_copy)

def _step_format():
    with open(STEP_PATH, 'r', errors='replace') as f:
        h = f.read(300)
    assert 'ISO-10303-21' in h
    assert 'HEADER' in h
check("step_valid_format", _step_format)

def _step_data():
    with open(STEP_PATH, 'r', errors='replace') as f:
        content = f.read()
    assert 'DATA;' in content
    n = sum(1 for l in content.splitlines() if l.startswith('#'))
    assert n > 100, f"Only {n} entities"
check("step_has_data_entities", _step_data)

# -- Result.json --
def _result_complete():
    r = json.load(open(RESULT_PATH))
    assert r['status'] == 'complete', r['status']
check("result_status_complete", _result_complete)

def _result_sourced_vs_gen():
    r = json.load(open(RESULT_PATH))
    svg = r.get('sourced_vs_generated', {})
    assert 'sourced_reference' in svg
    assert 'generated_new_parts' in svg
    assert len(svg['generated_new_parts']) >= 5
    assert 'NOT copied' in svg['sourced_reference'] or 'source-cache' in svg['sourced_reference']
check("result_sourced_vs_generated", _result_sourced_vs_gen)

# -- Validation.json --
def _val_pass():
    v = json.load(open(VALIDATION_PATH))
    assert v.get('overall_pass') is True
check("validation_overall_pass", _val_pass)

def _six_wheels():
    v = json.load(open(VALIDATION_PATH))
    assert v['wheel_count']['found'] == 6
    assert v['wheel_count']['pass'] is True
check("six_wheels", _six_wheels)

def _motors():
    v = json.load(open(VALIDATION_PATH))
    assert v['motors']['left'] is True
    assert v['motors']['right'] is True
    assert v['motors']['pass'] is True
check("left_right_motors", _motors)

def _gearboxes():
    v = json.load(open(VALIDATION_PATH))
    assert v['gearboxes']['left'] is True
    assert v['gearboxes']['right'] is True
check("gearboxes", _gearboxes)

def _sprockets():
    v = json.load(open(VALIDATION_PATH))
    assert v['transmission']['sprocket_count'] >= 4
    assert v['transmission']['pass'] is True
check("transmission_sprockets", _sprockets)

def _rails():
    v = json.load(open(VALIDATION_PATH))
    assert v['chassis_rails']['count'] >= 4
    assert v['chassis_rails']['pass'] is True
check("chassis_rails", _rails)

def _drop_center():
    v = json.load(open(VALIDATION_PATH))
    dc = v.get('drop_center')
    assert dc is not None
    assert dc['pass'] is True, f"drop_mm={dc.get('drop_mm')} expected={dc.get('expected_drop_mm')}"
check("drop_center_geometry", _drop_center)

def _no_collision():
    v = json.load(open(VALIDATION_PATH))
    aabb = v.get('aabb_interference', {})
    assert aabb.get('gearbox_lr_no_collision') is True
check("aabb_gearbox_no_collision", _no_collision)

def _bbox():
    v = json.load(open(VALIDATION_PATH))
    bbox = v.get('assembly_bbox_mm', {})
    dx = bbox.get('dx', 0)
    dy = bbox.get('dy', 0)
    assert 400 < dx < 900, f"dx={dx}"
    assert 400 < dy < 900, f"dy={dy}"
check("assembly_bbox_reasonable", _bbox)

# -- BOM --
def _bom_wheels():
    bom = json.load(open(BOM_PATH))
    items = [b for b in bom if 'Wheel' in b['item']]
    assert len(items) > 0
    total = sum(b['qty'] for b in items)
    assert total == 6, f"total={total}"
check("bom_six_wheels", _bom_wheels)

def _bom_motors():
    bom = json.load(open(BOM_PATH))
    items = [b for b in bom if 'Motor' in b['item'] or 'CIM' in b['item']]
    assert len(items) > 0
    total = sum(b['qty'] for b in items)
    assert total >= 2, f"total={total}"
check("bom_motors", _bom_motors)

def _bom_urls():
    bom = json.load(open(BOM_PATH))
    all_notes = ' '.join(b.get('notes', '') for b in bom)
    assert 'andymark.com' in all_notes.lower()
check("bom_source_urls", _bom_urls)

# -- Summary --
print(f"\n{'='*40}")
print(f"Results: {len(passed)} passed, {len(failed)} failed, {len(skipped)} skipped")
if failed:
    print("\nFailed:")
    for name, err in failed:
        print(f"  FAIL {name}: {err}")
    sys.exit(1)
else:
    print("All checks passed.")
    sys.exit(0)
