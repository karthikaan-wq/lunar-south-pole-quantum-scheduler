import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.energy.site_energy import energy_timeline_for_site
from backend.energy.solar_power import PanelConfig
from backend.energy.battery import BatteryConfig

from backend.communications.antenna import AntennaConfig
from backend.communications.direct_to_earth import LinkConstraints
from backend.communications.windows import WindowSettings

from backend.communications.site_surface_links import surface_links_for_assets
from backend.communications.site_windows import windows_for_site
from backend.communications.surface_opportunities import (
    compose_surface_opportunities,
    power_eligible_windows,
)


OUTPUT_DIR = PROJECT_ROOT / "docs" / "phase12_results"
OUTPUT_FILE = OUTPUT_DIR / "phase12_end_to_end.json"

START_UTC = "2026-11-15T00:00:00Z"
DURATION_DAYS = 14.0
ENERGY_STEP_MINUTES = 30.0

LANDER = {
    "name": "Malapert_Lander",
    "type": "lander",
    "latitude_deg": -85.99,
    "longitude_deg": 0.12,
    "antenna_height_m": 3.0,
}

ROVER = {
    "name": "Rover_01",
    "type": "rover",
    "latitude_deg": -86.0,
    "longitude_deg": 0.12,
    "antenna_height_m": 1.5,
}

ENERGY_SETTINGS = {
    "start_utc": START_UTC,
    "duration_days": DURATION_DAYS,
    "step_minutes": ENERGY_STEP_MINUTES,
    "max_range_m": 100000.0,
    "azimuth_step_deg": 0.25,
    "sunlit_threshold": 0.5,
    "n_disc_points": 400,
    "include_samples": True,
}

LANDER_PROFILE = {
    "panel_config": PanelConfig(
        kind="tracking",
        normal_elevation_deg=0.0,
        normal_azimuth_deg=0.0,
        area_m2=3.0,
        efficiency=0.28,
        dust_loss=0.05,
        degradation=0.0,
        panel_height_m=3.0,
    ),
    "battery_config": BatteryConfig(
        capacity_wh=2000.0,
        initial_soc=0.80,
        min_soc=0.20,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
    ),
    "base_load_w": 60.0,
}

ROVER_PROFILE = {
    "panel_config": PanelConfig(
        kind="tracking",
        normal_elevation_deg=0.0,
        normal_azimuth_deg=0.0,
        area_m2=0.8,
        efficiency=0.28,
        dust_loss=0.05,
        degradation=0.0,
        panel_height_m=1.5,
    ),
    "battery_config": BatteryConfig(
        capacity_wh=400.0,
        initial_soc=0.80,
        min_soc=0.20,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
    ),
    "base_load_w": 20.0,
}


def energy_summary(result):
    """Keep engineering summaries without duplicating all energy samples."""
    return {
        "site": result["site"],
        "settings": result["settings"],
        "terrain": result["terrain"],
        "panel": result["panel"],
        "battery": result["battery"],
        "load": result["load"],
        "summary": result["summary"],
        "sunlight_window_count": len(result["sunlight_windows"]),
        "warning_count": len(result["warnings"]),
        "warnings": result["warnings"],
        "power_eligible_window_count": len(
            power_eligible_windows(result)
        ),
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 76)
    print("PHASE 12 — ROVER-TO-LANDER END-TO-END COMMUNICATION")
    print("=" * 76)
    print(f"Start: {START_UTC}")
    print(f"Duration: {DURATION_DAYS} days")
    print()

    # ---------------------------------------------------------
    # 1. Static terrain-aware rover-to-lander surface link.
    # ---------------------------------------------------------

    print("[1/4] Evaluating the real NASA DEM surface link...")

    assets = [LANDER, ROVER]

    link_results = surface_links_for_assets(assets)

    pair = ("Malapert_Lander", "Rover_01")
    link_metrics = link_results[pair]

    print(f"  Distance: {link_metrics['distance_m']:.2f} m")
    print(f"  Minimum clearance: {link_metrics['min_clearance_m']:.2f} m")
    print(f"  Line of sight: {link_metrics['line_of_sight']}")
    print(f"  Fresnel ratio: {link_metrics['fresnel_ratio_min']:.4f}")
    print(f"  Usable: {link_metrics['usable']}")
    print()

    # ---------------------------------------------------------
    # 2. Independent energy timelines for rover and lander.
    # ---------------------------------------------------------

    print("[2/4] Simulating rover and lander energy timelines...")

    lander_energy = energy_timeline_for_site(
        **ENERGY_SETTINGS,
        lat_deg=LANDER["latitude_deg"],
        lon_deg=LANDER["longitude_deg"],
        panel_config=LANDER_PROFILE["panel_config"],
        battery_config=LANDER_PROFILE["battery_config"],
        base_load_w=LANDER_PROFILE["base_load_w"],
    )

    print(
        "  Lander energy simulation complete: "
        f"{lander_energy['summary']['sample_count']} samples"
    )

    rover_energy = energy_timeline_for_site(
        **ENERGY_SETTINGS,
        lat_deg=ROVER["latitude_deg"],
        lon_deg=ROVER["longitude_deg"],
        panel_config=ROVER_PROFILE["panel_config"],
        battery_config=ROVER_PROFILE["battery_config"],
        base_load_w=ROVER_PROFILE["base_load_w"],
    )

    print(
        "  Rover energy simulation complete: "
        f"{rover_energy['summary']['sample_count']} samples"
    )
    print()

    # ---------------------------------------------------------
    # 3. Lander direct-to-Earth communication windows.
    # ---------------------------------------------------------

    print("[3/4] Calculating lander-to-Earth communication windows...")

    earth_windows_result = windows_for_site(
        lat_deg=LANDER["latitude_deg"],
        lon_deg=LANDER["longitude_deg"],
        height_m=lander_energy["site"]["terrain_elevation_m"],
        start_utc=START_UTC,
        duration_days=DURATION_DAYS,
        step_minutes=5.0,
        antenna_height_m=LANDER["antenna_height_m"],
        max_range_m=40000.0,
        azimuth_step_deg=0.5,
        n_disc_points=400,
        antenna=AntennaConfig(),
        constraints=LinkConstraints(),
        window_settings=WindowSettings(),
    )

    print(f"  Earth visibility samples: {earth_windows_result['sample_count']}")
    print(f"  Accepted Earth windows: {len(earth_windows_result['windows'])}")
    print(f"  Rejected windows: {len(earth_windows_result['rejected'])}")
    print(
        "  Earth-link availability: "
        f"{earth_windows_result['link_summary']['availability_percent']:.2f}%"
    )
    print()

    # ---------------------------------------------------------
    # 4. Compose end-to-end store-and-forward opportunities.
    # ---------------------------------------------------------

    print("[4/4] Composing end-to-end communication opportunities...")

    opportunities = compose_surface_opportunities(
        link_metrics=link_metrics,
        rover_energy=rover_energy,
        lander_energy=lander_energy,
        earth_windows=earth_windows_result["windows"],
        max_wait_s=12.0 * 3600.0,
        min_forward_s=300.0,
    )

    print(
        "  Rover power windows: "
        f"{opportunities['rover_power_window_count']}"
    )
    print(
        "  Lander power windows: "
        f"{opportunities['lander_power_window_count']}"
    )
    print(
        "  Common power windows: "
        f"{opportunities['common_power_window_count']}"
    )
    print(
        "  Surface uplink windows: "
        f"{opportunities['uplink_window_count']}"
    )
    print(
        "  End-to-end forwarding opportunities: "
        f"{len(opportunities['forwarding_options'])}"
    )
    print()

    # ---------------------------------------------------------
    # 5. Export compact, reproducible engineering results.
    # ---------------------------------------------------------

    payload = {
        "project": "Lunar South Pole Quantum Scheduler",
        "phase": 12,
        "title": "Rover-to-Lander Surface Links and End-to-End Opportunities",

        "simulation_assumptions": {
            "start_utc": START_UTC,
            "duration_days": DURATION_DAYS,
            "energy_sampling_minutes": ENERGY_STEP_MINUTES,
            "earth_link_sampling_minutes": 5.0,
            "energy_horizon_range_m": 100000.0,
            "earth_horizon_range_m": 40000.0,
            "earth_horizon_azimuth_step_deg": 0.5,
            "earth_disc_points": 400,
            "surface_frequency_hz": 401.5e6,
            "surface_max_range_m": 10000.0,
            "surface_path_step_m": 40.0,
            "surface_min_clearance_m": 0.0,
            "surface_min_fresnel_ratio": 0.0,
            "maximum_forwarding_wait_hours": 12.0,
            "minimum_forwarding_duration_minutes": 5.0,
            "dem": "NASA LOLA 80 m DEM",
            "note": (
                "Power, antenna and radio parameters are engineering "
                "simulation assumptions, not verified flight hardware "
                "specifications."
            ),
        },

        "assets": {
            "lander": LANDER,
            "rover": ROVER,
        },

        "surface_link": {
            "asset_a": pair[0],
            "asset_b": pair[1],
            **link_metrics,
        },

        "energy": {
            "lander": energy_summary(lander_energy),
            "rover": energy_summary(rover_energy),
        },

        "earth_link": {
            "source": earth_windows_result["source"],
            "site": earth_windows_result["site"],
            "settings": earth_windows_result["settings"],
            "terrain": earth_windows_result["terrain"],
            "link_summary": earth_windows_result["link_summary"],
            "summary": earth_windows_result["summary"],
            "windows": earth_windows_result["windows"],
            "rejected": earth_windows_result["rejected"],
        },

        "end_to_end_opportunities": opportunities,
    }

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)

    print("=" * 76)
    print("PHASE 12 END-TO-END SIMULATION EXPORT COMPLETED")
    print(f"Output: {OUTPUT_FILE}")
    print("=" * 76)


if __name__ == "__main__":
    main()
