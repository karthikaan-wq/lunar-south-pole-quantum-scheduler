
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.visibility.site_visibility import (
    earth_visibility_for_site,
)

from scripts.phase8_visibility import (
    get_dem_site_elevation,
    OUTPUT_DIR,
)


# ============================================================
# PHASE 8 — NUMERICAL SENSITIVITY ANALYSIS
# ============================================================

SITE_NAME = "Malapert Massif"

LATITUDE_DEG = -85.99
LONGITUDE_DEG = 0.12

START_UTC = "2026-11-14T00:00:00Z"
DURATION_DAYS = 28.0
STEP_MINUTES = 60.0

ANTENNA_HEIGHT_M = 2.0
MAX_RANGE_M = 40000.0

CONFIGURATIONS = [
    {
        "name": "azimuth_1_degree",
        "azimuth_step_deg": 1.0,
        "disc_points": 400,
    },
    {
        "name": "baseline_0.5_degree_400_points",
        "azimuth_step_deg": 0.5,
        "disc_points": 400,
    },
    {
        "name": "azimuth_0.25_degree",
        "azimuth_step_deg": 0.25,
        "disc_points": 400,
    },
    {
        "name": "disc_200_points",
        "azimuth_step_deg": 0.5,
        "disc_points": 200,
    },
    {
        "name": "disc_1000_points",
        "azimuth_step_deg": 0.5,
        "disc_points": 1000,
    },
]


def run_configuration(configuration, elevation_m):
    """Run one numerical-resolution configuration."""

    print("\n" + "-" * 65)
    print(f"Experiment: {configuration['name']}")
    print(
        "Horizon spacing: "
        f"{configuration['azimuth_step_deg']} degrees"
    )
    print(
        "Earth-disc points: "
        f"{configuration['disc_points']}"
    )

    result = earth_visibility_for_site(
        lat_deg=LATITUDE_DEG,
        lon_deg=LONGITUDE_DEG,
        height_m=elevation_m,
        start_utc=START_UTC,
        duration_days=DURATION_DAYS,
        step_minutes=STEP_MINUTES,
        antenna_height_m=ANTENNA_HEIGHT_M,
        max_range_m=MAX_RANGE_M,
        azimuth_step_deg=configuration[
            "azimuth_step_deg"
        ],
        n_disc_points=configuration["disc_points"],
    )

    summary = result["visibility_summary"]

    print(f"Samples: {result['sample_count']}")
    print(
        "Mean visible fraction: "
        f"{summary['mean_visible_fraction']:.6f}"
    )
    print(
        "Any part visible: "
        f"{summary['percent_any_part_visible']:.3f}%"
    )
    print(
        "Fully visible: "
        f"{summary['percent_fully_visible']:.3f}%"
    )
    print(
        "Incomplete terrain samples: "
        f"{summary['samples_with_incomplete_terrain']}"
    )

    return result


def main():
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=" * 65)
    print("PHASE 8 — SENSITIVITY ANALYSIS")
    print("=" * 65)

    print(f"Study location: {SITE_NAME}")
    print(f"Coordinates: {LATITUDE_DEG}, {LONGITUDE_DEG}")
    print(f"Duration: {DURATION_DAYS} days")
    print(f"Time interval: {STEP_MINUTES} minutes")

    elevation_m = get_dem_site_elevation(
        LATITUDE_DEG,
        LONGITUDE_DEG,
    )

    print(f"DEM elevation: {elevation_m:.3f} m")

    results = {}

    for configuration in CONFIGURATIONS:
        result = run_configuration(
            configuration,
            elevation_m,
        )

        results[configuration["name"]] = result

    baseline_name = "baseline_0.5_degree_400_points"
    baseline = results[baseline_name]

    baseline_fractions = [
        sample["visible_fraction"]
        for sample in baseline["samples"]
    ]

    output_path = (
        OUTPUT_DIR / "phase8_sensitivity_results.csv"
    )

    fields = [
        "configuration",
        "horizon_azimuth_step_deg",
        "disc_points",
        "sample_count",
        "mean_visible_fraction",
        "percent_any_part_visible",
        "percent_centre_visible",
        "percent_fully_visible",
        "percent_blocked",
        "incomplete_terrain_samples",
        "mean_absolute_difference_from_baseline",
        "maximum_absolute_difference_from_baseline",
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

        for configuration in CONFIGURATIONS:
            name = configuration["name"]
            result = results[name]
            summary = result["visibility_summary"]

            fractions = [
                sample["visible_fraction"]
                for sample in result["samples"]
            ]

            if len(fractions) != len(baseline_fractions):
                raise ValueError(
                    f"Sample count mismatch for {name}"
                )

            differences = [
                abs(current - reference)
                for current, reference in zip(
                    fractions,
                    baseline_fractions,
                )
            ]

            writer.writerow({
                "configuration": name,
                "horizon_azimuth_step_deg": (
                    configuration["azimuth_step_deg"]
                ),
                "disc_points": configuration["disc_points"],
                "sample_count": result["sample_count"],
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
                "incomplete_terrain_samples": (
                    summary["samples_with_incomplete_terrain"]
                ),
                "mean_absolute_difference_from_baseline": (
                    sum(differences) / len(differences)
                ),
                "maximum_absolute_difference_from_baseline": (
                    max(differences)
                ),
            })

    print("\n" + "=" * 65)
    print("SENSITIVITY ANALYSIS COMPLETED")
    print("=" * 65)
    print(f"Results CSV: {output_path}")


if __name__ == "__main__":
    main()