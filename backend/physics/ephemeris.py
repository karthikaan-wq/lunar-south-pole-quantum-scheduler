
import math

import numpy as np
import spiceypy as spice

from .kernels import load_kernels
from .time_system import to_et, et_to_utc
from .lunar_frames import ME_FRAME, sub_earth_point


# Speed of light in kilometres per second
SPEED_OF_LIGHT_KM_S = 299792.458


def position(target, observer, et, frame="J2000", abcorr="NONE"):
    """
    Calculate the position of a target relative to an observer.

    Returns:
        Position vector in kilometres
        Light-travel time in seconds
    """
    load_kernels()

    vector, light_time = spice.spkpos(
        target,
        et,
        frame,
        abcorr,
        observer
    )

    return np.array(vector), light_time


def earth_from_moon(et, frame="J2000", abcorr="NONE"):
    """Earth's position relative to the Moon."""
    return position(
        "EARTH",
        "MOON",
        et,
        frame,
        abcorr
    )


def moon_from_earth(et, frame="J2000", abcorr="NONE"):
    """Moon's position relative to the Earth."""
    return position(
        "MOON",
        "EARTH",
        et,
        frame,
        abcorr
    )


def earth_equatorial_radius_km():
    """Get Earth's equatorial radius from SPICE."""
    load_kernels()

    _, radii = spice.bodvrd("EARTH", "RADII", 3)

    return float(radii[0])


def earth_angular_radius_deg(distance_km):
    """
    Calculate Earth's apparent angular radius
    as viewed from the Moon.
    """
    radius = earth_equatorial_radius_km()

    if distance_km <= radius:
        raise ValueError(
            "Distance must be greater than Earth's radius."
        )

    return math.degrees(
        math.asin(radius / distance_km)
    )


def earth_moon_state(moment):
    """
    Calculate the Earth-Moon astronomical state
    for a supplied UTC datetime.

    Geometric and apparent distances are reported separately.
    The rover observation model uses the Moon as observer
    and Earth as target.
    """
    load_kernels()

    # Convert UTC into SPICE Ephemeris Time
    et = to_et(moment)

    # --------------------------------------------------
    # 1. GEOMETRIC POSITIONS
    # --------------------------------------------------

    # Earth relative to Moon, without light-time correction
    earth_vec_geometric, _ = earth_from_moon(
        et,
        abcorr="NONE"
    )

    # Moon relative to Earth, without light-time correction
    moon_vec_geometric, _ = moon_from_earth(
        et,
        abcorr="NONE"
    )

    # Geometric Earth-Moon distance
    geometric_distance = float(
        np.linalg.norm(earth_vec_geometric)
    )

    # --------------------------------------------------
    # 2. APPARENT ROVER OBSERVATION
    # --------------------------------------------------

    # Earth as seen from the Moon, including light travel time
    earth_vec_apparent, light_time = earth_from_moon(
        et,
        abcorr="LT"
    )

    # Apparent Earth-Moon distance
    apparent_distance = float(
        np.linalg.norm(earth_vec_apparent)
    )

    # Apparent Earth location in Moon-fixed coordinates
    longitude, latitude = sub_earth_point(et)

    # Earth's apparent angular radius uses apparent distance
    angular_radius = earth_angular_radius_deg(
        apparent_distance
    )

    # --------------------------------------------------
    # 3. RETURN RESULTS
    # --------------------------------------------------

    return {
        "utc": et_to_utc(et),
        "et_seconds": et,

        # Geometric position vectors
        "earth_from_moon_j2000_km": (
            earth_vec_geometric.tolist()
        ),
        "moon_from_earth_j2000_km": (
            moon_vec_geometric.tolist()
        ),

        # Geometric and apparent distances
        "distance_km": geometric_distance,
        "apparent_distance_km": apparent_distance,

        # Light-time corrected apparent Earth vector
        "earth_from_moon_apparent_j2000_km": (
            earth_vec_apparent.tolist()
        ),

        # One-way light travel time
        "light_time_s": light_time,

        # Apparent angular size of Earth
        "earth_angular_radius_deg": angular_radius,

        # Rover's apparent Earth coordinates
        "sub_earth_lon_deg": longitude,
        "sub_earth_lat_deg": latitude,

        "moon_frame": ME_FRAME,
        "source": "SPICE",
    }
