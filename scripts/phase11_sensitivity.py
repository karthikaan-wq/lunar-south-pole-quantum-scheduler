import csv
import sys
from pathlib import Path
from dataclasses import replace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.energy.site_energy import energy_timeline_for_site
from scripts.phase11_energy import ASSET_PROFILES, SITES, START_UTC

OUTPUT_DIR = PROJECT_ROOT / "docs" / "phase11_results"

SITE_NAME = "Malapert"
ASSET_NAME = "Lander"

SITE = SITES[SITE_NAME]
BASE_PROFILE = ASSET_PROFILES[ASSET_NAME]

START_SETTINGS = {
    "start_utc": START_UTC,
    "duration_days": 14.0,
    "step_minutes": 30.0,
    "max_range_m": 100000.0,
    "sunlit_threshold": 0.5,
    "n_disc_points": 400,
    "include_samples": False,
}

PANEL_HEIGHTS_M = [1.0, 2.0, 3.0, 5.0, 10.0]
AZIMUTH_STEPS_DEG = [1.0, 0.5, 0.25]


def run_experiment(experiment_name, values, parameter_name):
    rows = []

    for value in values:
        print(f"{experiment_name}: {parameter_name} = {value}")

        panel_height = (
            value if parameter_name == "panel_height_m"
            else BASE_PROFILE["panel"].panel_height_m
        )
        panel = replace(
            BASE_PROFILE["panel"],
            panel_height_m=panel_height,
        )

        azimuth_step = (
            value if parameter_name == "azimuth_step_deg" else 0.25
        )

        result = energy_timeline_for_site(
            **START_SETTINGS,
            **SITE,
            panel_config=panel,
            battery_config=BASE_PROFILE["battery"],
            base_load_w=BASE_PROFILE["base_load_w"],
            azimuth_step_deg=azimuth_step,
        )

        summary = result["summary"]
        battery = result["battery"]
        terrain = result["terrain"]

        row = {
            "experiment": experiment_name,
            "parameter": parameter_name,
            "parameter_value": value,
            "site": SITE_NAME,
            "asset": ASSET_NAME,
            "duration_days": START_SETTINGS["duration_days"],
            "step_minutes": START_SETTINGS["step_minutes"],
            "horizon_range_m": START_SETTINGS["max_range_m"],
            "dem_resolution_m": terrain["dataset_resolution_m"],
            "horizon_directions": terrain["total_directions"],
            "complete_horizon_directions": terrain["complete_directions"],
            "sample_count": summary["sample_count"],
            "sunlit_sample_percent": summary["sunlit_sample_percent"],
            "sunlit_hours": summary["sunlit_hours"],
            "total_generated_wh": summary["total_generated_wh"],
            "total_generated_kwh": summary["total_generated_wh"] / 1000.0,
            "mean_sun_fraction": summary["mean_sun_fraction"],
            "total_unmet_load_wh": battery["total_unmet_load_wh"],
            "battery_final_soc": battery["final_soc"],
            "battery_minimum_soc": battery["minimum_observed_soc"],
            "battery_depleted": battery["depleted"],
            "sunlight_window_count": len(result["sunlight_windows"]),
            "warnings": " | ".join(result["warnings"]),
        }

        rows.append(row)

        print(
            f"  Sunlit: {row['sunlit_sample_percent']:.3f}% | "
            f"Generation: {row['total_generated_kwh']:.3f} kWh | "
            f"Unmet load: {row['total_unmet_load_wh']:.2f} Wh"
        )
        print(
            f"  Horizon: {row['complete_horizon_directions']}/"
            f"{row['horizon_directions']} directions"
        )

    return rows


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("PHASE 11 — SENSITIVITY EXPERIMENTS")
    print("=" * 72)
    print(f"Site: {SITE_NAME}")
    print(f"Asset: {ASSET_NAME}")
    print(f"Start: {START_UTC}")
    print("Duration: 14 days")
    print("Sampling interval: 30 minutes")
    print()

    height_rows = run_experiment(
        "Panel height sensitivity",
        PANEL_HEIGHTS_M,
        "panel_height_m",
    )

    print()

    azimuth_rows = run_experiment(
        "Horizon azimuth resolution sensitivity",
        AZIMUTH_STEPS_DEG,
        "azimuth_step_deg",
    )

    rows = height_rows + azimuth_rows
    output_path = OUTPUT_DIR / "phase11_sensitivity.csv"

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print()
    print(f"Saved sensitivity results: {output_path}")
    print(f"Total experiment runs: {len(rows)}")
    print("Sensitivity experiments completed.")


if __name__ == "__main__":
    main()
