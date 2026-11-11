
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import spiceypy as spice

# Add the project root to Python's import path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.physics.kernels import load_kernels
from backend.physics.time_system import to_et
from backend.physics.ephemeris import earth_moon_state
from backend.physics.lunar_frames import horizons_sub_observer_point


# JPL Horizons reference values
HORIZONS_DATA = [
    {
        "utc": "2026-11-10 00:00",
        "longitude": 3.450226,
        "latitude": 6.565800,
        "distance_km": 399774.94303,
    },
    {
        "utc": "2026-11-10 06:00",
        "longitude": 3.228553,
        "latitude": 6.558380,
        "distance_km": 400439.92738,
    },
    {
        "utc": "2026-11-10 12:00",
        "longitude": 2.996085,
        "latitude": 6.532149,
        "distance_km": 401077.96353,
    },
    {
        "utc": "2026-11-10 18:00",
        "longitude": 2.752930,
        "latitude": 6.487372,
        "distance_km": 401686.44976,
    },
    {
        "utc": "2026-11-11 00:00",
        "longitude": 2.499249,
        "latitude": 6.424359,
        "distance_km": 402262.67869,
    },
]


def main():
    load_kernels()

    start = datetime(
        2026, 11, 10, 0, 0, 0,
        tzinfo=timezone.utc
    )

    print("\nSPICE vs JPL Horizons comparison")
    print("=" * 105)

    for sample, reference in enumerate(HORIZONS_DATA):

        moment = start + timedelta(hours=6 * sample)
        et = to_et(moment)

        # Method 1: Rover view (Moon observer -> Earth target)
        rover_result = earth_moon_state(moment)

        rover_lon = rover_result["sub_earth_lon_deg"]
        rover_lat = rover_result["sub_earth_lat_deg"]

        # Method 2: Earth observer -> Moon target
        # Converted into the Moon-to-Earth direction
        horizons_lon, horizons_lat = horizons_sub_observer_point(et)

        # Calculate apparent Earth-Moon distance
        apparent_position, light_time = spice.spkpos(
            "MOON",
            et,
            "J2000",
            "LT",
            "EARTH"
        )

        apparent_distance = (
            sum(value * value for value in apparent_position) ** 0.5
        )

        # Calculate coordinate differences
        rover_lon_diff = rover_lon - reference["longitude"]
        rover_lat_diff = rover_lat - reference["latitude"]

        horizons_lon_diff = horizons_lon - reference["longitude"]
        horizons_lat_diff = horizons_lat - reference["latitude"]

        # Distance differences
        geometric_diff = (
            rover_result["distance_km"] - reference["distance_km"]
        )

        apparent_diff = apparent_distance - reference["distance_km"]

        print(f"\nUTC: {moment.strftime('%Y-%m-%d %H:%M')}")
        print("-" * 105)

        print("METHOD 1: ROVER VIEW")
        print(f"  SPICE longitude: {rover_lon:.6f} deg")
        print(f"  SPICE latitude:  {rover_lat:.6f} deg")
        print(f"  Longitude difference: {rover_lon_diff:+.6f} deg")
        print(f"  Latitude difference:  {rover_lat_diff:+.6f} deg")

        print("\nMETHOD 2: HORIZONS COMPARISON")
        print(f"  SPICE longitude: {horizons_lon:.6f} deg")
        print(f"  SPICE latitude:  {horizons_lat:.6f} deg")
        print(f"  Longitude difference: {horizons_lon_diff:+.6f} deg")
        print(f"  Latitude difference:  {horizons_lat_diff:+.6f} deg")

        print("\nJPL HORIZONS REFERENCE")
        print(f"  Longitude: {reference['longitude']:.6f} deg")
        print(f"  Latitude:  {reference['latitude']:.6f} deg")

        print("\nDISTANCE VALIDATION")
        print(f"  Geometric distance: {rover_result['distance_km']:.3f} km")
        print(f"  Horizons distance:  {reference['distance_km']:.3f} km")
        print(f"  Geometric difference: {geometric_diff:+.3f} km")
        print(f"  Apparent distance: {apparent_distance:.3f} km")
        print(f"  Apparent difference: {apparent_diff:+.3f} km")
        print(f"  SPICE light time: {light_time:.6f} seconds")

    print("\n" + "=" * 105)
    print("Comparison completed.")
    print("SPICE source: DE440s")
    print("Horizons source: DE441")
    print("Coordinate frame: MOON_ME_DE440_ME421")
    print("")


if __name__ == "__main__":
    main()
