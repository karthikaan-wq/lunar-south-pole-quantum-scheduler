
import math

import numpy as np
import spiceypy as spice

from .coordinates import (
    surface_vector_moon_fixed,
    azimuth_elevation,
)
from .kernels import load_kernels
from .lunar_frames import ME_FRAME
from .time_system import parse_utc, to_et


SUN_RADIUS_KM = 695700.0


def sun_at_times(
    lat_deg,
    lon_deg,
    height_m,
    time_strings,
):
    """
    Calculate the apparent Sun direction from a lunar surface site.

    Uses:
        Target: SUN
        Observer: MOON
        Frame: MOON_ME_DE440_ME421
        Aberration correction: NONE

    The observer is positioned at the specified lunar surface
    coordinates and height.

    Returns one record per input UTC timestamp containing:
        - UTC timestamp
        - Sun azimuth
        - Sun elevation
        - Sun distance
        - Sun angular radius

    Height must use the same reference convention as the
    Earth-track calculation.
    """

    if not (
        math.isfinite(lat_deg)
        and math.isfinite(lon_deg)
        and math.isfinite(height_m)
    ):
        raise ValueError("Site coordinates and height must be finite.")

    if not -90.0 <= lat_deg <= 90.0:
        raise ValueError("Latitude must be between -90 and 90 degrees.")

    if not -180.0 <= lon_deg <= 180.0:
        raise ValueError("Longitude must be between -180 and 180 degrees.")

    if not isinstance(time_strings, (list, tuple)):
        raise TypeError("time_strings must be a list or tuple.")

    if not time_strings:
        return []

    for index, timestamp in enumerate(time_strings):
        if not isinstance(timestamp, str) or not timestamp.strip():
            raise ValueError(
                f"Timestamp at index {index} must be a non-empty string."
            )

    # Load the existing project kernels once.
    load_kernels()

    # Position of the lunar observer in the Moon-fixed frame.
    site_vector = surface_vector_moon_fixed(
        lat_deg,
        lon_deg,
        height_m,
    )

    results = []

    for timestamp in time_strings:
        moment = parse_utc(timestamp)
        et = to_et(moment)

        # SPICE returns the Moon-to-Sun vector in kilometres.
        sun_moon, _ = spice.spkpos(
            "SUN",
            et,
            ME_FRAME,
            "NONE",
            "MOON",
        )

        sun_moon = np.asarray(sun_moon, dtype=float)

        # Convert the Moon-centred Sun vector into a
        # lander-centred Sun vector.
        sun_from_site = sun_moon - site_vector

        azimuth, elevation, distance_km = azimuth_elevation(
            sun_from_site,
            lat_deg,
            lon_deg,
        )

        if not math.isfinite(distance_km) or distance_km <= SUN_RADIUS_KM:
            raise ValueError(
                f"Invalid Sun distance at timestamp {timestamp}."
            )

        # Apparent angular radius of the Sun.
        angular_radius_deg = math.degrees(
            math.asin(
                min(1.0, SUN_RADIUS_KM / distance_km)
            )
        )

        results.append({
            "utc": timestamp,
            "azimuth_deg": float(azimuth),
            "elevation_deg": float(elevation),
            "distance_km": float(distance_km),
            "angular_radius_deg": float(angular_radius_deg),
        })

    return results
