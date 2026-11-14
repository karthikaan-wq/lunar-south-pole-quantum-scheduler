
import numpy as np


GOLDEN_ANGLE = np.pi * (3.0 - np.sqrt(5.0))


class HorizonModel:
    """
    Represents a terrain horizon sampled around 360 degrees.

    Horizon elevations are interpolated linearly between
    adjacent azimuth samples, including across north.

    Regular sampling intervals are required, but the final
    wraparound interval may be shorter when the requested
    spacing does not divide 360 degrees exactly.
    """

    def __init__(
        self,
        azimuth_deg,
        horizon_deg,
        complete=None,
    ):
        az = np.asarray(azimuth_deg, dtype=float)
        horizon = np.asarray(horizon_deg, dtype=float)

        if az.ndim != 1 or horizon.ndim != 1:
            raise ValueError(
                "Azimuth and horizon arrays must be one-dimensional."
            )

        if len(az) != len(horizon):
            raise ValueError(
                "Azimuth and horizon arrays must have equal lengths."
            )

        if len(az) < 8:
            raise ValueError(
                "At least 8 azimuth samples are required."
            )

        if not np.all(np.isfinite(az)):
            raise ValueError(
                "Azimuth values must be finite."
            )

        if np.any(az < 0.0) or np.any(az >= 360.0):
            raise ValueError(
                "Azimuth values must be in [0, 360)."
            )

        order = np.argsort(az)

        self.az = az[order]
        horizon = horizon[order]

        differences = np.diff(self.az)

        if np.any(differences <= 0.0):
            raise ValueError(
                "Azimuth samples must be unique."
            )

        expected_step = float(differences[0])

        if not np.allclose(
            differences,
            expected_step,
            rtol=1e-5,
            atol=1e-8,
        ):
            raise ValueError(
                "Azimuth samples must have regular spacing."
            )

        wrap_step = self.az[0] + 360.0 - self.az[-1]

        if not (
            0.0 < wrap_step <= expected_step + 1e-8
        ):
            raise ValueError(
                "Azimuth samples must cover the complete 360-degree circle."
            )

        self.step = expected_step
        self.az0 = float(self.az[0])

        if complete is None:
            complete = np.ones(len(az), dtype=bool)

        else:
            complete = np.asarray(
                complete,
                dtype=bool,
            )

            if complete.ndim != 1 or len(complete) != len(az):
                raise ValueError(
                    "Coverage array must match the azimuth array."
                )

            complete = complete[order]

        self.complete = complete & np.isfinite(horizon)

        # Missing horizon values are provisionally treated as
        # -90 degrees for interpolation, but remain incomplete.
        self.h = np.where(
            np.isfinite(horizon),
            horizon,
            -90.0,
        )

    @classmethod
    def from_profile(
        cls,
        profile,
        angle_key,
        complete_key=None,
    ):
        complete = (
            None
            if complete_key is None
            else profile[complete_key]
        )

        return cls(
            profile["azimuth_deg"],
            profile[angle_key],
            complete,
        )

    def horizon_at(self, azimuth_deg):
        """
        Interpolate horizon elevation at arbitrary azimuths.
        """

        return np.interp(
            np.asarray(azimuth_deg, dtype=float),
            self.az,
            self.h,
            period=360.0,
        )

    def complete_at(self, azimuth_deg):
        """
        Return whether both neighbouring horizon samples
        have complete terrain coverage.

        Uses actual neighbouring sample positions, including
        the shorter final wraparound interval.
        """

        azimuth = np.asarray(
            azimuth_deg,
            dtype=float,
        )

        if not np.all(np.isfinite(azimuth)):
            raise ValueError(
                "Azimuth values must be finite."
            )

        normalized = azimuth % 360.0

        upper = (
            np.searchsorted(
                self.az,
                normalized,
                side="right",
            )
            % len(self.az)
        )

        lower = (
            upper - 1
        ) % len(self.az)

        return (
            self.complete[lower]
            & self.complete[upper]
        )


def disc_pattern(n_points=400):
    """
    Generate area-uniform points inside a circular disc
    using a sunflower/golden-angle distribution.
    """

    if not isinstance(n_points, (int, np.integer)) or isinstance(
        n_points,
        (bool, np.bool_),
    ):
        raise ValueError(
            "n_points must be a positive integer."
        )

    if n_points <= 0:
        raise ValueError(
            "n_points must be positive."
        )

    i = np.arange(n_points)

    radius_fraction = np.sqrt(
        (i + 0.5) / n_points
    )

    phi = i * GOLDEN_ANGLE

    return radius_fraction, phi


def disc_sky_points(
    az_deg,
    el_deg,
    radius_deg,
    n_points=400,
):
    """
    Generate points distributed across Earth's apparent disc.

    Inputs:
        az_deg: Earth-centre azimuth.
        el_deg: Earth-centre elevation.
        radius_deg: Earth's apparent angular radius.
        n_points: Number of points per disc.

    Returns:
        point_azimuth_deg
        point_elevation_deg

    Both outputs have shape (number_of_time_samples, n_points).
    """

    az_c = np.atleast_1d(
        np.asarray(az_deg, dtype=float)
    )

    el_c = np.atleast_1d(
        np.asarray(el_deg, dtype=float)
    )

    radius_c = np.atleast_1d(
        np.asarray(radius_deg, dtype=float)
    )

    if az_c.ndim != 1 or el_c.ndim != 1 or radius_c.ndim != 1:
        raise ValueError(
            "Disc centre inputs must be one-dimensional."
        )

    if not (
        len(az_c) == len(el_c) == len(radius_c)
    ):
        raise ValueError(
            "Azimuth, elevation, and radius arrays must have equal lengths."
        )

    if not (
        np.all(np.isfinite(az_c))
        and np.all(np.isfinite(el_c))
        and np.all(np.isfinite(radius_c))
    ):
        raise ValueError(
            "Disc geometry inputs must be finite."
        )

    if np.any((el_c < -90.0) | (el_c > 90.0)):
        raise ValueError(
            "Elevation must be between -90 and 90 degrees."
        )

    if np.any(radius_c < 0.0) or np.any(radius_c > 180.0):
        raise ValueError(
            "Angular radius must be between 0 and 180 degrees."
        )

    radius_fraction, phi = disc_pattern(n_points)

    az_c = np.radians(az_c)[:, None]
    el_c = np.radians(el_c)[:, None]

    r = (
        np.radians(radius_c)[:, None]
        * radius_fraction[None, :]
    )

    sin_el = (
        np.sin(el_c) * np.cos(r)
        + np.cos(el_c) * np.sin(r) * np.cos(phi)[None, :]
    )

    az = az_c + np.arctan2(
        np.sin(phi)[None, :] * np.sin(r) * np.cos(el_c),
        np.cos(r) - np.sin(el_c) * sin_el,
    )

    return (
        np.degrees(az) % 360.0,
        np.degrees(
            np.arcsin(
                np.clip(sin_el, -1.0, 1.0)
            )
        ),
    )
