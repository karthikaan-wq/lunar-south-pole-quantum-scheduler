
import sys
from pathlib import Path

# Add the project root to Python's import path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np

from backend.physics.kernels import (
    kernels_present,
    load_kernels,
)
from backend.physics.time_system import (
    parse_utc,
    to_et,
)
from backend.physics.earth_geometry import lander_state


# --------------------------------------------------
# PHASE 5 VALIDATION
# Lunar lander position and Earth direction
# --------------------------------------------------

SITES = [
    {
        "name": "Shackleton Rim",
        "latitude_deg": -89.9,
        "longitude_deg": 129.78,
        "height_m": 0.0,
    },
    {
        "name": "Malapert Massif",
        "latitude_deg": -85.99,
        "longitude_deg": 0.12,
        "height_m": 100.0,
    },
    {
        "name": "Chandrayaan-3 Landing Site",
        "latitude_deg": -69.37,
        "longitude_deg": 32.32,
        "height_m": 0.0,
    },
]

DATES = [
    "2026-11-13T00:00:00Z",
    "2026-11-20T00:00:00Z",
    "2026-11-27T00:00:00Z",
    "2026-12-04T00:00:00Z",
]


def validate_lander_state(site, utc):
    """Calculate and validate one lander state."""

    moment = parse_utc(utc)
    et = to_et(moment)

    result = lander_state(
        lat_deg=site["latitude_deg"],
        lon_deg=site["longitude_deg"],
        height_m=site["height_m"],
        et=et,
    )

    moon_position = np.array(
        result["moon_fixed_position_km"]
    )

    j2000_position = np.array(
        result["j2000_position_km"]
    )

    earth_j2000 = result["earth_from_lander_j2000"]
    earth_moon = result["earth_from_lander_moon_fixed"]

    distance_j2000 = earth_j2000["distance_km"]
    distance_moon = earth_moon["distance_km"]

    # Check position vectors.
    assert moon_position.shape == (3,)
    assert j2000_position.shape == (3,)

    assert np.all(np.isfinite(moon_position))
    assert np.all(np.isfinite(j2000_position))

    # Check physically plausible Earth distance.
    assert 300000 < distance_j2000 < 500000

    # Both reference frames must produce the same distance.
    assert abs(distance_j2000 - distance_moon) < 1e-5

    # Check local East, North and Up unit vectors.
    axes = result["local_axes_j2000"]

    for axis_name in ("east", "north", "up"):
        axis = np.array(axes[axis_name])

        assert axis.shape == (3,)
        assert np.all(np.isfinite(axis))
        assert abs(np.linalg.norm(axis) - 1.0) < 1e-10

    # Check Earth direction unit vectors.
    unit_j2000 = np.array(earth_j2000["unit_vector"])
    unit_moon = np.array(earth_moon["unit_vector"])

    assert abs(np.linalg.norm(unit_j2000) - 1.0) < 1e-10
    assert abs(np.linalg.norm(unit_moon) - 1.0) < 1e-10

    return result


def main():
    print("=" * 75)
    print("PHASE 5: LUNAR LANDER GEOMETRY VALIDATION")
    print("=" * 75)

    if not kernels_present():
        raise RuntimeError(
            "NASA SPICE kernels are missing. "
            "Run scripts/download_kernels.py first."
        )

    load_kernels()

    total_checks = 0

    for site in SITES:
        print(f"\nSITE: {site['name']}")
        print("-" * 75)

        print(
            f"Latitude:  {site['latitude_deg']} degrees\n"
            f"Longitude: {site['longitude_deg']} degrees\n"
            f"Height:    {site['height_m']} metres"
        )

        for utc in DATES:
            result = validate_lander_state(site, utc)

            earth_j2000 = result["earth_from_lander_j2000"]
            earth_moon = result["earth_from_lander_moon_fixed"]

            print(f"\nUTC: {utc}")

            print(
                "Moon-fixed position (km):",
                np.round(
                    result["moon_fixed_position_km"], 3
                ),
            )

            print(
                "J2000 position (km):",
                np.round(
                    result["j2000_position_km"], 3
                ),
            )

            print(
                f"Earth distance (J2000): "
                f"{earth_j2000['distance_km']:.6f} km"
            )

            print(
                f"Earth distance (Moon-fixed): "
                f"{earth_moon['distance_km']:.6f} km"
            )

            print(
                "Earth direction (Moon-fixed):",
                np.round(
                    earth_moon["unit_vector"], 6
                ),
            )

            total_checks += 1

    print("\n" + "=" * 75)
    print("PHASE 5 VALIDATION COMPLETED")
    print("=" * 75)

    print(f"Sites tested: {len(SITES)}")
    print(f"Dates tested per site: {len(DATES)}")
    print(f"Successful lander-state checks: {total_checks}")

    print("\nAll position, direction and distance checks passed.")


if __name__ == "__main__":
    main()
