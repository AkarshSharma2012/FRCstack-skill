"""Nominal FRC pitch geometry for layout sketches, in millimetres."""

import argparse
import json
import math


def _teeth(value):
    if type(value) is not int or value < 2:
        raise ValueError("Tooth counts must be integers of at least two")
    return value


def _positive(value, name):
    if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return value


def spur_layout(driver_teeth, driven_teeth, diametral_pitch):
    """Nominal center distance for two external spur gears of a common DP."""
    driver = _teeth(driver_teeth)
    driven = _teeth(driven_teeth)
    dp = _positive(diametral_pitch, "Diametral pitch")
    diameters = (25.4 * driver / dp, 25.4 * driven / dp)
    return {
        "pitch_diameters_mm": diameters,
        "center_distance_mm": sum(diameters) / 2,
        "reduction": driven / driver,
        "driven_revolutions_per_driver_revolution": -driver / driven,
    }


def open_belt_layout(driver_teeth, driven_teeth, belt_teeth, pitch_mm):
    """Solve the pitch line around two pulleys with external common tangents."""
    driver = _teeth(driver_teeth)
    driven = _teeth(driven_teeth)
    belt = _teeth(belt_teeth)
    pitch = _positive(pitch_mm, "Belt pitch")
    radii = (driver * pitch / math.tau, driven * pitch / math.tau)
    difference = abs(radii[0] - radii[1])
    target_length = belt * pitch

    def pitch_length(center):
        angle = math.asin(difference / center)
        span = math.sqrt((center - difference) * (center + difference))
        return 2 * span + math.pi * sum(radii) + 2 * difference * angle

    low, high = sum(radii), target_length / 2
    if target_length <= pitch_length(low):
        raise ValueError("Belt is too short for separated pulley pitch circles")
    for _ in range(60):
        center = (low + high) / 2
        if pitch_length(center) < target_length:
            low = center
        else:
            high = center
    center = (low + high) / 2
    small_wrap = math.pi - 2 * math.asin(difference / center)
    return {
        "pitch_diameters_mm": tuple(2 * radius for radius in radii),
        "pitch_length_mm": target_length,
        "center_distance_mm": center,
        "small_pulley_wrap_deg": math.degrees(small_wrap),
        "small_pulley_teeth_in_wrap": min(driver, driven) * small_wrap / math.tau,
        "reduction": driven / driver,
        "driven_revolutions_per_driver_revolution": driver / driven,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("spur", "belt"):
        entry = commands.add_parser(command)
        entry.add_argument("driver", type=int)
        entry.add_argument("driven", type=int)
        if command == "spur":
            entry.add_argument("--dp", type=float, required=True)
        else:
            entry.add_argument("--belt-teeth", type=int, required=True)
            entry.add_argument("--pitch-mm", type=float, required=True)
    args = parser.parse_args()
    try:
        if args.command == "spur":
            result = spur_layout(args.driver, args.driven, args.dp)
        else:
            result = open_belt_layout(
                args.driver, args.driven, args.belt_teeth, args.pitch_mm
            )
        print(json.dumps(result, indent=2, allow_nan=False))
    except (ValueError, OverflowError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
