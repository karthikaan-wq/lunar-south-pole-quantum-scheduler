
from backend.physics.earth_geometry import earth_track
from backend.terrain.dem_loader import load_dem_terrain
from backend.terrain.horizon import horizon_profile

from .disc_visibility import HorizonModel
from .earth_visibility import (
    visibility_from_samples,
    summarize_visibility,
)


def earth_visibility_for_site(
    lat_deg,
    lon_deg,
    height_m,
    start_utc,
    duration_days,
    step_minutes=5.0,
    antenna_height_m=2.0,
    max_range_m=40000.0,
    azimuth_step_deg=0.5,
    n_disc_points=400,
    return_horizon_model=False,
):
    """
    Calculate Earth's terrain-aware apparent-disc visibility
    throughout a SPICE Earth track.

    Combines:
        Phase 6: Earth apparent geometry and time tracking.
        Phase 7: NASA LOLA terrain horizon.
        Phase 8: Apparent Earth-disc visibility.
        Phase 9: Optional reuse of the internal HorizonModel.

    Incomplete terrain coverage is preserved and flagged.

    By default, returns the original Phase 8 result dictionary.

    When return_horizon_model=True, returns a tuple:
        (result_dictionary, horizon_model)

    The HorizonModel is intended for internal Python use.
    It should not be exposed directly through a JSON API.
    """

    # 1. Calculate Earth's apparent geometry over time.
    # The observer height includes the antenna height.
    track = earth_track(
        lat_deg=lat_deg,
        lon_deg=lon_deg,
        height_m=height_m + antenna_height_m,
        start_utc=start_utc,
        duration_days=duration_days,
        step_minutes=step_minutes,
    )

    # 2. Load the real NASA LOLA terrain around the site.
    terrain = load_dem_terrain(
        lat_deg=lat_deg,
        lon_deg=lon_deg,
        half_size_m=max_range_m * 1.1 + 1000.0,
    )

    # 3. Calculate the terrain horizon.
    profile = horizon_profile(
        terrain=terrain,
        lat_deg=lat_deg,
        lon_deg=lon_deg,
        antenna_height_m=antenna_height_m,
        azimuth_step_deg=azimuth_step_deg,
        max_range_m=max_range_m,
        step_m=terrain.pixel_m,
    )

    # 4. Build the circular horizon interpolation model.
    horizon = HorizonModel.from_profile(
        profile,
        angle_key="horizon_elevation_deg",
        complete_key="horizon_is_complete",
    )

    # 5. Calculate visible Earth-disc fraction at every time.
    visibility_samples = visibility_from_samples(
        samples=track["samples"],
        horizon=horizon,
        n_points=n_disc_points,
    )

    # 6. Summarize terrain-aware visibility.
    visibility_summary = summarize_visibility(
        visibility_samples
    )

    complete_directions = int(
        profile["horizon_is_complete"].sum()
    )

    total_directions = int(
        len(profile["azimuth_deg"])
    )

    # 7. Build the standard Phase 8 result.
    result = {
        "source": "SPICE + NASA LOLA DEM",

        "site": {
            "latitude_deg": float(lat_deg),
            "longitude_deg": float(lon_deg),
            "height_m": float(height_m),
            "terrain_elevation_m": float(
                profile["site_height_m"]
            ),
            "antenna_height_m": float(antenna_height_m),
        },

        "settings": {
            "start_utc": track["start_utc"],
            "end_utc": track["end_utc"],
            "duration_days": track["duration_days"],
            "step_minutes": track["step_minutes"],
            "max_range_m": float(max_range_m),
            "azimuth_step_deg": float(azimuth_step_deg),
            "terrain_sample_step_m": float(terrain.pixel_m),
            "disc_points": int(n_disc_points),
        },

        "terrain": {
            "dataset": "NASA LOLA 80 m DEM",
            "dataset_resolution_m": float(terrain.pixel_m),
            "complete_directions": complete_directions,
            "total_directions": total_directions,
            "all_directions_complete": (
                complete_directions == total_directions
            ),
        },

        "earth_track_summary": track["summary"],

        "visibility_summary": visibility_summary,

        "sample_count": len(visibility_samples),

        "samples": visibility_samples,
    }

    # 8. Optionally return the internal horizon model for Phase 9.
    if return_horizon_model:
        return result, horizon

    return result
