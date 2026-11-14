
import math
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.physics.earth_geometry import earth_track
from backend.physics.sun_geometry import sun_at_times
from backend.communications.antenna import angular_separation_deg
from backend.terrain.dem_loader import load_dem_terrain
from backend.terrain.projection import lonlat_to_xy


# Use the Malapert Massif candidate from Phase 8.
LATITUDE_DEG = -85.99000
LONGITUDE_DEG = 0.12000

START_UTC = "2026-11-14T00:00:00Z"
DURATION_DAYS = 28.0
STEP_MINUTES = 1440.0  # One day

ANTENNA_HEIGHT_M = 2.0
MAX_RANGE_M = 40000.0


def get_dem_site_elevation():
    terrain = load_dem_terrain(
        lat_deg=LATITUDE_DEG,
        lon_deg=LONGITUDE_DEG,
        half_size_m=MAX_RANGE_M * 1.1 + 1000.0,
    )

    x, y = lonlat_to_xy(
        LATITUDE_DEG,
        LONGITUDE_DEG,
    )

    elevation = float(terrain.height_at(x, y))

    if not math.isfinite(elevation):
        raise ValueError("Invalid NASA LOLA site elevation.")

    return elevation


def main():
    print("=" * 76)
    print("PHASE 9 — SUN–EARTH ANGULAR SEPARATION VALIDATION")
    print("=" * 76)

    elevation = get_dem_site_elevation()
    observer_height = elevation + ANTENNA_HEIGHT_M

    print(f"Site latitude: {LATITUDE_DEG}")
    print(f"Site longitude: {LONGITUDE_DEG}")
    print(f"DEM elevation: {elevation:.3f} m")
    print(f"Antenna height: {ANTENNA_HEIGHT_M:.3f} m")
    print(f"Observer height: {observer_height:.3f} m")
    print()

    earth = earth_track(
        lat_deg=LATITUDE_DEG,
        lon_deg=LONGITUDE_DEG,
        height_m=observer_height,
        start_utc=START_UTC,
        duration_days=DURATION_DAYS,
        step_minutes=STEP_MINUTES,
    )

    earth_samples = earth["samples"]

    timestamps = [
        sample["utc"]
        for sample in earth_samples
    ]

    sun_samples = sun_at_times(
        lat_deg=LATITUDE_DEG,
        lon_deg=LONGITUDE_DEG,
        height_m=observer_height,
        time_strings=timestamps,
    )

    print(f"Number of timestamps: {len(timestamps)}")
    print()
    print("-" * 76)
    print(
        f"{'UTC':26} "
        f"{'Earth Az':>9} "
        f"{'Sun Az':>9} "
        f"{'Separation':>12}"
    )
    print("-" * 76)

    for earth_sample, sun_sample in zip(
        earth_samples,
        sun_samples,
    ):
        separation = angular_separation_deg(
            earth_sample["azimuth_deg"],
            earth_sample["elevation_deg"],
            sun_sample["azimuth_deg"],
            sun_sample["elevation_deg"],
        )

        print(
            f"{earth_sample['utc']:26} "
            f"{earth_sample['azimuth_deg']:9.3f} "
            f"{sun_sample['azimuth_deg']:9.3f} "
            f"{separation:11.3f}°"
        )

    print("-" * 76)
    print()
    print("Interpretation:")
    print(
        "A small separation means Earth and Sun appear "
        "in nearly the same direction from the lunar site."
    )
    print(
        "A separation near 180 degrees means they appear "
        "in nearly opposite directions."
    )
    print()
    print("Validation run completed.")


if __name__ == "__main__":
    main()
