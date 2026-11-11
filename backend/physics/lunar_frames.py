
import math

import numpy as np
import spiceypy as spice

from .kernels import load_kernels


# Moon mean Earth / polar axis reference frame
ME_FRAME = "MOON_ME_DE440_ME421"


def frame_is_known(name=ME_FRAME):
    """
    Check whether the requested lunar reference frame
    is recognized by SPICE.
    """
    load_kernels()

    return spice.namfrm(name) != 0


def rotation_j2000_to_moon(et, frame=ME_FRAME):
    """
    Return the rotation matrix from J2000 coordinates
    into the selected Moon-fixed reference frame.
    """
    load_kernels()

    matrix = spice.pxform("J2000", frame, et)

    return np.array(matrix)


def earth_in_moon_frame(et, abcorr="NONE", frame=ME_FRAME):
    """
    Calculate Earth's position relative to the Moon,
    expressed in the selected Moon-fixed frame.

    The Moon is the observer and Earth is the target.
    Returns a position vector in kilometres.
    """
    load_kernels()

    vector, light_time = spice.spkpos(
        "EARTH",
        et,
        frame,
        abcorr,
        "MOON"
    )

    return np.array(vector)


def sub_earth_point(et, abcorr="LT", frame=ME_FRAME):
    """
    Calculate Earth's apparent longitude and latitude
    in the Moon-fixed frame, as seen from the Moon.
    """
    vector = earth_in_moon_frame(
        et,
        abcorr=abcorr,
        frame=frame
    )

    _, longitude, latitude = spice.reclat(vector)

    return (
        math.degrees(longitude),
        math.degrees(latitude)
    )


def horizons_sub_observer_point(et, frame=ME_FRAME):
    """
    Calculate the apparent sub-observer point on the Moon
    as seen by an observer on Earth.

    This function is separate from the rover observation
    calculation and is intended for Horizons comparison.
    """
    load_kernels()

    vector, light_time = spice.spkpos(
        "MOON",
        et,
        frame,
        "LT",
        "EARTH"
    )

    vector = -np.array(vector)

    _, longitude, latitude = spice.reclat(vector)

    return (
        math.degrees(longitude),
        math.degrees(latitude)
    )
