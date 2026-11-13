
import math

import numpy as np


# LOLA elevation maps give heights above a sphere
# with this reference radius.
MOON_REFERENCE_RADIUS_KM = 1737.4


def normalize_lon(lon_deg):
    """
    Normalize longitude into the range -180 to +180 degrees.
    East longitude is positive.
    """
    return ((lon_deg + 180.0) % 360.0) - 180.0


def surface_vector_moon_fixed(lat_deg, lon_deg, height_m=0.0):
    """
    Calculate the position of a lunar surface point
    relative to the Moon's centre.

    Parameters:
        lat_deg: Latitude in degrees.
        lon_deg: Longitude in degrees.
        height_m: Height above the reference sphere in metres.

    Returns:
        NumPy array [x, y, z] in kilometres,
        expressed in the Moon-fixed frame.
    """

    radius = MOON_REFERENCE_RADIUS_KM + height_m / 1000.0

    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)

    return np.array([
        radius * math.cos(lat) * math.cos(lon),
        radius * math.cos(lat) * math.sin(lon),
        radius * math.sin(lat)
    ])


def local_axes(lat_deg, lon_deg):
    """
    Calculate the local East, North and Up unit vectors
    at a lunar surface location.

    Returns:
        east, north, up

    All vectors are expressed in the Moon-fixed frame.
    """

    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)

    east = np.array([
        -math.sin(lon),
        math.cos(lon),
        0.0
    ])

    north = np.array([
        -math.sin(lat) * math.cos(lon),
        -math.sin(lat) * math.sin(lon),
        math.cos(lat)
    ])

    up = np.array([
        math.cos(lat) * math.cos(lon),
        math.cos(lat) * math.sin(lon),
        math.sin(lat)
    ])

    return east, north, up


def enu_matrix(lat_deg, lon_deg):
    """
    Construct a transformation matrix that converts
    Moon-fixed vectors into local East-North-Up components.
    """

    east, north, up = local_axes(lat_deg, lon_deg)

    return np.vstack([
        east,
        north,
        up
    ])


def azimuth_elevation(vector_moon_fixed, lat_deg, lon_deg):
    """
    Calculate azimuth, elevation and distance for a vector
    expressed in the Moon-fixed frame.

    Azimuth is measured clockwise from local north:
        0 degrees   = North
        90 degrees  = East
        180 degrees = South
        270 degrees = West

    Elevation is measured relative to the local flat horizon:
        +90 degrees = Directly overhead
          0 degrees = Horizon
        -90 degrees = Directly below

    Parameters:
        vector_moon_fixed: Target direction vector in kilometres.
        lat_deg: Observer latitude in degrees.
        lon_deg: Observer longitude in degrees.

    Returns:
        azimuth_deg, elevation_deg, distance_km
    """

    vector = np.asarray(vector_moon_fixed, dtype=float)

    if vector.shape != (3,):
        raise ValueError("Direction vector must contain exactly 3 components.")

    if not np.all(np.isfinite(vector)):
        raise ValueError("Direction vector must contain only finite values.")

    distance_km = float(np.linalg.norm(vector))

    if distance_km == 0.0:
        raise ValueError("Direction vector cannot have zero length.")

    enu = enu_matrix(lat_deg, lon_deg) @ vector

    east = float(enu[0])
    north = float(enu[1])
    up = float(enu[2])

    azimuth_deg = math.degrees(math.atan2(east, north)) % 360.0

    elevation_ratio = max(-1.0, min(1.0, up / distance_km))
    elevation_deg = math.degrees(math.asin(elevation_ratio))

    return azimuth_deg, elevation_deg, distance_km
