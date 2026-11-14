
from dataclasses import asdict

from backend.physics.sun_geometry import sun_at_times
from backend.visibility.site_visibility import earth_visibility_for_site

from .antenna import AntennaConfig
from .direct_to_earth import (
    LinkConstraints,
    evaluate_direct_link,
)


def summarize_link_availability(link_samples):
    """
    Summarize direct-to-Earth communication availability.

    Reports:
        - Total evaluated time samples.
        - Available and unavailable samples.
        - Availability percentage.
        - Failure counts for each constraint.
    """

    total_samples = len(link_samples)

    available_samples = sum(
        1 for sample in link_samples
        if sample["link_available"]
    )

    unavailable_samples = total_samples - available_samples

    availability_percent = (
        100.0 * available_samples / total_samples
        if total_samples > 0
        else 0.0
    )

    failure_counts = {
        "terrain_coverage": 0,
        "earth_visible_fraction": 0,
        "earth_clearance": 0,
        "antenna_pointing": 0,
        "sun_exclusion": 0,
    }

    for sample in link_samples:
        for failure in sample["failed_checks"]:
            failure_counts[failure] += 1

    return {
        "total_samples": total_samples,
        "available_samples": available_samples,
        "unavailable_samples": unavailable_samples,
        "availability_percent": float(availability_percent),
        "failure_counts": failure_counts,
    }


def direct_to_earth_for_site(
    lat_deg,
    lon_deg,
    height_m,
    start_utc,
    duration_days,
    step_minutes=5.0,
    antenna_height_m=2.0,
    max_range_m=40000.0,
    azimuth_step_deg=0.5,
    n_disc_points=400,
    antenna=None,
    constraints=None,
):
    """
    Evaluate terrain-aware direct-to-Earth communication
    availability for a lunar surface site.

    Integrates:
        Phase 6: SPICE Earth geometry.
        Phase 7: NASA LOLA terrain horizon.
        Phase 8: Earth apparent-disc visibility.
        Phase 9: Sun geometry, antenna pointing, and link checks.

    The Phase 8 HorizonModel is reused internally. It is not
    included in the returned JSON-compatible dictionary.

    height_m follows the existing Phase 8 convention.
    The antenna height is added to it for both Earth and Sun
    observer geometry.
    """

    if antenna is None:
        antenna = AntennaConfig()

    if not isinstance(antenna, AntennaConfig):
        raise TypeError("antenna must be an AntennaConfig.")

    if constraints is None:
        constraints = LinkConstraints()

    if not isinstance(constraints, LinkConstraints):
        raise TypeError("constraints must be LinkConstraints.")

    # 1. Calculate Phase 8 visibility and retain its internal
    #    terrain horizon model for the Phase 9 checks.
    visibility, horizon = earth_visibility_for_site(
        lat_deg=lat_deg,
        lon_deg=lon_deg,
        height_m=height_m,
        start_utc=start_utc,
        duration_days=duration_days,
        step_minutes=step_minutes,
        antenna_height_m=antenna_height_m,
        max_range_m=max_range_m,
        azimuth_step_deg=azimuth_step_deg,
        n_disc_points=n_disc_points,
        return_horizon_model=True,
    )

    visibility_samples = visibility["samples"]

    # 2. Use exactly the same timestamps as the Earth track.
    timestamps = [
        sample["utc"]
        for sample in visibility_samples
    ]

    # 3. Calculate Sun geometry from the same lunar observer.
    observer_height_m = height_m + antenna_height_m

    sun_samples = sun_at_times(
        lat_deg=lat_deg,
        lon_deg=lon_deg,
        height_m=observer_height_m,
        time_strings=timestamps,
    )

    # 4. Evaluate all five direct-to-Earth link constraints.
    link_samples = evaluate_direct_link(
        visibility_samples=visibility_samples,
        sun_samples=sun_samples,
        horizon=horizon,
        antenna=antenna,
        constraints=constraints,
    )

    # 5. Summarize communication availability and failures.
    link_summary = summarize_link_availability(
        link_samples
    )

    # 6. Return only JSON-compatible data.
    return {
        "source": "SPICE + NASA LOLA DEM + Phase 9 Link Model",
        "site": visibility["site"],
        "settings": visibility["settings"],
        "terrain": visibility["terrain"],
        "earth_track_summary": visibility["earth_track_summary"],
        "visibility_summary": visibility["visibility_summary"],
        "link_constraints": asdict(constraints),
        "antenna": asdict(antenna),
        "link_summary": link_summary,
        "sample_count": len(link_samples),
        "samples": link_samples,
    }
