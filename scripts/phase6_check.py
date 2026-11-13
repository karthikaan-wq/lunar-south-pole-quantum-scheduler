
import sys
import csv
import math
from pathlib import Path
from datetime import datetime

# Add project root to Python path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt

from backend.physics.kernels import (
    kernels_present,
    load_kernels,
)

from backend.physics.earth_geometry import earth_track


# ============================================================
# PHASE 6: EARTH DIRECTION AND ELEVATION VALIDATION
# ============================================================

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

START_UTC = "2026-11-13T00:00:00Z"
DURATION_DAYS = 1.0
STEP_MINUTES = 5.0

EXPECTED_SAMPLE_COUNT = 289

OUTPUT_DIR = PROJECT_ROOT / "docs" / "phase6_results"


def parse_sample_time(utc):
    """Convert a SPICE UTC timestamp into datetime."""
    return datetime.fromisoformat(
        utc.replace("Z", "+00:00")
    )


def validate_track(site, track):
    """Validate one site's Earth tracking results."""

    samples = track["samples"]
    summary = track["summary"]

    assert len(samples) == EXPECTED_SAMPLE_COUNT
    assert track["sample_count"] == EXPECTED_SAMPLE_COUNT
    assert summary["sample_count"] == EXPECTED_SAMPLE_COUNT

    assert samples[0]["utc"] == track["start_utc"]
    assert samples[-1]["utc"] == track["end_utc"]

    previous_time = None

    for sample in samples:
        numeric_fields = [
            "azimuth_deg",
            "elevation_deg",
            "distance_km",
            "angular_radius_deg",
            "upper_limb_elevation_deg",
            "lower_limb_elevation_deg",
        ]

        for field in numeric_fields:
            assert math.isfinite(float(sample[field])), (
                f"Invalid {field} at {sample['utc']}"
            )

        assert 0.0 <= sample["azimuth_deg"] < 360.0

        assert -90.0 <= sample["elevation_deg"] <= 90.0

        assert 300000.0 < sample["distance_km"] < 500000.0

        assert sample["angular_radius_deg"] > 0.0

        assert (
            sample["upper_limb_elevation_deg"]
            > sample["elevation_deg"]
        )

        assert (
            sample["lower_limb_elevation_deg"]
            < sample["elevation_deg"]
        )

        current_time = parse_sample_time(sample["utc"])

        if previous_time is not None:
            assert current_time > previous_time

        previous_time = current_time

    assert track["correction"] == "NONE"
    assert track["horizon_model"] == "flat"

    return True


def save_csv(site, track):
    """Save all Earth tracking samples to CSV."""

    filename = (
        site["name"].lower()
        .replace(" ", "_")
        .replace("-", "_")
    )

    output_path = OUTPUT_DIR / f"{filename}_earth_track.csv"

    fields = [
        "utc",
        "elapsed_hours",
        "azimuth_deg",
        "elevation_deg",
        "distance_km",
        "angular_radius_deg",
        "upper_limb_elevation_deg",
        "lower_limb_elevation_deg",
    ]

    start_time = parse_sample_time(track["start_utc"])

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as csv_file:

        writer = csv.DictWriter(
            csv_file,
            fieldnames=fields,
        )

        writer.writeheader()

        for sample in track["samples"]:
            current_time = parse_sample_time(sample["utc"])

            elapsed_hours = (
                current_time - start_time
            ).total_seconds() / 3600.0

            row = {
                field: sample[field]
                for field in fields
                if field != "elapsed_hours"
            }

            row["elapsed_hours"] = elapsed_hours

            writer.writerow(row)

    return output_path


def save_plot(site, track):
    """Generate Earth's apparent elevation plot."""

    filename = (
        site["name"].lower()
        .replace(" ", "_")
        .replace("-", "_")
    )

    output_path = OUTPUT_DIR / f"{filename}_earth_elevation.png"

    start_time = parse_sample_time(track["start_utc"])

    elapsed_hours = []
    centre = []
    upper = []
    lower = []

    for sample in track["samples"]:
        current_time = parse_sample_time(sample["utc"])

        hours = (
            current_time - start_time
        ).total_seconds() / 3600.0

        elapsed_hours.append(hours)
        centre.append(sample["elevation_deg"])
        upper.append(sample["upper_limb_elevation_deg"])
        lower.append(sample["lower_limb_elevation_deg"])

    plt.figure(figsize=(12, 6))

    plt.plot(
        elapsed_hours,
        centre,
        label="Earth centre elevation",
        linewidth=2,
    )

    plt.plot(
        elapsed_hours,
        upper,
        label="Earth upper limb",
        linestyle="--",
    )

    plt.plot(
        elapsed_hours,
        lower,
        label="Earth lower limb",
        linestyle="--",
    )

    plt.axhline(
        y=0,
        linestyle=":",
        linewidth=1.5,
        label="Flat horizon",
    )

    plt.title(
        f"Earth Apparent Elevation - {site['name']}"
    )

    plt.xlabel("Elapsed time (hours)")
    plt.ylabel("Elevation (degrees)")

    plt.xlim(0, DURATION_DAYS * 24)

    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()

    plt.savefig(
        output_path,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close()

    return output_path


def main():
    print("=" * 75)
    print("PHASE 6: EARTH DIRECTION AND TRACK VALIDATION")
    print("=" * 75)

    if not kernels_present():
        raise RuntimeError(
            "NASA SPICE kernels are missing. "
            "Run scripts/download_kernels.py first."
        )

    load_kernels()

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_lines = [
        "PHASE 6 VALIDATION RESULTS",
        "=" * 60,
        f"Start UTC: {START_UTC}",
        f"Duration: {DURATION_DAYS} days",
        f"Sampling interval: {STEP_MINUTES} minutes",
        f"Expected samples per site: {EXPECTED_SAMPLE_COUNT}",
        "Aberration correction: NONE",
        "Horizon model: flat",
        "",
    ]

    total_samples = 0

    for site in SITES:
        print("\n" + "=" * 75)
        print(f"SITE: {site['name']}")
        print("=" * 75)

        print(
            f"Latitude:  {site['latitude_deg']} degrees\n"
            f"Longitude: {site['longitude_deg']} degrees\n"
            f"Height:    {site['height_m']} metres"
        )

        track = earth_track(
            lat_deg=site["latitude_deg"],
            lon_deg=site["longitude_deg"],
            height_m=site["height_m"],
            start_utc=START_UTC,
            duration_days=DURATION_DAYS,
            step_minutes=STEP_MINUTES,
        )

        validate_track(site, track)

        summary = track["summary"]

        csv_path = save_csv(site, track)
        plot_path = save_plot(site, track)

        total_samples += track["sample_count"]

        print(f"\nSamples: {track['sample_count']}")

        print(
            f"Earth distance: "
            f"{track['samples'][0]['distance_km']:.3f} km"
        )

        print(
            f"Angular radius: "
            f"{track['samples'][0]['angular_radius_deg']:.6f} degrees"
        )

        print(
            f"Minimum elevation: "
            f"{summary['minimum_elevation_deg']:.6f} degrees"
        )

        print(
            f"Maximum elevation: "
            f"{summary['maximum_elevation_deg']:.6f} degrees"
        )

        print(
            "Earth centre above flat horizon samples: "
            f"{summary['earth_centre_above_flat_horizon_samples']}"
        )

        print(
            "Earth disc intersects flat horizon samples: "
            f"{summary['earth_disc_intersects_flat_horizon_samples']}"
        )

        print(
            "Earth disc entirely above flat horizon samples: "
            f"{summary['earth_disc_entirely_above_flat_horizon_samples']}"
        )

        print(f"\nCSV saved: {csv_path}")
        print(f"Plot saved: {plot_path}")

        report_lines.extend([
            f"SITE: {site['name']}",
            f"Latitude: {site['latitude_deg']}",
            f"Longitude: {site['longitude_deg']}",
            f"Height: {site['height_m']} m",
            f"Samples: {track['sample_count']}",
            f"Start UTC: {track['start_utc']}",
            f"End UTC: {track['end_utc']}",
            f"Minimum elevation: {summary['minimum_elevation_deg']:.6f} deg",
            f"Maximum elevation: {summary['maximum_elevation_deg']:.6f} deg",
            f"Minimum lower limb: {summary['minimum_lower_limb_elevation_deg']:.6f} deg",
            f"Maximum upper limb: {summary['maximum_upper_limb_elevation_deg']:.6f} deg",
            f"Centre above horizon samples: {summary['earth_centre_above_flat_horizon_samples']}",
            f"Disc intersects horizon samples: {summary['earth_disc_intersects_flat_horizon_samples']}",
            f"Disc entirely above horizon samples: {summary['earth_disc_entirely_above_flat_horizon_samples']}",
            f"CSV: {csv_path.name}",
            f"Plot: {plot_path.name}",
            "",
        ])

        print("\nAll checks passed for this site.")

    report_lines.extend([
        "=" * 60,
        "PHASE 6 VALIDATION COMPLETED",
        f"Sites tested: {len(SITES)}",
        f"Total samples: {total_samples}",
        "All numerical and tracking checks passed.",
    ])

    report_path = OUTPUT_DIR / "phase6_validation_results.txt"

    report_path.write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    print("\n" + "=" * 75)
    print("PHASE 6 NUMERICAL VALIDATION COMPLETED")
    print("=" * 75)

    print(f"Sites tested: {len(SITES)}")
    print(f"Total samples: {total_samples}")
    print(f"Results directory: {OUTPUT_DIR}")
    print(f"Validation report: {report_path}")

    print("\nAll numerical, tracking and plotting checks passed.")


if __name__ == "__main__":
    main()
