"""
tests/test_drivetrain_2026.py
Readiness test for AM14U6 2026 drivetrain build.
Distinguishes sourced assembly vs generated additions.
"""
import json
import os
import sys
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO_ROOT, '.frcstack', 'drivetrain-10min-20261108')
RESULT_PATH = os.path.join(OUT_DIR, 'result.json')
VALIDATION_PATH = os.path.join(OUT_DIR, 'validation.json')
BOM_PATH = os.path.join(OUT_DIR, 'bom.json')
STEP_PATH = os.path.join(OUT_DIR, 'am14u6_2026_drivetrain.step')
SOURCE_REF = os.path.join(REPO_ROOT, '.frcstack', 'source-cache', 'KB-2026-rev.step')
SCRIPT_PATH = os.path.join(REPO_ROOT, 'scripts', 'drivetrain_2026.py')


# ---- Artifact existence ----

def test_step_exists():
    """STEP file must exist and be non-trivial in size."""
    assert os.path.exists(STEP_PATH), f"STEP not found: {STEP_PATH}"
    size = os.path.getsize(STEP_PATH)
    assert size > 50_000, f"STEP too small ({size} bytes), likely empty"


def test_result_json_exists():
    assert os.path.exists(RESULT_PATH)


def test_validation_json_exists():
    assert os.path.exists(VALIDATION_PATH)


def test_bom_json_exists():
    assert os.path.exists(BOM_PATH)


def test_source_script_exists():
    assert os.path.exists(SCRIPT_PATH), "drivetrain_2026.py must exist in scripts/"


# ---- Generated vs sourced distinction ----

def test_step_not_copy_of_source_ref():
    """
    Generated STEP must NOT be a byte-for-byte copy of the source reference.
    The source KB-2026-rev.step is a full vendor file; our output is new geometry.
    """
    if not os.path.exists(SOURCE_REF):
        pytest.skip("Source reference not present, skip copy check")
    gen_size = os.path.getsize(STEP_PATH)
    src_size = os.path.getsize(SOURCE_REF)
    # Generated should be much smaller (custom parts, not full KitBot vendor)
    assert gen_size != src_size, "STEP appears to be copy of source reference (same size)"
    # Also verify source is substantially larger (vendor file is 50MB)
    assert src_size > 10_000_000, f"Source ref unexpectedly small: {src_size}"
    assert gen_size < src_size, "Generated STEP should be smaller than full vendor KB-2026"


def test_step_is_valid_step_format():
    """Check STEP file has correct ISO-10303-21 header."""
    with open(STEP_PATH, 'r', errors='replace') as f:
        header = f.read(200)
    assert 'ISO-10303-21' in header, "STEP file missing ISO-10303-21 header"
    assert 'HEADER' in header, "STEP file missing HEADER section"


def test_step_has_data_section():
    """STEP file must have a DATA section with actual geometry entities."""
    with open(STEP_PATH, 'r', errors='replace') as f:
        content = f.read()
    assert 'DATA;' in content, "STEP file missing DATA section"
    # Count entity lines (lines starting with #)
    entity_count = sum(1 for l in content.splitlines() if l.startswith('#'))
    assert entity_count > 100, f"Too few STEP entities ({entity_count}), geometry likely empty"


# ---- Result.json checks ----

def test_result_status():
    with open(RESULT_PATH) as f:
        result = json.load(f)
    assert result['status'] == 'complete', f"Build status: {result['status']}"


def test_result_has_sourced_vs_generated():
    """result.json must distinguish sourced reference vs generated parts."""
    with open(RESULT_PATH) as f:
        result = json.load(f)
    svg = result.get('sourced_vs_generated', {})
    assert 'sourced_reference' in svg, "Missing sourced_reference in result.json"
    assert 'generated_new_parts' in svg, "Missing generated_new_parts in result.json"
    assert len(svg['generated_new_parts']) >= 5, "Must document at least 5 generated parts"
    # Sourced ref must mention KB-2026 not in output
    assert 'NOT copied' in svg['sourced_reference'] or 'source-cache' in svg['sourced_reference']


# ---- Validation.json checks ----

def test_validation_overall_pass():
    with open(VALIDATION_PATH) as f:
        v = json.load(f)
    assert v.get('overall_pass') is True, f"Validation failed: {v}"


def test_six_wheels():
    with open(VALIDATION_PATH) as f:
        v = json.load(f)
    wc = v['wheel_count']
    assert wc['found'] == 6, f"Expected 6 wheels, found {wc['found']}"
    assert wc['pass'] is True


def test_left_right_motors():
    with open(VALIDATION_PATH) as f:
        v = json.load(f)
    motors = v['motors']
    assert motors['left'] is True, "Left motor missing"
    assert motors['right'] is True, "Right motor missing"
    assert motors['pass'] is True


def test_gearboxes():
    with open(VALIDATION_PATH) as f:
        v = json.load(f)
    gb = v['gearboxes']
    assert gb['left'] is True, "Left gearbox missing"
    assert gb['right'] is True, "Right gearbox missing"


def test_transmission_sprockets():
    with open(VALIDATION_PATH) as f:
        v = json.load(f)
    t = v['transmission']
    assert t['sprocket_count'] >= 4, f"Need >=4 sprockets, found {t['sprocket_count']}"
    assert t['pass'] is True


def test_chassis_rails():
    with open(VALIDATION_PATH) as f:
        v = json.load(f)
    r = v['chassis_rails']
    assert r['count'] >= 4, f"Need >=4 rails, found {r['count']}"
    assert r['pass'] is True


def test_drop_center_geometry():
    """Middle wheels must be ~1/8\" (3.175mm) lower than front/rear."""
    with open(VALIDATION_PATH) as f:
        v = json.load(f)
    dc = v.get('drop_center')
    assert dc is not None, "Drop-center check missing from validation"
    assert dc['pass'] is True, (
        f"Drop-center failed: got {dc.get('drop_mm')}mm, "
        f"expected {dc.get('expected_drop_mm')}mm"
    )


def test_aabb_gearbox_no_collision():
    """Left and right gearboxes must not collide (Y clearance > 0)."""
    with open(VALIDATION_PATH) as f:
        v = json.load(f)
    aabb = v.get('aabb_interference', {})
    assert aabb.get('gearbox_lr_no_collision') is True, (
        f"Gearbox L/R collision detected: {aabb}"
    )


def test_assembly_bbox_reasonable():
    """Assembly bounding box must match 26\"x26\" frame footprint roughly."""
    with open(VALIDATION_PATH) as f:
        v = json.load(f)
    bbox = v.get('assembly_bbox_mm', {})
    # Frame is 660.4mm square; with wheels sticking out, expect 600-800mm
    dx = bbox.get('dx', 0)
    dy = bbox.get('dy', 0)
    assert 400 < dx < 900, f"Assembly X extent {dx}mm unexpected for 26\" frame"
    assert 400 < dy < 900, f"Assembly Y extent {dy}mm unexpected for 26\" frame"


# ---- BOM checks ----

def test_bom_has_six_wheels():
    with open(BOM_PATH) as f:
        bom = json.load(f)
    wheel_items = [b for b in bom if 'Wheel' in b['item'] or 'wheel' in b['item']]
    assert len(wheel_items) > 0, "BOM missing wheel entry"
    total_wheels = sum(b['qty'] for b in wheel_items if 'Wheel' in b['item'])
    assert total_wheels == 6, f"BOM shows {total_wheels} wheels, expected 6"


def test_bom_has_motors():
    with open(BOM_PATH) as f:
        bom = json.load(f)
    motor_items = [b for b in bom if 'Motor' in b['item'] or 'CIM' in b['item'] or 'Falcon' in b['item']]
    assert len(motor_items) > 0, "BOM missing motor entry"
    total_motors = sum(b['qty'] for b in motor_items)
    assert total_motors >= 2, f"BOM shows {total_motors} motors, expected >=2"


def test_bom_source_urls():
    """BOM must reference AndyMark URL for base kit."""
    with open(BOM_PATH) as f:
        bom = json.load(f)
    all_notes = ' '.join(b.get('notes', '') for b in bom)
    assert 'andymark.com' in all_notes.lower(), "BOM missing AndyMark source URL"


if __name__ == '__main__':
    # Run directly for quick check
    import subprocess
    r = subprocess.run(
        [sys.executable, '-m', 'pytest', __file__, '-v', '--tb=short'],
        capture_output=False
    )
    sys.exit(r.returncode)
