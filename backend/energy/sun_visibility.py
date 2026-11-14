import numpy as np

from ..communications.antenna import angular_separation_deg
from ..visibility.disc_visibility import disc_sky_points


def occulted_fraction(separation_deg, sun_radius_deg, earth_radius_deg):
    """Fraction of the Sun's disc hidden behind Earth's disc."""
    d, rs, re = np.broadcast_arrays(
        np.asarray(separation_deg, dtype=float),
        np.asarray(sun_radius_deg, dtype=float),
        np.asarray(earth_radius_deg, dtype=float),
    )

    smaller = np.minimum(rs, re)

    with np.errstate(all="ignore"):
        a1 = rs ** 2 * np.arccos(
            np.clip((d ** 2 + rs ** 2 - re ** 2) / (2 * d * rs), -1, 1)
        )
        a2 = re ** 2 * np.arccos(
            np.clip((d ** 2 + re ** 2 - rs ** 2) / (2 * d * re), -1, 1)
        )
        triangle = 0.5 * np.sqrt(
            np.maximum(
                0.0,
                (-d + rs + re)
                * (d + rs - re)
                * (d - rs + re)
                * (d + rs + re),
            )
        )
        lens = a1 + a2 - triangle

    overlap = np.where(
        d >= rs + re,
        0.0,
        np.where(d <= np.abs(re - rs), np.pi * smaller ** 2, lens),
    )

    return overlap / (np.pi * rs ** 2)


def sun_visibility_from_samples(
    sun_samples,
    horizon,
    earth_samples=None,
    n_points=400,
):
    """
    Calculate terrain visibility and eclipse-adjusted sunlight fractions.

    sun_samples contain azimuth_deg, elevation_deg and angular_radius_deg.
    earth_samples, when supplied, contain the corresponding apparent Earth
    coordinates and angular radius at the same timestamps.
    """
    az = np.array([s["azimuth_deg"] for s in sun_samples], dtype=float)
    el = np.array([s["elevation_deg"] for s in sun_samples], dtype=float)
    radius = np.array(
        [s["angular_radius_deg"] for s in sun_samples],
        dtype=float,
    )

    point_az, point_el = disc_sky_points(az, el, radius, n_points)

    terrain_fraction = np.mean(
        point_el > horizon.horizon_at(point_az),
        axis=1,
    )
    complete = np.all(horizon.complete_at(point_az), axis=1)

    if earth_samples is None:
        eclipse_factor = np.ones(len(sun_samples))
    else:
        if len(earth_samples) != len(sun_samples):
            raise ValueError(
                "earth_samples must have the same length as sun_samples"
            )

        e_az = np.array(
            [e["azimuth_deg"] for e in earth_samples],
            dtype=float,
        )
        e_el = np.array(
            [e["elevation_deg"] for e in earth_samples],
            dtype=float,
        )
        e_radius = np.array(
            [e["angular_radius_deg"] for e in earth_samples],
            dtype=float,
        )

        separation = np.array(
            [
                angular_separation_deg(a1, el1, a2, el2)
                for a1, el1, a2, el2 in zip(az, el, e_az, e_el)
            ],
            dtype=float,
        )
        eclipse_factor = 1.0 - occulted_fraction(
            separation,
            radius,
            e_radius,
        )

    sun_fraction = terrain_fraction * eclipse_factor

    return [
        {
            "time": sample.get("time"),
            "azimuth_deg": float(a),
            "elevation_deg": float(e),
            "terrain_fraction": float(tf),
            "eclipse_factor": float(ef),
            "sun_fraction": float(sf),
            "sun_in_view": bool(tf > 0.0),
            "coverage_complete": bool(c),
        }
        for sample, a, e, tf, ef, sf, c in zip(
            sun_samples,
            az,
            el,
            terrain_fraction,
            eclipse_factor,
            sun_fraction,
            complete,
        )
    ]
