
import math

import numpy as np

from .projection import MOON_RADIUS_M, lonlat_to_xy


def horizon_profile(
    terrain,
    lat_deg: float,
    lon_deg: float,
    antenna_height_m: float = 2.0,
    azimuth_step_deg: float = 1.0,
    max_range_m: float = 40000.0,
    step_m: float | None = None,
):
    """
    Calculate the terrain horizon in every requested azimuth direction.

    Azimuth convention:
        0 degrees   = North
        90 degrees  = East
        180 degrees = South
        270 degrees = West

    Returns the maximum terrain elevation angle along each ray,
    the distance to the highest sampled terrain, and terrain coverage
    information for each direction.

    A horizon is marked complete only when every sampled point,
    including the requested maximum range, has valid terrain data.
    """

    values = [
        lat_deg,
        lon_deg,
        antenna_height_m,
        azimuth_step_deg,
        max_range_m,
    ]

    if not all(math.isfinite(float(v)) for v in values):
        raise ValueError("All horizon parameters must be finite.")

    lat_deg = float(lat_deg)
    lon_deg = float(lon_deg)
    antenna_height_m = float(antenna_height_m)
    azimuth_step_deg = float(azimuth_step_deg)
    max_range_m = float(max_range_m)

    if not -90.0 <= lat_deg <= 0.0:
        raise ValueError("Latitude must be between -90 and 0 degrees.")

    if antenna_height_m < 0.0:
        raise ValueError("Antenna height cannot be negative.")

    if not 0.25 <= azimuth_step_deg <= 10.0:
        raise ValueError("Azimuth step must be between 0.25 and 10 degrees.")

    if max_range_m <= 0.0 or max_range_m > 100000.0:
        raise ValueError(
            "Maximum range must be greater than 0 and at most 100 km."
        )

    if step_m is None:
        step_m = terrain.pixel_m

    step_m = float(step_m)

    if not math.isfinite(step_m) or step_m <= 0.0:
        raise ValueError("Sampling step must be positive and finite.")

    site_x, site_y = lonlat_to_xy(lat_deg, lon_deg)
    site_height_m = terrain.height_at(site_x, site_y)

    if not math.isfinite(site_height_m):
        raise ValueError(
            "The observation site is outside the terrain map or has missing data."
        )

    r_site = (
        MOON_RADIUS_M
        + site_height_m
        + antenna_height_m
    )

    azimuths = np.arange(
        0.0,
        360.0,
        azimuth_step_deg,
        dtype=np.float64,
    )

    # Always include the exact requested maximum range.
    distances = np.arange(
        step_m,
        max_range_m,
        step_m,
        dtype=np.float64,
    )

    distances = np.append(distances, max_range_m)

    distances = np.unique(distances)

    lat1 = math.radians(lat_deg)
    lon1 = math.radians(lon_deg)

    horizon_angles = np.full(
        azimuths.shape,
        np.nan,
        dtype=np.float64,
    )

    blocking_distances = np.full(
        azimuths.shape,
        np.nan,
        dtype=np.float64,
    )

    ray_reaches_end = np.zeros(
        azimuths.shape,
        dtype=bool,
    )

    ray_coverage_complete = np.zeros(
        azimuths.shape,
        dtype=bool,
    )

    horizon_is_complete = np.zeros(
        azimuths.shape,
        dtype=bool,
    )

    for i, azimuth_deg in enumerate(azimuths):

        bearing = math.radians(float(azimuth_deg))

        angular_distance = distances / MOON_RADIUS_M

        lat2 = np.arcsin(
            np.sin(lat1) * np.cos(angular_distance)
            + np.cos(lat1)
            * np.sin(angular_distance)
            * math.cos(bearing)
        )

        lon2 = lon1 + np.arctan2(
            math.sin(bearing)
            * np.sin(angular_distance)
            * math.cos(lat1),
            np.cos(angular_distance)
            - np.sin(lat1) * np.sin(lat2),
        )

        lat2_deg = np.degrees(lat2)
        lon2_deg = np.degrees(lon2)

        ray_x = np.empty(
            distances.shape,
            dtype=np.float64,
        )

        ray_y = np.empty(
            distances.shape,
            dtype=np.float64,
        )

        for j in range(distances.size):
            ray_x[j], ray_y[j] = lonlat_to_xy(
                float(lat2_deg[j]),
                float(lon2_deg[j]),
            )

        terrain_heights = np.array(
            [
                terrain.height_at(float(x), float(y))
                for x, y in zip(ray_x, ray_y)
            ],
            dtype=np.float64,
        )

        valid = np.isfinite(terrain_heights)

        # The last sample is exactly max_range_m.
        ray_reaches_end[i] = bool(valid[-1])

        # Complete coverage requires every sample to be valid.
        ray_coverage_complete[i] = bool(np.all(valid))

        if not np.any(valid):
            continue

        r_terrain = (
            MOON_RADIUS_M
            + terrain_heights[valid]
        )

        delta = distances[valid] / MOON_RADIUS_M

        elevation_angles = np.degrees(
            np.arctan2(
                r_terrain * np.cos(delta) - r_site,
                r_terrain * np.sin(delta),
            )
        )

        best = int(np.argmax(elevation_angles))

        horizon_angles[i] = float(
            elevation_angles[best]
        )

        blocking_distances[i] = float(
            distances[valid][best]
        )

        # A partial horizon is not a complete terrain horizon.
        horizon_is_complete[i] = ray_coverage_complete[i]

    return {
        "azimuth_deg": azimuths,
        "horizon_elevation_deg": horizon_angles,
        "blocking_distance_m": blocking_distances,
        "ray_reaches_end": ray_reaches_end,
        "ray_coverage_complete": ray_coverage_complete,
        "horizon_is_complete": horizon_is_complete,
        "site_height_m": float(site_height_m),
        "antenna_height_m": antenna_height_m,
        "max_range_m": max_range_m,
        "azimuth_step_deg": azimuth_step_deg,
        "sample_step_m": step_m,
    }


def horizon_at_azimuth(profile, azimuth_deg: float) -> float:
    """
    Interpolate the horizon elevation at any compass azimuth.
    """

    azimuth_deg = float(azimuth_deg)

    if not math.isfinite(azimuth_deg):
        raise ValueError("Azimuth must be finite.")

    azimuths = np.asarray(
        profile["azimuth_deg"],
        dtype=np.float64,
    )

    elevations = np.asarray(
        profile["horizon_elevation_deg"],
        dtype=np.float64,
    )

    if azimuths.ndim != 1 or elevations.ndim != 1:
        raise ValueError(
            "Horizon profile arrays must be one-dimensional."
        )

    if azimuths.size == 0 or azimuths.size != elevations.size:
        raise ValueError(
            "Horizon profile arrays must be non-empty and equal in size."
        )

    valid = np.isfinite(elevations)

    if not np.any(valid):
        return float("nan")

    return float(
        np.interp(
            azimuth_deg % 360.0,
            azimuths[valid],
            elevations[valid],
            period=360.0,
        )
    )
