
from dataclasses import dataclass
import math


def angular_separation_deg(
    azimuth1_deg: float,
    elevation1_deg: float,
    azimuth2_deg: float,
    elevation2_deg: float,
) -> float:
    """
    Calculate the spherical angular separation between
    two directions expressed as azimuth and elevation.

    Azimuth is measured clockwise from north.
    Elevation is measured from the local horizontal plane.
    """

    values = (
        azimuth1_deg,
        elevation1_deg,
        azimuth2_deg,
        elevation2_deg,
    )

    if not all(math.isfinite(value) for value in values):
        raise ValueError("All pointing angles must be finite.")

    if not (
        -90.0 <= elevation1_deg <= 90.0
        and -90.0 <= elevation2_deg <= 90.0
    ):
        raise ValueError("Elevation must be between -90 and 90 degrees.")

    az1 = math.radians(azimuth1_deg)
    el1 = math.radians(elevation1_deg)
    az2 = math.radians(azimuth2_deg)
    el2 = math.radians(elevation2_deg)

    dot = (
        math.sin(el1) * math.sin(el2)
        + math.cos(el1) * math.cos(el2) * math.cos(az1 - az2)
    )

    return math.degrees(math.acos(max(-1.0, min(1.0, dot))))


def azimuth_in_range(
    azimuth_deg: float,
    minimum_deg: float,
    maximum_deg: float,
) -> bool:
    """
    Check whether an azimuth lies inside a permitted range.

    Supports ranges crossing north, such as 300 to 60 degrees.
    A range spanning 360 degrees permits every azimuth.
    """

    values = (azimuth_deg, minimum_deg, maximum_deg)

    if not all(math.isfinite(value) for value in values):
        raise ValueError("Azimuth range values must be finite.")

    azimuth = azimuth_deg % 360.0
    minimum = minimum_deg % 360.0
    maximum = maximum_deg % 360.0

    if abs(maximum_deg - minimum_deg) >= 360.0:
        return True

    if minimum <= maximum:
        return minimum <= azimuth <= maximum

    return azimuth >= minimum or azimuth <= maximum


@dataclass(frozen=True)
class AntennaConfig:
    """
    Mechanical and pointing configuration for a lunar antenna.

    kind:
        "steerable" or "fixed"

    For a steerable antenna:
        Azimuth and elevation limits define its mechanical range.

    For a fixed antenna:
        boresight_azimuth_deg and boresight_elevation_deg
        define its fixed pointing direction.
        half_beamwidth_deg defines its angular acceptance radius.
    """

    kind: str = "steerable"

    min_elevation_deg: float = -10.0
    max_elevation_deg: float = 90.0

    min_azimuth_deg: float = 0.0
    max_azimuth_deg: float = 360.0

    boresight_azimuth_deg: float = 0.0
    boresight_elevation_deg: float = 0.0

    half_beamwidth_deg: float = 5.0

    def __post_init__(self):
        if self.kind not in ("steerable", "fixed"):
            raise ValueError(
                "Antenna kind must be 'steerable' or 'fixed'."
            )

        numeric_values = (
            self.min_elevation_deg,
            self.max_elevation_deg,
            self.min_azimuth_deg,
            self.max_azimuth_deg,
            self.boresight_azimuth_deg,
            self.boresight_elevation_deg,
            self.half_beamwidth_deg,
        )

        if not all(math.isfinite(value) for value in numeric_values):
            raise ValueError("Antenna configuration values must be finite.")

        if not (
            -90.0 <= self.min_elevation_deg
            <= self.max_elevation_deg <= 90.0
        ):
            raise ValueError("Invalid mechanical elevation limits.")

        if not (
            -90.0 <= self.boresight_elevation_deg <= 90.0
        ):
            raise ValueError("Boresight elevation must be between -90 and 90 degrees.")

        if not (0.0 < self.half_beamwidth_deg <= 180.0):
            raise ValueError("Half-beamwidth must be in (0, 180].")


def pointing_ok(
    azimuth_deg: float,
    elevation_deg: float,
    config: AntennaConfig,
) -> bool:
    """
    Determine whether an antenna can point toward a target.

    Steerable:
        Target must be within mechanical azimuth and elevation limits.

    Fixed:
        Target must be inside the fixed antenna beam.
        Target must also be within mechanical elevation limits.
    """

    if not isinstance(config, AntennaConfig):
        raise TypeError("config must be an AntennaConfig.")

    if not (
        math.isfinite(azimuth_deg)
        and math.isfinite(elevation_deg)
    ):
        raise ValueError("Target pointing angles must be finite.")

    if not -90.0 <= elevation_deg <= 90.0:
        raise ValueError("Target elevation must be between -90 and 90 degrees.")

    if not (
        config.min_elevation_deg
        <= elevation_deg
        <= config.max_elevation_deg
    ):
        return False

    if config.kind == "steerable":
        return azimuth_in_range(
            azimuth_deg,
            config.min_azimuth_deg,
            config.max_azimuth_deg,
        )

    separation = angular_separation_deg(
        azimuth_deg,
        elevation_deg,
        config.boresight_azimuth_deg,
        config.boresight_elevation_deg,
    )

    return separation <= config.half_beamwidth_deg
