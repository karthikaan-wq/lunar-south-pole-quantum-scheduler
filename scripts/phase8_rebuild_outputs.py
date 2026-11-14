
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.visibility.earth_visibility import summarize_visibility

from scripts.phase8_visibility import (
    SITES,
    OUTPUT_DIR,
    get_dem_site_elevation,
    write_combined_csv,
    write_summary_csv,
    write_timeline_plot,
)


NUMERIC_FIELDS = [
    "azimuth_deg",
    "elevation_deg",
    "angular_radius_deg",
    "horizon_at_centre_deg",
    "margin_deg",
    "visible_fraction",
]

BOOLEAN_FIELDS = [
    "centre_visible",
    "any_part_visible",
    "fully_visible",
    "blocked",
    "coverage_complete",
    "centre_coverage_complete",
]


def load_site_samples(filename):
    """Load and convert previously saved visibility samples."""

    path = OUTPUT_DIR / filename

    if not path.exists():
        raise FileNotFoundError(
            f"Required results file not found: {path}"
        )

    samples = []

    with path.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            sample = dict(row)

            for field in NUMERIC_FIELDS:
                sample[field] = float(sample[field])

            for field in BOOLEAN_FIELDS:
                sample[field] = (
                    sample[field].strip().lower() == "true"
                )

            samples.append(sample)

    if not samples:
        raise ValueError(
            f"No samples found in {filename}"
        )

    return samples


def main():
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_results = {}

    print("=" * 65)
    print("PHASE 8 — RECOVERING SAVED SCIENTIFIC RESULTS")
    print("=" * 65)

    for site_name, (lat, lon) in SITES.items():
        safe_name = (
            site_name.lower()
            .replace(" ", "_")
            .replace("-", "_")
        )

        filename = f"{safe_name}_visibility.csv"

        print(f"\nLoading: {site_name}")

        samples = load_site_samples(filename)

        elevation = get_dem_site_elevation(lat, lon)

        summary = summarize_visibility(samples)

        all_results[site_name] = {
            "site": {
                "latitude_deg": lat,
                "longitude_deg": lon,
                "terrain_elevation_m": elevation,
            },
            "samples": samples,
            "visibility_summary": summary,
        }

        print(f"Samples recovered: {len(samples)}")
        print(
            "Mean visible fraction: "
            f"{summary['mean_visible_fraction']:.4f}"
        )

    print("\nRebuilding combined CSV...")
    combined_path = write_combined_csv(all_results)

    print("Rebuilding summary CSV...")
    summary_path = write_summary_csv(all_results)

    print("Generating timeline plot...")
    plot_path = write_timeline_plot(all_results)

    print("\n" + "=" * 65)
    print("RECOVERY COMPLETED")
    print("=" * 65)

    print(f"Combined CSV: {combined_path}")
    print(f"Summary CSV: {summary_path}")
    print(f"Timeline PNG: {plot_path}")


if __name__ == "__main__":
    main()