
import csv
import math
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt

# Add project root to Python path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.terrain.dem_loader import load_dem_terrain
from backend.terrain.projection import lonlat_to_xy

from backend.visibility.site_visibility import (
    earth_visibility_for_site,
)


# ============================================================
# PHASE 8: THREE-SITE EARTH VISIBILITY STUDY
# ============================================================

SITES = {
    "Shackleton Floor Candidate": (-89.73391, 122.03549),
    "Shackleton Rim Candidate": (-89.67869, -163.05292),
    "Malapert Massif": (-85.99000, 0.12000),
}

START_UTC = "2026-11-14T00:00:00Z"
DURATION_DAYS = 28.0
STEP_MINUTES = 30.0

ANTENNA_HEIGHT_M = 2.0
MAX_RANGE_M = 40000.0
AZIMUTH_STEP_DEG = 0.5
DISC_POINTS = 400

OUTPUT_DIR = (
    PROJECT_ROOT / "docs" / "phase8_results"
)


def get_dem_site_elevation(lat_deg, lon_deg):
    """Get the interpolated site elevation from NASA LOLA."""

    terrain = load_dem_terrain(
        lat_deg=lat_deg,
        lon_deg=lon_deg,
        half_size_m=MAX_RANGE_M * 1.1 + 1000.0,
    )

    x, y = lonlat_to_xy(lat_deg, lon_deg)

    elevation = float(terrain.height_at(x, y))

    if not math.isfinite(elevation):
        raise ValueError(
            f"Could not determine DEM elevation at "
            f"{lat_deg}, {lon_deg}."
        )

    return elevation


def write_site_csv(site_name, samples):
    """Write one site's complete time-series results."""

    safe_name = (
        site_name.lower()
        .replace(" ", "_")
        .replace("-", "_")
    )

    output_path = (
        OUTPUT_DIR / f"{safe_name}_visibility.csv"
    )

    fields = [
        "utc",
        "azimuth_deg",
        "elevation_deg",
        "angular_radius_deg",
        "horizon_at_centre_deg",
        "margin_deg",
        "visible_fraction",
        "centre_visible",
        "any_part_visible",
        "fully_visible",
        "blocked",
        "coverage_complete",
        "centre_coverage_complete",
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
            extrasaction="ignore",
        )

        writer.writeheader()
        writer.writerows(samples)

    return output_path


def write_combined_csv(all_results):
    """Write all sites into one combined CSV."""

    output_path = (
        OUTPUT_DIR / "phase8_all_sites_visibility.csv"
    )

    fields = [
        "site",
        "utc",
        "azimuth_deg",
        "elevation_deg",
        "angular_radius_deg",
        "horizon_at_centre_deg",
        "margin_deg",
        "visible_fraction",
        "centre_visible",
        "any_part_visible",
        "fully_visible",
        "blocked",
        "coverage_complete",
        "centre_coverage_complete",
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
        )

        writer.writeheader()

        for site_name, result in all_results.items():
            for sample in result["samples"]:
                row = {
                    "site": site_name,
                    **sample,
                }

                writer.writerow(row)

    return output_path



def write_summary_csv(all_results):
    """Write one summary row per study location."""

    output_path = (
        OUTPUT_DIR / "phase8_visibility_summary.csv"
    )

    fields = [
        "site",
        "latitude_deg",
        "longitude_deg",
        "elevation_m",
        "sample_count",
        "mean_visible_fraction",
        "percent_any_part_visible",
        "percent_centre_visible",
        "percent_fully_visible",
        "percent_blocked",
        "samples_with_incomplete_terrain",
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
        )

        writer.writeheader()

        for site_name, result in all_results.items():
            site = result["site"]
            summary = result["visibility_summary"]

            writer.writerow({
                "site": site_name,
                "latitude_deg": site["latitude_deg"],
                "longitude_deg": site["longitude_deg"],
                "elevation_m": site["terrain_elevation_m"],
                "sample_count": summary["samples"],
                "mean_visible_fraction": (
                    summary["mean_visible_fraction"]
                ),
                "percent_any_part_visible": (
                    summary["percent_any_part_visible"]
                ),
                "percent_centre_visible": (
                    summary["percent_centre_visible"]
                ),
                "percent_fully_visible": (
                    summary["percent_fully_visible"]
                ),
                "percent_blocked": (
                    summary["percent_blocked"]
                ),
                "samples_with_incomplete_terrain": (
                    summary["samples_with_incomplete_terrain"]
                ),
            })

    return output_path



def write_timeline_plot(all_results):
    """Plot visible Earth-disc fraction for all three sites."""

    output_path = (
        OUTPUT_DIR / "phase8_visibility_timeline.png"
    )

    plt.figure(figsize=(14, 7))

    for site_name, result in all_results.items():
        samples = result["samples"]

        times = [
            datetime.fromisoformat(
                sample["utc"].replace("Z", "+00:00")
            )
            for sample in samples
        ]

        fractions = [
            sample["visible_fraction"]
            for sample in samples
        ]

        plt.plot(
            times,
            fractions,
            label=site_name,
            linewidth=1.5,
        )

    plt.xlabel("UTC")
    plt.ylabel("Visible fraction of Earth's disc")
    plt.title(
        "Phase 8 — Terrain-Aware Earth Visibility "
        "at Three Lunar Sites"
    )

    plt.ylim(-0.05, 1.05)
    plt.yticks([
        0.0,
        0.25,
        0.50,
        0.75,
        1.0,
    ])

    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.xticks(rotation=30)
    plt.tight_layout()

    plt.savefig(
        output_path,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close()

    return output_path


def main():
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_results = {}

    print("=" * 72)
    print("PHASE 8 — THREE-SITE EARTH VISIBILITY STUDY")
    print("=" * 72)

    print(f"Start UTC: {START_UTC}")
    print(f"Duration: {DURATION_DAYS} days")
    print(f"Time interval: {STEP_MINUTES} minutes")
    print(f"Earth-disc samples: {DISC_POINTS}")
    print(f"Horizon azimuth spacing: {AZIMUTH_STEP_DEG} degrees")
    print(f"Terrain range: {MAX_RANGE_M / 1000:.1f} km")

    for site_name, (lat, lon) in SITES.items():
        print("\n" + "-" * 72)
        print(f"SITE: {site_name}")
        print(f"Coordinates: {lat}, {lon}")

        elevation = get_dem_site_elevation(lat, lon)

        print(f"DEM site elevation: {elevation:.3f} m")
        print("Calculating Earth visibility...")

        result = earth_visibility_for_site(
            lat_deg=lat,
            lon_deg=lon,
            height_m=elevation,
            start_utc=START_UTC,
            duration_days=DURATION_DAYS,
            step_minutes=STEP_MINUTES,
            antenna_height_m=ANTENNA_HEIGHT_M,
            max_range_m=MAX_RANGE_M,
            azimuth_step_deg=AZIMUTH_STEP_DEG,
            n_disc_points=DISC_POINTS,
        )

        all_results[site_name] = result

        summary = result["visibility_summary"]

        print(f"Samples: {result['sample_count']}")
        print(
            "Mean visible fraction: "
            f"{summary['mean_visible_fraction']:.4f}"
        )
        print(
            "Any part visible: "
            f"{summary['percent_any_part_visible']:.2f}%"
        )
        print(
            "Centre visible: "
            f"{summary['percent_centre_visible']:.2f}%"
        )
        print(
            "Fully visible: "
            f"{summary['percent_fully_visible']:.2f}%"
        )
        print(
            "Blocked: "
            f"{summary['percent_blocked']:.2f}%"
        )
        print(
            "Incomplete terrain samples: "
            f"{summary['samples_with_incomplete_terrain']}"
        )

        csv_path = write_site_csv(
            site_name,
            result["samples"],
        )

        print(f"Site CSV: {csv_path}")

    print("\n" + "-" * 72)
    print("SAVING COMBINED RESULTS")

    combined_path = write_combined_csv(all_results)
    summary_path = write_summary_csv(all_results)
    plot_path = write_timeline_plot(all_results)

    print(f"Combined CSV: {combined_path}")
    print(f"Summary CSV: {summary_path}")
    print(f"Timeline PNG: {plot_path}")

    print("\n" + "=" * 72)
    print("PHASE 8 THREE-SITE STUDY FINISHED")
    print("=" * 72)


if __name__ == "__main__":
    main()
