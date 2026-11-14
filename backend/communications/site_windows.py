
from __future__ import annotations

from typing import Any

from backend.physics.earth_samples import earth_samples_at
from backend.physics.sun_geometry import sun_at_times
from backend.physics.time_system import parse_utc, to_et, et_to_utc
from backend.visibility.site_visibility import earth_visibility_for_site
from backend.visibility.earth_visibility import visibility_from_samples

from .antenna import AntennaConfig
from .direct_to_earth import LinkConstraints, evaluate_direct_link
from .windows import (
    WindowSettings,
    build_windows,
    parse_time,
    summarize_windows,
    to_iso,
)


def windows_for_site(
    lat_deg: float,
    lon_deg: float,
    height_m: float,
    start_utc: str,
    duration_days: float,
    step_minutes: float = 5.0,
    antenna_height_m: float = 2.0,
    max_range_m: float = 40000.0,
    azimuth_step_deg: float = 0.5,
    n_disc_points: int = 400,
    antenna: AntennaConfig | None = None,
    constraints: LinkConstraints | None = None,
    window_settings: WindowSettings | None = None,
) -> dict[str, Any]:
    """
    Calculate terrain-aware direct-to-Earth communication windows.

    Integrates:
        Phase 6: SPICE Earth geometry.
        Phase 7: NASA LOLA terrain horizon.
        Phase 8: Earth-disc terrain visibility.
        Phase 9: Antenna and Sun-exclusion link constraints.
        Phase 10: Refined communication windows.

    The terrain horizon is generated once and reused for all
    sampled and refined timestamp evaluations.

    Returns:
        A JSON-compatible dictionary containing:
            site
            settings
            terrain
            sample_count
            samples
            windows
            rejected
            summary

    Note:
        The returned windows describe geometric link availability.
        They do not constitute a complete RF link budget.
    """

    if antenna is None:
        antenna = AntennaConfig()

    if not isinstance(antenna, AntennaConfig):
        raise TypeError("antenna must be an AntennaConfig.")

    if constraints is None:
        constraints = LinkConstraints()

    if not isinstance(constraints, LinkConstraints):
        raise TypeError("constraints must be LinkConstraints.")

    if window_settings is None:
        window_settings = WindowSettings()

    if not isinstance(window_settings, WindowSettings):
        raise TypeError("window_settings must be WindowSettings.")

    # ---------------------------------------------------------
    # 1. Generate Phase 8 terrain-aware Earth visibility.
    #    Retain the HorizonModel for repeated boundary checks.
    # ---------------------------------------------------------

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

    if not visibility_samples:
        raise ValueError("Earth visibility returned no samples.")

    # ---------------------------------------------------------
    # 2. Generate Sun geometry at exactly the Earth sample times.
    # ---------------------------------------------------------

    timestamps = [
        sample["utc"]
        for sample in visibility_samples
    ]

    observer_height_m = float(height_m) + float(antenna_height_m)

    sun_samples = sun_at_times(
        lat_deg=lat_deg,
        lon_deg=lon_deg,
        height_m=observer_height_m,
        time_strings=timestamps,
    )

    # ---------------------------------------------------------
    # 3. Evaluate Phase 9 communication constraints.
    # ---------------------------------------------------------

    link_samples = evaluate_direct_link(
        visibility_samples=visibility_samples,
        sun_samples=sun_samples,
        horizon=horizon,
        antenna=antenna,
        constraints=constraints,
    )

    if len(link_samples) != len(visibility_samples):
        raise ValueError(
            "Phase 9 returned a different number of link samples "
            "than Earth visibility samples."
        )

    # ---------------------------------------------------------
    # 4. Prepare Phase 10 sample arrays.
    # ---------------------------------------------------------

    times_s = [
        parse_time(sample["utc"])
        for sample in link_samples
    ]

    flags = [
        bool(sample["link_available"])
        for sample in link_samples
    ]

    extras = {
        "visible_fraction": [
            float(sample["earth"]["visible_fraction"])
            for sample in link_samples
        ],
        "clearance_deg": [
            float(sample["earth"]["clearance_deg"])
            for sample in link_samples
        ],
        "sun_earth_separation_deg": [
            float(sample["sun"]["separation_from_earth_deg"])
            for sample in link_samples
        ],
    }

    # ---------------------------------------------------------
    # 5. Define the continuous state evaluator.
    #
    #    Phase 10 calls this function repeatedly during
    #    bisection to refine entry and exit boundaries.
    # ---------------------------------------------------------

    def state_fn(epoch_seconds: float) -> dict[str, Any]:
        # Convert Unix seconds to a normalized SPICE UTC timestamp.
        requested_utc = to_iso(epoch_seconds)

        moment = parse_utc(requested_utc)
        et = to_et(moment)

        normalized_utc = et_to_utc(et)

        # Calculate Earth geometry at this exact timestamp.
        earth_samples = earth_samples_at(
            lat_deg=lat_deg,
            lon_deg=lon_deg,
            height_m=observer_height_m,
            time_strings=[normalized_utc],
        )

        # Calculate terrain-aware Earth-disc visibility
        # using the same horizon generated above.
        refined_visibility = visibility_from_samples(
            samples=earth_samples,
            horizon=horizon,
            n_points=n_disc_points,
        )

        # Calculate Sun geometry at the identical timestamp.
        refined_sun = sun_at_times(
            lat_deg=lat_deg,
            lon_deg=lon_deg,
            height_m=observer_height_m,
            time_strings=[normalized_utc],
        )

        # Re-evaluate all five Phase 9 link constraints.
        refined_link = evaluate_direct_link(
            visibility_samples=refined_visibility,
            sun_samples=refined_sun,
            horizon=horizon,
            antenna=antenna,
            constraints=constraints,
        )

        if not refined_link:
            raise RuntimeError(
                "Phase 9 returned no result for a refined timestamp."
            )

        result = refined_link[0]

        return {
            "up": bool(result["link_available"]),
            "reasons": list(result["failed_checks"]),
            "checks": result["checks"],
            "utc": result["utc"],
        }

    # ---------------------------------------------------------
    # 6. Build refined windows from sampled availability.
    # ---------------------------------------------------------

    built = build_windows(
        times_s=times_s,
        flags=flags,
        state_fn=state_fn,
        settings=window_settings,
        extras=extras,
    )

    # ---------------------------------------------------------
    # 7. Summarize accepted windows.
    # ---------------------------------------------------------

    period_duration_s = (
        float(duration_days) * 86400.0
    )

    summary = summarize_windows(
        windows=built["windows"],
        rejected=built["rejected"],
        period_duration_s=period_duration_s,
    )

    # ---------------------------------------------------------
    # 8. Return a JSON-compatible result.
    # ---------------------------------------------------------

    return {
        "source": (
            "SPICE + NASA LOLA DEM + Phase 9 Direct-to-Earth "
            "Link Model + Phase 10 Refined Windows"
        ),

        "site": visibility["site"],

        "settings": {
            **visibility["settings"],
            "window_resolution_s": window_settings.resolution_s,
            "max_gap_s": window_settings.max_gap_s,
            "min_duration_s": window_settings.min_duration_s,
            "antenna": {
                "kind": antenna.kind,
                "min_elevation_deg": antenna.min_elevation_deg,
                "max_elevation_deg": antenna.max_elevation_deg,
            },
            "link_constraints": {
                "min_visible_fraction": constraints.min_visible_fraction,
                "min_clearance_deg": constraints.min_clearance_deg,
                "require_complete_terrain": (
                    constraints.require_complete_terrain
                ),
                "sun_exclusion_deg": constraints.sun_exclusion_deg,
                "sun_exclusion_only_if_sun_in_view": (
                    constraints.sun_exclusion_only_if_sun_in_view
                ),
            },
        },

        "terrain": visibility["terrain"],

        "earth_track_summary": visibility["earth_track_summary"],

        "visibility_summary": visibility["visibility_summary"],

        "link_summary": {
            "total_samples": len(link_samples),
            "available_samples": sum(flags),
            "unavailable_samples": len(flags) - sum(flags),
            "availability_percent": (
                100.0 * sum(flags) / len(flags)
            ),
        },

        "sample_count": len(link_samples),

        "samples": link_samples,

        "windows": built["windows"],

        "rejected": built["rejected"],

        "summary": summary,
    }
