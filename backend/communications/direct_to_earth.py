
from dataclasses import dataclass
import math

from .antenna import (
    AntennaConfig,
    angular_separation_deg,
    pointing_ok,
)
from backend.visibility.disc_visibility import HorizonModel


@dataclass(frozen=True)
class LinkConstraints:
    """Configurable requirements for a direct-to-Earth link."""

    min_visible_fraction: float = 0.5
    min_clearance_deg: float = 0.5
    require_complete_terrain: bool = True

    sun_exclusion_deg: float = 3.0
    sun_exclusion_only_if_sun_in_view: bool = True

    def __post_init__(self):
        if not math.isfinite(self.min_visible_fraction):
            raise ValueError("Minimum visible fraction must be finite.")

        if not 0.0 <= self.min_visible_fraction <= 1.0:
            raise ValueError(
                "Minimum visible fraction must be between 0 and 1."
            )

        if not math.isfinite(self.min_clearance_deg):
            raise ValueError("Minimum clearance must be finite.")

        if not -90.0 <= self.min_clearance_deg <= 90.0:
            raise ValueError(
                "Minimum clearance must be between -90 and 90 degrees."
            )

        if not math.isfinite(self.sun_exclusion_deg):
            raise ValueError("Sun exclusion angle must be finite.")

        if not 0.0 <= self.sun_exclusion_deg <= 180.0:
            raise ValueError(
                "Sun exclusion angle must be between 0 and 180 degrees."
            )


def _validate_matching_samples(visibility_samples, sun_samples):
    """Ensure Earth and Sun samples refer to identical timestamps."""

    if len(visibility_samples) != len(sun_samples):
        raise ValueError(
            "Earth visibility and Sun samples must have equal lengths."
        )

    for index, (earth, sun) in enumerate(
        zip(visibility_samples, sun_samples)
    ):
        if earth.get("utc") is None or sun.get("utc") is None:
            raise ValueError(
                f"Sample {index} is missing its UTC timestamp."
            )

        if earth["utc"] != sun["utc"]:
            raise ValueError(
                f"Earth and Sun timestamps do not match at index {index}."
            )


def evaluate_direct_link(
    visibility_samples,
    sun_samples,
    horizon,
    antenna,
    constraints=None,
):
    """
    Evaluate direct-to-Earth communication availability.

    Five checks:
        1. Terrain coverage.
        2. Visible fraction of Earth's apparent disc.
        3. Earth-centre clearance above terrain.
        4. Antenna pointing capability.
        5. Sun exclusion angle.

    Returns one decision record per timestamp.

    Phase 8 timestamps use the key "utc".
    """

    if not isinstance(horizon, HorizonModel):
        raise TypeError("horizon must be a HorizonModel.")

    if not isinstance(antenna, AntennaConfig):
        raise TypeError("antenna must be an AntennaConfig.")

    if constraints is None:
        constraints = LinkConstraints()

    if not isinstance(constraints, LinkConstraints):
        raise TypeError("constraints must be LinkConstraints.")

    if len(visibility_samples) == 0:
        if len(sun_samples) != 0:
            raise ValueError(
                "Earth and Sun samples must have equal lengths."
            )
        return []

    _validate_matching_samples(
        visibility_samples,
        sun_samples,
    )

    required_earth_fields = (
        "azimuth_deg",
        "elevation_deg",
        "visible_fraction",
        "margin_deg",
        "coverage_complete",
    )

    required_sun_fields = (
        "azimuth_deg",
        "elevation_deg",
        "angular_radius_deg",
    )

    results = []

    for index, (earth, sun) in enumerate(
        zip(visibility_samples, sun_samples)
    ):
        missing_earth = [
            field for field in required_earth_fields
            if field not in earth
        ]

        missing_sun = [
            field for field in required_sun_fields
            if field not in sun
        ]

        if missing_earth or missing_sun:
            raise ValueError(
                f"Sample {index} has missing fields: "
                f"Earth={missing_earth}, Sun={missing_sun}"
            )

        earth_az = float(earth["azimuth_deg"])
        earth_el = float(earth["elevation_deg"])
        visible_fraction = float(earth["visible_fraction"])
        clearance = float(earth["margin_deg"])

        sun_az = float(sun["azimuth_deg"])
        sun_el = float(sun["elevation_deg"])
        sun_radius = float(sun["angular_radius_deg"])

        numeric_values = (
            earth_az,
            earth_el,
            visible_fraction,
            clearance,
            sun_az,
            sun_el,
            sun_radius,
        )

        if not all(math.isfinite(value) for value in numeric_values):
            raise ValueError(
                f"Sample {index} contains non-finite geometry."
            )

        if not 0.0 <= visible_fraction <= 1.0:
            raise ValueError(
                f"Sample {index} has invalid visible fraction."
            )

        if not 0.0 <= sun_radius <= 180.0:
            raise ValueError(
                f"Sample {index} has invalid Sun angular radius."
            )

        # Check 1: terrain coverage.
        terrain_complete = bool(earth["coverage_complete"])

        coverage_ok = (
            terrain_complete
            if constraints.require_complete_terrain
            else True
        )

        # Check 2: enough of Earth's apparent disc is visible.
        terrain_ok = (
            visible_fraction >= constraints.min_visible_fraction
        )

        # Check 3: Earth centre has sufficient terrain clearance.
        clearance_ok = (
            clearance >= constraints.min_clearance_deg
        )

        # Check 4: antenna can point toward Earth's centre.
        antenna_ok = pointing_ok(
            earth_az,
            earth_el,
            antenna,
        )

        # Determine whether the Sun's apparent upper limb
        # is above the terrain horizon.
        sun_horizon = float(
            horizon.horizon_at(sun_az)
        )

        sun_terrain_complete = bool(
            horizon.complete_at(sun_az)
        )

        sun_upper_limb = sun_el + sun_radius

        sun_in_view = (
            sun_upper_limb > sun_horizon
            if sun_terrain_complete
            else None
        )

        # Check 5: Sun exclusion.
        sun_separation = angular_separation_deg(
            earth_az,
            earth_el,
            sun_az,
            sun_el,
        )

        if constraints.sun_exclusion_deg == 0.0:
            sun_ok = True

        else:
            apply_sun_exclusion = (
                not constraints.sun_exclusion_only_if_sun_in_view
                or sun_in_view is not False
            )

            sun_ok = not (
                apply_sun_exclusion
                and sun_separation < constraints.sun_exclusion_deg
            )

        checks = {
            "terrain_coverage": bool(coverage_ok),
            "earth_visible_fraction": bool(terrain_ok),
            "earth_clearance": bool(clearance_ok),
            "antenna_pointing": bool(antenna_ok),
            "sun_exclusion": bool(sun_ok),
        }

        failed_checks = [
            name for name, passed in checks.items()
            if not passed
        ]

        results.append({
            "utc": earth["utc"],
            "link_available": len(failed_checks) == 0,
            "checks": checks,
            "failed_checks": failed_checks,
            "first_failure": (
                failed_checks[0]
                if failed_checks
                else None
            ),
            "earth": {
                "azimuth_deg": earth_az,
                "elevation_deg": earth_el,
                "visible_fraction": visible_fraction,
                "clearance_deg": clearance,
                "terrain_coverage_complete": terrain_complete,
            },
            "sun": {
                "azimuth_deg": sun_az,
                "elevation_deg": sun_el,
                "angular_radius_deg": sun_radius,
                "separation_from_earth_deg": sun_separation,
                "upper_limb_elevation_deg": sun_upper_limb,
                "terrain_coverage_complete": sun_terrain_complete,
                "in_view": sun_in_view,
            },
        })

    return results
