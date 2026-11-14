import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.energy.site_energy import energy_timeline_for_site
from backend.energy.solar_power import PanelConfig
from backend.energy.battery import BatteryConfig


OUTPUT_DIR = PROJECT_ROOT / "docs" / "phase11_results"

START_UTC = "2026-11-14T00:00:00Z"
DURATION_DAYS = 28.0
STEP_MINUTES = 30.0

COMMON_SETTINGS = {
    "start_utc": START_UTC,
    "duration_days": DURATION_DAYS,
    "step_minutes": STEP_MINUTES,
    "max_range_m": 100000.0,
    "azimuth_step_deg": 0.25,
    "sunlit_threshold": 0.5,
    "n_disc_points": 400,
    "include_samples": True,
}

SITES = {
    "Floor": {
        "lat_deg": -89.73391,
        "lon_deg": 122.03549,
    },
    "Rim": {
        "lat_deg": -89.67869,
        "lon_deg": -163.05292,
    },
    "Malapert": {
        "lat_deg": -85.99,
        "lon_deg": 0.12,
    },
}

ASSET_PROFILES = {
    "Lander": {
        "panel": PanelConfig(
            kind="tracking",
            normal_elevation_deg=0.0,
            normal_azimuth_deg=0.0,
            area_m2=3.0,
            efficiency=0.28,
            dust_loss=0.05,
            degradation=0.0,
            panel_height_m=3.0,
        ),
        "battery": BatteryConfig(
            capacity_wh=2000.0,
            initial_soc=0.80,
            min_soc=0.20,
            charge_efficiency=0.95,
            discharge_efficiency=0.95,
        ),
        "base_load_w": 60.0,
    },
    "Rover": {
        "panel": PanelConfig(
            kind="tracking",
            normal_elevation_deg=0.0,
            normal_azimuth_deg=0.0,
            area_m2=0.8,
            efficiency=0.28,
            dust_loss=0.05,
            degradation=0.0,
            panel_height_m=1.5,
        ),
        "battery": BatteryConfig(
            capacity_wh=400.0,
            initial_soc=0.80,
            min_soc=0.20,
            charge_efficiency=0.95,
            discharge_efficiency=0.95,
        ),
        "base_load_w": 20.0,
    },
}


def parse_utc(value):
    """Convert an ISO UTC timestamp into a timezone-aware datetime."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def write_summary_csv(results):
    """Write one engineering summary row for each site and asset."""
    fields = [
        "site",
        "asset",
        "latitude_deg",
        "longitude_deg",
        "terrain_elevation_m",
        "panel_height_m",
        "dem_dataset",
        "dem_resolution_m",
        "horizon_complete_directions",
        "horizon_total_directions",
        "sample_count",
        "sunlit_sample_percent",
        "sunlit_hours",
        "total_generated_wh",
        "total_generated_kwh",
        "mean_sun_fraction",
        "minimum_sun_fraction",
        "maximum_sun_fraction",
        "battery_capacity_wh",
        "initial_soc",
        "final_soc",
        "minimum_observed_soc",
        "total_stored_wh",
        "total_drawn_wh",
        "total_wasted_wh",
        "total_unmet_load_wh",
        "battery_depleted",
        "below_minimum_soc",
        "sunlight_window_count",
        "warning_count",
    ]

    path = OUTPUT_DIR / "phase11_summary.csv"

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for (site_name, asset_name), result in results.items():
            site = result["site"]
            terrain = result["terrain"]
            panel = result["panel"]
            battery = result["battery"]
            summary = result["summary"]

            writer.writerow({
                "site": site_name,
                "asset": asset_name,
                "latitude_deg": site["latitude_deg"],
                "longitude_deg": site["longitude_deg"],
                "terrain_elevation_m": site["terrain_elevation_m"],
                "panel_height_m": panel["panel_height_m"],
                "dem_dataset": terrain["dataset"],
                "dem_resolution_m": terrain["dataset_resolution_m"],
                "horizon_complete_directions": terrain["complete_directions"],
                "horizon_total_directions": terrain["total_directions"],
                "sample_count": summary["sample_count"],
                "sunlit_sample_percent": summary["sunlit_sample_percent"],
                "sunlit_hours": summary["sunlit_hours"],
                "total_generated_wh": summary["total_generated_wh"],
                "total_generated_kwh": summary["total_generated_wh"] / 1000.0,
                "mean_sun_fraction": summary["mean_sun_fraction"],
                "minimum_sun_fraction": summary["minimum_sun_fraction"],
                "maximum_sun_fraction": summary["maximum_sun_fraction"],
                "battery_capacity_wh": battery["capacity_wh"],
                "initial_soc": battery["initial_soc"],
                "final_soc": battery["final_soc"],
                "minimum_observed_soc": battery["minimum_observed_soc"],
                "total_stored_wh": battery["total_stored_wh"],
                "total_drawn_wh": battery["total_drawn_wh"],
                "total_wasted_wh": battery["total_wasted_wh"],
                "total_unmet_load_wh": battery["total_unmet_load_wh"],
                "battery_depleted": battery["depleted"],
                "below_minimum_soc": battery["below_minimum"],
                "sunlight_window_count": len(result["sunlight_windows"]),
                "warning_count": len(result["warnings"]),
            })

    print(f"Saved summary CSV: {path}")


def write_samples_csv(results):
    """Export all time-series observations for every simulation."""
    fields = [
        "site",
        "asset",
        "utc",
        "azimuth_deg",
        "elevation_deg",
        "sun_distance_km",
        "terrain_fraction",
        "eclipse_factor",
        "sun_fraction",
        "sunlit",
        "solar_power_w",
        "battery_soc",
        "battery_soc_percent",
        "below_minimum_soc",
        "coverage_complete",
    ]

    path = OUTPUT_DIR / "phase11_all_samples.csv"

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for (site_name, asset_name), result in results.items():
            for sample in result["samples"]:
                writer.writerow({
                    "site": site_name,
                    "asset": asset_name,
                    "utc": sample["utc"],
                    "azimuth_deg": sample["azimuth_deg"],
                    "elevation_deg": sample["elevation_deg"],
                    "sun_distance_km": sample["sun_distance_km"],
                    "terrain_fraction": sample["terrain_fraction"],
                    "eclipse_factor": sample["eclipse_factor"],
                    "sun_fraction": sample["sun_fraction"],
                    "sunlit": sample["sunlit"],
                    "solar_power_w": sample["solar_power_w"],
                    "battery_soc": sample["battery_soc"],
                    "battery_soc_percent": sample["battery_soc"] * 100.0,
                    "below_minimum_soc": sample["below_minimum_soc"],
                    "coverage_complete": sample["coverage_complete"],
                })

    print(f"Saved time-series CSV: {path}")


def write_windows_csv(results):
    """Export each detected sunlight window as a structured JSON field."""
    path = OUTPUT_DIR / "phase11_sunlight_windows.csv"
    fields = ["site", "asset", "window_index", "start_utc", "end_utc",
              "duration_s", "window_json"]

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for (site_name, asset_name), result in results.items():
            for index, window in enumerate(result["sunlight_windows"], start=1):
                writer.writerow({
                    "site": site_name,
                    "asset": asset_name,
                    "window_index": index,
                    "start_utc": window.get("start_utc", ""),
                    "end_utc": window.get("end_utc", ""),
                    "duration_s": window.get("duration_s", ""),
                    "window_json": json.dumps(window, ensure_ascii=False),
                })

    print(f"Saved sunlight windows CSV: {path}")


def write_json(results):
    """Save full simulation outputs, including all sample-level data."""
    payload = {
        "project": "Lunar South Pole Quantum Scheduler",
        "phase": 11,
        "title": "Solar Generation and Battery Survival",
        "simulation_assumptions": {
            "start_utc": START_UTC,
            "duration_days": DURATION_DAYS,
            "sampling_interval_minutes": STEP_MINUTES,
            "horizon_range_m": COMMON_SETTINGS["max_range_m"],
            "horizon_azimuth_step_deg": COMMON_SETTINGS["azimuth_step_deg"],
            "sunlit_threshold": COMMON_SETTINGS["sunlit_threshold"],
            "sun_disc_points": COMMON_SETTINGS["n_disc_points"],
            "dem": "NASA LOLA 80 m DEM",
            "solar_constant_w_m2": 1361.0,
            "battery_efficiencies": 0.95,
            "dust_loss": 0.05,
            "note": (
                "Asset power, battery capacity and load values are "
                "simulation assumptions, not verified hardware specifications."
            ),
        },
        "results": [
            {
                "site": site_name,
                "asset": asset_name,
                **result,
            }
            for (site_name, asset_name), result in results.items()
        ],
    }

    path = OUTPUT_DIR / "phase11_results.json"

    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)

    print(f"Saved complete JSON results: {path}")


def write_battery_plot(results):
    """Compare battery SOC over time for both assets at each site."""
    figure, axes = plt.subplots(
        len(SITES),
        1,
        figsize=(15, 11),
        sharex=True,
    )

    for axis, site_name in zip(axes, SITES):
        for asset_name in ASSET_PROFILES:
            result = results[(site_name, asset_name)]
            samples = result["samples"]

            times = [
                parse_utc(sample["utc"])
                for sample in samples
            ]
            soc_percent = [
                sample["battery_soc"] * 100.0
                for sample in samples
            ]

            axis.plot(
                times,
                soc_percent,
                linewidth=1.5,
                label=f"{asset_name} battery SOC",
            )

        axis.axhline(
            20.0,
            linestyle="--",
            linewidth=1.0,
            label="20% minimum SOC warning",
        )
        axis.set_ylabel("Battery SOC (%)")
        axis.set_ylim(-3, 105)
        axis.set_title(site_name)
        axis.grid(True, alpha=0.3)
        axis.legend(loc="best")

    axes[-1].set_xlabel("UTC")
    axes[-1].xaxis.set_major_formatter(
        mdates.DateFormatter("%m-%d %H:%M", tz=times[0].tzinfo)
    )

    figure.suptitle(
        "Phase 11 — Lunar Solar Energy and Battery Survival",
        fontsize=15,
    )
    figure.tight_layout()

    path = OUTPUT_DIR / "phase11_battery_survival.png"
    figure.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(figure)

    print(f"Saved battery comparison plot: {path}")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = {}

    print("=" * 72)
    print("PHASE 11 — LUNAR SOLAR GENERATION AND BATTERY SURVIVAL")
    print("=" * 72)
    print(f"Start: {START_UTC}")
    print(f"Duration: {DURATION_DAYS} days")
    print(f"Sampling interval: {STEP_MINUTES} minutes")
    print(f"Horizon: {COMMON_SETTINGS['max_range_m'] / 1000:.0f} km")
    print(f"Azimuth resolution: {COMMON_SETTINGS['azimuth_step_deg']} degrees")
    print()

    for site_name, site in SITES.items():
        for asset_name, profile in ASSET_PROFILES.items():
            print(f"Processing {site_name} — {asset_name}...")

            result = energy_timeline_for_site(
                **COMMON_SETTINGS,
                **site,
                panel_config=profile["panel"],
                battery_config=profile["battery"],
                base_load_w=profile["base_load_w"],
            )

            results[(site_name, asset_name)] = result

            summary = result["summary"]
            battery = result["battery"]

            print(f"  Samples: {summary['sample_count']}")
            print(f"  Sunlit time: {summary['sunlit_hours']:.2f} hours")
            print(
                "  Sunlit samples: "
                f"{summary['sunlit_sample_percent']:.2f}%"
            )
            print(
                "  Generated energy: "
                f"{summary['total_generated_wh'] / 1000.0:.3f} kWh"
            )
            print(f"  Final battery SOC: {battery['final_soc'] * 100:.2f}%")
            print(
                "  Minimum observed SOC: "
                f"{battery['minimum_observed_soc'] * 100:.2f}%"
            )
            print(
                "  Unmet load: "
                f"{battery['total_unmet_load_wh'] / 1000.0:.3f} kWh"
            )
            print(f"  Battery depleted: {battery['depleted']}")
            print(f"  Sunlight windows: {len(result['sunlight_windows'])}")
            print(
                "  Horizon coverage: "
                f"{result['terrain']['complete_directions']}/"
                f"{result['terrain']['total_directions']}"
            )

            for warning in result["warnings"]:
                print(f"  WARNING: {warning}")

            print()

    write_summary_csv(results)
    write_samples_csv(results)
    write_windows_csv(results)
    write_json(results)
    write_battery_plot(results)

    print()
    print("Phase 11 simulation exports completed.")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
