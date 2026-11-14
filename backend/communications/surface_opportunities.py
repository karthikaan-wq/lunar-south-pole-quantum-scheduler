from collections.abc import Mapping, Sequence
import math
from collections.abc import Mapping, Sequence
from typing import Any

from .surface_links import (
    forwarding_options,
    intersect_windows,
)
from .windows import (
    parse_time,
    to_iso,
    windows_from_flags,
)


def power_eligible_windows(energy_result: Mapping[str, Any]):
    """
    Convert an energy timeline into conservative power-eligible intervals.

    Scheduling assumptions:
      - Battery SOC must be above zero.
      - Battery SOC must not be below the configured minimum.
      - Unmet load during the preceding sample interval must be zero.

    An interval ending with unmet load is conservatively excluded.
    This does not model automatic hardware shutdown or load shedding.
    """
    samples = energy_result.get("samples")

    if not isinstance(samples, Sequence) or isinstance(samples, (str, bytes)):
        raise ValueError("Energy result must contain a samples sequence.")

    if len(samples) < 2:
        raise ValueError("At least two energy samples are required.")

    times_s = []
    flags = []

    for index, sample in enumerate(samples):
        if not isinstance(sample, Mapping):
            raise ValueError(f"Energy sample {index} must be a mapping.")

        try:
            timestamp = parse_time(sample["utc"])
            soc = float(sample["battery_soc"])
            below_minimum = bool(sample["below_minimum_soc"])
            unmet_load_wh = float(
                sample.get("unmet_load_wh_since_previous_sample", 0.0)
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(
                f"Energy sample {index} has invalid power fields."
            ) from error

        if not 0.0 <= soc <= 1.0:
            raise ValueError(
                f"Energy sample {index} has battery SOC outside 0..1."
            )

        if not math.isfinite(unmet_load_wh) or unmet_load_wh < 0.0:
            raise ValueError(
                f"Energy sample {index} has invalid unmet-load energy."
            )

        times_s.append(timestamp)
        flags.append(
            not below_minimum
            and soc > 0.0
            and unmet_load_wh == 0.0
        )

    return windows_from_flags(times_s, flags)


def compose_surface_opportunities(
    link_metrics: Mapping[str, Any],
    rover_energy: Mapping[str, Any],
    lander_energy: Mapping[str, Any],
    earth_windows: Sequence[Mapping[str, Any]],
    max_wait_s: float = 12.0 * 3600.0,
    min_forward_s: float = 300.0,
):
    """
    Compose static surface-link, power and lander Earth-link availability.

    A surface uplink is possible only when:
      1. The static terrain-aware surface link is usable.
      2. Both rover and lander are power-eligible.

    Forwarding is possible when a lander Earth window starts no more
    than max_wait_s after the uplink ends and provides at least
    min_forward_s of remaining availability.
    """
    if not isinstance(link_metrics, Mapping):
        raise ValueError("link_metrics must be a mapping.")

    rover_windows = power_eligible_windows(rover_energy)
    lander_power_windows = power_eligible_windows(lander_energy)

    common_power_windows = intersect_windows(
        [(item["start_s"], item["end_s"]) for item in rover_windows],
        [(item["start_s"], item["end_s"]) for item in lander_power_windows],
    )

    earth_intervals = []

    for index, window in enumerate(earth_windows):
        if not isinstance(window, Mapping):
            raise ValueError(f"Earth window {index} must be a mapping.")

        try:
            start_s = float(window["start_s"])
            end_s = float(window["end_s"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(
                f"Earth window {index} must contain start_s and end_s."
            ) from error

        if end_s > start_s:
            earth_intervals.append((start_s, end_s))

    surface_link_usable = bool(link_metrics.get("usable", False))

    uplink_intervals = (
        common_power_windows if surface_link_usable else []
    )

    forwarding = forwarding_options(
        uplink_intervals,
        earth_intervals,
        max_wait_s=max_wait_s,
        min_forward_s=min_forward_s,
    )

    formatted_uplinks = [
        {
            "start_s": start,
            "end_s": end,
            "start_utc": to_iso(start),
            "end_utc": to_iso(end),
            "duration_s": end - start,
        }
        for start, end in uplink_intervals
    ]

    formatted_forwarding = []

    for item in forwarding:
        options = []

        for option in item["options"]:
            options.append({
                **option,
                "earth_start_utc": to_iso(option["earth_start_s"]),
                "earth_end_utc": to_iso(option["earth_end_s"]),
            })

        formatted_forwarding.append({
            **item,
            "uplink_start_utc": to_iso(item["uplink_start_s"]),
            "uplink_end_utc": to_iso(item["uplink_end_s"]),
            "options": options,
        })

    return {
        "surface_link_usable": surface_link_usable,
        "rover_power_window_count": len(rover_windows),
        "lander_power_window_count": len(lander_power_windows),
        "common_power_window_count": len(common_power_windows),
        "uplink_window_count": len(formatted_uplinks),
        "uplink_windows": formatted_uplinks,
        "forwarding_options": formatted_forwarding,
        "settings": {
            "max_wait_s": float(max_wait_s),
            "min_forward_s": float(min_forward_s),
            "power_eligibility_rule": (
                "battery_soc > 0, below_minimum_soc is false, and preceding_interval_unmet_load_wh == 0"
            ),
            "power_rule_is_scheduling_assumption": True,
        },
    }
