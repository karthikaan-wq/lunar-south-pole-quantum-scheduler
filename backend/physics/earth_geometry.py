
import numpy as np

from .coordinates import (
    surface_vector_moon_fixed,
    local_axes,
)
from .kernels import load_kernels
from .lunar_frames import (
    ME_FRAME,
    earth_in_moon_frame,
    rotation_j2000_to_moon,
)
from .time_system import et_to_utc

import spiceypy as spice


def lander_position_j2000(
    lat_deg,
    lon_deg,
    height_m,
    et,
):
    """
    Calculate the lander's position relative to Earth's centre
    in the J2000 reference frame.

    Returns a position vector in kilometres.
    """
    load_kernels()

    # Lander position relative to the Moon's centre
    site_moon = surface_vector_moon_fixed(
        lat_deg,
        lon_deg,
        height_m,
    )

    # Moon position relative to Earth's centre in J2000
    moon_position, _ = spice.spkpos(
        "MOON",
        et,
        "J2000",
        "NONE",
        "EARTH",
    )

    # Convert Moon-fixed site vector into J2000 coordinates.
    # rotation_j2000_to_moon maps J2000 -> Moon-fixed,
    # so its transpose maps Moon-fixed -> J2000.
    rotation = rotation_j2000_to_moon(et)
    site_j2000 = rotation.T @ site_moon

    return np.array(moon_position) + site_j2000


def local_axes_j2000(
    lat_deg,
    lon_deg,
    et,
):
    """
    Calculate local East, North, and Up unit vectors
    in the J2000 reference frame.

    Returns (east, north, up).
    """
    load_kernels()

    east_moon, north_moon, up_moon = local_axes(
        lat_deg,
        lon_deg,
    )

    rotation = rotation_j2000_to_moon(et)

    # Convert each local direction from Moon-fixed to J2000.
    east_j2000 = rotation.T @ east_moon
    north_j2000 = rotation.T @ north_moon
    up_j2000 = rotation.T @ up_moon

    return (
        east_j2000,
        north_j2000,
        up_j2000,
    )


def earth_from_lander_j2000(
    lat_deg,
    lon_deg,
    height_m,
    et,
):
    """
    Calculate the direction and distance from the lander
    toward Earth's centre in J2000 coordinates.

    Returns:
        earth_vector: vector from lander to Earth, km
        distance_km: distance to Earth's centre, km
        unit_vector: normalized direction toward Earth
    """
    lander = lander_position_j2000(
        lat_deg,
        lon_deg,
        height_m,
        et,
    )

    # Earth is the origin of the Earth-centred J2000 frame.
    earth_vector = -lander

    distance_km = float(np.linalg.norm(earth_vector))

    if distance_km == 0:
        raise ValueError("Lander position cannot coincide with Earth's centre.")

    unit_vector = earth_vector / distance_km

    return (
        earth_vector,
        distance_km,
        unit_vector,
    )


def earth_from_lander_moon_fixed(
    lat_deg,
    lon_deg,
    height_m,
    et,
    abcorr="NONE",
):
    """
    Calculate Earth's direction from the lander,
    expressed in the Moon-fixed reference frame.

    Returns:
        earth_vector: vector from lander toward Earth, km
        distance_km: distance to Earth's centre, km
        unit_vector: normalized direction toward Earth
    """
    load_kernels()

    # Earth position relative to the Moon.
    earth_moon = earth_in_moon_frame(
        et,
        abcorr=abcorr,
        frame=ME_FRAME,
    )

    # Lander position relative to the Moon.
    site_moon = surface_vector_moon_fixed(
        lat_deg,
        lon_deg,
        height_m,
    )

    earth_vector = earth_moon - site_moon

    distance_km = float(np.linalg.norm(earth_vector))

    if distance_km == 0:
        raise ValueError("Earth and lander positions cannot coincide.")

    unit_vector = earth_vector / distance_km

    return (
        earth_vector,
        distance_km,
        unit_vector,
    )


def lander_state(
    lat_deg,
    lon_deg,
    height_m,
    et,
):
    """
    Calculate the complete geometric state of a lunar lander.

    Returns its:
        - UTC timestamp
        - Moon-fixed position
        - J2000 position
        - Local East, North, Up directions in J2000
        - Earth direction in J2000
        - Earth direction in Moon-fixed coordinates
    """
    load_kernels()

    site_moon = surface_vector_moon_fixed(
        lat_deg,
        lon_deg,
        height_m,
    )

    lander_j2000 = lander_position_j2000(
        lat_deg,
        lon_deg,
        height_m,
        et,
    )

    east_j2000, north_j2000, up_j2000 = local_axes_j2000(
        lat_deg,
        lon_deg,
        et,
    )

    earth_j2000, distance_j2000, earth_unit_j2000 = (
        earth_from_lander_j2000(
            lat_deg,
            lon_deg,
            height_m,
            et,
        )
    )

    earth_moon, distance_moon, earth_unit_moon = (
        earth_from_lander_moon_fixed(
            lat_deg,
            lon_deg,
            height_m,
            et,
            abcorr="NONE",
        )
    )

    return {
        "utc": et_to_utc(et),
        "latitude_deg": float(lat_deg),
        "longitude_deg": float(lon_deg),
        "height_m": float(height_m),

        "moon_fixed_position_km": site_moon.tolist(),

        "j2000_position_km": lander_j2000.tolist(),

        "local_axes_j2000": {
            "east": east_j2000.tolist(),
            "north": north_j2000.tolist(),
            "up": up_j2000.tolist(),
        },

        "earth_from_lander_j2000": {
            "vector_km": earth_j2000.tolist(),
            "distance_km": distance_j2000,
            "unit_vector": earth_unit_j2000.tolist(),
        },

        "earth_from_lander_moon_fixed": {
            "vector_km": earth_moon.tolist(),
            "distance_km": distance_moon,
            "unit_vector": earth_unit_moon.tolist(),
        },
    }
