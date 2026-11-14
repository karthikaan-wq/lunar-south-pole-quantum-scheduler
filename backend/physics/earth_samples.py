
from __future__ import annotations

from typing import Sequence

from .earth_geometry import (
    earth_from_lander_moon_fixed,
    sample_from_vector,
)
from .time_system import (
    et_to_utc,
    parse_utc,
    to_et,
)


def earth_samples_at(
    lat_deg: float,
    lon_deg: float,
    height_m: float,
    time_strings: Sequence[str],
) -> list[dict]:
    """
    Calculate Earth's apparent geometry at a lunar surface site
    for a sequence of UTC timestamps.

    Uses the existing Phase 6 SPICE Earth geometry functions.

    Parameters:
        lat_deg: Lunar latitude in degrees.
        lon_deg: East longitude in degrees.
        height_m: Observer height above the lunar reference sphere,
                  in metres. Include antenna height when appropriate.
        time_strings: Sequence of ISO-format UTC timestamps.

    Returns:
        A list of dictionaries containing:
            utc
            azimuth_deg
            elevation_deg
            distance_km
            angular_radius_deg
            lower_limb_elevation_deg
            upper_limb_elevation_deg

    All Earth geometry is expressed relative to the local
    lunar observer and uses geometric SPICE correction NONE.
    """

    if not -90.0 <= float(lat_deg) <= 90.0:
        raise ValueError("Latitude must be between -90 and 90 degrees.")

    if not -360.0 <= float(lon_deg) <= 360.0:
        raise ValueError("Longitude must be between -360 and 360 degrees.")

    if float(height_m) < 0.0:
        raise ValueError("Observer height cannot be negative.")

    if not time_strings:
        return []

    samples = []

    for timestamp in time_strings:
        if not isinstance(timestamp, str) or not timestamp.strip():
            raise ValueError("Every timestamp must be a non-empty string.")

        # Convert the input UTC timestamp into SPICE Ephemeris Time.
        moment = parse_utc(timestamp)
        et = to_et(moment)

        # Calculate Earth's direction from the lunar observer.
        earth_vector, distance_km, _ = earth_from_lander_moon_fixed(
            lat_deg=float(lat_deg),
            lon_deg=float(lon_deg),
            height_m=float(height_m),
            et=et,
            abcorr="NONE",
        )

        # Convert the Earth vector into local apparent geometry.
        sample = sample_from_vector(
            earth_vector_moon_fixed=earth_vector,
            lat_deg=float(lat_deg),
            lon_deg=float(lon_deg),
        )

        sample["utc"] = et_to_utc(et)

        # Preserve the distance returned by the geometry function.
        sample["distance_km"] = float(distance_km)

        samples.append(sample)

    return samples
