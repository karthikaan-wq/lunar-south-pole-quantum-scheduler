import csv
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.communications.site_windows import windows_for_site


OUTPUT_DIR = PROJECT_ROOT / "docs" / "phase10_results"

START_UTC = "2026-11-14T00:00:00Z"
DURATION_DAYS = 1.0
STEP_MINUTES = 60.0

COMMON_SETTINGS = {
    "start_utc": START_UTC,
    "duration_days": DURATION_DAYS,
    "step_minutes": STEP_MINUTES,
    "antenna_height_m": 2.0,
    "max_range_m": 40000.0,
    "azimuth_step_deg": 0.5,
    "n_disc_points": 400,
}

SITES = {
    "Shackleton": {
        "lat_deg": -89.9,
        "lon_deg": 129.78,
        "height_m": -337.9839796904814,
    },
    "Malapert": {
        "lat_deg": -85.99,
        "lon_deg": 0.12,
        "height_m": 4842.28,
    },
}


def parse_utc(value):
    """Convert an ISO UTC timestamp into a timezone-aware datetime."""
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def write_sample_csv(results):
    """Export flattened sample-level communication-link results."""

    fields = [
        "site",
        "utc",
        "link_available",
        "failed_checks",
        "first_failure",
        "terrain_coverage",
        "earth_visible_fraction_check",
        "earth_clearance_check",
        "antenna_pointing_check",
        "sun_exclusion_check",
        "earth_azimuth_deg",
        "earth_elevation_deg",
        "earth_visible_fraction",
        "earth_clearance_deg",
        "earth_terrain_coverage_complete",
        "sun_azimuth_deg",
        "sun_elevation_deg",
        "sun_angular_radius_deg",
        "sun_earth_separation_deg",
        "sun_upper_limb_elevation_deg",
        "sun_terrain_coverage_complete",
        "sun_in_view",
    ]

    path = OUTPUT_DIR / "phase10_all_sites_samples.csv"

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for site_name, result in results.items():
            for sample in result["samples"]:
                earth = sample["earth"]
                sun = sample["sun"]
                checks = sample["checks"]

                writer.writerow({
                    "site": site_name,
                    "utc": sample["utc"],
                    "link_available": sample["link_available"],
                    "failed_checks": ";".join(sample["failed_checks"]),
                    "first_failure": sample["first_failure"] or "",
                    "terrain_coverage": checks["terrain_coverage"],
                    "earth_visible_fraction_check": checks["earth_visible_fraction"],
                    "earth_clearance_check": checks["earth_clearance"],
                    "antenna_pointing_check": checks["antenna_pointing"],
                    "sun_exclusion_check": checks["sun_exclusion"],
                    "earth_azimuth_deg": earth["azimuth_deg"],
                    "earth_elevation_deg": earth["elevation_deg"],
                    "earth_visible_fraction": earth["visible_fraction"],
                    "earth_clearance_deg": earth["clearance_deg"],
                    "earth_terrain_coverage_complete": earth["terrain_coverage_complete"],
                    "sun_azimuth_deg": sun["azimuth_deg"],
                    "sun_elevation_deg": sun["elevation_deg"],
                    "sun_angular_radius_deg": sun["angular_radius_deg"],
                    "sun_earth_separation_deg": sun["separation_from_earth_deg"],
                    "sun_upper_limb_elevation_deg": sun["upper_limb_elevation_deg"],
                    "sun_terrain_coverage_complete": sun["terrain_coverage_complete"],
                    "sun_in_view": sun["in_view"],
                })

    print(f"Saved sample data: {path}")


def write_windows_csv(results):
    """Export refined windows and their observation-boundary flags."""

    fields = [
        "site",
        "window_id",
        "start_utc",
        "end_utc",
        "duration_s",
        "available_s",
        "bridged_gap_s",
        "starts_before_period",
        "ends_after_period",
        "clipped",
        "limiting_checks",
        "visible_fraction_mean",
        "visible_fraction_min",
        "visible_fraction_max",
        "clearance_deg_mean",
        "clearance_deg_min",
        "clearance_deg_max",
        "sun_earth_separation_deg_mean",
        "sun_earth_separation_deg_min",
        "sun_earth_separation_deg_max",
    ]

    path = OUTPUT_DIR / "phase10_windows.csv"

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for site_name, result in results.items():
            for window in result["windows"]:
                stats = window["stats"]
                visible = stats["visible_fraction"]
                clearance = stats["clearance_deg"]
                separation = stats["sun_earth_separation_deg"]

                writer.writerow({
                    "site": site_name,
                    "window_id": window["window_id"],
                    "start_utc": window["start_utc"],
                    "end_utc": window["end_utc"],
                    "duration_s": window["duration_s"],
                    "available_s": window["available_s"],
                    "bridged_gap_s": window["bridged_gap_s"],
                    "starts_before_period": window["starts_before_period"],
                    "ends_after_period": window["ends_after_period"],
                    "clipped": window["clipped"],
                    "limiting_checks": ";".join(window["limiting_checks"]),
                    "visible_fraction_mean": visible["mean"],
                    "visible_fraction_min": visible["min"],
                    "visible_fraction_max": visible["max"],
                    "clearance_deg_mean": clearance["mean"],
                    "clearance_deg_min": clearance["min"],
                    "clearance_deg_max": clearance["max"],
                    "sun_earth_separation_deg_mean": separation["mean"],
                    "sun_earth_separation_deg_min": separation["min"],
                    "sun_earth_separation_deg_max": separation["max"],
                })

    print(f"Saved window data: {path}")


def write_summary_csv(results):
    """Write one summary row per site."""

    fields = [
        "site",
        "latitude_deg",
        "longitude_deg",
        "ground_elevation_m",
        "antenna_height_m",
        "dem_dataset",
        "dem_resolution_m",
        "complete_horizon_directions",
        "total_horizon_directions",
        "sample_count",
        "available_samples",
        "unavailable_samples",
        "availability_percent",
        "window_count",
        "rejected_window_count",
        "total_available_s",
        "total_available_hours",
        "longest_window_s",
        "windows_touching_period_edges",
    ]

    path = OUTPUT_DIR / "phase10_summary.csv"

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for site_name, result in results.items():
            site = result["site"]
            terrain = result["terrain"]
            link = result["link_summary"]
            summary = result["summary"]

            writer.writerow({
                "site": site_name,
                "latitude_deg": site["latitude_deg"],
                "longitude_deg": site["longitude_deg"],
                "ground_elevation_m": site["terrain_elevation_m"],
                "antenna_height_m": site["antenna_height_m"],
                "dem_dataset": terrain["dataset"],
                "dem_resolution_m": terrain["dataset_resolution_m"],
                "complete_horizon_directions": terrain["complete_directions"],
                "total_horizon_directions": terrain["total_directions"],
                "sample_count": link["total_samples"],
                "available_samples": link["available_samples"],
                "unavailable_samples": link["unavailable_samples"],
                "availability_percent": link["availability_percent"],
                "window_count": summary["window_count"],
                "rejected_window_count": summary["rejected_count"],
                "total_available_s": summary["total_available_s"],
                "total_available_hours": summary["total_available_hours"],
                "longest_window_s": summary["longest_window_s"],
                "windows_touching_period_edges": summary["windows_touching_period_edges"],
            })

    print(f"Saved site summary: {path}")


def write_timeline_plot(results):
    """Plot sampled availability and refined windows for each site."""

    figure, axes = plt.subplots(
        len(results),
        1,
        figsize=(14, 7),
        sharex=True,
    )

    if len(results) == 1:
        axes = [axes]

    for axis, (site_name, result) in zip(axes, results.items()):
        samples = result["samples"]
        times = [parse_utc(sample["utc"]) for sample in samples]
        availability = [
            1 if sample["link_available"] else 0
            for sample in samples
        ]

        axis.step(
            times,
            availability,
            where="post",
            linewidth=1.8,
            label="Sampled link availability",
        )

        axis.scatter(
            times,
            availability,
            s=18,
            zorder=3,
        )

        for window in result["windows"]:
            start = parse_utc(window["start_utc"])
            end = parse_utc(window["end_utc"])

            axis.axvspan(
                start,
                end,
                alpha=0.18,
                label="Detected window",
            )

        axis.set_yticks([0, 1])
        axis.set_yticklabels(["Unavailable", "Available"])
        axis.set_ylim(-0.2, 1.2)
        axis.set_title(
            f"{site_name} — "
            f"{result['link_summary']['availability_percent']:.1f}% "
            "sampled availability"
        )
        axis.grid(True, alpha=0.3)

    axes[-1].set_xlabel("UTC")
    axes[-1].xaxis.set_major_formatter(
        mdates.DateFormatter("%m-%d %H:%M", tz=times[0].tzinfo)
    )
    figure.suptitle(
        "Phase 10 — Lunar South Pole Communication Availability",
        fontsize=14,
    )
    figure.tight_layout()

    path = OUTPUT_DIR / "phase10_communications_timeline.png"
    figure.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(figure)

    print(f"Saved timeline plot: {path}")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = {}

    print("=" * 68)
    print("PHASE 10 — REAL-DATA COMMUNICATION WINDOW GENERATION")
    print("=" * 68)
    print(f"Observation start: {START_UTC}")
    print(f"Duration: {DURATION_DAYS} days")
    print(f"Sampling interval: {STEP_MINUTES} minutes")
    print()

    for site_name, site in SITES.items():
        print(f"Processing {site_name}...")

        parameters = {
            **COMMON_SETTINGS,
            **site,
        }

        result = windows_for_site(**parameters)
        results[site_name] = result

        print(f"  Samples: {result['sample_count']}")
        print(
            "  Link availability: "
            f"{result['link_summary']['availability_percent']:.2f}%"
        )
        print(f"  Refined windows: {len(result['windows'])}")
        print(f"  Rejected windows: {len(result['rejected'])}")
        print(
            "  Terrain coverage: "
            f"{result['terrain']['complete_directions']}/"
            f"{result['terrain']['total_directions']}"
        )
        print()

    write_sample_csv(results)
    write_windows_csv(results)
    write_summary_csv(results)
    write_timeline_plot(results)

    print()
    print("Phase 10 real-data exports completed.")


if __name__ == "__main__":
    main()
