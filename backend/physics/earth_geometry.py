
import math
from datetime import timedelta

import numpy as np
import spiceypy as spice

from .coordinates import (
    surface_vector_moon_fixed,
    local_axes,
    azimuth_elevation,
)
from .kernels import load_kernels
from .lunar_frames import (
    ME_FRAME,
    earth_in_moon_frame,
    rotation_j2000_to_moon,
)
from .time_system import (
    parse_utc,
    to_et,
    et_to_utc,
)


EARTH_EQUATORIAL_RADIUS_KM = 6378.137
DEFAULT_TRACK_STEP_MINUTES = 5
MAX_TRACK_SAMPLES = 20000


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

    site_moon = surface_vector_moon_fixed(
        lat_deg,
        lon_deg,
        height_m,
    )

    moon_position, _ = spice.spkpos(
        "MOON",
        et,
        "J2000",
        "NONE",
        "EARTH",
    )

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

    earth_vector = -lander
    distance_km = float(np.linalg.norm(earth_vector))

    if distance_km == 0:
        raise ValueError(
            "Lander position cannot coincide with Earth's centre."
        )

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

    earth_moon = earth_in_moon_frame(
        et,
        abcorr=abcorr,
        frame=ME_FRAME,
    )

    site_moon = surface_vector_moon_fixed(
        lat_deg,
        lon_deg,
        height_m,
    )

    earth_vector = earth_moon - site_moon
    distance_km = float(np.linalg.norm(earth_vector))

    if distance_km == 0:
        raise ValueError(
            "Earth and lander positions cannot coincide."
        )

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


# ============================================================
# PHASE 6: EARTH DIRECTION AND APPARENT GEOMETRY
# ============================================================

def earth_angular_radius_deg(distance_km):
    """
    Calculate Earth's apparent angular radius as seen
    from the lander.

    Uses the Earth's equatorial radius and geometric distance
    to Earth's centre.

    This is an angular-radius approximation, not a terrain
    visibility calculation.
    """
    distance_km = float(distance_km)

    if not math.isfinite(distance_km):
        raise ValueError("Distance must be finite.")

    if distance_km <= EARTH_EQUATORIAL_RADIUS_KM:
        raise ValueError(
            "Distance must be greater than Earth's radius."
        )

    ratio = EARTH_EQUATORIAL_RADIUS_KM / distance_km

    return math.degrees(math.asin(ratio))


def sample_from_vector(
    earth_vector_moon_fixed,
    lat_deg,
    lon_deg,
):
    """
    Convert an Earth direction vector into local azimuth,
    elevation, distance, and apparent angular-radius values.

    The elevation is measured relative to a flat local horizon.
    """
    azimuth_deg, elevation_deg, distance_km = azimuth_elevation(
        earth_vector_moon_fixed,
        lat_deg,
        lon_deg,
    )

    angular_radius_deg = earth_angular_radius_deg(distance_km)

    return {
        "azimuth_deg": azimuth_deg,
        "elevation_deg": elevation_deg,
        "distance_km": distance_km,
        "angular_radius_deg": angular_radius_deg,
        "lower_limb_elevation_deg": (
            elevation_deg - angular_radius_deg
        ),
        "upper_limb_elevation_deg": (
            elevation_deg + angular_radius_deg
        ),
    }


def earth_direction(
    lat_deg,
    lon_deg,
    height_m,
    utc,
):
    """
    Calculate Earth's geometric direction from a lunar lander
    at a specified UTC time.

    Returns azimuth, centre elevation, distance, angular radius,
    and upper/lower limb elevations.
    """
    moment = parse_utc(utc)
    et = to_et(moment)

    earth_vector, distance_km, unit_vector = (
        earth_from_lander_moon_fixed(
            lat_deg,
            lon_deg,
            height_m,
            et,
            abcorr="NONE",
        )
    )

    result = sample_from_vector(
        earth_vector,
        lat_deg,
        lon_deg,
    )

    result.update({
        "utc": et_to_utc(et),
        "latitude_deg": float(lat_deg),
        "longitude_deg": float(lon_deg),
        "height_m": float(height_m),
        "earth_vector_moon_fixed_km": earth_vector.tolist(),
        "earth_unit_vector_moon_fixed": unit_vector.tolist(),
        "distance_km": distance_km,
        "correction": "NONE",
        "horizon_model": "flat",
    })

    return result


def summarize_track(samples):
    """
    Summarize an Earth elevation track.

    The summary describes Earth's centre and apparent upper
    and lower limbs relative to a flat local horizon.
    """
    if not samples:
        raise ValueError("Cannot summarize an empty Earth track.")

    elevations = [
        float(sample["elevation_deg"])
        for sample in samples
    ]

    upper_limb = [
        float(sample["upper_limb_elevation_deg"])
        for sample in samples
    ]

    lower_limb = [
        float(sample["lower_limb_elevation_deg"])
        for sample in samples
    ]

    return {
        "sample_count": len(samples),

        "minimum_elevation_deg": min(elevations),
        "maximum_elevation_deg": max(elevations),

        "minimum_upper_limb_elevation_deg": min(upper_limb),
        "maximum_upper_limb_elevation_deg": max(upper_limb),

        "minimum_lower_limb_elevation_deg": min(lower_limb),
        "maximum_lower_limb_elevation_deg": max(lower_limb),

        "earth_centre_above_flat_horizon_samples": sum(
            elevation > 0.0 for elevation in elevations
        ),

        "earth_disc_intersects_flat_horizon_samples": sum(
            sample["upper_limb_elevation_deg"] > 0.0
            and sample["lower_limb_elevation_deg"] < 0.0
            for sample in samples
        ),

        "earth_disc_entirely_above_flat_horizon_samples": sum(
            sample["lower_limb_elevation_deg"] >= 0.0
            for sample in samples
        ),
    }


def earth_track(
    lat_deg,
    lon_deg,
    height_m,
    start_utc,
    duration_days,
    step_minutes=DEFAULT_TRACK_STEP_MINUTES,
):
    """
    Sample Earth's geometric direction over a time interval.

    Parameters:
        lat_deg: Lander latitude in degrees.
        lon_deg: Lander longitude in degrees.
        height_m: Lander height above the reference sphere.
        start_utc: ISO-format UTC start time.
        duration_days: Positive duration in days.
        step_minutes: Positive sampling interval in minutes.

    The number of samples is limited to MAX_TRACK_SAMPLES.
    The final sample is included even when the duration is
    not an exact multiple of the sampling interval.
    """
    duration_days = float(duration_days)
    step_minutes = float(step_minutes)

    if not math.isfinite(duration_days) or duration_days <= 0:
        raise ValueError("duration_days must be a finite positive number.")

    if not math.isfinite(step_minutes) or step_minutes <= 0:
        raise ValueError("step_minutes must be a finite positive number.")

    start = parse_utc(start_utc)
    duration = timedelta(days=duration_days)
    step = timedelta(minutes=step_minutes)
    end = start + duration

    total_seconds = duration.total_seconds()
    step_seconds = step.total_seconds()

    full_steps = int(total_seconds // step_seconds)

    sample_count = full_steps + 1

    if full_steps * step_seconds < total_seconds:
        sample_count += 1

    if sample_count > MAX_TRACK_SAMPLES:
        raise ValueError(
            f"Track requires {sample_count} samples; "
            f"maximum allowed is {MAX_TRACK_SAMPLES}."
        )

    samples = []

    for index in range(full_steps + 1):
        moment = start + index * step

        et = to_et(moment)

        earth_vector, _, _ = earth_from_lander_moon_fixed(
            lat_deg,
            lon_deg,
            height_m,
            et,
            abcorr="NONE",
        )

        sample = sample_from_vector(
            earth_vector,
            lat_deg,
            lon_deg,
        )

        sample["utc"] = et_to_utc(et)
        samples.append(sample)

    # Include the exact end time when it does not fall
    # on a regular sampling interval.
    if samples[-1]["utc"] != et_to_utc(to_et(end)):
        end_et = to_et(end)

        earth_vector, _, _ = earth_from_lander_moon_fixed(
            lat_deg,
            lon_deg,
            height_m,
            end_et,
            abcorr="NONE",
        )

        final_sample = sample_from_vector(
            earth_vector,
            lat_deg,
            lon_deg,
        )

        final_sample["utc"] = et_to_utc(end_et)
        samples.append(final_sample)

    return {
        "latitude_deg": float(lat_deg),
        "longitude_deg": float(lon_deg),
        "height_m": float(height_m),
        "start_utc": et_to_utc(to_et(start)),
        "end_utc": et_to_utc(to_et(end)),
        "duration_days": duration_days,
        "step_minutes": step_minutes,
        "sample_count": len(samples),
        "correction": "NONE",
        "horizon_model": "flat",
        "samples": samples,
        "summary": summarize_track(samples),
    }
