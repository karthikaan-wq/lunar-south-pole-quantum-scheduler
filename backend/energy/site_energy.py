from ..terrain.dem_loader import load_dem_terrain
from ..terrain.horizon import horizon_profile
from ..visibility.disc_visibility import HorizonModel


def build_horizon_for(
    lat_deg,
    lon_deg,
    height_above_ground_m,
    max_range_m=100000.0,
    azimuth_step_deg=0.25,
):
    """
    Build a terrain horizon at the solar panel's physical height.

    The DEM site elevation is handled by the terrain model.
    height_above_ground_m is the panel height above that terrain.
    """
    terrain = load_dem_terrain(
        lat_deg=lat_deg,
        lon_deg=lon_deg,
        half_size_m=max_range_m * 1.1 + 1000.0,
    )

    profile = horizon_profile(
        terrain=terrain,
        lat_deg=lat_deg,
        lon_deg=lon_deg,
        antenna_height_m=height_above_ground_m,
        azimuth_step_deg=azimuth_step_deg,
        max_range_m=max_range_m,
        step_m=terrain.pixel_m,
    )

    horizon = HorizonModel.from_profile(
        profile,
        angle_key="horizon_elevation_deg",
        complete_key="horizon_is_complete",
    )

    metadata = {
        "dataset": "NASA LOLA 80 m DEM",
        "dataset_resolution_m": float(terrain.pixel_m),
        "terrain_elevation_m": float(profile["site_height_m"]),
        "panel_height_m": float(height_above_ground_m),
        "max_range_m": float(max_range_m),
        "azimuth_step_deg": float(azimuth_step_deg),
        "complete_directions": int(
            profile["horizon_is_complete"].sum()
        ),
        "total_directions": int(len(profile["azimuth_deg"])),
    }

    metadata["all_directions_complete"] = (
        metadata["complete_directions"] == metadata["total_directions"]
    )

    return horizon, metadata

from datetime import timedelta

from ..communications.windows import (
    WindowSettings,
    build_windows,
    to_iso,
)
from ..physics.earth_samples import earth_samples_at
from ..physics.sun_geometry import sun_at_times
from ..physics.time_system import parse_utc
from .battery import BatteryConfig, load_profile, simulate_battery
from .solar_power import PanelConfig, solar_power_w
from .sun_visibility import sun_visibility_from_samples


def energy_timeline_for_site(
    lat_deg,
    lon_deg,
    start_utc,
    duration_days=14.0,
    step_minutes=30.0,
    panel_config=None,
    battery_config=None,
    base_load_w=60.0,
    extra_loads=(),
    max_range_m=100000.0,
    azimuth_step_deg=0.25,
    sunlit_threshold=0.5,
    n_disc_points=400,
    include_samples=True,
):
    """
    Simulate terrain-aware solar generation and battery survival.

    Terrain and eclipse visibility are calculated independently and
    multiplied as an approximation. Their joint disc overlap is not
    an exact geometric intersection.

    Tracking panels track solar azimuth while retaining their
    configured normal elevation. Actuator and slew constraints
    are not modelled.
    """
    import math
    import numpy as np

    if panel_config is None:
        panel_config = PanelConfig()

    if battery_config is None:
        battery_config = BatteryConfig()

    if not math.isfinite(duration_days) or duration_days <= 0.0:
        raise ValueError("duration_days must be finite and positive.")

    if not math.isfinite(step_minutes) or step_minutes <= 0.0:
        raise ValueError("step_minutes must be finite and positive.")

    if not math.isfinite(base_load_w) or base_load_w < 0.0:
        raise ValueError("base_load_w must be finite and nonnegative.")

    if not 0.0 <= sunlit_threshold <= 1.0:
        raise ValueError("sunlit_threshold must be between 0 and 1.")

    if n_disc_points < 20:
        raise ValueError("n_disc_points must be at least 20.")

    start = parse_utc(start_utc)
    duration_s = duration_days * 86400.0
    step_s = step_minutes * 60.0

    interval_count = int(math.ceil(duration_s / step_s))

    offsets = [
        min(i * step_s, duration_s)
        for i in range(interval_count + 1)
    ]

    moments = [
        start + timedelta(seconds=offset)
        for offset in offsets
    ]

    time_strings = [
        moment.strftime("%Y-%m-%dT%H:%M:%SZ")
        for moment in moments
    ]

    times_s = np.array(
        [moment.timestamp() for moment in moments],
        dtype=float,
    )

    # Build the terrain horizon at the physical panel height.
    horizon, terrain_metadata = build_horizon_for(
        lat_deg=lat_deg,
        lon_deg=lon_deg,
        height_above_ground_m=panel_config.panel_height_m,
        max_range_m=max_range_m,
        azimuth_step_deg=azimuth_step_deg,
    )

    observer_height_m = (
        terrain_metadata["terrain_elevation_m"]
        + panel_config.panel_height_m
    )

    # Calculate apparent Sun and Earth geometry at identical times.
    sun_samples = sun_at_times(
        lat_deg,
        lon_deg,
        observer_height_m,
        time_strings,
    )

    earth_samples = earth_samples_at(
        lat_deg,
        lon_deg,
        observer_height_m,
        time_strings,
    )

    # Normalize the Sun timestamp field for the energy output.
    normalized_sun = [
        {**sample, "time": sample["utc"]}
        for sample in sun_samples
    ]

    visibility = sun_visibility_from_samples(
        normalized_sun,
        horizon,
        earth_samples=earth_samples,
        n_points=n_disc_points,
    )

    sun_fraction = np.array(
        [sample["sun_fraction"] for sample in visibility],
        dtype=float,
    )

    terrain_fraction = np.array(
        [sample["terrain_fraction"] for sample in visibility],
        dtype=float,
    )

    eclipse_factor = np.array(
        [sample["eclipse_factor"] for sample in visibility],
        dtype=float,
    )

    coverage_complete = np.array(
        [sample["coverage_complete"] for sample in visibility],
        dtype=bool,
    )

    sunlit_flags = sun_fraction >= sunlit_threshold

    # Convert apparent Sun geometry into electrical power.
    generated_power_w = solar_power_w(
        distance_km=np.array(
            [sample["distance_km"] for sample in sun_samples],
            dtype=float,
        ),
        azimuth_deg=np.array(
            [sample["azimuth_deg"] for sample in sun_samples],
            dtype=float,
        ),
        elevation_deg=np.array(
            [sample["elevation_deg"] for sample in sun_samples],
            dtype=float,
        ),
        sun_fraction=sun_fraction,
        config=panel_config,
    )

    # Loads and battery simulation use intervals between samples.
    # The final sample is an endpoint, not another full interval.
    dt_s = np.diff(times_s)

    loads_w = load_profile(
        times_s[:-1],
        base_w=base_load_w,
        extra_loads=extra_loads,
    )

    battery = simulate_battery(
        power_w=generated_power_w[:-1],
        load_w=loads_w,
        dt_s=dt_s,
        config=battery_config,
    )

    soc = np.concatenate((
        [battery_config.initial_soc],
        battery["soc"],
    ))

    below_minimum = soc < battery_config.min_soc

    # Recalculate the physical state at refined window boundaries.
    def state_at(epoch_seconds):
        timestamp = to_iso(epoch_seconds)

        sun = sun_at_times(
            lat_deg,
            lon_deg,
            observer_height_m,
            [timestamp],
        )

        earth = earth_samples_at(
            lat_deg,
            lon_deg,
            observer_height_m,
            [timestamp],
        )

        sample = {**sun[0], "time": sun[0]["utc"]}

        result = sun_visibility_from_samples(
            [sample],
            horizon,
            earth_samples=earth,
            n_points=n_disc_points,
        )[0]

        available = result["sun_fraction"] >= sunlit_threshold

        return {
            "up": bool(available),
            "reasons": (
                [] if available
                else ["sun_fraction_below_threshold"]
            ),
        }

    window_result = build_windows(
        times_s=times_s,
        flags=sunlit_flags,
        state_fn=state_at,
        settings=WindowSettings(
            resolution_s=60.0,
            max_gap_s=0.0,
            min_duration_s=1800.0,
        ),
        extras={
            "sun_fraction": sun_fraction,
            "solar_power_w": generated_power_w,
        },
    )

    interval_sunlit_hours = float(
        np.sum(dt_s * sunlit_flags[:-1]) / 3600.0
    )

    total_generated_wh = float(
        np.sum(generated_power_w[:-1] * dt_s / 3600.0)
    )

    samples = []

    for i, (sun, visible) in enumerate(
        zip(sun_samples, visibility)
    ):
        samples.append({
            "utc": time_strings[i],
            "azimuth_deg": float(sun["azimuth_deg"]),
            "elevation_deg": float(sun["elevation_deg"]),
            "sun_distance_km": float(sun["distance_km"]),
            "terrain_fraction": float(terrain_fraction[i]),
            "eclipse_factor": float(eclipse_factor[i]),
            "sun_fraction": float(sun_fraction[i]),
            "sunlit": bool(sunlit_flags[i]),
            "solar_power_w": float(generated_power_w[i]),
            "battery_soc": float(soc[i]),
            "below_minimum_soc": bool(below_minimum[i]),
            "coverage_complete": bool(coverage_complete[i]),
        })

    warnings = []

    if not terrain_metadata["all_directions_complete"]:
        warnings.append(
            "Some terrain horizon directions have incomplete DEM coverage."
        )

    if not np.all(coverage_complete):
        warnings.append(
            "Some solar-disc visibility samples use incomplete terrain horizons."
        )

    if np.any(below_minimum):
        warnings.append(
            "Battery state of charge fell below the configured minimum."
        )

    if np.any(battery["depleted"]):
        warnings.append(
            "Battery depletion occurred; unmet load is reported."
        )

    result = {
        "source": "SPICE + NASA LOLA DEM + solar and battery simulation",
        "site": {
            "latitude_deg": float(lat_deg),
            "longitude_deg": float(lon_deg),
            "terrain_elevation_m": float(
                terrain_metadata["terrain_elevation_m"]
            ),
            "observer_height_m": float(observer_height_m),
        },
        "settings": {
            "start_utc": time_strings[0],
            "end_utc": time_strings[-1],
            "duration_days": float(duration_days),
            "step_minutes": float(step_minutes),
            "sunlit_threshold": float(sunlit_threshold),
            "max_range_m": float(max_range_m),
            "azimuth_step_deg": float(azimuth_step_deg),
            "disc_points": int(n_disc_points),
        },
        "terrain": terrain_metadata,
        "panel": {
            "kind": panel_config.kind,
            "area_m2": float(panel_config.area_m2),
            "efficiency": float(panel_config.efficiency),
            "dust_loss": float(panel_config.dust_loss),
            "degradation": float(panel_config.degradation),
            "panel_height_m": float(panel_config.panel_height_m),
            "normal_elevation_deg": float(
                panel_config.normal_elevation_deg
            ),
            "normal_azimuth_deg": float(
                panel_config.normal_azimuth_deg
            ),
        },
        "battery": {
            "capacity_wh": float(battery_config.capacity_wh),
            "initial_soc": float(battery_config.initial_soc),
            "minimum_soc": float(battery_config.min_soc),
            "final_soc": float(battery["final_soc"]),
            "minimum_observed_soc": float(battery["minimum_soc"]),
            "total_stored_wh": float(battery["total_stored_wh"]),
            "total_drawn_wh": float(battery["total_drawn_wh"]),
            "total_wasted_wh": float(battery["total_wasted_wh"]),
            "total_unmet_load_wh": float(
                battery["total_unmet_load_wh"]
            ),
            "depleted": bool(np.any(battery["depleted"])),
            "below_minimum": bool(np.any(below_minimum)),
        },
        "load": {
            "base_load_w": float(base_load_w),
        },
        "summary": {
            "sample_count": len(time_strings),
            "sunlit_sample_percent": float(
                100.0 * np.mean(sunlit_flags)
            ),
            "sunlit_hours": interval_sunlit_hours,
            "total_generated_wh": total_generated_wh,
            "minimum_sun_fraction": float(np.min(sun_fraction)),
            "maximum_sun_fraction": float(np.max(sun_fraction)),
            "mean_sun_fraction": float(np.mean(sun_fraction)),
            "complete_horizon_samples": int(
                np.count_nonzero(coverage_complete)
            ),
        },
        "sunlight_windows": window_result["windows"],
        "rejected_sunlight_windows": window_result["rejected"],
        "warnings": warnings,
    }

    if include_samples:
        result["samples"] = samples

    return result
