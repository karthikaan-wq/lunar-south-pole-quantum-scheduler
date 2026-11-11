
from datetime import datetime, timedelta, timezone

from backend.physics.ephemeris import earth_moon_state
from backend.physics.kernels import load_kernels, KERNEL_DIR


def main():
    print("=" * 60)
    print("PHASE 4 - NASA SPICE VERIFICATION")
    print("=" * 60)

    print("\nKernel directory:", KERNEL_DIR)

    print("\nLoading NASA SPICE kernels...")
    load_kernels()
    print("All kernels loaded successfully.")

    start = datetime(
        2026, 11, 10, 0, 0,
        tzinfo=timezone.utc
    )

    samples = []

    print("\nCalculating Earth-Moon states...")
    print("-" * 60)

    # 56 samples at 12-hour intervals = 28 days
    for sample in range(56):
        moment = start + timedelta(hours=12 * sample)

        result = earth_moon_state(moment)
        samples.append(result)

        print(
            f"{result['utc']} | "
            f"Distance: {result['distance_km']:,.2f} km | "
            f"Lon: {result['sub_earth_lon_deg']:.3f} deg | "
            f"Lat: {result['sub_earth_lat_deg']:.3f} deg"
        )

    distances = [
        item["distance_km"] for item in samples
    ]

    longitudes = [
        item["sub_earth_lon_deg"] for item in samples
    ]

    latitudes = [
        item["sub_earth_lat_deg"] for item in samples
    ]

    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)

    print(
        f"Distance range: "
        f"{min(distances):,.2f} - {max(distances):,.2f} km"
    )

    print(
        f"Longitude range: "
        f"{min(longitudes):.3f} - {max(longitudes):.3f} deg"
    )

    print(
        f"Latitude range: "
        f"{min(latitudes):.3f} - {max(latitudes):.3f} deg"
    )

    print(
        f"First Earth angular radius: "
        f"{samples[0]['earth_angular_radius_deg']:.4f} deg"
    )

    print(
        f"First light travel time: "
        f"{samples[0]['light_time_s']:.4f} seconds"
    )

    print("\nData source:", samples[0]["source"])
    print("Moon frame:", samples[0]["moon_frame"])

    print("\nVerification script finished.")


if __name__ == "__main__":
    main()
