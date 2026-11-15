
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from backend.communications.site_surface_links import (
    surface_links_for_assets,
)
from backend.communications.site_windows import windows_for_site
from backend.communications.surface_opportunities import (
    power_eligible_windows,
)
from backend.communications.windows import WindowSettings, parse_time
from backend.energy.site_energy import energy_timeline_for_site
from backend.scheduling.models import (
    SchedulingProblem,
    TimeWindow,
)


@dataclass
class EnvironmentPreparation:
    """Prepared scheduling problem and its environmental evidence."""

    problem: SchedulingProblem
    energy_results: dict[str, dict[str, Any]]
    earth_results: dict[str, dict[str, Any]]
    surface_results: dict[tuple[str, str], Any]
    warnings: list[str] = field(default_factory=list)


def _iso_utc(epoch_s: float) -> str:
    return (
        datetime.fromtimestamp(epoch_s, tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _read(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _clip_windows(
    windows: Sequence[Mapping[str, Any]],
    horizon_start_s: float,
    horizon_end_s: float,
) -> list[TimeWindow]:
    """Clip windows to the mission horizon and discard invalid intervals."""
    result = []

    for window in windows:
        start_s = max(
            horizon_start_s,
            float(window["start_s"]),
        )
        end_s = min(
            horizon_end_s,
            float(window["end_s"]),
        )

        if end_s > start_s:
            result.append(
                TimeWindow(start_s=start_s, end_s=end_s)
            )

    return result


def _merge_windows(
    windows: Sequence[TimeWindow],
) -> list[TimeWindow]:
    """Merge overlapping or touching intervals."""
    ordered = sorted(
        windows,
        key=lambda item: (item.start_s, item.end_s),
    )

    merged: list[list[float]] = []

    for window in ordered:
        if not merged or window.start_s > merged[-1][1]:
            merged.append([window.start_s, window.end_s])
        else:
            merged[-1][1] = max(
                merged[-1][1],
                window.end_s,
            )

    return [
        TimeWindow(start_s=start, end_s=end)
        for start, end in merged
    ]


def _intersect_windows(
    first: Sequence[TimeWindow],
    second: Sequence[TimeWindow],
) -> list[TimeWindow]:
    """Intersect two collections of half-open time intervals."""
    left = _merge_windows(first)
    right = _merge_windows(second)

    result = []
    i = 0
    j = 0

    while i < len(left) and j < len(right):
        start_s = max(
            left[i].start_s,
            right[j].start_s,
        )
        end_s = min(
            left[i].end_s,
            right[j].end_s,
        )

        if end_s > start_s:
            result.append(
                TimeWindow(
                    start_s=start_s,
                    end_s=end_s,
                )
            )

        if left[i].end_s < right[j].end_s:
            i += 1
        else:
            j += 1

    return _merge_windows(result)


def _split_bridged_windows(
    windows: Sequence[Mapping[str, Any]],
) -> list[dict[str, float]]:
    """
    Split merged communication windows around every bridged gap.

    The scheduler must not treat a bridged interval as continuously
    available communication time.
    """
    result = []

    for window in windows:
        start_s = float(window["start_s"])
        end_s = float(window["end_s"])

        gaps = sorted(
            window.get("bridged_gaps", []),
            key=lambda item: float(item["start_s"]),
        )

        cursor = start_s

        for gap in gaps:
            gap_start = float(gap["start_s"])
            gap_end = float(gap["end_s"])

            if gap_start > cursor:
                result.append({
                    "start_s": cursor,
                    "end_s": min(gap_start, end_s),
                })

            cursor = max(cursor, gap_end)

        if end_s > cursor:
            result.append({
                "start_s": cursor,
                "end_s": end_s,
            })

    return [
        item
        for item in result
        if item["end_s"] > item["start_s"]
    ]


def _energy_windows(
    energy_result: Mapping[str, Any],
    horizon_start_s: float,
    horizon_end_s: float,
) -> list[TimeWindow]:
    """Convert baseline battery-safe samples into scheduling intervals."""
    raw = power_eligible_windows(energy_result)

    windows = [
        {
            "start_s": item["start_s"],
            "end_s": item["end_s"],
        }
        for item in raw
    ]

    return _clip_windows(
        windows,
        horizon_start_s,
        horizon_end_s,
    )


def _earth_windows(
    earth_result: Mapping[str, Any],
    horizon_start_s: float,
    horizon_end_s: float,
) -> list[TimeWindow]:
    """Convert refined DTE windows into continuous usable intervals."""
    raw = _split_bridged_windows(
        earth_result.get("windows", [])
    )

    return _clip_windows(
        raw,
        horizon_start_s,
        horizon_end_s,
    )


def _surface_link_is_usable(result: Any) -> bool:
    """Require a usable, sufficiently complete terrain-link result."""
    usable = bool(_read(result, "usable", False))
    complete = bool(_read(result, "data_complete", True))

    return usable and complete


def _find_surface_result(
    results: Mapping[tuple[str, str], Any],
    first: str,
    second: str,
) -> Any | None:
    """Find a terrain-link result regardless of endpoint ordering."""
    return results.get((first, second), results.get((second, first)))


def prepare_environment(
    problem: SchedulingProblem,
    *,
    energy_step_minutes: float = 30.0,
    communication_step_minutes: float = 5.0,
    energy_max_range_m: float = 100000.0,
    earth_max_range_m: float = 40000.0,
    earth_azimuth_step_deg: float = 0.5,
    surface_margin_m: float = 3000.0,
) -> EnvironmentPreparation:
    """
    Prepare a scheduling problem using the project's existing physics.

    Uses:
      - SPICE and NASA LOLA solar/terrain energy simulation.
      - Battery SOC, minimum-SOC and unmet-load checks.
      - SPICE/LOLA direct-to-Earth visibility.
      - Terrain-aware static rover/lander surface-link feasibility.

    Important limitation:
      Battery-safe windows are calculated using baseline asset loads.
      Transmission radio loads are not yet part of candidate selection.
      This preparation therefore does not certify the energy feasibility
      of the final combined transmission schedule.
    """
    if not problem.assets:
        raise ValueError(
            "Environmental preparation requires configured physical assets."
        )

    if energy_step_minutes <= 0:
        raise ValueError("energy_step_minutes must be positive.")

    if communication_step_minutes <= 0:
        raise ValueError("communication_step_minutes must be positive.")

    horizon_start = problem.horizon_start_s
    horizon_end = problem.horizon_end_s
    duration_days = (horizon_end - horizon_start) / 86400.0
    start_utc = _iso_utc(horizon_start)

    assets = {
        asset.name: asset
        for asset in problem.assets
    }

    warnings: list[str] = []
    energy_results: dict[str, dict[str, Any]] = {}
    earth_results: dict[str, dict[str, Any]] = {}
    asset_power_windows: dict[str, list[TimeWindow]] = {}
    asset_earth_windows: dict[str, list[TimeWindow]] = {}
    sunlight_windows: list[TimeWindow] = []

    # ---------------------------------------------------------
    # 1. Energy and battery simulation for each asset.
    # ---------------------------------------------------------
    for asset in problem.assets:
        energy = energy_timeline_for_site(
            lat_deg=asset.latitude_deg,
            lon_deg=asset.longitude_deg,
            start_utc=start_utc,
            duration_days=duration_days,
            step_minutes=energy_step_minutes,
            panel_config=asset.panel_config,
            battery_config=asset.battery_config,
            base_load_w=asset.base_load_w,
            max_range_m=energy_max_range_m,
            include_samples=True,
        )

        if not energy.get("samples"):
            raise RuntimeError(
                f"Energy simulation returned no samples for {asset.name}."
            )

        energy_results[asset.name] = energy

        asset_power_windows[asset.name] = _energy_windows(
            energy,
            horizon_start,
            horizon_end,
        )

        sunlight_windows.extend(
            _clip_windows(
                energy.get("sunlight_windows", []),
                horizon_start,
                horizon_end,
            )
        )

        for warning in energy.get("warnings", []):
            warnings.append(f"{asset.name}: {warning}")

        if not asset_power_windows[asset.name]:
            warnings.append(
                f"{asset.name}: no baseline battery-safe intervals "
                "were found."
            )

    # ---------------------------------------------------------
    # 2. Direct-to-Earth geometry for each asset.
    # ---------------------------------------------------------
    for asset in problem.assets:
        earth = windows_for_site(
            lat_deg=asset.latitude_deg,
            lon_deg=asset.longitude_deg,
            height_m=asset.height_m,
            start_utc=start_utc,
            duration_days=duration_days,
            step_minutes=communication_step_minutes,
            antenna_height_m=asset.antenna_height_m,
            max_range_m=earth_max_range_m,
            azimuth_step_deg=earth_azimuth_step_deg,
            window_settings=WindowSettings(
                resolution_s=60.0,
                max_gap_s=0.0,
                min_duration_s=1800.0,
            ),
        )

        earth_results[asset.name] = earth

        geometric_windows = _earth_windows(
            earth,
            horizon_start,
            horizon_end,
        )

        asset_earth_windows[asset.name] = _intersect_windows(
            geometric_windows,
            asset_power_windows[asset.name],
        )

        terrain = earth.get("terrain", {})
        if terrain and not terrain.get("all_directions_complete", True):
            warnings.append(
                f"{asset.name}: direct-to-Earth terrain coverage "
                "is incomplete."
            )

        if not asset_earth_windows[asset.name]:
            warnings.append(
                f"{asset.name}: no overlapping direct-to-Earth and "
                "baseline battery-safe windows were found."
            )

    # ---------------------------------------------------------
    # 3. Static terrain-aware surface-link feasibility.
    # ---------------------------------------------------------
    surface_link_profiles = [
        link
        for link in problem.links
        if link.link_type == "surface"
    ]

    surface_results: dict[tuple[str, str], Any] = {}

    if surface_link_profiles:
        if len(problem.assets) < 2:
            raise ValueError(
                "Surface links require at least two configured assets."
            )

        surface_assets = [
            {
                "name": asset.name,
                "type": asset.type,
                "latitude_deg": asset.latitude_deg,
                "longitude_deg": asset.longitude_deg,
                "antenna_height_m": asset.antenna_height_m,
            }
            for asset in problem.assets
        ]

        surface_results = surface_links_for_assets(
            surface_assets,
            margin_m=surface_margin_m,
        )

    # ---------------------------------------------------------
    # 4. Replace link windows with prepared feasible intervals.
    # ---------------------------------------------------------
    prepared_links = []

    for link in problem.links:
        if link.source_asset not in assets:
            raise ValueError(
                f"Link {link.link_id} has unknown source asset "
                f"{link.source_asset!r}."
            )

        source_windows = asset_power_windows[link.source_asset]

        if link.link_type == "earth":
            if link.destination_asset != "Earth":
                raise ValueError(
                    f"Earth link {link.link_id} must have destination "
                    "'Earth'."
                )

            windows = _intersect_windows(
                source_windows,
                asset_earth_windows[link.source_asset],
            )

        else:
            if link.destination_asset not in assets:
                raise ValueError(
                    f"Surface link {link.link_id} has unknown destination "
                    f"{link.destination_asset!r}."
                )

            geometry = _find_surface_result(
                surface_results,
                link.source_asset,
                link.destination_asset,
            )

            if geometry is None:
                raise RuntimeError(
                    f"No terrain-link result was returned for "
                    f"{link.source_asset} and {link.destination_asset}."
                )

            if not _surface_link_is_usable(geometry):
                warnings.append(
                    f"{link.link_id}: terrain-aware surface link "
                    "is not usable or its data is incomplete."
                )
                windows = []
            else:
                windows = _intersect_windows(
                    source_windows,
                    asset_power_windows[link.destination_asset],
                )

        prepared_link = link.model_copy(
            update={"windows": windows}
        )
        prepared_links.append(prepared_link)

        if not windows:
            warnings.append(
                f"{link.link_id}: no feasible environmental windows."
            )

    # ---------------------------------------------------------
    # 5. Preserve environmental sunlight information.
    # ---------------------------------------------------------
    combined_sunlight = _merge_windows(sunlight_windows)

    prepared_data = problem.model_dump()
    prepared_data["links"] = [
        link.model_dump()
        for link in prepared_links
    ]
    prepared_data["sunlight_windows"] = [
        window.model_dump()
        for window in combined_sunlight
    ]

    prepared_problem = SchedulingProblem.model_validate(
        prepared_data
    )

    # Remove duplicate warning messages while preserving order.
    warnings = list(dict.fromkeys(warnings))

    return EnvironmentPreparation(
        problem=prepared_problem,
        energy_results=energy_results,
        earth_results=earth_results,
        surface_results=surface_results,
        warnings=warnings,
    )
